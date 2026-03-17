package com.example.earlywarningsystem.ui.sensorhistory

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.horizontalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowUpward
import androidx.compose.material.icons.outlined.ArrowBack
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.example.earlywarningsystem.data.model.SensorReading
import com.example.earlywarningsystem.util.conductivityToTds
import com.example.earlywarningsystem.util.endOfDayLocal
import com.example.earlywarningsystem.util.formatTimestamp12Hour
import com.example.earlywarningsystem.util.startOfDayLocal
import java.util.Locale
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SensorHistoryScreen(
    viewModel: SensorHistoryViewModel,
    modifier: Modifier = Modifier,
    onBack: () -> Unit = {}
) {
    val readings by viewModel.displayedReadings.collectAsState()
    val rangeDescription by viewModel.rangeDescription.collectAsState()
    val selectedInterval by viewModel.selectedIntervalMinutes.collectAsState()
    val selectedRange by viewModel.selectedRange.collectAsState()
    val isRefreshing by viewModel.isRefreshing.collectAsState()
    val listState = rememberLazyListState()
    val scope = rememberCoroutineScope()

    val showScrollToTop by remember {
        derivedStateOf { listState.firstVisibleItemIndex > 0 || listState.firstVisibleItemScrollOffset > 200 }
    }

    var showSelectDatePicker by remember { mutableStateOf(false) }
    var showCustomFromPicker by remember { mutableStateOf(false) }
    var showCustomToPicker by remember { mutableStateOf(false) }
    var customFromEpoch by remember { mutableLongStateOf(System.currentTimeMillis()) }

    if (showSelectDatePicker) {
        val state = rememberDatePickerState(initialSelectedDateMillis = System.currentTimeMillis())
        DatePickerDialog(
            onDismissRequest = { showSelectDatePicker = false },
            confirmButton = {
                TextButton(onClick = {
                    state.selectedDateMillis?.let { viewModel.setRangeSelectDate(startOfDayLocal(it)) }
                    showSelectDatePicker = false
                }) { Text("OK") }
            }
        ) {
            DatePicker(state = state)
        }
    }
    if (showCustomFromPicker) {
        val state = rememberDatePickerState(initialSelectedDateMillis = customFromEpoch)
        DatePickerDialog(
            onDismissRequest = { showCustomFromPicker = false },
            confirmButton = {
                TextButton(onClick = {
                    state.selectedDateMillis?.let {
                        customFromEpoch = startOfDayLocal(it)
                        showCustomFromPicker = false
                        showCustomToPicker = true
                    }
                }) { Text("Next") }
            }
        ) {
            DatePicker(state = state)
        }
    }
    if (showCustomToPicker) {
        val state = rememberDatePickerState(initialSelectedDateMillis = customFromEpoch)
        DatePickerDialog(
            onDismissRequest = { showCustomToPicker = false },
            confirmButton = {
                TextButton(onClick = {
                    state.selectedDateMillis?.let { toEpoch ->
                        viewModel.setRangeCustom(customFromEpoch, endOfDayLocal(toEpoch))
                        showCustomToPicker = false
                    }
                }) { Text("OK") }
            }
        ) {
            DatePicker(state = state)
        }
    }

    var viewMode by remember { mutableStateOf("Values") }
    var graphParameter by remember { mutableStateOf("temperature") }

    PullToRefreshBox(
        isRefreshing = isRefreshing,
        onRefresh = { viewModel.refresh() },
        modifier = modifier.fillMaxSize()
    ) {
        Box(modifier = Modifier.fillMaxSize()) {
            LazyColumn(
                state = listState,
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(horizontal = 20.dp, vertical = 16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                item(key = "header") {
                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        TextButton(
                            onClick = onBack,
                            contentPadding = PaddingValues(0.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Outlined.ArrowBack,
                                contentDescription = "Back to dashboard"
                            )
                            Spacer(Modifier.width(4.dp))
                            Text(
                                text = "Back",
                                style = MaterialTheme.typography.labelMedium
                            )
                        }
                        Text(
                            text = "Sensor history",
                            style = MaterialTheme.typography.headlineMedium,
                            fontWeight = FontWeight.SemiBold,
                            color = MaterialTheme.colorScheme.onSurface
                        )
                        Text(
                            text = rangeDescription,
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Text(
                            text = "View",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            FilterChip(
                                selected = viewMode == "Values",
                                onClick = { viewMode = "Values" },
                                label = { Text("Values", style = MaterialTheme.typography.labelMedium) }
                            )
                            FilterChip(
                                selected = viewMode == "Graph",
                                onClick = { viewMode = "Graph" },
                                label = { Text("Graph", style = MaterialTheme.typography.labelMedium) }
                            )
                        }
                        Text(
                            text = "Time interval",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .horizontalScroll(rememberScrollState()),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            listOf(0 to "All", 5 to "5 min", 30 to "30 min", 60 to "1 hour").forEach { (minutes, label) ->
                                FilterChip(
                                    selected = selectedInterval == minutes,
                                    onClick = { viewModel.setIntervalMinutes(minutes) },
                                    label = { Text(label, style = MaterialTheme.typography.labelMedium) }
                                )
                            }
                        }
                        Text(
                            text = "Date range",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .horizontalScroll(rememberScrollState()),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            FilterChip(
                                selected = selectedRange is SensorHistoryRange.Last24h,
                                onClick = { viewModel.setRangeLast24h() },
                                label = { Text("Last 24 hours", style = MaterialTheme.typography.labelMedium) }
                            )
                            FilterChip(
                                selected = selectedRange is SensorHistoryRange.SelectDate,
                                onClick = { showSelectDatePicker = true },
                                label = { Text("Select date", style = MaterialTheme.typography.labelMedium) }
                            )
                            FilterChip(
                                selected = selectedRange is SensorHistoryRange.Custom,
                                onClick = { showCustomFromPicker = true },
                                label = { Text("Custom", style = MaterialTheme.typography.labelMedium) }
                            )
                        }
                        Spacer(Modifier.height(8.dp))
                    }
                }
                if (readings.isEmpty()) {
                    item(key = "empty") {
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(16.dp),
                            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f))
                        ) {
                            Text(
                                text = "No sensor data for the selected range.",
                                modifier = Modifier.padding(20.dp),
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                } else if (viewMode == "Graph") {
                    item(key = "graph") {
                        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text(
                                text = "Parameter",
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .horizontalScroll(rememberScrollState()),
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                listOf(
                                    "temperature" to "Temperature",
                                    "ph" to "pH",
                                    "dissolved_oxygen" to "DO",
                                    "salinity" to "Salinity",
                                    "tds" to "TDS"
                                ).forEach { (param, label) ->
                                    FilterChip(
                                        selected = graphParameter == param,
                                        onClick = { graphParameter = param },
                                        label = { Text(label, style = MaterialTheme.typography.labelMedium) }
                                    )
                                }
                            }
                            SensorHistoryChart(
                                readings = readings,
                                parameter = graphParameter,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(300.dp)
                            )
                        }
                    }
                } else {
                    items(
                        items = readings,
                        key = { it.timestamp }
                    ) { reading ->
                        SensorHistoryRow(reading = reading)
                    }
                }
            }

            if (showScrollToTop) {
                FloatingActionButton(
                    onClick = { scope.launch { listState.animateScrollToItem(0) } },
                    modifier = Modifier
                        .align(Alignment.BottomEnd)
                        .padding(16.dp)
                ) {
                    Icon(
                        imageVector = Icons.Filled.ArrowUpward,
                        contentDescription = "Scroll to top"
                    )
                }
            }
        }
    }
}

private fun formatSensorValue(value: Double, decimals: Int): String =
    if (value.isNaN()) "—" else String.format(Locale.US, "%.${decimals}f", value)

@Composable
private fun SensorHistoryRow(reading: SensorReading) {
    val timeStr = formatTimestamp12Hour(reading.timestamp)
    val isAerationOn = reading.aerationStatus.equals("ACTIVATED", ignoreCase = true)
    val salinity = if (!reading.salinity.isNaN() && reading.salinity > 0.0) "${formatSensorValue(reading.salinity, 1)} ppt" else "—"
    val tds = conductivityToTds(if (!reading.ec.isNaN()) reading.ec else null)?.let { "${formatSensorValue(it, 0)} ppm" } ?: "—"

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text = timeStr,
                style = MaterialTheme.typography.labelLarge,
                fontWeight = FontWeight.Medium,
                color = MaterialTheme.colorScheme.primary
            )
            FlowRow(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 12.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                MiniChip(label = "Temp", value = "${formatSensorValue(reading.temperature, 1)} °C")
                MiniChip(label = "pH", value = formatSensorValue(reading.ph, 2))
                MiniChip(label = "DO", value = "${formatSensorValue(reading.doSalinityCompensated, 2)} mg/L")
                MiniChip(label = "Salinity", value = salinity)
                MiniChip(label = "TDS", value = tds)
                MiniChip(label = "Aeration", value = if (isAerationOn) "On" else "Off")
            }
        }
    }
}

@Composable
private fun MiniChip(label: String, value: String) {
    Row(
        modifier = Modifier
            .clip(RoundedCornerShape(8.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f))
            .padding(horizontal = 10.dp, vertical = 6.dp)
    ) {
        Text(
            text = "$label: ",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Text(
            text = value,
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.Medium,
            color = MaterialTheme.colorScheme.onSurface
        )
    }
}
