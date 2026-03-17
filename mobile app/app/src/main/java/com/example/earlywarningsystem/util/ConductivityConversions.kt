package com.example.earlywarningsystem.util

import java.math.BigDecimal
import java.math.RoundingMode

/** EC in µS/cm to mS/cm. */
private fun ecUsToMcScm(ecUs: Double): Double = ecUs / 1000.0

/**
 * Converts electrical conductivity in mS/cm to TDS (ppm).
 *
 * Requested formula:
 * raw_ppt = 0.657973 * EC_mScm - 2.245991
 * TDS_ppm = max(0, raw_ppt) * 1000
 *
 * Notes:
 * - In aquaculture, "ppt" for salinity usually means parts-per-thousand (‰), where 1 ppt = 1000 ppm.
 * - This function returns ppm and rounds to a whole number.
 */
fun conductivityToTds(ecMscm: Double?): Double? =
    if (ecMscm != null && !ecMscm.isNaN()) {
        val rawPpt = 0.657973 * ecMscm - 2.245991
        val ppm = (rawPpt.coerceAtLeast(0.0)) * 1000.0
        BigDecimal(ppm).setScale(0, RoundingMode.HALF_UP).toDouble()
    } else null

/**
 * Converts electrical conductivity (µS/cm) to salinity (ppt) from EC in mS/cm.
 * Formula: salinity = 0.657973 * EC_mScm - 2.245991. Clamped to [0, 42]. Rounded to 2 decimal places.
 */
fun conductivityToSalinity(ecUs: Double?): Double? =
    if (ecUs != null && !ecUs.isNaN()) {
        val ecMcScm = ecUsToMcScm(ecUs)
        val raw = 0.657973 * ecMcScm - 2.245991
        val clamped = raw.coerceIn(0.0, 42.0)
        BigDecimal(clamped).setScale(2, RoundingMode.HALF_UP).toDouble()
    } else null
