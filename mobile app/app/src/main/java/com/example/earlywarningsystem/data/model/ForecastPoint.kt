package com.example.earlywarningsystem.data.model

data class ForecastPoint(
    val parameter: String,
    val date: String,
    val time: String,
    val predicted: Double,
    val lower: Double,
    val upper: Double
) {
    /** ISO 8601 style datetime for ordering/parsing */
    val dateTime: String get() = "${date}T${time}:00"
}
