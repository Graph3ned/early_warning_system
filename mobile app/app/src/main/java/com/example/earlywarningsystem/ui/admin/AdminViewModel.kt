package com.example.earlywarningsystem.ui.admin

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.earlywarningsystem.data.model.Recipient
import com.example.earlywarningsystem.data.repository.EwsRepository
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

class AdminViewModel(
    private val ewsRepository: EwsRepository
) : ViewModel() {

    val recipients: StateFlow<List<Recipient>> = ewsRepository.recipientsFlow()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    fun addRecipient(name: String, phone: String, active: Boolean = true, onResult: (Result<Unit>) -> Unit) {
        viewModelScope.launch {
            onResult(ewsRepository.addRecipient(name, phone, active))
        }
    }

    fun updateRecipient(id: String, name: String, phone: String, active: Boolean, onResult: (Result<Unit>) -> Unit) {
        viewModelScope.launch {
            onResult(ewsRepository.updateRecipient(id, name, phone, active))
        }
    }

    fun deleteRecipient(id: String, onResult: (Result<Unit>) -> Unit) {
        viewModelScope.launch {
            onResult(ewsRepository.deleteRecipient(id))
        }
    }
}
