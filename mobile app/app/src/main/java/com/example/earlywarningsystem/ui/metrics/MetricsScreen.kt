package com.example.earlywarningsystem.ui.metrics

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.ArrowBack
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.example.earlywarningsystem.data.model.ForecastMetrics
import com.example.earlywarningsystem.util.formatForecastRunLabel
import java.util.Locale

private val PARAM_LABELS = mapOf(
    "temperature" to "Temperature",
    "ph" to "pH",
    "dissolved_oxygen" to "Dissolved Oxygen",
    "salinity" to "Salinity",
    "tds" to "TDS",
    "ec" to "TDS"
)

@Composable
fun MetricsScreen(
    viewModel: MetricsViewModel,
    modifier: Modifier = Modifier,
    onBack: () -> Unit = {}
) {
    val metricsList by viewModel.metrics.collectAsState()
    val runIds by viewModel.runIds.collectAsState()
    val selectedRunId by viewModel.selectedRunId.collectAsState()
    val latestRunId by viewModel.latestRunId.collectAsState()

    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(PaddingValues(16.dp))
            .verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        TextButton(
            onClick = onBack,
            contentPadding = PaddingValues(0.dp)
        ) {
            Icon(
                imageVector = Icons.Outlined.ArrowBack,
                contentDescription = "Back to forecasts"
            )
            Spacer(Modifier.width(4.dp))
            Text(
                text = "Back",
                style = MaterialTheme.typography.labelMedium
            )
        }
        Text(
            text = "Metrics",
            style = MaterialTheme.typography.headlineSmall,
            color = MaterialTheme.colorScheme.primary
        )
        Text(
            text = "MAE, RMSE and MAPE per forecast run",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )

        if (runIds.isNotEmpty()) {
            Text(
                text = "Forecast run",
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 8.dp)
            )
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState())
                    .padding(vertical = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                runIds.forEachIndexed { index, id ->
                    val isSelected = id == selectedRunId
                    val isLatest = id == latestRunId
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
        if (metricsList.isEmpty()) {
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
            ) {
                Text(
                    text = "No metrics available",
                    modifier = Modifier.padding(16.dp),
                    style = MaterialTheme.typography.bodyLarge
                )
            }
        } else {
            metricsList.forEach { m ->
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text(
                            text = PARAM_LABELS[m.parameter] ?: m.parameter,
                            style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.primary
                        )
                        Text(
                            text = "MAE: ${String.format(Locale.US, "%.3f", m.mae)}",
                            style = MaterialTheme.typography.bodyLarge,
                            color = MaterialTheme.colorScheme.onSurface
                        )
                        Text(
                            text = "RMSE: ${String.format(Locale.US, "%.3f", m.rmse)}",
                            style = MaterialTheme.typography.bodyLarge,
                            color = MaterialTheme.colorScheme.onSurface
                        )
                        m.mape?.let { value ->
                            Text(
                                text = "MAPE: ${String.format(Locale.US, "%.2f", value)}%",
                                style = MaterialTheme.typography.bodyLarge,
                                color = MaterialTheme.colorScheme.onSurface
                            )
                        }
                    }
                }
            }
        }
    }
}
