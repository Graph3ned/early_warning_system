package com.example.earlywarningsystem.ui.sensorhistory

import android.graphics.Color
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.viewinterop.AndroidView
import com.example.earlywarningsystem.data.model.SensorReading
import com.example.earlywarningsystem.util.conductivityToTds
import com.example.earlywarningsystem.util.formatTimestamp12Hour
import com.github.mikephil.charting.charts.LineChart
import com.github.mikephil.charting.components.AxisBase
import com.github.mikephil.charting.components.XAxis
import com.github.mikephil.charting.data.Entry
import com.github.mikephil.charting.data.LineData
import com.github.mikephil.charting.data.LineDataSet
import com.github.mikephil.charting.formatter.ValueFormatter
import com.github.mikephil.charting.interfaces.datasets.ILineDataSet
import com.example.earlywarningsystem.ui.forecasts.ChartMarkerView

private fun getValue(reading: SensorReading, parameter: String): Double? {
    val value = when (parameter) {
        "temperature" -> reading.temperature
        "ph" -> reading.ph
        "dissolved_oxygen" -> reading.doSalinityCompensated
        "salinity" -> if (!reading.salinity.isNaN()) reading.salinity else null
        "tds" -> conductivityToTds(if (!reading.ec.isNaN()) reading.ec else null)
        else -> null
    }
    return if (value != null && !value.isNaN()) value else null
}

/**
 * Same chart style as ForecastChart (MPAndroidChart LineChart): one series for the selected parameter.
 */
@Composable
fun SensorHistoryChart(
    readings: List<SensorReading>,
    parameter: String,
    modifier: Modifier = Modifier
) {
    val textColor = MaterialTheme.colorScheme.onSurface.toArgb()
    val gridColor = MaterialTheme.colorScheme.outline.copy(alpha = 0.4f).toArgb()
    val ordered = readings.reversed()
    val labels = ordered.map { r ->
        val full = formatTimestamp12Hour(r.timestamp)
        if (full.contains(" at ")) full.substringAfter(" at ") else full
    }
    val entries = ordered.mapIndexed { i, r ->
        getValue(r, parameter)?.let { Entry(i.toFloat(), it.toFloat()) }
    }.filterNotNull()

    AndroidView(
        modifier = modifier,
        factory = { context ->
            LineChart(context).apply {
                description.isEnabled = false
                setTouchEnabled(true)
                isDragEnabled = true
                setScaleEnabled(true)
                setPinchZoom(true)
                xAxis.position = XAxis.XAxisPosition.BOTTOM
                xAxis.setDrawGridLines(false)
                xAxis.labelRotationAngle = -45f
                xAxis.setAvoidFirstLastClipping(true)
                axisLeft.setDrawGridLines(true)
                axisRight.isEnabled = false
                setNoDataText("")
                setNoDataTextColor(Color.TRANSPARENT)
            }
        },
        update = { chart ->
            chart.xAxis.textColor = textColor
            chart.axisLeft.textColor = textColor
            chart.axisLeft.gridColor = gridColor
            chart.legend.textColor = textColor
            if (entries.isEmpty()) {
                chart.data = null
                chart.setNoDataText("")
                chart.invalidate()
                return@AndroidView
            }
            val seriesLabel = when (parameter) {
                "temperature" -> "Temperature (°C)"
                "ph" -> "pH"
                "dissolved_oxygen" -> "DO (mg/L)"
                "salinity" -> "Salinity (ppt)"
                "tds" -> "TDS (ppm)"
                else -> parameter
            }
            val valueUnit = when (parameter) {
                "temperature" -> " °C"
                "ph" -> ""
                "dissolved_oxygen" -> " mg/L"
                "salinity" -> " ppt"
                "tds" -> " ppm"
                else -> ""
            }
            val set = LineDataSet(entries, seriesLabel).apply {
                color = Color.parseColor("#6200EE")
                setCircleColor(Color.parseColor("#6200EE"))
                lineWidth = 2f
                setDrawValues(false)
            }
            chart.xAxis.valueFormatter = object : ValueFormatter() {
                override fun getAxisLabel(value: Float, axis: AxisBase?): String {
                    val index = kotlin.math.round(value).toInt().coerceIn(0, (labels.size - 1).coerceAtLeast(0))
                    return labels.getOrElse(index) { "" }
                }
            }
            chart.xAxis.setLabelCount(labels.size.coerceIn(1, 48), false)
            chart.xAxis.granularity = 1f
            chart.xAxis.axisMinimum = -0.5f
            chart.xAxis.axisMaximum = (labels.size - 1).toFloat() + 0.5f
            chart.xAxis.setSpaceMin(1f)
            chart.xAxis.setSpaceMax(1f)
            chart.data = LineData(listOf(set) as List<ILineDataSet>)
            chart.legend.isEnabled = true
            chart.marker = ChartMarkerView(chart.context, labels, valueUnit, when (parameter) {
                "salinity" -> 1
                "tds" -> 0
                else -> 2
            })
            chart.invalidate()
        }
    )
}
