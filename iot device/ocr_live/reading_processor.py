"""
Process OCR results: validate readings, persist to database, sync to Firebase, control relay,
and send alerts (no-data, invalid data, and marine threshold alerts).
"""

import threading
import time
from datetime import datetime, timezone

from database_storage import store_reading
from firebase_sync import request_firebase_sync
from firebase_device_status import write_device_status
from gsm_alert import send_no_data_alert
from ocr_config import (
    PARAMETERS,
    NO_DATA_ALERT_PHONES,
    NO_DATA_ALERT_COOLDOWN_SECONDS,
    DO_RELAY_ON_MAX,
    DO_RELAY_OFF_MIN,
)
from ocr_engine import (
    extract_numeric_value,
    conductivity_to_tds,
    conductivity_to_salinity,
    salinity_factor_weiss,
    do_salt_compensated_mgl,
)
from marine_alerts import (
    get_level_do,
    get_level_temp,
    get_level_sal,
    get_level_ph,
    should_send_sms_do,
    should_send_sms_temp,
    should_send_sms_sal,
    should_send_sms_ph,
    get_cooldown_seconds,
    get_sms_message,
)
from gsm_alert import send_alert_to_all_recipients
from relay_control import activate_relay, deactivate_relay, relay_state
from prophet_local_storage import get_forecast_status_local, get_forecast_run_points


class ReadingProcessor:
    def __init__(self, no_storage=False):
        """
        no_storage: if True, do not write to SQLite, Firebase, or device_status (for dry-run / no-DB mode).
        Relay control and SMS alerts still run when no_storage=True.
        """
        self.no_storage = no_storage
        self.last_alert_time = {}  # (param, level) -> timestamp, e.g. ("DO", "warning")
        self.last_no_data_alert_time = 0

    def _get_next_predicted_do_danger_epoch(self) -> float | None:
        """
        Look up the latest Prophet forecast run in the local SQLite DB and return the
        epoch time (seconds since epoch) of the earliest predicted dissolved_oxygen
        value for TODAY that is below DO_RELAY_ON_MAX and still in the future.
        Returns None when no such prediction exists.
        """
        try:
            status = get_forecast_status_local()
            if not status:
                return None
            run_id = status.get("latest_run_id")
            if not run_id:
                return None
            points = get_forecast_run_points(run_id)
            rows = points.get("dissolved_oxygen") or []
            if not rows:
                return None
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            best_epoch = None
            for date_str, time_str, pred, _lo, _hi in rows:
                if date_str != today_str:
                    continue
                try:
                    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                    epoch = dt.timestamp()
                except Exception:
                    continue
                if epoch <= now.timestamp():
                    continue
                try:
                    pred_val = float(pred)
                except (TypeError, ValueError):
                    continue
                if pred_val >= DO_RELAY_ON_MAX:
                    continue
                if best_epoch is None or epoch < best_epoch:
                    best_epoch = epoch
            return best_epoch
        except Exception:
            return None

    def process(self, results, last_results, last_ec_mScm, recipient_manager):
        """
        Process reading: no-data alert, invalid alert, or store + relay + Firebase + threshold alert.
        Mutates last_results (clears on all_results_invalid). Returns "no_data" | "invalid_data" | "ok".
        """
        all_results_invalid = all(
            (results.get(p) is None or results.get(p) == "--" or
            "?" in str(results.get(p, "")) or str(results.get(p, "")).strip() == "")
            for p in PARAMETERS
        )
        if all_results_invalid:
            print("[WARN] All OCR results are invalid (device display may be off/blank). Skipping data storage.")
            for p in PARAMETERS:
                last_results[p] = None
            try:
                t = time.time()
                if t - self.last_no_data_alert_time >= NO_DATA_ALERT_COOLDOWN_SECONDS and NO_DATA_ALERT_PHONES:
                    phones = list(NO_DATA_ALERT_PHONES)
                    print("Sending 'no data detected' alert (in background)...")
                    processor_self = self

                    def _send_no_data_and_record_cooldown_on_success():
                        result = send_no_data_alert(list(phones))
                        if result and result.get("success", 0) > 0:
                            processor_self.last_no_data_alert_time = time.time()
                            print("'No data' alert sent; cooldown started.")
                        else:
                            print("[WARN] 'No data' alert failed (e.g. ESP timeout); cooldown NOT started.")

                    threading.Thread(target=_send_no_data_and_record_cooldown_on_success, daemon=True).start()
                elif t - self.last_no_data_alert_time < NO_DATA_ALERT_COOLDOWN_SECONDS:
                    m = int((NO_DATA_ALERT_COOLDOWN_SECONDS - (t - self.last_no_data_alert_time)) / 60)
                    print(f"'No data' alert cooldown active ({m} minutes remaining)")
                else:
                    print("[WARN] No static phone numbers configured for 'no data' alerts.")
            except Exception as e:
                print(f"[WARN] Error sending 'no data' alert: {e}")
            if not self.no_storage:
                try:
                    write_device_status(
                        "no_data",
                        message="No data from OCR (display off or blank)",
                    )
                except Exception:
                    pass
            return "no_data"

        # Use current OCR results (results), not last_results, so question marks in this
        # reading are detected as invalid. last_results can still hold previous good values.
        temp_value = extract_numeric_value(results.get("TEMP"))
        ph_value = extract_numeric_value(results.get("pH"))
        do_value = extract_numeric_value(results.get("DO"))
        ec_value = last_ec_mScm
        all_params_valid = (
            temp_value is not None and ph_value is not None and do_value is not None and ec_value is not None
            and "?" not in str(results.get("TEMP", ""))
            and "?" not in str(results.get("pH", ""))
            and "?" not in str(results.get("DO", ""))
            and results.get("TEMP") != "--" and results.get("pH") != "--" and results.get("DO") != "--"
        )
        if not all_params_valid:
            # Keep logging and skipping storage, but do NOT send SMS for invalid data.
            print("[WARN] Invalid or incomplete readings detected (device may be off). Skipping data storage.")
            invalid_params = []
            if temp_value is None or "?" in str(results.get("TEMP", "")) or results.get("TEMP") == "--":
                invalid_params.append("TEMP")
            if ph_value is None or "?" in str(results.get("pH", "")) or results.get("pH") == "--":
                invalid_params.append("pH")
            if do_value is None or "?" in str(results.get("DO", "")) or results.get("DO") == "--":
                invalid_params.append("DO")
            if ec_value is None:
                invalid_params.append("EC")
            print(f"   Invalid parameters: {', '.join(invalid_params)}")
            # No device_status write and no invalid-data SMS here; only no-data SMS (above) and marine alerts (below) remain.
            return "invalid_data"

        if temp_value is None or ph_value is None or do_value is None or ec_value is None:
            missing = [x for x, v in [("TEMP", temp_value), ("pH", ph_value), ("DO", do_value), ("EC", ec_value)] if v is None]
            print(f"[WARN] Skipping database storage - missing required values: {', '.join(missing)}")
            return "ok"

        sal_value = conductivity_to_salinity(ec_value)
        # DO salinity compensation (Weiss): prefer compensated DO; fall back to raw DO when salinity is unavailable.
        if sal_value is not None and sal_value > 0:
            Fs = salinity_factor_weiss(temp_value, sal_value)
            do_compensated = do_salt_compensated_mgl(do_value, Fs)
        else:
            do_compensated = do_value

        # Relay control (DO only): use salinity-compensated DO (or raw DO when no salinity).
        # Hysteresis: ON when DO <= DO_RELAY_ON_MAX; OFF when DO >= DO_RELAY_OFF_MIN.
        # In band (between the two): do not change relay; report status from actual relay state.

        # Prediction-based control: use local Prophet forecast (from sensor_readings.db).
        # If there is a predicted DO danger time today (predicted < DO_RELAY_ON_MAX),
        # then:
        #   - Turn relay ON starting 30 minutes before that predicted time.
        #   - At/after the predicted time, if actual compensated DO is not below the
        #     DO_RELAY_ON_MAX threshold, turn the relay OFF (do not keep it ON just
        #     because of previous hysteresis).
        now_epoch = time.time()
        predicted_epoch = self._get_next_predicted_do_danger_epoch()
        in_prediction_window = False
        if predicted_epoch is not None:
            pre_window_start = predicted_epoch - 30 * 60
            if pre_window_start <= now_epoch < predicted_epoch:
                in_prediction_window = True
                if not relay_state:
                    activate_relay()
                aeration_status = "ACTIVATED"
            elif now_epoch >= predicted_epoch and do_compensated > DO_RELAY_ON_MAX:
                if relay_state:
                    deactivate_relay()
                aeration_status = "DEACTIVATED"

        if not in_prediction_window:
            if do_compensated <= DO_RELAY_ON_MAX:
                if not relay_state:
                    activate_relay()
                aeration_status = "ACTIVATED"
            elif do_compensated >= DO_RELAY_OFF_MIN:
                if relay_state:
                    deactivate_relay()
                aeration_status = "DEACTIVATED"
            else:
                # In hysteresis band: relay stays as-is. Only show ACTIVATED if relay is actually on (DO was ≤ threshold).
                aeration_status = "ACTIVATED" if relay_state else "DEACTIVATED"

        if not self.no_storage:
            if not store_reading(temp_value, ph_value, do_value, ec_value, aeration_status, do_salinity_compensated=do_compensated, salinity=sal_value):
                print("[WARN] Failed to store reading in database")
                return "ok"
            print(f"Stored reading in database: TEMP={temp_value}C, pH={ph_value}, DO={do_value}mg/L, EC={ec_value} mS/cm, Aeration={aeration_status}")
            try:
                accepted = request_firebase_sync()
                if accepted:
                    print("Firebase sync requested (background worker)")
            except Exception as e:
                print(f"[WARN] Firebase sync enqueue error: {e}")
            # Do not block the OCR loop on network calls.
            def _device_status_safe():
                try:
                    write_device_status("ok")
                except Exception as e:
                    print(f"[WARN] device_status update failed: {e}")

            threading.Thread(target=_device_status_safe, daemon=True).start()
        else:
            sal_str = f", Salinity={sal_value:.2f} ppt" if sal_value is not None else ""
            print(f"Reading (no DB/Firebase): TEMP={temp_value}C, pH={ph_value}, DO={do_value}mg/L, EC={ec_value} mS/cm{sal_str}, Aeration={aeration_status}")

        # Marine fish cage: per-parameter, per-level SMS with cooldowns. TDS: read/transmit only, no alerts.
        tds_value = conductivity_to_tds(ec_value)  # Transmit only; no SMS, no threshold

        try:
            now = time.time()
            # Use compensated DO (or raw DO when no salinity) for SMS alerts to reflect effective oxygen availability.
            params_to_check = [
                ("DO", do_compensated, should_send_sms_do),
                ("TEMP", temp_value, should_send_sms_temp),
                ("SAL", sal_value, should_send_sms_sal),
                ("pH", ph_value, should_send_sms_ph),
            ]
            # Reset cooldown when value returns to normal
            if get_level_do(do_value) == "normal":
                self.last_alert_time.pop(("DO", "warning"), None)
                self.last_alert_time.pop(("DO", "critical"), None)
            if get_level_temp(temp_value) == "normal":
                self.last_alert_time.pop(("TEMP", "warning"), None)
                self.last_alert_time.pop(("TEMP", "critical"), None)
            if get_level_sal(sal_value) == "normal":
                self.last_alert_time.pop(("SAL", "warning"), None)
                self.last_alert_time.pop(("SAL", "critical"), None)
            if get_level_ph(ph_value) == "normal":
                self.last_alert_time.pop(("pH", "warning"), None)
                self.last_alert_time.pop(("pH", "critical"), None)

            for param, value, should_send_fn in params_to_check:
                level_tuple = should_send_fn(value)
                if not level_tuple or level_tuple[0] is None:
                    continue
                level = level_tuple[0]
                key = (param, level)
                cooldown_sec = get_cooldown_seconds(param, level)
                last = self.last_alert_time.get(key, 0)
                if now - last < cooldown_sec:
                    m_remaining = int((cooldown_sec - (now - last)) / 60)
                    print(f"Marine alert cooldown active: {param} {level} ({m_remaining} minutes remaining)")
                    continue
                message = get_sms_message(param, value, level)
                if not message or recipient_manager is None:
                    continue
                ckey = f"marine:{param}:{level}"
                processor_self = self

                def _send_marine(param, lvl, msg, ck, sec, key_inner):
                    result = send_alert_to_all_recipients(msg, cooldown_key=ck, cooldown_seconds=sec)
                    if result and result.get("success", 0) > 0:
                        processor_self.last_alert_time[key_inner] = time.time()
                        print(f"Marine alert sent: {param} {lvl}; cooldown started.")
                    else:
                        print(f"[WARN] Marine alert failed for {param} {lvl}; cooldown NOT started.")

                threading.Thread(
                    target=_send_marine,
                    args=(param, level, message, ckey, cooldown_sec, key),
                    daemon=True,
                ).start()
        except Exception as e:
            print(f"[WARN] Error in marine threshold/alert: {e}")
        return "ok"
