package com.example.earlywarningsystem.data.model

/**
 * A single early-warning item from forecast trend analysis.
 * thresholdCrossingUtc: from backend if present; else derived from analysis_timestamp_utc + time_to_threshold_hours.
 */
data class TrendWarning(
    val parameter: String,
    val message: String,
    val severity: String,
    val timeToThresholdHours: Double? = null,
    val thresholdCrossingUtc: String? = null,
    val confidence: String? = null
)
