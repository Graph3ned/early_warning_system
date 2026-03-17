package com.example.earlywarningsystem.util

import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

private val inputFormats = listOf(
    SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US).apply { timeZone = TimeZone.getTimeZone("UTC") },
    SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US),
    SimpleDateFormat("yyyy-MM-dd'T'HH:mm", Locale.US),
    SimpleDateFormat("yyyy-MM-dd'T'HH-mm-ss", Locale.US),
    SimpleDateFormat("yyyy-MM-dd't'HH-mm-ss", Locale.US)
)

private val outputFormat = SimpleDateFormat("MMM d, yyyy 'at' h:mm a", Locale.US)
private val runLabelFormat = SimpleDateFormat("MMM d, h:mm a", Locale.US)
private val dateOnlyFormat = SimpleDateFormat("MMM d, yyyy", Locale.US)
/** Local time only (e.g. "7:00 PM") for chart axis so labels match actuals. Uses default timezone. */
private val localTimeOnlyFormat = SimpleDateFormat("h:mm a", Locale.US)

/**
 * Formats an ISO-style timestamp (e.g. 2026-02-04T10:00:00) to 12-hour format.
 * Example: "Feb 4, 2026 at 10:00 AM"
 */
fun formatTimestamp12Hour(isoTimestamp: String?): String {
    if (isoTimestamp.isNullOrBlank()) return "—"
    val trimmed = isoTimestamp.trim()
    for (fmt in inputFormats) {
        try {
            val date = fmt.parse(trimmed) ?: continue
            return outputFormat.format(date)
        } catch (_: Exception) { }
    }
    return trimmed
}

/**
 * Formats a forecast run ID for chip labels. Handles IDs like "run_2026-02-07T10-58-54";
 * returns a short readable form like "Feb 7, 10:58 AM". Otherwise returns "Run #n".
 */
fun formatForecastRunLabel(runId: String, runNumber: Int): String {
    if (runId.isBlank()) return "Run #$runNumber"
    val trimmed = runId.trim().removePrefix("run_").trim()
    if (trimmed.isEmpty()) return "Run #$runNumber"
    for (fmt in inputFormats) {
        try {
            val date = fmt.parse(trimmed) ?: continue
            return runLabelFormat.format(date)
        } catch (_: Exception) { }
    }
    return "Run #$runNumber"
}

/** Format epoch millis as date only, e.g. "Feb 7, 2026". */
fun formatDateOnly(epochMillis: Long): String = dateOnlyFormat.format(Date(epochMillis))

/** Format epoch millis as local time only (e.g. "7:00 PM"). Used so forecast chart labels match actuals. */
fun formatEpochToLocalTimeOnly(epochMillis: Long): String = localTimeOnlyFormat.format(Date(epochMillis))

/**
 * Converts an hour string (e.g. "14", "14:00", "14:30", "0", "12") to 12-hour format with optional minutes
 * (e.g. "2:00 PM", "2:30 PM", "12 AM", "12 PM"). Used for chart axis labels; keeps 30-min intervals distinct.
 */
fun formatHourTo12Hour(time: String?): String {
    if (time.isNullOrBlank()) return ""
    val trimmed = time.trim()
    val hour: Int
    val minute: Int
    if (trimmed.contains(":")) {
        val parts = trimmed.split(":")
        hour = parts[0].trim().toIntOrNull() ?: return trimmed
        minute = parts.getOrNull(1)?.trim()?.take(2)?.toIntOrNull() ?: 0
    } else {
        hour = trimmed.toIntOrNull() ?: return trimmed
        minute = 0
    }
    val h24 = hour % 24
    val (h12, ampm) = when {
        h24 == 0 -> 12 to "AM"
        h24 < 12 -> h24 to "AM"
        h24 == 12 -> 12 to "PM"
        else -> (h24 - 12) to "PM"
    }
    val mm = minute.toString().padStart(2, '0')
    return "$h12:$mm $ampm"
}
