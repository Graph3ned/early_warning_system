package com.example.earlywarningsystem.ui.alerts

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Warning
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import kotlinx.coroutines.delay
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import com.example.earlywarningsystem.data.model.ForecastTrendLatest
import com.example.earlywarningsystem.data.model.TrendWarning
import com.example.earlywarningsystem.util.formatTimeLeft
import com.example.earlywarningsystem.util.getThresholdCrossingEpochMillis
import com.example.earlywarningsystem.util.isWarningActive
import com.example.earlywarningsystem.util.replaceSummaryTime

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AlertsScreen(
    viewModel: AlertsViewModel,
    modifier: Modifier = Modifier
) {
    val forecastTrend by viewModel.forecastTrend.collectAsState()
    val isRefreshing by viewModel.isRefreshing.collectAsState()

    PullToRefreshBox(
        isRefreshing = isRefreshing,
        onRefresh = { viewModel.refresh() },
        modifier = modifier.fillMaxSize()
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(PaddingValues(horizontal = 20.dp, vertical = 16.dp)),
            verticalArrangement = Arrangement.spacedBy(20.dp)
        ) {
            Text(
                text = "Alerts",
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onSurface
            )

            Text(
                text = "Early warnings",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Medium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            when {
                forecastTrend == null ->
                    EmptyCard(message = "No trend data available.")
                else -> EarlyWarningsSection(trend = forecastTrend!!)
            }
        }
    }
}

@Composable
private fun EmptyCard(message: String) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f)),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
    ) {
        Text(
            text = message,
            modifier = Modifier.padding(20.dp),
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

@Composable
private fun EarlyWarningsSection(trend: ForecastTrendLatest) {
    var nowForRefresh by remember { mutableStateOf(System.currentTimeMillis()) }
    LaunchedEffect(Unit) {
        while (true) {
            delay(10_000)
            nowForRefresh = System.currentTimeMillis()
        }
    }
    val activeWarningsWithTime = remember(trend, nowForRefresh) {
        trend.warnings.mapNotNull { w ->
            val crossing = getThresholdCrossingEpochMillis(w, trend.analysisTimestampUtc)
            if (crossing != null && isWarningActive(crossing, nowForRefresh)) {
                Pair(w, formatTimeLeft(crossing, nowForRefresh))
            } else null
        }
    }

    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        if (activeWarningsWithTime.isEmpty()) {
            EmptyCard(message = "No active warning.")
        } else {
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(20.dp),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
            ) {
                Column(modifier = Modifier.padding(20.dp)) {
                    Text(
                        text = "Warnings",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.SemiBold,
                        color = MaterialTheme.colorScheme.primary
                    )
                    Spacer(Modifier.height(12.dp))
                    activeWarningsWithTime.forEachIndexed { index, (warning, timeLeft) ->
                        WarningRow(warning = warning, timeLeft = timeLeft)
                        if (index < activeWarningsWithTime.size - 1) {
                            HorizontalDivider(
                                modifier = Modifier.padding(vertical = 8.dp),
                                color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f)
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun WarningRow(warning: TrendWarning, timeLeft: String?) {
    val isCritical = warning.severity.equals("critical", ignoreCase = true)
    val severityColor = if (isCritical) Color(0xFFB71C1C) else Color(0xFFE65100)
    val severityBg = if (isCritical) Color(0xFFFFEBEE) else Color(0xFFFFF3E0)
    val displayMessage = if (timeLeft != null) replaceSummaryTime(warning.message, timeLeft) else warning.message
    val annotatedMessage = if (timeLeft != null && displayMessage.contains(timeLeft)) {
        buildAnnotatedString {
            val start = displayMessage.indexOf(timeLeft)
            append(displayMessage.substring(0, start))
            withStyle(SpanStyle(fontSize = MaterialTheme.typography.titleMedium.fontSize, fontWeight = FontWeight.SemiBold)) {
                append(timeLeft)
            }
            append(displayMessage.substring(start + timeLeft.length))
        }
    } else {
        buildAnnotatedString { append(displayMessage) }
    }

    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.Top,
        horizontalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        Box(
            modifier = Modifier
                .clip(RoundedCornerShape(6.dp))
                .background(severityBg)
                .padding(horizontal = 8.dp, vertical = 4.dp)
        ) {
            Text(
                text = warning.severity.uppercase(),
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.SemiBold,
                color = severityColor
            )
        }
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = annotatedMessage,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface
            )
            warning.confidence?.let { conf ->
                Spacer(Modifier.height(4.dp))
                Text(
                    text = "Confidence: $conf",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}
