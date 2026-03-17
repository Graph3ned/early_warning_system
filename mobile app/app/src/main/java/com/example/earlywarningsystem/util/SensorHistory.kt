package com.example.earlywarningsystem.util

import com.example.earlywarningsystem.data.model.ForecastPoint
import com.example.earlywarningsystem.data.model.SensorReading
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale
import java.util.TimeZone

private val isoFormats = listOf(
    SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US).apply { timeZone = TimeZone.getTimeZone("UTC") },
    SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US),
    SimpleDateFormat("yyyy-MM-dd'T'HH:mm", Locale.US),
    SimpleDateFormat("yyyy-MM-dd'T'HH-mm-ss", Locale.US),
    SimpleDateFormat("yyyy-MM-dd't'HH-mm-ss", Locale.US),
    SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US)
)

/**
 * Parses sensor_data timestamp (key) to epoch millis. Tries Long parse then ISO formats.
 */
fun parseSensorTimestampToEpochMillis(timestamp: String?): Long? {
    if (timestamp.isNullOrBlank()) return null
    timestamp.trim().toLongOrNull()?.let { return it }
    for (fmt in isoFormats) {
        try {
            fmt.parse(timestamp.trim())?.time?.let { return it }
        } catch (_: Exception) { }
    }
    return null
}

/** Hour bucket key matching ForecastPoint date/time: "yyyy-MM-dd|HH:00". Uses default (local) timezone so keys match forecast. */
fun sensorReadingToHourBucketKey(reading: SensorReading): String? {
    val millis = parseSensorTimestampToEpochMillis(reading.timestamp) ?: return null
    val cal = Calendar.getInstance().apply { timeInMillis = millis }
    val date = String.format(Locale.US, "%04d-%02d-%02d", cal.get(Calendar.YEAR), cal.get(Calendar.MONTH) + 1, cal.get(Calendar.DAY_OF_MONTH))
    val time = String.format(Locale.US, "%02d:00", cal.get(Calendar.HOUR_OF_DAY))
    return "$date|$time"
}

/** 30-minute bucket key: "yyyy-MM-dd|HH:00" or "yyyy-MM-dd|HH:30". Uses default (local) timezone. */
fun sensorReadingTo30MinBucketKey(reading: SensorReading): String? {
    val millis = parseSensorTimestampToEpochMillis(reading.timestamp) ?: return null
    return epochToLocal30MinSlotKey(millis)
}

/** Same format as sensorReadingTo30MinBucketKey: "yyyy-MM-dd|HH:00" or "HH:30" in local time. */
fun epochToLocal30MinSlotKey(epochMillis: Long): String {
    val cal = Calendar.getInstance().apply { timeInMillis = epochMillis }
    val date = String.format(Locale.US, "%04d-%02d-%02d", cal.get(Calendar.YEAR), cal.get(Calendar.MONTH) + 1, cal.get(Calendar.DAY_OF_MONTH))
    val hour = cal.get(Calendar.HOUR_OF_DAY)
    val minute = cal.get(Calendar.MINUTE)
    val time = if (minute < 30) String.format(Locale.US, "%02d:00", hour) else String.format(Locale.US, "%02d:30", hour)
    return "$date|$time"
}

/**
 * Aggregates sensor readings to 30-minute buckets. Returns map from key "date|HH:00" or "date|HH:30" to average value.
 */
fun aggregateSensorReadingsTo30Min(
    readings: List<SensorReading>,
    parameter: String
): Map<String, Double> {
    val valueSelector: (SensorReading) -> Double = when (parameter) {
        "temperature" -> { r -> r.temperature }
        "ph" -> { r -> r.ph }
        "dissolved_oxygen" -> { r -> r.doSalinityCompensated }
        "ec" -> { r -> r.ec }
        "salinity" -> { r -> if (!r.salinity.isNaN()) r.salinity else 0.0 }
        "tds" -> { r -> conductivityToTds(if (!r.ec.isNaN()) r.ec else null) ?: 0.0 }
        else -> return emptyMap()
    }
    val grouped = mutableMapOf<String, MutableList<Double>>()
    for (r in readings) {
        val key = sensorReadingTo30MinBucketKey(r) ?: continue
        val v = valueSelector(r)
        if (!v.isNaN()) grouped.getOrPut(key) { mutableListOf() }.add(v)
    }
    return grouped.mapValues { (_, values) -> values.average() }
}

/** Parses slot key "yyyy-MM-dd|HH:mm" to epoch millis (start of that slot in local time). */
private fun slotKeyToEpochMillis(slotKey: String): Long? {
    val parts = slotKey.split("|")
    if (parts.size != 2) return null
    val (datePart, timePart) = parts
    val timeWithSec = if (timePart.length <= 5) "$timePart:00" else timePart
    val dateTimeStr = "${datePart}T$timeWithSec"
    return try {
        forecastLocalFormat.parse(dateTimeStr)?.time
    } catch (_: Exception) { null }
}

/**
 * For each 30-minute slot, returns the value from the **single reading closest to the slot time**
 * (not the average). So the forecast actual at e.g. 2:30 PM will match one of the values you see
 * in Sensor History for that time, instead of an average of multiple readings.
 */
fun actualsFromClosestReadingPer30MinSlot(
    readings: List<SensorReading>,
    parameter: String
): Map<String, Double> {
    val valueSelector: (SensorReading) -> Double = when (parameter) {
        "temperature" -> { r -> r.temperature }
        "ph" -> { r -> r.ph }
        "dissolved_oxygen" -> { r -> r.doSalinityCompensated }
        "ec" -> { r -> r.ec }
        "salinity" -> { r -> if (!r.salinity.isNaN()) r.salinity else 0.0 }
        "tds" -> { r -> conductivityToTds(if (!r.ec.isNaN()) r.ec else null) ?: 0.0 }
        else -> return emptyMap()
    }
    val grouped = mutableMapOf<String, MutableList<Pair<Long, Double>>>()
    for (r in readings) {
        val key = sensorReadingTo30MinBucketKey(r) ?: continue
        val epoch = parseSensorTimestampToEpochMillis(r.timestamp) ?: continue
        val v = valueSelector(r)
        if (!v.isNaN()) grouped.getOrPut(key) { mutableListOf() }.add(epoch to v)
    }
    return grouped.mapValues { (key, list) ->
        val slotStart = slotKeyToEpochMillis(key) ?: return@mapValues list.first().second
        list.minByOrNull { kotlin.math.abs(it.first - slotStart) }!!.second
    }
}

/**
 * Aggregates sensor readings to hourly buckets and returns map from hour key "date|time"
 * to average value for the given parameter. Parameter: "temperature", "ph", "dissolved_oxygen", "ec", "salinity", "tds".
 */
fun aggregateSensorReadingsToHourly(
    readings: List<SensorReading>,
    parameter: String
): Map<String, Double> {
    val valueSelector: (SensorReading) -> Double = when (parameter) {
        "temperature" -> { r -> r.temperature }
        "ph" -> { r -> r.ph }
        "dissolved_oxygen" -> { r -> r.doSalinityCompensated }
        "ec" -> { r -> r.ec }
        "salinity" -> { r -> if (!r.salinity.isNaN()) r.salinity else 0.0 }
        "tds" -> { r -> conductivityToTds(if (!r.ec.isNaN()) r.ec else null) ?: 0.0 }
        else -> return emptyMap()
    }
    val grouped = mutableMapOf<String, MutableList<Double>>()
    for (r in readings) {
        val key = sensorReadingToHourBucketKey(r) ?: continue
        val v = valueSelector(r)
        if (!v.isNaN()) grouped.getOrPut(key) { mutableListOf() }.add(v)
    }
    return grouped.mapValues { (_, values) -> values.average() }
}

/** Forecast points from Firebase are in local time (same timezone as device/Pi); parse as local so 10:30 shows as 10:30. */
private val forecastLocalFormat = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US)

/**
 * Parses a forecast point's date (yyyy-MM-dd) and time (H:00 or HH:00) to epoch millis.
 * Interpreted as local time so the chart shows the same time as the forecast (e.g. 10:30 AM).
 */
fun forecastPointHourToEpochMillis(date: String, time: String): Long? {
    val timePart = when {
        time.contains(":") -> time
        else -> "${time.padStart(2, '0')}:00"
    }
    val dateTimeStr = "${date}T${timePart}:00"
    return try {
        forecastLocalFormat.parse(dateTimeStr)?.time
    } catch (_: Exception) { null }
}

/**
 * Returns (startEpochMillis, endEpochMillis) covering the full range of the forecast points.
 * Points must be sorted by date then time. End is exclusive (start of hour after last point).
 */
fun forecastPointsToTimeRange(points: List<ForecastPoint>): Pair<Long, Long>? {
    if (points.isEmpty()) return null
    val first = forecastPointHourToEpochMillis(points.first().date, points.first().time) ?: return null
    val last = forecastPointHourToEpochMillis(points.last().date, points.last().time) ?: return null
    val endExclusive = last + 60 * 60 * 1000L
    return Pair(first, endExclusive)
}

/** Interval for 30-minute slots (ms). */
private const val THIRTY_MIN_MS = 30 * 60 * 1000L

/**
 * Generates 30-minute slot keys "yyyy-MM-dd|HH:00" or "yyyy-MM-dd|HH:30" from startEpochMillis to endEpochMillis (exclusive).
 */
fun forecastRangeTo30MinSlots(startEpochMillis: Long, endEpochMillis: Long): List<String> {
    val slots = mutableListOf<String>()
    var t = startEpochMillis
    val cal = Calendar.getInstance()
    while (t < endEpochMillis) {
        cal.timeInMillis = t
        val date = String.format(Locale.US, "%04d-%02d-%02d", cal.get(Calendar.YEAR), cal.get(Calendar.MONTH) + 1, cal.get(Calendar.DAY_OF_MONTH))
        val hour = cal.get(Calendar.HOUR_OF_DAY)
        val minute = cal.get(Calendar.MINUTE)
        val time = if (minute < 30) String.format(Locale.US, "%02d:00", hour) else String.format(Locale.US, "%02d:30", hour)
        slots.add("$date|$time")
        t += THIRTY_MIN_MS
    }
    return slots
}

/**
 * For each forecast point (date, time), get the aggregated actual value.
 * Returns list same size as points; null where no actual data for that hour.
 */
fun matchActualsToForecastPoints(
    points: List<ForecastPoint>,
    aggregatedByHour: Map<String, Double>
): List<Float?> {
    return points.map { p ->
        val timePart = when {
            p.time.contains(":") -> p.time
            else -> "${p.time.padStart(2, '0')}:00"
        }
        val key = "${p.date}|$timePart"
        aggregatedByHour[key]?.toFloat()
    }
}

/**
 * For each 30-minute slot key "date|HH:mm", get the aggregated actual value from the 30-min map.
 * Returns list same size as slots; null where no actual data for that slot.
 */
fun matchActualsTo30MinSlots(slots: List<String>, aggregatedBy30Min: Map<String, Double>): List<Float?> {
    return slots.map { key -> aggregatedBy30Min[key]?.toFloat() }
}

/**
 * Match actuals to each expanded forecast point (11:00, 11:30, 12:00, 12:30, ...).
 * For each point, convert its UTC (date, time) to local 30-min slot key and look up in aggregated map.
 * Returns list same size as expandedPoints; null where no actual data for that slot.
 */
fun matchActualsToExpandedPoints(expandedPoints: List<ForecastPoint>, aggregatedBy30Min: Map<String, Double>): List<Float?> {
    return expandedPoints.map { point ->
        val epoch = forecastPointHourToEpochMillis(point.date, point.time) ?: return@map null
        val slotKey = epochToLocal30MinSlotKey(epoch)
        aggregatedBy30Min[slotKey]?.toFloat()
    }
}

/**
 * Expands hourly forecast points to 30-minute resolution: each hour becomes two slots (:00 and :30)
 * with the same predicted/lower/upper. If Firebase already returns 30-min points (e.g. 7:00, 7:30),
 * returns them as-is to avoid duplicating (7:00, 7:30, 7:00, 7:30).
 */
fun expandForecastPointsTo30Min(hourlyPoints: List<ForecastPoint>): List<ForecastPoint> {
    if (hourlyPoints.isEmpty()) return emptyList()
    val already30Min = hourlyPoints.any { p ->
        val t = p.time.trim()
        t.endsWith(":30") || t.contains(":30")
    }
    if (already30Min) return hourlyPoints
    val expanded = mutableListOf<ForecastPoint>()
    for (p in hourlyPoints) {
        val timePart = when {
            p.time.contains(":") -> p.time.substringBefore(":")
            else -> p.time
        }.padStart(2, '0')
        expanded.add(p.copy(time = "${timePart}:00"))
        expanded.add(p.copy(time = "${timePart}:30"))
    }
    return expanded
}

/** True if epoch millis is within the last 24 hours from now. */
fun isWithinLast24Hours(epochMillis: Long, nowMillis: Long = System.currentTimeMillis()): Boolean {
    return (nowMillis - epochMillis) <= 24 * 60 * 60 * 1000L
}

/** Start of calendar day (00:00:00.000) in default timezone for the given epoch. */
fun startOfDayLocal(epochMillis: Long): Long {
    val cal = Calendar.getInstance().apply { timeInMillis = epochMillis }
    cal.set(Calendar.HOUR_OF_DAY, 0)
    cal.set(Calendar.MINUTE, 0)
    cal.set(Calendar.SECOND, 0)
    cal.set(Calendar.MILLISECOND, 0)
    return cal.timeInMillis
}

/** End of calendar day (23:59:59.999) in default timezone for the given epoch. */
fun endOfDayLocal(epochMillis: Long): Long {
    val cal = Calendar.getInstance().apply { timeInMillis = epochMillis }
    cal.set(Calendar.HOUR_OF_DAY, 23)
    cal.set(Calendar.MINUTE, 59)
    cal.set(Calendar.SECOND, 59)
    cal.set(Calendar.MILLISECOND, 999)
    return cal.timeInMillis
}

/** Floor epoch millis to the start of an interval bucket (intervalMinutes: 1, 5, 30, 60). */
fun floorToIntervalMillis(epochMillis: Long, intervalMinutes: Int): Long {
    val ms = intervalMinutes * 60 * 1000L
    return (epochMillis / ms) * ms
}

private val isoOutputForBucket = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US)
private val isoOutputUtc = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US).apply { timeZone = TimeZone.getTimeZone("UTC") }

/** Format epoch millis as ISO string for display (formatTimestamp12Hour can parse it). */
fun epochMillisToIsoString(epochMillis: Long): String = isoOutputForBucket.format(Date(epochMillis))

/** Format epoch millis as ISO string in UTC, for Firebase key range queries so all readings in range are returned. */
fun epochMillisToIsoStringUtc(epochMillis: Long): String = isoOutputUtc.format(Date(epochMillis))

/**
 * Aggregate readings into time buckets (intervalMinutes: 1, 5, 30, 60). Returns one SensorReading per bucket
 * (timestamp = bucket start as ISO, values = averages; aeration = ACTIVATED if any in bucket). Latest first.
 */
fun aggregateSensorReadingsByInterval(
    readings: List<SensorReading>,
    intervalMinutes: Int
): List<SensorReading> {
    if (readings.isEmpty() || intervalMinutes < 1) return emptyList()
    val bucketLists = mutableMapOf<Long, MutableList<SensorReading>>()
    for (r in readings) {
        val epoch = parseSensorTimestampToEpochMillis(r.timestamp) ?: continue
        val bucketStart = floorToIntervalMillis(epoch, intervalMinutes)
        bucketLists.getOrPut(bucketStart) { mutableListOf() }.add(r)
    }
    fun List<Double>.averageOrNaN(): Double = filter { !it.isNaN() }.let { if (it.isEmpty()) Double.NaN else it.average() }
    return bucketLists.map { (bucketStart, list) ->
        val salinities = list.map { it.salinity }.filter { it > 0.0 && !it.isNaN() }
        SensorReading(
            timestamp = epochMillisToIsoString(bucketStart),
            temperature = list.map { it.temperature }.averageOrNaN(),
            ph = list.map { it.ph }.averageOrNaN(),
            dissolvedOxygen = list.map { it.dissolvedOxygen }.averageOrNaN(),
            doSalinityCompensated = list.map { it.doSalinityCompensated }.averageOrNaN(),
            ec = list.map { it.ec }.averageOrNaN(),
            salinity = if (salinities.isNotEmpty()) salinities.average() else 0.0,
            aerationStatus = if (list.any { it.aerationStatus.equals("ACTIVATED", ignoreCase = true) }) "ACTIVATED" else list.firstOrNull()?.aerationStatus
        )
    }.sortedByDescending { parseSensorTimestampToEpochMillis(it.timestamp) ?: 0L }
}
