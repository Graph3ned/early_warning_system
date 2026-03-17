package com.example.earlywarningsystem.ui.forecasts

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.earlywarningsystem.data.model.ForecastPoint
import com.example.earlywarningsystem.data.repository.EwsRepository
import com.example.earlywarningsystem.util.actualsFromClosestReadingPer30MinSlot
import com.example.earlywarningsystem.util.conductivityToTds
import com.example.earlywarningsystem.util.expandForecastPointsTo30Min
import com.example.earlywarningsystem.util.forecastPointsToTimeRange
import com.example.earlywarningsystem.util.matchActualsToExpandedPoints
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.merge
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

private val FORECAST_PARAMETERS = listOf("temperature", "ph", "dissolved_oxygen", "salinity", "tds")

class ForecastsViewModel(
    private val ewsRepository: EwsRepository
) : ViewModel() {

    val forecastStatus = ewsRepository.forecastStatusFlow()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), null)

    val runId: StateFlow<String> = forecastStatus.map { it?.latestRunId ?: "" }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), "")

    private val refreshTrigger = MutableSharedFlow<Unit>(replay = 0)

    val runIds: StateFlow<List<String>> = merge(flowOf(Unit), refreshTrigger)
        .flatMapLatest { ewsRepository.forecastRunIdsFlow() }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    val selectedRunId = MutableStateFlow("")

    init {
        runId.onEach { id ->
            if (id.isNotBlank() && selectedRunId.value.isEmpty()) selectedRunId.value = id
        }.launchIn(viewModelScope)
    }

    private val forecastPointsCache = mutableMapOf<String, StateFlow<List<ForecastPoint>>>()
    private val pointsWithActualsCache = mutableMapOf<String, StateFlow<Pair<List<ForecastPoint>, List<Float?>>>>()

    fun forecastPoints(parameter: String): StateFlow<List<ForecastPoint>> =
        forecastPointsCache.getOrPut(parameter) {
            val repoParam = when (parameter) {
                "tds" -> "ec"
                else -> parameter
            }
            merge(flowOf(Unit), refreshTrigger).flatMapLatest { selectedRunId }.flatMapLatest { id ->
                ewsRepository.forecastPointsFlow(id, repoParam).map { list ->
                    when (parameter) {
                        "salinity" -> list.map { p -> p.copy(parameter = "salinity") }
                        "tds" -> list.map { p ->
                            ForecastPoint(
                                parameter = "tds",
                                date = p.date,
                                time = p.time,
                                predicted = conductivityToTds(p.predicted) ?: 0.0,
                                lower = conductivityToTds(p.lower) ?: 0.0,
                                upper = conductivityToTds(p.upper) ?: 0.0
                            )
                        }
                        else -> list
                    }
                }
            }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())
        }

    fun forecastPointsWithActuals(parameter: String): StateFlow<Pair<List<ForecastPoint>, List<Float?>>> =
        pointsWithActualsCache.getOrPut(parameter) {
            forecastPoints(parameter).flatMapLatest { points ->
                when {
                    points.isEmpty() -> flowOf(Pair(emptyList<ForecastPoint>(), emptyList<Float?>()))
                    else -> {
                        val range = forecastPointsToTimeRange(points)
                        if (range == null || range.second <= range.first) {
                            val expanded = expandForecastPointsTo30Min(points)
                            flowOf(Pair(expanded, List(expanded.size) { null }))
                        } else {
                            ewsRepository.sensorReadingsInRangeFlow(range.first, range.second).map { readings ->
                                val expandedPoints = expandForecastPointsTo30Min(points)
                                val closestPerSlot = actualsFromClosestReadingPer30MinSlot(readings, parameter)
                                val actuals = matchActualsToExpandedPoints(expandedPoints, closestPerSlot)
                                Pair(expandedPoints, actuals)
                            }
                        }
                    }
                }
            }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), Pair(emptyList(), emptyList()))
        }

    fun setSelectedRunId(id: String) {
        selectedRunId.value = id
    }

    private val _isRefreshing = MutableStateFlow(false)
    val isRefreshing: StateFlow<Boolean> = _isRefreshing.asStateFlow()

    fun refresh() {
        viewModelScope.launch {
            _isRefreshing.value = true
            refreshTrigger.emit(Unit)
            delay(500)
            _isRefreshing.value = false
        }
    }

    val parameters: List<String> = FORECAST_PARAMETERS
}
