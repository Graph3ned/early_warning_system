package com.example.earlywarningsystem.data.model

data class ForecastStatus(
    val system: String,
    val reason: String,
    val latestRunId: String? = null,
    val lastForecastAt: String? = null
)
