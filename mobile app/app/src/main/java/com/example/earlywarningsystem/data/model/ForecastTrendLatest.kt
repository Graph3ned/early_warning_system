package com.example.earlywarningsystem.data.model

/**
 * Result of forecast trend analysis written to Firebase at `forecast_trend/latest`.
 * The app only reads this; trend is computed by the Prophet server.
 */
data class ForecastTrendLatest(
    val runId: String,
    val analysisTimestampUtc: String? = null,
    val summaryMessages: List<String> = emptyList(),
    val warnings: List<TrendWarning> = emptyList()
)
