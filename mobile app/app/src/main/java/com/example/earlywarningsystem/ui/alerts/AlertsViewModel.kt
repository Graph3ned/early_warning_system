package com.example.earlywarningsystem.ui.alerts

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.earlywarningsystem.data.model.ForecastTrendLatest
import com.example.earlywarningsystem.data.repository.EwsRepository
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.merge
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

class AlertsViewModel(
    private val ewsRepository: EwsRepository
) : ViewModel() {

    private val refreshTrigger = MutableSharedFlow<Unit>(replay = 0)

    val forecastTrend: StateFlow<ForecastTrendLatest?> = merge(flowOf(Unit), refreshTrigger)
        .flatMapLatest { ewsRepository.forecastTrendLatestFlow() }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), null)

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
}
