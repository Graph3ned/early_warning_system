package com.example.earlywarningsystem.util

import com.example.earlywarningsystem.data.model.DeviceStatus
import java.text.SimpleDateFormat
import java.util.Locale
import java.util.TimeZone

private const val STALE_THRESHOLD_MINUTES = 30L

/**
 * Builds list of device alert messages from [DeviceStatus] for no_data, invalid_readings,
 * esp_connected === false, stale status, and Pi temperature (Critical/High).
 */
fun getDeviceAlerts(status: DeviceStatus?): List<String> {
    if (status == null) return emptyList()
    val alerts = mutableListOf<String>()
    if (status.isNoData) {
        alerts.add(status.message?.takeIf { it.isNotBlank() }
            ?: "No data from OCR — device display may be off or blank.")
    }
    if (status.isInvalidReadings) {
        val detail = buildString {
            status.invalidParams?.takeIf { it.isNotEmpty() }?.let { params ->
                append("Invalid: ${params.joinToString(", ")}.")
            }
            status.message?.takeIf { it.isNotBlank() }?.let { msg ->
                if (isNotEmpty()) append(" ")
                append(msg)
            }
        }
        alerts.add(if (detail.isNotEmpty()) detail else "Invalid or incomplete readings from OCR.")
    }
    if (status.espConnected == false) {
        alerts.add("ESP8266 not connected — relay/SMS may be unavailable.")
    }
    if (isDeviceStatusStale(status)) {
        alerts.add("Pi status is stale — no recent update from Pi.")
    }
    // Pi CPU temperature status: show Critical or High (80°C+) as alerts
    status.message?.takeIf { it.isNotBlank() }?.let { msg ->
        if (!status.isNoData && !status.isInvalidReadings && isPiTemperatureAlert(msg)) {
            alerts.add(msg)
        }
    }
    return alerts
}

/**
 * True if [message] is a Pi temperature alert (Critical 85°C+ or High 80–85°C).
 */
private fun isPiTemperatureAlert(message: String): Boolean {
    val m = message.lowercase()
    return m.contains("critical") && m.contains("85") ||
        m.contains("high") && m.contains("80") ||
        m.contains("throttling")
}

/**
 * True if [status] last update is older than [STALE_THRESHOLD_MINUTES] minutes.
 * Uses last_updated_utc when present.
 */
fun isDeviceStatusStale(status: DeviceStatus?): Boolean {
    if (status == null) return false
    val utc = status.lastUpdatedUtc ?: return false
    val epoch = parseIsoUtcToEpochMillis(utc) ?: return false
    val now = System.currentTimeMillis()
    return (now - epoch) > STALE_THRESHOLD_MINUTES * 60 * 1000
}

private val isoUtcFormat = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US).apply {
    timeZone = TimeZone.getTimeZone("UTC")
}

private fun parseIsoUtcToEpochMillis(isoUtc: String): Long? = try {
    isoUtcFormat.parse(isoUtc?.trim() ?: "")?.time
} catch (_: Exception) {
    null
}
