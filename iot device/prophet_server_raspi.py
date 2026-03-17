"""Prophet forecasting for Raspberry Pi: local-first.
Reads sensor data from local SQLite, trains Prophet, writes forecasts to local DB, then syncs to Firebase when online.
Run from early_warning_system folder. Works without internet; Firebase key needed only for sync.
"""

import os
import sys
import firebase_admin
from firebase_admin import credentials, db
import pandas as pd
from prophet import Prophet
from sklearn.metrics import mean_absolute_error, mean_squared_error
import numpy as np
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
import pytz

# ============================================================================
# CONFIGURATION
# ============================================================================

_script_dir = os.path.dirname(os.path.abspath(__file__))
# Allow importing ocr_config from early_warning_system/ocr_live
_main_dir = os.path.dirname(_script_dir)
if _main_dir not in sys.path:
    sys.path.insert(0, _main_dir)

FIREBASE_KEY_PATH = os.environ.get("FIREBASE_KEY_PATH") or os.path.join(_script_dir, "firebase_key.json")
DATABASE_URL = os.environ.get("FIREBASE_DATABASE_URL", "https://early-waring-system-default-rtdb.asia-southeast1.firebasedatabase.app/")

SAMPLING_INTERVAL = "30min"
INTERVAL_MINUTES = 30
FORECAST_HORIZON_HOURS = 24
POINTS_PER_DAY = 24 * (60 // INTERVAL_MINUTES)
MIN_DAYS_REQUIRED = 7
MIN_DATA_POINTS = MIN_DAYS_REQUIRED * POINTS_PER_DAY

_max_stale = os.environ.get("MAX_STALE_HOURS", "").strip()
MAX_STALE_HOURS = int(_max_stale) if _max_stale else 2
VALIDATION_POINTS = POINTS_PER_DAY

MIN_DAYS_FOR_WEEKLY_SEASONALITY = 14
MIN_POINTS_FOR_WEEKLY_SEASONALITY = MIN_DAYS_FOR_WEEKLY_SEASONALITY * POINTS_PER_DAY
PROPHET_CONFIG_BASE = {
    "daily_seasonality": True,
    "yearly_seasonality": False,
    "changepoint_prior_scale": 0.1,
    "interval_width": 0.80,
    "uncertainty_samples": 1000
}


def get_prophet_config(n_points: int) -> dict:
    """Weekly seasonality enabled only when enough history."""
    config = dict(PROPHET_CONFIG_BASE)
    config["weekly_seasonality"] = n_points >= MIN_POINTS_FOR_WEEKLY_SEASONALITY
    return config

PARAMETERS = {
    "temperature": "temperature",
    "ph": "ph",
    "dissolved_oxygen": "do_salinity_compensated",
    "ec": "ec",
    "salinity": "salinity",
}

UTC = pytz.UTC
RUN_ID_TIMEZONE = os.environ.get("FORECAST_TIMEZONE", "Asia/Manila")
HISTORY_START_DATE = os.environ.get("HISTORY_START_DATE", "").strip() or None

# ============================================================================
# FIREBASE INITIALIZATION
# ============================================================================

def initialize_firebase(key_path: str = FIREBASE_KEY_PATH, database_url: str = DATABASE_URL) -> bool:
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(key_path)
            firebase_admin.initialize_app(cred, {"databaseURL": database_url})
            print("Firebase initialized successfully")
            return True
        print("Firebase already initialized")
        return True
    except FileNotFoundError:
        print(f"Error: Firebase key file not found at {key_path}")
        print("   Put firebase_key.json in the same folder as this script or set FIREBASE_KEY_PATH.")
        return False
    except Exception as e:
        print(f"Error initializing Firebase: {e}")
        return False

# ============================================================================
# DATA FETCHING (LOCAL FIRST)
# ============================================================================

def fetch_sensor_data_from_local() -> Optional[pd.DataFrame]:
    """Read sensor data from local SQLite (same DB as OCR pipeline). Returns same shape as Firebase version."""
    from database_storage import get_sensor_data_for_prophet

    rows = get_sensor_data_for_prophet(limit=None)
    if not rows:
        print("No sensor data found in local database")
        return None

    records = []
    for row in rows:
        timestamp_iso, temperature, ph, dissolved_oxygen, ec, salinity, do_salinity_compensated = row
        try:
            ts_clean = timestamp_iso.replace("Z", "").replace("+00:00", "")
            timestamp = pd.to_datetime(ts_clean, utc=True)
            records.append({
                "timestamp": timestamp,
                "temperature": temperature,
                "ph": ph,
                "do_salinity_compensated": do_salinity_compensated,
                "ec": ec,
                "salinity": salinity,
            })
        except (ValueError, TypeError) as e:
            print(f"Skipping invalid row {timestamp_iso}: {e}")
            continue

    if not records:
        return None

    df = pd.DataFrame(records)
    df.set_index("timestamp", inplace=True)
    df.sort_index(inplace=True)
    df.index = df.index.tz_localize(None)

    print(f"Fetched {len(df)} sensor records from local database")
    print(f"   Date range: {df.index.min()} to {df.index.max()}")
    return df


def check_data_quality(df: pd.DataFrame) -> Tuple[bool, str]:
    """(is_valid, reason). No interpolation: each required parameter must have >= MIN_DATA_POINTS valid points."""
    if df is None or len(df) == 0:
        return False, "No data available"

    required = {"temperature", "ph", "ec"}
    for p in required:
        if p not in df.columns:
            return False, f"Missing required parameters: {p}"

    # Require each required parameter to have enough non-null points (no interpolation)
    for p in required:
        valid_count = df[p].notna().sum()
        if valid_count < MIN_DATA_POINTS:
            progress = int((valid_count / MIN_DATA_POINTS) * 100)
            return False, f"Insufficient data for {p} ({valid_count}/{MIN_DATA_POINTS} points, {progress}%)"

    last_timestamp = df.index.max()
    now_naive = datetime.now()
    hours_since_last = (now_naive - last_timestamp).total_seconds() / 3600

    if hours_since_last > MAX_STALE_HOURS:
        return False, f"Data is stale (last update {hours_since_last:.1f} hours ago, max {MAX_STALE_HOURS}h)"

    return True, "Data quality checks passed"

# ============================================================================
# PROPHET FORECASTING
# ============================================================================

def prepare_prophet_data(df: pd.DataFrame, parameter: str) -> Optional[pd.DataFrame]:
    """(ds, y) for Prophet; drops nulls for parameter."""
    if parameter not in df.columns:
        return None

    prophet_df = df[[parameter]].copy()
    prophet_df = prophet_df.dropna()

    if len(prophet_df) < MIN_DATA_POINTS:
        return None

    prophet_df.reset_index(inplace=True)
    prophet_df = prophet_df.rename(columns={prophet_df.columns[0]: "ds", parameter: "y"})
    return prophet_df

def train_and_validate_model(prophet_df: pd.DataFrame) -> Tuple[Prophet, float, float, float]:
    if len(prophet_df) < MIN_DATA_POINTS:
        raise ValueError(f"Insufficient data for validation: need {MIN_DATA_POINTS} points, got {len(prophet_df)}")

    train_df = prophet_df[:-VALIDATION_POINTS].copy()
    test_df = prophet_df[-VALIDATION_POINTS:].copy()

    val_model = Prophet(**get_prophet_config(len(prophet_df)))
    val_model.fit(train_df)

    val_future = val_model.make_future_dataframe(
        periods=VALIDATION_POINTS,
        freq=SAMPLING_INTERVAL
    )
    val_forecast = val_model.predict(val_future)

    val_predictions = val_forecast.tail(VALIDATION_POINTS)["yhat"].values
    y_true = test_df["y"].values
    mae = mean_absolute_error(y_true, val_predictions)
    rmse = np.sqrt(mean_squared_error(y_true, val_predictions))

    # Mean Absolute Percentage Error (exclude zero ground-truth values)
    non_zero_mask = y_true != 0
    if np.any(non_zero_mask):
        mape = np.mean(np.abs((y_true[non_zero_mask] - val_predictions[non_zero_mask]) / y_true[non_zero_mask])) * 100.0
    else:
        mape = np.nan

    return val_model, mae, rmse, mape

def generate_forecast(model: Prophet, last_timestamp: pd.Timestamp,
                     forecast_hours: int = FORECAST_HORIZON_HOURS) -> pd.DataFrame:
    """Future timestamps only (after last_timestamp), at SAMPLING_INTERVAL."""
    num_steps = forecast_hours * (60 // INTERVAL_MINUTES)
    future_timestamps = []
    for i in range(1, num_steps + 1):
        future_ts = last_timestamp + pd.Timedelta(minutes=INTERVAL_MINUTES * i)
        future_timestamps.append(future_ts)

    future = pd.DataFrame({"ds": future_timestamps})
    forecast = model.predict(future)
    return forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]]

def forecast_parameter(df: pd.DataFrame, param_name: str, param_column: str) -> Optional[Tuple[pd.DataFrame, float, float, float]]:
    """Train, validate, forecast one parameter. Returns (forecast_df, MAE, RMSE, MAPE) or None."""
    try:
        prophet_df = prepare_prophet_data(df, param_column)
        if prophet_df is None:
            print(f"Insufficient data for {param_name} (column {param_column})")
            return None

        val_model, mae, rmse, mape = train_and_validate_model(prophet_df)

        full_model = Prophet(**get_prophet_config(len(prophet_df)))
        full_model.fit(prophet_df)

        last_timestamp = prophet_df["ds"].max()
        forecast = generate_forecast(full_model, last_timestamp, FORECAST_HORIZON_HOURS)

        if len(forecast) == 0:
            print(f"No future predictions generated for {param_name}")
            return None

        mape_str = f"{mape:.3f}" if not np.isnan(mape) else "nan"
        print(f"{param_name}: MAE={mae:.3f}, RMSE={rmse:.3f}, MAPE={mape_str}, Forecast points={len(forecast)} (column {param_column})")
        return forecast, mae, rmse, mape

    except Exception as e:
        print(f"Error forecasting {param_name}: {e}")
        return None

# ============================================================================
# FIREBASE UPLOAD
# ============================================================================

def generate_run_id() -> str:
    try:
        tz = pytz.timezone(RUN_ID_TIMEZONE)
        now = datetime.now(tz)
    except Exception:
        now = datetime.now(timezone.utc)
    return f"run_{now.strftime('%Y-%m-%dT%H-%M-%S')}"

def upload_forecast(run_id: str, parameter: str, forecast_df: pd.DataFrame):
    """forecast/<run_id>/<parameter>/<date>/<time> -> predicted, lower, upper."""
    try:
        ref = db.reference(f"forecast/{run_id}/{parameter}")

        for _, row in forecast_df.iterrows():
            timestamp = pd.to_datetime(row["ds"])
            date_str = timestamp.strftime("%Y-%m-%d")
            time_str = timestamp.strftime("%H:%M")
            ref.child(date_str).child(time_str).set({
                "predicted": float(row["yhat"]),
                "lower": float(row["yhat_lower"]),
                "upper": float(row["yhat_upper"])
            })

        print(f"Uploaded forecast for {parameter} ({len(forecast_df)} points)")

    except Exception as e:
        print(f"Error uploading forecast for {parameter}: {e}")
        raise

def upload_metrics(run_id: str, parameter: str, mae: float, rmse: float, mape: float):
    try:
        ref = db.reference(f"forecast_metrics/{run_id}/{parameter}")
        payload = {
            "MAE": float(mae),
            "RMSE": float(rmse),
        }
        if not np.isnan(mape):
            payload["MAPE"] = float(mape)
        ref.set(payload)
        mape_str = f"{mape:.3f}" if not np.isnan(mape) else "nan"
        print(f"Uploaded metrics for {parameter}: MAE={mae:.3f}, RMSE={rmse:.3f}, MAPE={mape_str}")

    except Exception as e:
        print(f"Error uploading metrics for {parameter}: {e}")
        raise

def update_forecast_status(system_status: str, reason: str, run_id: Optional[str] = None):
    """Push forecast status to Firebase (used when online)."""
    try:
        status = {
            "system": system_status,
            "reason": reason
        }

        if run_id:
            status["latest_run_id"] = run_id
            status["last_forecast_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        db.reference("forecast_status").set(status)
        print(f"Updated forecast status: {system_status} - {reason}")

    except Exception as e:
        print(f"Error updating forecast status: {e}")


def push_forecast_run_to_firebase(run_id: str) -> bool:
    """Read forecast run from local DB and push to Firebase. Returns True if fully synced."""
    import prophet_local_storage as pls

    if not initialize_firebase():
        return False

    try:
        points = pls.get_forecast_run_points(run_id)
        for param, rows in points.items():
            ref = db.reference(f"forecast/{run_id}/{param}")
            for date_str, time_str, pred, lower, upper in rows:
                ref.child(date_str).child(time_str).set({
                    "predicted": float(pred),
                    "lower": float(lower),
                    "upper": float(upper),
                })
        print(f"Uploaded forecast points for run {run_id}")

        metrics = pls.get_forecast_run_metrics(run_id)
        for param, metric_values in metrics.items():
            # Support both (mae, rmse) and (mae, rmse, mape)
            if len(metric_values) == 3:
                mae, rmse, mape = metric_values
            else:
                mae, rmse = metric_values
                mape = np.nan
            payload = {
                "MAE": float(mae),
                "RMSE": float(rmse),
            }
            if not np.isnan(mape):
                payload["MAPE"] = float(mape)
            db.reference(f"forecast_metrics/{run_id}/{param}").set(payload)
        print(f"Uploaded forecast metrics for run {run_id}")

        status = pls.get_forecast_status_local()
        if status:
            payload = {"system": status["system"], "reason": status["reason"]}
            if status.get("latest_run_id"):
                payload["latest_run_id"] = status["latest_run_id"]
                payload["last_forecast_at"] = status["last_forecast_at"]
            db.reference("forecast_status").set(payload)
            print("Updated forecast status on Firebase")

        trend = pls.get_forecast_trend_date_and_payload(run_id)
        if trend:
            date_key, payload = trend
            ref = db.reference("forecast_trend")
            ref.child(date_key).set(payload)
            ref.child("latest").set(payload)
            print(f"Uploaded forecast trend to forecast_trend/{date_key} and forecast_trend/latest")

        pls.mark_forecast_run_synced(run_id)
        print(f"Synced run {run_id} to Firebase")
        return True

    except Exception as e:
        print(f"Firebase sync failed (run {run_id}): {e}. Data remains in local DB for retry.")
        return False


# ============================================================================
# FORECAST TREND (thresholds from ocr_config)
# ============================================================================

def _get_trend_thresholds_from_ocr_config():
    from early_warning_system.ocr_live import ocr_config as oc
    return {
        "dissolved_oxygen": [
            {"type": "min", "value": oc.DO_NORMAL_MIN, "severity": "warning", "label": f"{oc.DO_NORMAL_MIN} mg/L"},
            {"type": "min", "value": oc.DO_CRITICAL_MAX, "severity": "critical", "label": f"{oc.DO_CRITICAL_MAX} mg/L"},
        ],
        "ph": [
            {"type": "min", "value": oc.PH_NORMAL_MIN, "severity": "warning", "label": str(oc.PH_NORMAL_MIN)},
            {"type": "min", "value": oc.PH_CRITICAL_LOW_MAX, "severity": "critical", "label": str(oc.PH_CRITICAL_LOW_MAX)},
            {"type": "max", "value": oc.PH_NORMAL_MAX, "severity": "warning", "label": str(oc.PH_NORMAL_MAX)},
            {"type": "max", "value": oc.PH_CRITICAL_HIGH_MIN, "severity": "critical", "label": str(oc.PH_CRITICAL_HIGH_MIN)},
        ],
        "temperature": [
            {"type": "min", "value": oc.TEMP_NORMAL_MIN, "severity": "warning", "label": f"{oc.TEMP_NORMAL_MIN} C"},
            {"type": "min", "value": oc.TEMP_CRITICAL_LOW_MAX, "severity": "critical", "label": f"{oc.TEMP_CRITICAL_LOW_MAX} C"},
            {"type": "max", "value": oc.TEMP_NORMAL_MAX, "severity": "warning", "label": f"{oc.TEMP_NORMAL_MAX} C"},
            {"type": "max", "value": oc.TEMP_CRITICAL_HIGH_MIN, "severity": "critical", "label": f"{oc.TEMP_CRITICAL_HIGH_MIN} C"},
        ],
    }


def _get_salinity_trend_thresholds_from_ocr_config():
    from early_warning_system.ocr_live import ocr_config as oc
    return [
        {"type": "min", "value": oc.SAL_NORMAL_MIN, "severity": "warning", "label": f"{oc.SAL_NORMAL_MIN} ppt"},
        {"type": "min", "value": oc.SAL_CRITICAL_LOW_MAX, "severity": "critical", "label": f"{oc.SAL_CRITICAL_LOW_MAX} ppt"},
        {"type": "max", "value": oc.SAL_NORMAL_MAX, "severity": "warning", "label": f"{oc.SAL_NORMAL_MAX} ppt"},
        {"type": "max", "value": oc.SAL_CRITICAL_HIGH_MIN, "severity": "critical", "label": f"{oc.SAL_CRITICAL_HIGH_MIN} ppt"},
    ]


_TREND_THRESHOLDS = _get_trend_thresholds_from_ocr_config()
_SALINITY_TREND_THRESHOLDS = _get_salinity_trend_thresholds_from_ocr_config()
_TREND_EPSILON = {"dissolved_oxygen": 0.05, "ph": 0.02, "temperature": 0.1, "salinity": 0.2, "ec": 0.05}
_TREND_DISPLAY_NAMES = {"dissolved_oxygen": "Dissolved oxygen", "ph": "pH", "temperature": "Temperature", "ec": "EC", "salinity": "Salinity"}


def _trend_parse_hours(ts_iso: str, start_iso: str) -> float:
    try:
        ts = pd.to_datetime(ts_iso)
        start = pd.to_datetime(start_iso)
        return (ts - start).total_seconds() / 3600.0
    except Exception:
        return 0.0


def _trend_slope_direction(points, param):
    if len(points) < 2:
        return 0.0, "stable"
    first, last = points[0], points[-1]
    hours = _trend_parse_hours(last["timestamp"], first["timestamp"])
    if hours <= 0:
        return 0.0, "stable"
    slope = (last["predicted"] - first["predicted"]) / hours
    eps = _TREND_EPSILON.get(param, 0.01)
    if slope > eps:
        return slope, "increasing"
    if slope < -eps:
        return slope, "decreasing"
    return slope, "stable"


def _trend_find_crossing(points, th_type, th_value):
    if not points:
        return None
    start_iso = points[0]["timestamp"]
    for i in range(1, len(points)):
        prev, curr = points[i - 1]["predicted"], points[i]["predicted"]
        t_prev = _trend_parse_hours(points[i - 1]["timestamp"], start_iso)
        t_curr = _trend_parse_hours(points[i]["timestamp"], start_iso)
        crossed = False
        if th_type == "min":
            crossed = (prev >= th_value > curr) or (prev > th_value >= curr)
        else:
            crossed = (prev <= th_value < curr) or (prev < th_value <= curr)
        if crossed:
            if curr == prev:
                t_cross, v_cross = t_curr, th_value
            else:
                frac = (th_value - prev) / (curr - prev)
                t_cross = t_prev + frac * (t_curr - t_prev)
                v_cross = th_value
            return (t_cross, i, v_cross)
    return None


def _trend_confidence(points, th_type, th_value, crossing_hours):
    if not points or crossing_hours <= 0:
        return "medium"
    start_iso = points[0]["timestamp"]
    for p in points:
        h = _trend_parse_hours(p["timestamp"], start_iso)
        if h >= crossing_hours:
            lower, upper = p.get("lower"), p.get("upper")
            if lower is None or upper is None:
                return "medium"
            if th_type == "min":
                return "high" if upper < th_value else "medium"
            return "high" if lower > th_value else "medium"
    return "medium"


def _trend_analyze_param(param, points):
    result = {
        "parameter": param,
        "display_name": _TREND_DISPLAY_NAMES.get(param, param),
        "direction": "stable",
        "slope_per_hour": 0.0,
        "crossings": [],
        "time_to_threshold_hours": None,
        "time_to_threshold_severity": None,
        "messages": [],
        "warnings": [],
    }
    if not points or len(points) < 2:
        return result

    if param == "salinity":
        points = [p for p in points if p.get("predicted") is not None]
        if len(points) < 2:
            return result
        thresholds_to_use = _SALINITY_TREND_THRESHOLDS
        slope_param = "salinity"
    else:
        thresholds_to_use = _TREND_THRESHOLDS.get(param, [])
        slope_param = param

    slope, direction = _trend_slope_direction(points, slope_param)
    result["direction"] = direction
    result["slope_per_hour"] = round(float(slope), 6)
    first_ts = points[0]["timestamp"]
    horizon_hours = _trend_parse_hours(points[-1]["timestamp"], first_ts)
    for th in thresholds_to_use:
        t_type, t_value = th["type"], th["value"]
        severity, label = th["severity"], th["label"]
        crossing = _trend_find_crossing(points, t_type, t_value)
        if crossing is None:
            continue
        hours_to_cross, idx, _ = crossing
        confidence = _trend_confidence(points, t_type, t_value, hours_to_cross)
        result["crossings"].append({
            "threshold_label": label,
            "threshold_value": t_value,
            "severity": severity,
            "hours_from_start": round(hours_to_cross, 2),
            "confidence": confidence,
        })
        if result["time_to_threshold_hours"] is None or hours_to_cross < result["time_to_threshold_hours"]:
            result["time_to_threshold_hours"] = round(hours_to_cross, 2)
            result["time_to_threshold_severity"] = severity
        name = result["display_name"]
        if param == "dissolved_oxygen":
            result["messages"].append(f"{name} is predicted to fall below {label} within {hours_to_cross:.1f} hours.")
            result["warnings"].append({"parameter": param, "message": f"DO is predicted to fall below {label} within {hours_to_cross:.1f} hours.", "severity": severity, "time_to_threshold_hours": round(hours_to_cross, 2), "confidence": confidence})
        elif param == "ph":
            side = "below" if t_type == "min" else "above"
            result["messages"].append(f"pH is predicted to go {side} {label} within {hours_to_cross:.1f} hours.")
            result["warnings"].append({"parameter": param, "message": f"pH is predicted to go {side} {label} within {hours_to_cross:.1f} hours.", "severity": severity, "time_to_threshold_hours": round(hours_to_cross, 2), "confidence": confidence})
        elif param == "temperature":
            if t_type == "min":
                result["messages"].append(f"Temperature is predicted to fall below {label} within {hours_to_cross:.1f} hours.")
                result["warnings"].append({"parameter": param, "message": f"Temperature is predicted to fall below {label} within {hours_to_cross:.1f} hours.", "severity": severity, "time_to_threshold_hours": round(hours_to_cross, 2), "confidence": confidence})
            else:
                result["messages"].append(f"Temperature is predicted to exceed {label} within {hours_to_cross:.1f} hours.")
                result["warnings"].append({"parameter": param, "message": f"Temperature is predicted to exceed {label} within {hours_to_cross:.1f} hours.", "severity": severity, "time_to_threshold_hours": round(hours_to_cross, 2), "confidence": confidence})
        elif param == "salinity":
            if t_type == "min":
                result["messages"].append(f"Salinity is predicted to fall below {label} within {hours_to_cross:.1f} hours.")
                result["warnings"].append({"parameter": param, "message": f"Salinity is predicted to fall below {label} within {hours_to_cross:.1f} hours.", "severity": severity, "time_to_threshold_hours": round(hours_to_cross, 2), "confidence": confidence})
            else:
                result["messages"].append(f"Salinity is predicted to exceed {label} within {hours_to_cross:.1f} hours.")
                result["warnings"].append({"parameter": param, "message": f"Salinity is predicted to exceed {label} within {hours_to_cross:.1f} hours.", "severity": severity, "time_to_threshold_hours": round(hours_to_cross, 2), "confidence": confidence})
    if not result["messages"] and direction != "stable":
        name = result["display_name"]
        if direction == "decreasing":
            result["messages"].append(f"{name} is predicted to decrease over the next {horizon_hours:.0f} hours.")
        else:
            result["messages"].append(f"{name} is predicted to increase over the next {horizon_hours:.0f} hours.")
    return result


def _dataframe_to_trend_points(forecast_df):
    """Forecast df -> list of {timestamp, predicted, lower, upper}."""
    points = []
    for _, row in forecast_df.iterrows():
        ts = pd.to_datetime(row["ds"])
        timestamp = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        points.append({
            "timestamp": timestamp,
            "predicted": float(row["yhat"]),
            "lower": float(row.get("yhat_lower", row["yhat"])),
            "upper": float(row.get("yhat_upper", row["yhat"])),
        })
    return points


def run_forecast_trend_and_upload(run_id: str, forecast_dfs: Dict[str, pd.DataFrame]):
    """Trend analysis; returns payload for local storage and Firebase push (no direct Firebase write here)."""
    if not forecast_dfs:
        return None
    parameters_result = {}
    all_warnings = []
    for param, frame in forecast_dfs.items():
        points = _dataframe_to_trend_points(frame)
        if not points:
            continue
        analysis = _trend_analyze_param(param, points)
        parameters_result[param] = analysis
        all_warnings.extend(analysis.get("warnings", []))
    analysis_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "run_id": run_id,
        "analysis_timestamp_utc": analysis_ts,
        "parameters": parameters_result,
        "warnings": all_warnings,
    }
    return payload


# ============================================================================
# MAIN FORECASTING CYCLE
# ============================================================================

def run_forecasting_cycle():
    import prophet_local_storage as pls

    print("\n" + "="*60)
    print("EARLY WARNING SYSTEM - PROPHET FORECASTING CYCLE (Raspberry Pi)")
    print("Local-first: sensor data from SQLite, forecasts stored locally then synced to Firebase.")
    print("="*60 + "\n")

    pls.init_forecast_tables()

    print("Fetching sensor data from local database...")
    df = fetch_sensor_data_from_local()

    if df is None:
        pls.store_forecast_status_local("NOT_READY", "No data available")
        try:
            if initialize_firebase():
                update_forecast_status("NOT_READY", "No data available")
        except Exception as e:
            print(f"Firebase status update skipped (offline?): {e}")
        return

    if SAMPLING_INTERVAL:
        df = df.resample(SAMPLING_INTERVAL).mean()
        print(f"Resampled to {SAMPLING_INTERVAL} interval: {len(df)} points (no interpolation)")

    if HISTORY_START_DATE:
        try:
            start_ts = pd.Timestamp(HISTORY_START_DATE)
            n_before = len(df)
            df = df[df.index >= start_ts]
            print(f"Using data from {HISTORY_START_DATE} onward: {len(df)} points (dropped {n_before - len(df)} older)")
            if len(df) == 0:
                pls.store_forecast_status_local("NOT_READY", f"No data on or after {HISTORY_START_DATE}")
                try:
                    if initialize_firebase():
                        update_forecast_status("NOT_READY", f"No data on or after {HISTORY_START_DATE}")
                except Exception as e:
                    print(f"Firebase status update skipped: {e}")
                return
        except Exception as e:
            print(f"Invalid HISTORY_START_DATE '{HISTORY_START_DATE}': {e}. Using all data.")

    print("Checking data quality...")
    is_valid, reason = check_data_quality(df)

    if not is_valid:
        pls.store_forecast_status_local("NOT_READY", reason)
        try:
            if initialize_firebase():
                update_forecast_status("NOT_READY", reason)
        except Exception as e:
            print(f"Firebase status update skipped: {e}")
        print(f"Data quality check failed: {reason}")
        return

    print(f"Data quality check passed: {reason}")

    run_id = generate_run_id()
    print(f"Forecast run ID: {run_id}\n")

    successful_forecasts = 0
    failed_forecasts = 0
    forecast_dfs = {}

    for param_name, param_column in PARAMETERS.items():
        print(f"Forecasting {param_name}...")
        result = forecast_parameter(df, param_name, param_column)

        if result is None:
            failed_forecasts += 1
            continue

        forecast_df, mae, rmse, mape = result

        try:
            forecast_rows = []
            for _, row in forecast_df.iterrows():
                ts = pd.to_datetime(row["ds"])
                forecast_rows.append((
                    ts.strftime("%Y-%m-%d"),
                    ts.strftime("%H:%M"),
                    float(row["yhat"]),
                    float(row["yhat_lower"]),
                    float(row["yhat_upper"]),
                ))
            pls.store_forecast_points(run_id, param_name, forecast_rows)
            pls.store_forecast_metrics(run_id, param_name, mae, rmse, mape)
            successful_forecasts += 1
            forecast_dfs[param_name] = forecast_df
        except Exception as e:
            print(f"Failed to store forecast for {param_name}: {e}")
            failed_forecasts += 1

    if successful_forecasts > 0:
        reason = f"Forecast completed: {successful_forecasts} successful, {failed_forecasts} failed"
        pls.store_forecast_run(run_id, "READY", reason)
        pls.store_forecast_status_local("READY", reason, run_id)
        print(f"\nForecasting cycle completed successfully!")
        print(f"   Successful: {successful_forecasts}, Failed: {failed_forecasts}")

        try:
            trend_payload = run_forecast_trend_and_upload(run_id, forecast_dfs)
            if trend_payload:
                date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                pls.store_forecast_trend_local(run_id, date_key, trend_payload)
                print(f"Stored forecast trend locally (forecast_trend/{date_key})")
                for w in trend_payload.get("warnings", []):
                    print("   ", w.get("message", w))
            else:
                print("Forecast trend: no data")
        except Exception as e:
            print("Forecast trend failed:", e)

        try:
            if push_forecast_run_to_firebase(run_id):
                print("Firebase sync completed.")
            else:
                print("Firebase sync skipped or failed; data is in local DB for later sync.")
        except Exception as e:
            print(f"Firebase sync error: {e}. Data is in local DB for later sync.")
    else:
        reason = f"All forecasts failed ({failed_forecasts} parameters)"
        pls.store_forecast_run(run_id, "NOT_READY", reason)
        pls.store_forecast_status_local("NOT_READY", reason, run_id)
        try:
            if initialize_firebase():
                update_forecast_status("NOT_READY", reason, run_id)
        except Exception as e:
            print(f"Firebase status update skipped: {e}")
        print(f"\nForecasting cycle failed for all parameters")

    print("\n" + "="*60 + "\n")

# ============================================================================
# EXECUTION
# ============================================================================

def sync_pending_forecasts_to_firebase():
    """Push any forecast runs that are stored locally but not yet synced to Firebase (e.g. after coming back online)."""
    import prophet_local_storage as pls

    pls.init_forecast_tables()
    unsynced = pls.get_unsynced_forecast_runs()
    if not unsynced:
        print("No unsynced forecast runs.")
        return
    print(f"Found {len(unsynced)} unsynced run(s). Pushing to Firebase...")
    for run_id in unsynced:
        if push_forecast_run_to_firebase(run_id):
            print(f"  Synced {run_id}")
        else:
            print(f"  Failed to sync {run_id}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "sync":
        sync_pending_forecasts_to_firebase()
    else:
        run_forecasting_cycle()
