package com.example.earlywarningsystem.util

import com.example.earlywarningsystem.data.model.TrendWarning
import java.text.SimpleDateFormat
import java.util.Locale
import java.util.TimeZone

private val isoUtcFormat = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US).apply {
    timeZone = TimeZone.getTimeZone("UTC")
}

private val isoUtcFormatOptionalMillis = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.US).apply {
    timeZone = TimeZone.getTimeZone("UTC")
}

/**
 * Parses an ISO UTC timestamp (e.g. "2026-02-08T15:00:00Z") to epoch millis.
 */
fun parseIsoUtcToEpochMillis(isoUtc: String?): Long? {
    if (isoUtc.isNullOrBlank()) return null
    val trimmed = isoUtc.trim()
    return try {
        isoUtcFormat.parse(trimmed)?.time ?: isoUtcFormatOptionalMillis.parse(trimmed)?.time
    } catch (_: Exception) {
        null
    }
}

/**
 * Epoch millis when the parameter is predicted to cross the threshold.
 * Uses threshold_crossing_utc from payload if present; else derives from
 * analysis_timestamp_utc + time_to_threshold_hours.
 */
fun getThresholdCrossingEpochMillis(warning: TrendWarning, analysisTimestampUtc: String?): Long? {
    warning.thresholdCrossingUtc?.takeIf { it.isNotBlank() }?.let { ts ->
        parseIsoUtcToEpochMillis(ts)?.let { return it }
    }
    val analysisEpoch = parseIsoUtcToEpochMillis(analysisTimestampUtc ?: "") ?: return null
    val hours = warning.timeToThresholdHours ?: return null
    return analysisEpoch + (hours * 3600 * 1000).toLong()
}

/**
 * True if the predicted crossing time is in the future (warning still active).
 */
fun isWarningActive(crossingEpochMillis: Long?, nowMillis: Long = System.currentTimeMillis()): Boolean {
    return crossingEpochMillis != null && nowMillis < crossingEpochMillis
}

/**
 * Human-readable time left until crossing, e.g. "in 4.2 hours" or "in 45 min".
 * Call only when crossingEpochMillis > nowMillis.
 */
fun formatTimeLeft(crossingEpochMillis: Long, nowMillis: Long = System.currentTimeMillis()): String {
    val remainingMs = (crossingEpochMillis - nowMillis).coerceAtLeast(0L)
    val remainingMinutes = remainingMs / (60 * 1000)
    return when {
        remainingMinutes < 60 -> "in $remainingMinutes min"
        else -> {
            val hours = remainingMs / (3600.0 * 1000)
            "in ${"%.1f".format(hours)} hours"
        }
    }
}

private val withinHoursPattern = Regex("within\\s+[\\d.]+\\s*hours?", RegexOption.IGNORE_CASE)

/**
 * Replaces static "within X hours" (or "within X.X hours") in summary text with dynamic [timeLeft].
 * e.g. "predicted to fall below 4 mg/L within 5.2 hours" -> "predicted to fall below 4 mg/L in 4.2 hours"
 */
fun replaceSummaryTime(summaryText: String, timeLeft: String): String {
    return summaryText.replace(withinHoursPattern, timeLeft)
}
