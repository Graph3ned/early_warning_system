package com.example.earlywarningsystem.ui.metrics

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.earlywarningsystem.data.model.ForecastMetrics
import com.example.earlywarningsystem.data.repository.EwsRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.flow.stateIn

class MetricsViewModel(
    private val ewsRepository: EwsRepository
) : ViewModel() {

    val latestRunId: StateFlow<String> = ewsRepository.forecastStatusFlow()
        .map { it?.latestRunId ?: "" }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), "")

    val runIds: StateFlow<List<String>> = ewsRepository.forecastRunIdsFlow()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    val selectedRunId = MutableStateFlow("")

    init {
        latestRunId.onEach { id ->
            if (id.isNotBlank() && selectedRunId.value.isEmpty()) {
                selectedRunId.value = id
            }
        }.launchIn(viewModelScope)
    }

    fun setSelectedRunId(id: String) {
        selectedRunId.value = id
    }

    val metrics: StateFlow<List<ForecastMetrics>> =
        selectedRunId.flatMapLatest { id ->
            ewsRepository.forecastMetricsFlow(id)
        }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())
}
