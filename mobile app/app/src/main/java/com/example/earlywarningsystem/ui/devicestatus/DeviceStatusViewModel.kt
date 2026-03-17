package com.example.earlywarningsystem.ui.devicestatus

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.earlywarningsystem.data.model.DeviceStatus
import com.example.earlywarningsystem.data.repository.EwsRepository
import com.example.earlywarningsystem.util.getDeviceAlerts
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn

class DeviceStatusViewModel(
    private val ewsRepository: EwsRepository
) : ViewModel() {

    val deviceStatus: StateFlow<DeviceStatus?> = ewsRepository.deviceStatusFlow()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), null)

    val deviceAlerts: StateFlow<List<String>> = ewsRepository.deviceStatusFlow()
        .map { status -> getDeviceAlerts(status) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())
}
