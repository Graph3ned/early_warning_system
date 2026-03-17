package com.example.earlywarningsystem.ui.forecasts

import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
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
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ScrollableTabRow
import androidx.compose.material3.Tab
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.example.earlywarningsystem.data.model.ForecastPoint
import com.example.earlywarningsystem.data.model.ForecastStatus
import com.example.earlywarningsystem.util.formatForecastRunLabel
import com.example.earlywarningsystem.util.formatTimestamp12Hour
import kotlinx.coroutines.launch

private val PARAM_LABELS = mapOf(
    "temperature" to "Temperature (°C)",
    "ph" to "pH",
    "dissolved_oxygen" to "Dissolved Oxygen (mg/L)",
    "salinity" to "Salinity (ppt)",
    "tds" to "TDS (ppm)"
)
private val PARAM_UNITS = mapOf(
    "temperature" to "°C",
    "ph" to "",
    "dissolved_oxygen" to "mg/L",
    "salinity" to "ppt",
    "tds" to "ppm"
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ForecastsScreen(
    viewModel: ForecastsViewModel,
    modifier: Modifier = Modifier,
    onOpenMetrics: () -> Unit = {}
) {
    val runId by viewModel.runId.collectAsState()
    val runIds by viewModel.runIds.collectAsState()
    val selectedRunId by viewModel.selectedRunId.collectAsState()
    val forecastStatus by viewModel.forecastStatus.collectAsState()
    val isRefreshing by viewModel.isRefreshing.collectAsState()
    val pagerState = rememberPagerState(pageCount = { viewModel.parameters.size })
    val scope = rememberCoroutineScope()

    PullToRefreshBox(
        isRefreshing = isRefreshing,
        onRefresh = { viewModel.refresh() },
        modifier = modifier.fillMaxSize()
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
        ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(PaddingValues(horizontal = 20.dp, vertical = 16.dp)),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "Forecasts",
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onSurface
            )
            TextButton(onClick = onOpenMetrics) {
                Text(
                    text = "Metrics",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary
                )
            }
        }
        Text(
            text = "Forecast status",
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.Medium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(horizontal = 20.dp)
        )
        if (forecastStatus != null) {
            ForecastStatusCard(
                status = forecastStatus!!,
                latestRunId = runId,
                modifier = Modifier.padding(horizontal = 20.dp)
            )
            Spacer(Modifier.height(16.dp))
        }
        if (runIds.isEmpty() && runId.isBlank()) {
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 20.dp),
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f))
            ) {
                Text(
                    text = "No forecast run available. Run a forecast to see charts.",
                    modifier = Modifier.padding(20.dp),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        } else {
            if (runIds.isNotEmpty()) {
                Text(
                    text = "Forecast run",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Medium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(horizontal = 20.dp)
                )
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .horizontalScroll(rememberScrollState())
                        .padding(horizontal = 20.dp, vertical = 8.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    runIds.forEachIndexed { index, id ->
                        val isSelected = id == selectedRunId
                        val isLatest = id == runId
                        FilterChip(
                            selected = isSelected,
                            onClick = { viewModel.setSelectedRunId(id) },
                            label = {
                                Text(
                                    text = if (isLatest) "Latest" else formatForecastRunLabel(id, index + 1),
                                    style = MaterialTheme.typography.labelMedium,
                                    maxLines = 1
                                )
                            }
                        )
                    }
                }
            }
            ScrollableTabRow(
                selectedTabIndex = pagerState.currentPage,
                modifier = Modifier.fillMaxWidth()
            ) {
                viewModel.parameters.forEachIndexed { index, param ->
                    Tab(
                        selected = pagerState.currentPage == index,
                        onClick = {
                            scope.launch {
                                pagerState.animateScrollToPage(index)
                            }
                        },
                        text = {
                            Text(
                                text = PARAM_LABELS[param] ?: param,
                                style = MaterialTheme.typography.labelMedium
                            )
                        }
                    )
                }
            }
            HorizontalPager(
                state = pagerState,
                modifier = Modifier.fillMaxWidth().height(320.dp),
                userScrollEnabled = true
            ) { page ->
                val param = viewModel.parameters[page]
                val pairState = viewModel.forecastPointsWithActuals(param).collectAsState(
                    initial = Pair(emptyList<ForecastPoint>(), emptyList<Float?>())
                )
                val points = pairState.value.first
                val actuals = pairState.value.second
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(16.dp)
                ) {
                    ForecastChart(
                        points = points,
                        parameterLabel = PARAM_LABELS[param] ?: param,
                        valueUnit = PARAM_UNITS[param] ?: "",
                        valueDecimals = when (param) {
                            "salinity" -> 1
                            "tds" -> 0
                            else -> 2
                        },
                        actualValues = actuals,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(280.dp)
                    )
                }
            }
        }
        }
    }
}

@Composable
private fun ForecastStatusCard(
    status: ForecastStatus,
    latestRunId: String = "",
    modifier: Modifier = Modifier
) {
    val isReady = status.system.equals("READY", ignoreCase = true)
    val statusColor = if (isReady) Color(0xFF2E7D32) else Color(0xFFE65100)
    val statusBg = if (isReady) Color(0xFFE8F5E9) else Color(0xFFFFF3E0)
    val lastRunFormatted = if (latestRunId.isNotBlank()) {
        val fromRunId = formatForecastRunLabel(latestRunId, 1)
        if (fromRunId.startsWith("Run #")) formatTimestamp12Hour(status.lastForecastAt) else fromRunId
    } else {
        formatTimestamp12Hour(status.lastForecastAt)
    }

    Card(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(modifier = Modifier.padding(20.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(10.dp))
                        .background(statusBg)
                        .padding(horizontal = 14.dp, vertical = 8.dp)
                ) {
                    Text(
                        text = status.system,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                        color = statusColor
                    )
                }
            }
            Spacer(Modifier.height(12.dp))
            Text(
                text = status.reason,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            if (lastRunFormatted != "—") {
                Spacer(Modifier.height(8.dp))
                Text(
                    text = "Last run: $lastRunFormatted",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}
