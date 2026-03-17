package com.example.earlywarningsystem.ui.sensorhistory

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.earlywarningsystem.data.model.SensorReading
import com.example.earlywarningsystem.data.repository.EwsRepository
import com.example.earlywarningsystem.util.aggregateSensorReadingsByInterval
import com.example.earlywarningsystem.util.endOfDayLocal
import com.example.earlywarningsystem.util.formatDateOnly
import com.example.earlywarningsystem.util.startOfDayLocal
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.merge
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

sealed class SensorHistoryRange {
    data object Last24h : SensorHistoryRange()
    data class SelectDate(val dayStartEpoch: Long) : SensorHistoryRange()
    data class Custom(val fromEpoch: Long, val toEpoch: Long) : SensorHistoryRange()
}

class SensorHistoryViewModel(
    private val ewsRepository: EwsRepository
) : ViewModel() {

    private val rangeState = MutableStateFlow<SensorHistoryRange>(
        SensorHistoryRange.SelectDate(startOfDayLocal(System.currentTimeMillis()))
    )
    private val intervalState = MutableStateFlow(0) // 0 = All, 5, 30, 60 minutes

    val selectedIntervalMinutes: StateFlow<Int> = intervalState
    val selectedRange: StateFlow<SensorHistoryRange> = rangeState

    private val refreshTrigger = MutableSharedFlow<Unit>(replay = 0)

    val displayedReadings: StateFlow<List<SensorReading>> = merge(flowOf(Unit), refreshTrigger)
        .flatMapLatest { rangeState }
        .flatMapLatest { range ->
            val now = System.currentTimeMillis()
            val (start, end) = when (range) {
                is SensorHistoryRange.Last24h ->
                    Pair(now - 24 * 60 * 60 * 1000L, now)
                is SensorHistoryRange.SelectDate ->
                    startOfDayLocal(range.dayStartEpoch) to endOfDayLocal(range.dayStartEpoch)
                is SensorHistoryRange.Custom ->
                    range.fromEpoch to range.toEpoch
            }
            ewsRepository.sensorReadingsInRangeFlow(start, end).flatMapLatest { list ->
                intervalState.map { interval ->
                    if (interval <= 0) list else aggregateSensorReadingsByInterval(list, interval)
                }
            }
        }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    fun setIntervalMinutes(minutes: Int) {
        if (minutes in listOf(0, 5, 30, 60)) intervalState.value = minutes
    }

    fun setRangeLast24h() {
        rangeState.value = SensorHistoryRange.Last24h
    }

    fun setRangeSelectDate(dayStartEpoch: Long) {
        rangeState.value = SensorHistoryRange.SelectDate(dayStartEpoch)
    }

    fun setRangeCustom(fromEpoch: Long, toEpoch: Long) {
        rangeState.value = SensorHistoryRange.Custom(fromEpoch, toEpoch)
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

    val rangeDescription: StateFlow<String> = rangeState.map { range ->
        when (range) {
            is SensorHistoryRange.Last24h -> "Last 24 hours"
            is SensorHistoryRange.SelectDate -> formatDateOnly(range.dayStartEpoch)
            is SensorHistoryRange.Custom -> "${formatDateOnly(range.fromEpoch)} – ${formatDateOnly(range.toEpoch)}"
        }
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), formatDateOnly(System.currentTimeMillis()))
}
