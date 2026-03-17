package com.example.earlywarningsystem.ui.dashboard

import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Air
import androidx.compose.material.icons.outlined.Schedule
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.example.earlywarningsystem.data.model.SensorReading
import com.example.earlywarningsystem.data.model.UserRole
import com.example.earlywarningsystem.util.classifyDo
import com.example.earlywarningsystem.util.classifyPh
import com.example.earlywarningsystem.util.classifySalinity
import com.example.earlywarningsystem.util.classifyTemperature
import com.example.earlywarningsystem.util.conductivityToTds
import com.example.earlywarningsystem.util.formatTimestamp12Hour
import com.example.earlywarningsystem.util.ParameterStatus
import com.example.earlywarningsystem.util.ThresholdConfig
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(
    viewModel: DashboardViewModel,
    userRole: UserRole = UserRole.VIEWER,
    modifier: Modifier = Modifier,
    onOpenHistory: () -> Unit = {}
) {
    val reading by viewModel.latestReading.collectAsState()
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
                text = "Dashboard",
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onSurface
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                SectionTitle("Sensor readings")
                HistoryTextButton(onOpenHistory = onOpenHistory)
            }
            if (reading == null) {
                EmptyStateCard(message = "Waiting for sensor data…")
            } else {
                SensorReadingCard(reading!!, isAdmin = userRole == UserRole.ADMIN)
            }
        }
    }
}

@Composable
private fun SectionTitle(title: String) {
    Text(
        text = title,
        style = MaterialTheme.typography.titleSmall,
        fontWeight = FontWeight.Medium,
        color = MaterialTheme.colorScheme.onSurfaceVariant
    )
}

@Composable
private fun EmptyStateCard(message: String) {
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
private fun HistoryTextButton(onOpenHistory: () -> Unit) {
    androidx.compose.material3.TextButton(onClick = onOpenHistory) {
        Text(
            text = "History",
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.Medium,
            color = MaterialTheme.colorScheme.primary
        )
    }
}

@Composable
private fun SensorReadingCard(reading: SensorReading, isAdmin: Boolean = false) {
    val formattedTime = formatTimestamp12Hour(reading.timestamp)
    val isAerationOn = reading.aerationStatus.equals("ACTIVATED", ignoreCase = true)

    Card(
        modifier = Modifier.fillMaxWidth(),
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
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Outlined.Schedule,
                        contentDescription = null,
                        modifier = Modifier.size(18.dp),
                        tint = MaterialTheme.colorScheme.primary
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(
                        text = formattedTime,
                        style = MaterialTheme.typography.labelLarge,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            Spacer(Modifier.height(16.dp))
            HorizontalDivider(
                modifier = Modifier.fillMaxWidth(),
                color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f)
            )
            Spacer(Modifier.height(16.dp))
            ParameterStatusRow(
                name = "Dissolved Oxygen (DO)",
                value = if (reading.doSalinityCompensated.isNaN()) "—" else "${String.format(Locale.US, "%.2f", reading.doSalinityCompensated)} mg/L",
                optimalRef = ThresholdConfig.DO_OPTIMAL_REF,
                status = classifyDo(reading.doSalinityCompensated)
            )
            Spacer(Modifier.height(10.dp))
            ParameterStatusRow(
                name = "Temperature",
                value = if (reading.temperature.isNaN()) "—" else "${reading.temperature} °C",
                optimalRef = ThresholdConfig.TEMP_OPTIMAL_REF,
                status = classifyTemperature(reading.temperature)
            )
            Spacer(Modifier.height(10.dp))
            ParameterStatusRow(
                name = "Salinity",
                value = if (!reading.salinity.isNaN() && reading.salinity > 0.0) "${String.format(Locale.US, "%.1f", reading.salinity)} ppt" else "—",
                optimalRef = ThresholdConfig.SAL_OPTIMAL_REF,
                status = if (!reading.salinity.isNaN() && reading.salinity > 0.0) classifySalinity(reading.salinity) else ParameterStatus.Normal
            )
            Spacer(Modifier.height(10.dp))
            ParameterStatusRow(
                name = "pH",
                value = if (reading.ph.isNaN()) "—" else "${reading.ph}",
                optimalRef = ThresholdConfig.PH_OPTIMAL_REF,
                status = classifyPh(reading.ph)
            )
            Spacer(Modifier.height(12.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                MetricChip(
                    label = "TDS",
                    value = conductivityToTds(if (!reading.ec.isNaN()) reading.ec else null)?.let { "${String.format(Locale.US, "%.0f", it)} ppm" } ?: "—",
                    modifier = Modifier.weight(1f)
                )
                if (isAdmin) {
                    MetricChip(
                        label = "EC",
                        value = if (reading.ec.isNaN()) "—" else "${String.format(Locale.US, "%.2f", reading.ec)} mS/cm",
                        modifier = Modifier.weight(1f)
                    )
                }
                AerationChip(
                    isOn = isAerationOn,
                    modifier = Modifier.weight(1f)
                )
            }
        }
    }
}

/** BFAR color coding: Green = Normal, Yellow = Warning, Red = Critical. */
private fun statusColor(status: ParameterStatus): Color = when (status) {
    ParameterStatus.Normal -> Color(0xFF2E7D32)   // Green
    ParameterStatus.Warning -> Color(0xFFF9A825)  // Yellow
    ParameterStatus.Critical -> Color(0xFFC62828) // Red
}

@Composable
private fun ParameterStatusRow(
    name: String,
    value: String,
    optimalRef: String,
    status: ParameterStatus
) {
    val color = statusColor(status)
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(color.copy(alpha = 0.12f))
            .padding(14.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = name,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Text(
                text = value,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onSurface
            )
            Text(
                text = "Optimal: $optimalRef",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
        Box(
            modifier = Modifier
                .clip(RoundedCornerShape(8.dp))
                .background(color.copy(alpha = 0.2f))
                .padding(horizontal = 10.dp, vertical = 6.dp)
        ) {
            Text(
                text = status.name,
                style = MaterialTheme.typography.labelLarge,
                fontWeight = FontWeight.SemiBold,
                color = color
            )
        }
    }
}

@Composable
private fun MetricChip(
    label: String,
    value: String,
    modifier: Modifier = Modifier
) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(12.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f))
            .padding(horizontal = 14.dp, vertical = 12.dp)
    ) {
        Column {
            Text(
                text = label,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Text(
                text = value,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onSurface
            )
        }
    }
}

@Composable
private fun AerationChip(
    isOn: Boolean,
    modifier: Modifier = Modifier
) {
    val bgColor = if (isOn) Color(0xFFE8F5E9) else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f)
    val textColor = if (isOn) Color(0xFF2E7D32) else MaterialTheme.colorScheme.onSurfaceVariant

    Box(
        modifier = modifier
            .clip(RoundedCornerShape(12.dp))
            .background(bgColor)
            .padding(horizontal = 14.dp, vertical = 12.dp)
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Icon(
                imageVector = Icons.Outlined.Air,
                contentDescription = null,
                modifier = Modifier.size(20.dp),
                tint = textColor
            )
            Column {
                Text(
                    text = "Aeration",
                    style = MaterialTheme.typography.labelMedium,
                    color = textColor
                )
                Text(
                    text = if (isOn) "On" else "Off",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = textColor
                )
            }
        }
    }
}
