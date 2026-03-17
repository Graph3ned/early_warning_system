package com.example.earlywarningsystem

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.example.earlywarningsystem.data.repository.AuthRepository
import com.example.earlywarningsystem.data.repository.EwsRepository
import com.example.earlywarningsystem.di.EwsViewModelFactory
import com.example.earlywarningsystem.ui.navigation.EwsApp
import com.example.earlywarningsystem.ui.theme.EarlyWarningSystemTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val authRepository = AuthRepository()
        val ewsRepository = EwsRepository()
        val viewModelFactory = EwsViewModelFactory(authRepository, ewsRepository)
        setContent {
            EarlyWarningSystemTheme {
                EwsApp(viewModelFactory = viewModelFactory)
            }
        }
    }
}
