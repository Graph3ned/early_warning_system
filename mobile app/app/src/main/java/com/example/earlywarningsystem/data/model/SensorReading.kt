package com.example.earlywarningsystem.data.model

data class SensorReading(
    val timestamp: String,
    val temperature: Double,
    val ph: Double,
    val dissolvedOxygen: Double,
    /** Salinity-compensated DO for display; from Firebase do_salinity_compensated or dissolved_oxygen when missing. */
    val doSalinityCompensated: Double,
    val ec: Double,
    val salinity: Double = 0.0,
    val aerationStatus: String? = null
)
