package com.example.earlywarningsystem.data.model

data class ForecastMetrics(
    val runId: String,
    val parameter: String,
    val mae: Double,
    val rmse: Double,
    val mape: Double? = null
)
