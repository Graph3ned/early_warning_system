package com.example.earlywarningsystem.di

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import com.example.earlywarningsystem.data.repository.AuthRepository
import com.example.earlywarningsystem.data.repository.EwsRepository
import com.example.earlywarningsystem.ui.admin.AdminViewModel
import com.example.earlywarningsystem.ui.alerts.AlertsViewModel
import com.example.earlywarningsystem.ui.auth.AuthViewModel
import com.example.earlywarningsystem.ui.dashboard.DashboardViewModel
import com.example.earlywarningsystem.ui.devicestatus.DeviceStatusViewModel
import com.example.earlywarningsystem.ui.forecasts.ForecastsViewModel
import com.example.earlywarningsystem.ui.sensorhistory.SensorHistoryViewModel
import com.example.earlywarningsystem.ui.metrics.MetricsViewModel

class EwsViewModelFactory(
    private val authRepository: AuthRepository,
    private val ewsRepository: EwsRepository
) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        return when {
            modelClass.isAssignableFrom(AuthViewModel::class.java) ->
                AuthViewModel(authRepository) as T
            modelClass.isAssignableFrom(DashboardViewModel::class.java) ->
                DashboardViewModel(ewsRepository) as T
            modelClass.isAssignableFrom(AlertsViewModel::class.java) ->
                AlertsViewModel(ewsRepository) as T
            modelClass.isAssignableFrom(ForecastsViewModel::class.java) ->
                ForecastsViewModel(ewsRepository) as T
            modelClass.isAssignableFrom(MetricsViewModel::class.java) ->
                MetricsViewModel(ewsRepository) as T
            modelClass.isAssignableFrom(AdminViewModel::class.java) ->
                AdminViewModel(ewsRepository) as T
            modelClass.isAssignableFrom(DeviceStatusViewModel::class.java) ->
                DeviceStatusViewModel(ewsRepository) as T
            modelClass.isAssignableFrom(SensorHistoryViewModel::class.java) ->
                SensorHistoryViewModel(ewsRepository) as T
            else -> throw IllegalArgumentException("Unknown ViewModel: ${modelClass.name}")
        }
    }
}
