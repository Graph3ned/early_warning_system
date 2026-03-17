package com.example.earlywarningsystem.util

import com.example.earlywarningsystem.data.model.SensorReading
import java.util.Locale

/**
 * Status classification for BFAR Bangus cage culture water quality parameters.
 * Green = Normal, Yellow = Warning, Red = Critical.
 */
enum class ParameterStatus {
    Normal,
    Warning,
    Critical
}

/**
 * BFAR Bangus cage culture threshold configuration.
 * Ranges are non-overlapping; comparisons use consistent <=, >=.
 *
 * DO: mg/L | Temperature: °C | pH: unitless | Salinity: ppt
 */
object ThresholdConfig {

    // ——— Dissolved Oxygen (DO) ———
    // Normal: ≥ 4; Warning: 2.5–<4; Critical: < 2.5
    const val DO_NORMAL_MIN = 4.0
    const val DO_WARNING_MIN = 2.5
    const val DO_OPTIMAL_REF = "≥ 4.0 mg/L"

    // ——— Temperature (°C) ———
    // Normal: 26–30; Warning: 23–<26 or >30–35; Critical: < 23 or > 35
    const val TEMP_NORMAL_MIN = 26.0
    const val TEMP_NORMAL_MAX = 30.0
    const val TEMP_WARNING_LOW_MIN = 23.0
    const val TEMP_WARNING_HIGH_MAX = 35.0
    const val TEMP_OPTIMAL_REF = "26–30 °C"

    // ——— pH ———
    // Normal: 7.5–8.5; Warning: 6–<7.5 or 8.5–9.5; Critical: < 6 or > 9.5
    const val PH_NORMAL_MIN = 7.5
    const val PH_NORMAL_MAX = 8.5
    const val PH_WARNING_MIN = 6.0
    const val PH_WARNING_HIGH_MAX = 9.5
    const val PH_OPTIMAL_REF = "7.5–8.5"

    // ——— Salinity (ppt) ———
    // Normal: 10–35; Warning: 5–<10 or >35 and ≤109; Critical: < 5 or > 109
    const val SAL_NORMAL_MIN = 10.0
    const val SAL_NORMAL_MAX = 35.0
    const val SAL_CRITICAL_LOW_MAX = 5.0   // Critical when value < 5
    const val SAL_CRITICAL_HIGH_MIN = 109.0
    const val SAL_OPTIMAL_REF = "10–35 ppt"
}

/** DO: Normal ≥ 4; Warning 2.5–<4; Critical < 2.5. NaN → Normal. */
fun classifyDo(value: Double): ParameterStatus = when {
    value.isNaN() -> ParameterStatus.Normal
    value >= ThresholdConfig.DO_NORMAL_MIN -> ParameterStatus.Normal
    value < ThresholdConfig.DO_WARNING_MIN -> ParameterStatus.Critical
    else -> ParameterStatus.Warning // 2.5 ≤ value < 4
}

/** Temperature: Normal 26–30; Warning 23–<26 or >30–35; Critical < 23 or > 35. */
fun classifyTemperature(value: Double): ParameterStatus = when {
    value.isNaN() -> ParameterStatus.Normal
    value in ThresholdConfig.TEMP_NORMAL_MIN..ThresholdConfig.TEMP_NORMAL_MAX -> ParameterStatus.Normal
    value >= ThresholdConfig.TEMP_WARNING_LOW_MIN && value < ThresholdConfig.TEMP_NORMAL_MIN -> ParameterStatus.Warning  // 23–<26
    value > ThresholdConfig.TEMP_NORMAL_MAX && value <= ThresholdConfig.TEMP_WARNING_HIGH_MAX -> ParameterStatus.Warning  // >30–35
    else -> ParameterStatus.Critical
}

/** Salinity: Normal 10–35; Warning 5–<10 or >35 and ≤109; Critical < 5 or > 109. */
fun classifySalinity(value: Double): ParameterStatus = when {
    value.isNaN() -> ParameterStatus.Normal
    value > ThresholdConfig.SAL_CRITICAL_HIGH_MIN -> ParameterStatus.Critical
    value < ThresholdConfig.SAL_CRITICAL_LOW_MAX -> ParameterStatus.Critical   // < 5 ppt
    value in ThresholdConfig.SAL_NORMAL_MIN..ThresholdConfig.SAL_NORMAL_MAX -> ParameterStatus.Normal
    value < ThresholdConfig.SAL_NORMAL_MIN -> ParameterStatus.Warning   // 5 ≤ value < 10
    else -> ParameterStatus.Warning   // > 35 and ≤ 109
}

/** pH: Normal 7.5–8.5; Warning 6–<7.5 or 8.5–9.5; Critical < 6 or > 9.5. */
fun classifyPh(value: Double): ParameterStatus = when {
    value.isNaN() -> ParameterStatus.Normal
    value in ThresholdConfig.PH_NORMAL_MIN..ThresholdConfig.PH_NORMAL_MAX -> ParameterStatus.Normal
    value >= ThresholdConfig.PH_WARNING_MIN && value < ThresholdConfig.PH_NORMAL_MIN -> ParameterStatus.Warning  // 6–<7.5
    value > ThresholdConfig.PH_NORMAL_MAX && value <= ThresholdConfig.PH_WARNING_HIGH_MAX -> ParameterStatus.Warning  // 8.5–9.5
    else -> ParameterStatus.Critical
}

/**
 * Returns alert messages for parameters that are Warning or Critical.
 * DO: < 2.5 → Critical; < 4 → Low Dissolved Oxygen – Monitoring Advised.
 */
fun getSensorWarnings(reading: SensorReading): List<String> {
    val warnings = mutableListOf<String>()

    if (!reading.doSalinityCompensated.isNaN()) {
        val doVal = reading.doSalinityCompensated
        val doStatus = classifyDo(doVal)
        if (doStatus != ParameterStatus.Normal) {
            warnings.add(
                when {
                    doVal < ThresholdConfig.DO_WARNING_MIN -> "Critical Dissolved Oxygen – Aeration Activated"
                    doVal < ThresholdConfig.DO_NORMAL_MIN -> "Low Dissolved Oxygen – Monitoring Advised"
                    else -> "Dissolved oxygen (${String.format(Locale.US, "%.2f", doVal)} mg/L) is ${doStatus.name.lowercase()} (optimal ${ThresholdConfig.DO_OPTIMAL_REF})."
                }
            )
        }
    }

    if (!reading.ph.isNaN()) {
        val phStatus = classifyPh(reading.ph)
        if (phStatus != ParameterStatus.Normal) {
            warnings.add("pH (${String.format(Locale.US, "%.2f", reading.ph)}) is ${phStatus.name.lowercase()} (optimal ${ThresholdConfig.PH_OPTIMAL_REF}).")
        }
    }

    if (!reading.temperature.isNaN()) {
        val tempStatus = classifyTemperature(reading.temperature)
        if (tempStatus != ParameterStatus.Normal) {
            warnings.add("Temperature (${String.format(Locale.US, "%.1f", reading.temperature)} °C) is ${tempStatus.name.lowercase()} (optimal ${ThresholdConfig.TEMP_OPTIMAL_REF}).")
        }
    }

    if (!reading.salinity.isNaN() && reading.salinity > 0.0) {
        val salStatus = classifySalinity(reading.salinity)
        if (salStatus != ParameterStatus.Normal) {
            warnings.add("Salinity (${String.format(Locale.US, "%.1f", reading.salinity)} ppt) is ${salStatus.name.lowercase()} (optimal ${ThresholdConfig.SAL_OPTIMAL_REF}).")
        }
    }

    return warnings
}
