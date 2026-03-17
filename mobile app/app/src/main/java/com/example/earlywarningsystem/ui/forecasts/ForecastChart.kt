package com.example.earlywarningsystem.ui.forecasts

import android.graphics.Color
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.viewinterop.AndroidView
import com.example.earlywarningsystem.data.model.ForecastPoint
import com.example.earlywarningsystem.util.formatHourTo12Hour
import com.github.mikephil.charting.charts.LineChart
import com.github.mikephil.charting.components.AxisBase
import com.github.mikephil.charting.components.XAxis
import com.github.mikephil.charting.data.Entry
import com.github.mikephil.charting.data.LineData
import com.github.mikephil.charting.data.LineDataSet
import com.github.mikephil.charting.formatter.ValueFormatter
import com.github.mikephil.charting.interfaces.datasets.ILineDataSet

@Composable
fun ForecastChart(
    points: List<ForecastPoint>,
    parameterLabel: String,
    valueUnit: String = "",
    valueDecimals: Int = 2,
    actualValues: List<Float?> = emptyList(),
    modifier: Modifier = Modifier
) {
    val textColor = MaterialTheme.colorScheme.onSurface.toArgb()
    val gridColor = MaterialTheme.colorScheme.outline.copy(alpha = 0.4f).toArgb()

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
            if (points.isEmpty()) {
                chart.data = null
                chart.setNoDataText("")
                chart.invalidate()
                return@AndroidView
            }
            // Forecast times are in local; show them as-is (10:30 AM, etc.)
            val labels = points.map { formatHourTo12Hour(it.time) }
            val predictedEntries = points.mapIndexed { i, p -> Entry(i.toFloat(), p.predicted.toFloat()) }
            val lowerEntries = points.mapIndexed { i, p -> Entry(i.toFloat(), p.lower.toFloat()) }
            val upperEntries = points.mapIndexed { i, p -> Entry(i.toFloat(), p.upper.toFloat()) }

            // Actual: one Entry per non-null value (works for 1 point or all 24)
            val actualEntries = actualValues.take(points.size).mapIndexed { i, v ->
                if (v != null) Entry(i.toFloat(), v) else null
            }.filterNotNull()

            val setActual = LineDataSet(
                if (actualEntries.isEmpty()) emptyList() else actualEntries,
                "Actual"
            ).apply {
                color = Color.parseColor("#E65100")
                setCircleColor(Color.parseColor("#E65100"))
                lineWidth = 2f
                setDrawValues(false)
                setCircleRadius(4f)
                if (actualEntries.isEmpty()) {
                    setDrawCircles(false)
                }
            }

            val setPredicted = LineDataSet(predictedEntries, "Predicted").apply {
                color = Color.parseColor("#6200EE")
                setCircleColor(Color.parseColor("#6200EE"))
                lineWidth = 2f
                setDrawValues(false)
            }
            val setLower = LineDataSet(lowerEntries, "Lower").apply {
                color = Color.parseColor("#03DAC6")
                setCircleColor(Color.TRANSPARENT)
                setCircleRadius(0f)
                lineWidth = 1f
                setDrawValues(false)
                setDrawCircles(false)
            }
            val setUpper = LineDataSet(upperEntries, "Upper").apply {
                color = Color.parseColor("#03DAC6")
                setCircleColor(Color.TRANSPARENT)
                setCircleRadius(0f)
                lineWidth = 1f
                setDrawValues(false)
                setDrawCircles(false)
            }
            val dataSets = mutableListOf<LineDataSet>(setActual, setPredicted, setLower, setUpper)

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
            chart.data = LineData(dataSets as List<ILineDataSet>)
            chart.legend.isEnabled = true
            chart.marker = ChartMarkerView(chart.context, labels, if (valueUnit.isBlank()) "" else " $valueUnit", valueDecimals)
            chart.invalidate()
        }
    )
}
