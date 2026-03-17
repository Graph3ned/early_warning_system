package com.example.earlywarningsystem.ui.forecasts

import android.content.Context
import android.widget.TextView
import com.github.mikephil.charting.components.MarkerView
import com.github.mikephil.charting.data.Entry
import com.github.mikephil.charting.highlight.Highlight
import com.github.mikephil.charting.utils.MPPointF
import com.example.earlywarningsystem.R
import java.util.Locale

/**
 * Shows time (x) and value (y) when the user taps on the chart.
 */
class ChartMarkerView(
    context: Context,
    private val timeLabels: List<String>,
    private val valueSuffix: String,
    private val valueDecimals: Int = 2
) : MarkerView(context, R.layout.chart_marker) {

    private val timeText: TextView = findViewById(R.id.chart_marker_time)
    private val valueText: TextView = findViewById(R.id.chart_marker_value)

    override fun refreshContent(e: Entry, highlight: Highlight) {
        val index = e.x.toInt().coerceIn(0, (timeLabels.size - 1).coerceAtLeast(0))
        val time = timeLabels.getOrNull(index) ?: ""
        val valueStr = String.format(Locale.US, "%.${valueDecimals}f", e.y)
        timeText.text = time
        valueText.text = valueStr + valueSuffix
        super.refreshContent(e, highlight)
    }

    override fun getOffset(): MPPointF {
        return MPPointF(-(width / 2).toFloat(), -height.toFloat())
    }
}
