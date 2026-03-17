package com.example.earlywarningsystem.data.model

/**
 * Pi/device status from Firebase `device_status`.
 * reading_status: "ok" | "no_data" | "invalid_readings"
 * last_updated_local preferred for "Last updated at" in UI.
 */
data class DeviceStatus(
    val readingStatus: String,
    val lastUpdatedUtc: String?,
    val lastUpdatedLocal: String?,
    val espConnected: Boolean? = null,
    val invalidParams: List<String>? = null,
    val message: String? = null,
    val piTemperatureCelsius: Double? = null
) {
    val isOk: Boolean get() = readingStatus.equals("ok", ignoreCase = true)
    val isNoData: Boolean get() = readingStatus.equals("no_data", ignoreCase = true)
    val isInvalidReadings: Boolean get() = readingStatus.equals("invalid_readings", ignoreCase = true)
}
