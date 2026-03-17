package com.example.earlywarningsystem.data.repository

import com.example.earlywarningsystem.data.model.DeviceStatus
import com.example.earlywarningsystem.data.model.ForecastMetrics
import com.example.earlywarningsystem.data.model.ForecastPoint
import com.example.earlywarningsystem.data.model.ForecastStatus
import com.example.earlywarningsystem.data.model.ForecastTrendLatest
import com.example.earlywarningsystem.data.model.Recipient
import com.example.earlywarningsystem.data.model.SensorReading
import com.example.earlywarningsystem.data.model.TrendWarning
import com.example.earlywarningsystem.util.epochMillisToIsoString
import com.example.earlywarningsystem.util.isWithinLast24Hours
import com.example.earlywarningsystem.util.parseSensorTimestampToEpochMillis
import com.google.firebase.database.DataSnapshot
import com.google.firebase.database.DatabaseError
import com.google.firebase.database.FirebaseDatabase
import com.google.firebase.database.ValueEventListener
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.tasks.await

class EwsRepository {
    private val database = FirebaseDatabase.getInstance().reference

    /** Firebase may return numbers as Double, Long, or Int; normalize to Double? for trend hours. */
    private fun readDoubleFromSnapshot(snapshot: DataSnapshot): Double? {
        if (!snapshot.exists()) return null
        return when (val v = snapshot.value) {
            is Number -> v.toDouble()
            else -> snapshot.getValue(Double::class.java)
        }
    }

    /**
     * Reads one sensor_data entry. Missing numeric parameters are represented as Double.NaN
     * so the entry is still returned; the UI shows "—" and skips warnings for missing values.
     */
    private fun readSensorEntry(snapshot: DataSnapshot): SensorReading? {
        val key = snapshot.key ?: return null
        val temp = readDoubleFromSnapshot(snapshot.child("temperature")) ?: Double.NaN
        val ph = readDoubleFromSnapshot(snapshot.child("ph")) ?: Double.NaN
        val do2 = readDoubleFromSnapshot(snapshot.child("dissolved_oxygen")) ?: Double.NaN
        val doCompensated = readDoubleFromSnapshot(snapshot.child("do_salinity_compensated")) ?: do2
        val ec = readDoubleFromSnapshot(snapshot.child("ec")) ?: Double.NaN
        val salinity = readDoubleFromSnapshot(snapshot.child("salinity")) ?: Double.NaN
        val aeration = snapshot.child("aeration_status").getValue(String::class.java)
        return SensorReading(
            timestamp = key,
            temperature = temp,
            ph = ph,
            dissolvedOxygen = do2,
            doSalinityCompensated = doCompensated,
            ec = ec,
            salinity = salinity,
            aerationStatus = aeration
        )
    }

    /** Real-time flow of the latest sensor reading (last child under sensor_data). */
    fun latestSensorReadingFlow(): Flow<SensorReading?> = callbackFlow {
        val ref = database.child("sensor_data").orderByKey().limitToLast(1)
        val listener = object : ValueEventListener {
            override fun onDataChange(snapshot: DataSnapshot) {
                if (!snapshot.exists()) {
                    trySend(null)
                    return
                }
                var latest: SensorReading? = null
                for (child in snapshot.children) {
                    readSensorEntry(child)?.let { latest = it }
                }
                trySend(latest)
            }
            override fun onCancelled(error: DatabaseError) {
                trySend(null)
            }
        }
        ref.addValueEventListener(listener)
        awaitClose { ref.removeEventListener(listener) }
    }

    /** Real-time flow of Pi/device status at device_status (single object). */
    fun deviceStatusFlow(): Flow<DeviceStatus?> = callbackFlow {
        val ref = database.child("device_status")
        val listener = object : ValueEventListener {
            override fun onDataChange(snapshot: DataSnapshot) {
                if (!snapshot.exists()) {
                    trySend(null)
                    return
                }
                val readingStatus = snapshot.child("reading_status").getValue(String::class.java) ?: ""
                if (readingStatus.isBlank()) {
                    trySend(null)
                    return
                }
                val lastUpdatedUtc = snapshot.child("last_updated_utc").getValue(String::class.java)
                val lastUpdatedLocal = snapshot.child("last_updated_local").getValue(String::class.java)
                val espConnected = snapshot.child("esp_connected").getValue(Boolean::class.java)
                val invalidParamsList = snapshot.child("invalid_params").children.mapNotNull { it.getValue(String::class.java) }
                val invalidParams = invalidParamsList.takeIf { it.isNotEmpty() }
                val message = snapshot.child("message").getValue(String::class.java)
                val piTemp = when (val v = snapshot.child("pi_temperature_celsius").value) {
                    is Number -> v.toDouble()
                    else -> null
                }
                trySend(
                    DeviceStatus(
                        readingStatus = readingStatus,
                        lastUpdatedUtc = lastUpdatedUtc,
                        lastUpdatedLocal = lastUpdatedLocal,
                        espConnected = espConnected,
                        invalidParams = invalidParams,
                        message = message,
                        piTemperatureCelsius = piTemp
                    )
                )
            }
            override fun onCancelled(error: DatabaseError) {
                trySend(null)
            }
        }
        ref.addValueEventListener(listener)
        awaitClose { ref.removeEventListener(listener) }
    }

    /** One-shot: sensor readings from the last 24 hours (up to 500 entries). Latest first. */
    fun sensorReadingsLast24hFlow(): Flow<List<SensorReading>> = flow {
        try {
            val now = System.currentTimeMillis()
            val start = now - 24 * 60 * 60 * 1000L
            emit(sensorReadingsInRange(start, now))
        } catch (_: Exception) {
            // Permission denied or network error – return empty list instead of crashing.
            emit(emptyList())
        }
    }

    /** One-shot: sensor readings in [startEpochMillis, endEpochMillis]. Latest first. Queries by key range when keys are epoch-like. */
    fun sensorReadingsInRangeFlow(startEpochMillis: Long, endEpochMillis: Long): Flow<List<SensorReading>> = flow {
        try {
            emit(sensorReadingsInRange(startEpochMillis, endEpochMillis))
        } catch (_: Exception) {
            emit(emptyList())
        }
    }

    private suspend fun sensorReadingsInRange(startEpochMillis: Long, endEpochMillis: Long): List<SensorReading> {
        // Use local-time ISO keys so a selected day (e.g. Feb 21) queries "2026-02-21T00:00:00" to "2026-02-22T00:00:00"
        // and returns all 424 entries for that day (Firebase often stores keys in local time)
        val startKey = epochMillisToIsoString(startEpochMillis)
        val endKeyExclusive = epochMillisToIsoString(endEpochMillis + 1000L)
        val ref = database.child("sensor_data").orderByKey().startAt(startKey).endAt(endKeyExclusive)
        val snapshot = ref.get().await()
        if (!snapshot.exists()) return emptyList()
        return snapshot.children.mapNotNull { child -> readSensorEntry(child) }
            .filter { reading ->
                val epoch = parseSensorTimestampToEpochMillis(reading.timestamp) ?: return@filter false
                epoch in startEpochMillis..endEpochMillis
            }
            .sortedByDescending { parseSensorTimestampToEpochMillis(it.timestamp) ?: 0L }
    }

    /** One-shot: list of forecast run IDs (children of forecast/), newest first. */
    fun forecastRunIdsFlow(): Flow<List<String>> = flow {
        try {
            val ref = database.child("forecast")
            val snapshot = ref.get().await()
            if (!snapshot.exists()) {
                emit(emptyList())
                return@flow
            }
            val ids = snapshot.children.mapNotNull { it.key }.toList()
            emit(ids.reversed())
        } catch (_: Exception) {
            emit(emptyList())
        }
    }

    /** Real-time flow of forecast_status. */
    fun forecastStatusFlow(): Flow<ForecastStatus?> = callbackFlow {
        val ref = database.child("forecast_status")
        val listener = object : ValueEventListener {
            override fun onDataChange(snapshot: DataSnapshot) {
                if (!snapshot.exists()) {
                    trySend(null)
                    return
                }
                val system = snapshot.child("system").getValue(String::class.java) ?: ""
                val reason = snapshot.child("reason").getValue(String::class.java) ?: ""
                val latestRunId = snapshot.child("latest_run_id").getValue(String::class.java)
                val lastForecastAt = snapshot.child("last_forecast_at").getValue(String::class.java)
                trySend(ForecastStatus(system = system, reason = reason, latestRunId = latestRunId, lastForecastAt = lastForecastAt))
            }
            override fun onCancelled(error: DatabaseError) {
                trySend(null)
            }
        }
        ref.addValueEventListener(listener)
        awaitClose { ref.removeEventListener(listener) }
    }

    /** Real-time flow of forecast trend (early warnings) at forecast_trend/latest. */
    fun forecastTrendLatestFlow(): Flow<ForecastTrendLatest?> = callbackFlow {
        val ref = database.child("forecast_trend").child("latest")
        val listener = object : ValueEventListener {
            override fun onDataChange(snapshot: DataSnapshot) {
                if (!snapshot.exists()) {
                    trySend(null)
                    return
                }
                val runId = snapshot.child("run_id").getValue(String::class.java) ?: ""
                val analysisTimestampUtc = snapshot.child("analysis_timestamp_utc").getValue(String::class.java)
                val summaryMessages = mutableListOf<String>()
                val summarySnap = snapshot.child("summary_messages")
                for (child in summarySnap.children) {
                    child.getValue(String::class.java)?.let { summaryMessages.add(it) }
                }
                val warnings = mutableListOf<TrendWarning>()
                val warningsSnap = snapshot.child("warnings")
                for (child in warningsSnap.children) {
                    val param = child.child("parameter").getValue(String::class.java) ?: ""
                    val msg = child.child("message").getValue(String::class.java) ?: ""
                    val sev = child.child("severity").getValue(String::class.java) ?: "warning"
                    val hours = readDoubleFromSnapshot(child.child("time_to_threshold_hours"))
                    val thresholdCrossingUtc = child.child("threshold_crossing_utc").getValue(String::class.java)
                    val confidence = child.child("confidence").getValue(String::class.java)
                    warnings.add(TrendWarning(parameter = param, message = msg, severity = sev, timeToThresholdHours = hours, thresholdCrossingUtc = thresholdCrossingUtc, confidence = confidence))
                }
                trySend(ForecastTrendLatest(runId = runId, analysisTimestampUtc = analysisTimestampUtc, summaryMessages = summaryMessages, warnings = warnings))
            }
            override fun onCancelled(error: DatabaseError) {
                trySend(null)
            }
        }
        ref.addValueEventListener(listener)
        awaitClose { ref.removeEventListener(listener) }
    }

    private val forecastParameters = listOf("temperature", "ph", "dissolved_oxygen", "ec")

    /** One-shot load of 24h forecast points for a parameter. Structure: forecast/<runId>/<parameter>/<date>/<time> -> predicted, lower, upper */
    fun forecastPointsFlow(runId: String, parameter: String): Flow<List<ForecastPoint>> = flow {
        if (runId.isBlank()) {
            emit(emptyList())
            return@flow
        }
        try {
            val ref = database.child("forecast").child(runId).child(parameter)
            val snapshot = ref.get().await()
            if (!snapshot.exists()) {
                emit(emptyList())
                return@flow
            }
            val points = mutableListOf<ForecastPoint>()
            for (dateChild in snapshot.children) {
                val date = dateChild.key ?: continue
                for (timeChild in dateChild.children) {
                    val time = timeChild.key ?: continue
                    val pred = timeChild.child("predicted").getValue(Double::class.java) ?: continue
                    val lower = timeChild.child("lower").getValue(Double::class.java) ?: pred
                    val upper = timeChild.child("upper").getValue(Double::class.java) ?: pred
                    points.add(ForecastPoint(parameter = parameter, date = date, time = time, predicted = pred, lower = lower, upper = upper))
                }
            }
            points.sortWith(compareBy({ it.date }, { it.time }))
            emit(points)
        } catch (_: Exception) {
            emit(emptyList())
        }
    }

    /** One-shot load of forecast metrics for latest run. forecast_metrics/<runId>/<parameter> -> MAE, RMSE, (optional) MAPE */
    fun forecastMetricsFlow(runId: String): Flow<List<ForecastMetrics>> = flow {
        if (runId.isBlank()) {
            emit(emptyList())
            return@flow
        }
        try {
            val ref = database.child("forecast_metrics").child(runId)
            val snapshot = ref.get().await()
            if (!snapshot.exists()) {
                emit(emptyList())
                return@flow
            }
            val list = mutableListOf<ForecastMetrics>()
            for (paramChild in snapshot.children) {
                val param = paramChild.key ?: continue
                if (param.equals("ec", ignoreCase = true)) continue
                val mae = paramChild.child("MAE").getValue(Double::class.java) ?: continue
                val rmse = paramChild.child("RMSE").getValue(Double::class.java) ?: continue
                val mape = paramChild.child("MAPE").getValue(Double::class.java)
                list.add(ForecastMetrics(runId = runId, parameter = param, mae = mae, rmse = rmse, mape = mape))
                // Salinity and TDS share the same metrics: add a TDS row with salinity's numbers
                if (param.equals("salinity", ignoreCase = true)) {
                    list.add(ForecastMetrics(runId = runId, parameter = "tds", mae = mae, rmse = rmse, mape = mape))
                }
            }
            emit(list)
        } catch (_: Exception) {
            emit(emptyList())
        }
    }

    /** Real-time list of recipients. Path: recipients/<id> -> name, phone, active */
    fun recipientsFlow(): Flow<List<Recipient>> = callbackFlow {
        val ref = database.child("recipients")
        val listener = object : ValueEventListener {
            override fun onDataChange(snapshot: DataSnapshot) {
                val list = snapshot.children.mapNotNull { child ->
                    val id = child.key ?: return@mapNotNull null
                    val name = child.child("name").getValue(String::class.java) ?: ""
                    val phone = child.child("phone").getValue(String::class.java) ?: ""
                    val active = child.child("active").getValue(Boolean::class.java) ?: true
                    Recipient(id = id, name = name, phone = phone, active = active)
                }
                trySend(list)
            }
            override fun onCancelled(error: DatabaseError) {
                trySend(emptyList())
            }
        }
        ref.addValueEventListener(listener)
        awaitClose { ref.removeEventListener(listener) }
    }

    suspend fun addRecipient(name: String, phone: String, active: Boolean = true): Result<Unit> = runCatching {
        val key = database.child("recipients").push().key ?: throw IllegalStateException("Push failed")
        database.child("recipients").child(key).setValue(
            mapOf("name" to name, "phone" to phone, "active" to active)
        ).await()
    }

    suspend fun updateRecipient(id: String, name: String, phone: String, active: Boolean): Result<Unit> = runCatching {
        database.child("recipients").child(id).setValue(
            mapOf("name" to name, "phone" to phone, "active" to active)
        ).await()
    }

    suspend fun deleteRecipient(id: String): Result<Unit> = runCatching {
        database.child("recipients").child(id).removeValue().await()
    }
}
