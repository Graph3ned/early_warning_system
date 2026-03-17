package com.example.earlywarningsystem.ui.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.earlywarningsystem.data.model.UserRole
import com.example.earlywarningsystem.data.repository.AuthRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch

data class AuthUiState(
    val isLoggedIn: Boolean = false,
    val userRole: UserRole = UserRole.VIEWER,
    val isLoading: Boolean = false,
    val error: String? = null
)

data class AccountState(
    val email: String = "",
    val isLoading: Boolean = false,
    val message: String? = null,
    val error: String? = null
)

class AuthViewModel(
    private val authRepository: AuthRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(AuthUiState(isLoggedIn = authRepository.isLoggedIn()))
    val uiState: StateFlow<AuthUiState> = _uiState.asStateFlow()

    // For this app, treat any logged-in account as ADMIN, and anonymous users as VIEWER.
    // This avoids needing a separate "role" value in Firebase for your thesis demo.
    val userRole: StateFlow<UserRole> = authRepository.currentUserIdFlow()
        .map { uid -> if (uid != null) UserRole.ADMIN else UserRole.VIEWER }
        .stateIn(
            viewModelScope,
            SharingStarted.WhileSubscribed(5000),
            if (authRepository.isLoggedIn()) UserRole.ADMIN else UserRole.VIEWER
        )

    private val _accountState = MutableStateFlow(AccountState())
    val accountState: StateFlow<AccountState> = _accountState.asStateFlow()

    init {
        viewModelScope.launch {
            if (authRepository.isLoggedIn()) {
                _uiState.value = _uiState.value.copy(
                    isLoggedIn = true,
                    userRole = authRepository.getCurrentUserRole()
                )
            }
        }
    }

    fun signIn(email: String, password: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            authRepository.signIn(email, password)
                .onSuccess {
                    _uiState.value = _uiState.value.copy(
                        isLoggedIn = true,
                        isLoading = false,
                        userRole = authRepository.getCurrentUserRole(),
                        error = null
                    )
                }
                .onFailure {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = it.message ?: "Sign in failed"
                    )
                }
        }
    }

    fun register(email: String, password: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            authRepository.register(email, password)
                .onSuccess {
                    _uiState.value = _uiState.value.copy(
                        isLoggedIn = true,
                        isLoading = false,
                        userRole = authRepository.getCurrentUserRole(),
                        error = null
                    )
                }
                .onFailure {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = it.message ?: "Registration failed"
                    )
                }
        }
    }

    fun signOut() {
        authRepository.signOut()
        _uiState.value = AuthUiState(isLoggedIn = false, userRole = UserRole.VIEWER)
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    fun loadProfile() {
        _accountState.value = _accountState.value.copy(
            email = authRepository.getCurrentUserEmail().orEmpty(),
            error = null,
            message = null
        )
    }

    fun updateEmail(currentPassword: String, newEmail: String) {
        viewModelScope.launch {
            val email = authRepository.getCurrentUserEmail() ?: ""
            if (email.isBlank()) {
                _accountState.value = _accountState.value.copy(error = "No email to update")
                return@launch
            }
            _accountState.value = _accountState.value.copy(isLoading = true, error = null, message = null)
            authRepository.reauthenticate(email, currentPassword)
                .onFailure {
                    _accountState.value = _accountState.value.copy(
                        isLoading = false,
                        error = it.message ?: "Current password is incorrect"
                    )
                    return@launch
                }
            authRepository.updateEmail(newEmail)
                .onSuccess {
                    _accountState.value = _accountState.value.copy(
                        isLoading = false,
                        email = newEmail,
                        message = "Email updated"
                    )
                }
                .onFailure {
                    _accountState.value = _accountState.value.copy(
                        isLoading = false,
                        error = it.message ?: "Failed to update email"
                    )
                }
        }
    }

    fun changePassword(currentPassword: String, newPassword: String) {
        viewModelScope.launch {
            val email = authRepository.getCurrentUserEmail() ?: ""
            if (email.isBlank()) {
                _accountState.value = _accountState.value.copy(error = "Cannot verify identity")
                return@launch
            }
            _accountState.value = _accountState.value.copy(isLoading = true, error = null, message = null)
            authRepository.reauthenticate(email, currentPassword)
                .onFailure {
                    _accountState.value = _accountState.value.copy(
                        isLoading = false,
                        error = it.message ?: "Current password is incorrect"
                    )
                    return@launch
                }
            authRepository.updatePassword(newPassword)
                .onSuccess {
                    _accountState.value = _accountState.value.copy(
                        isLoading = false,
                        message = "Password updated"
                    )
                }
                .onFailure {
                    _accountState.value = _accountState.value.copy(
                        isLoading = false,
                        error = it.message ?: "Failed to update password"
                    )
                }
        }
    }

    fun clearAccountMessage() {
        _accountState.value = _accountState.value.copy(message = null, error = null)
    }
}
