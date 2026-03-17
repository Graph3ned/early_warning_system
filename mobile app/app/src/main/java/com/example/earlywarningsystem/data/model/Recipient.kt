package com.example.earlywarningsystem.data.model

data class Recipient(
    val id: String,
    val name: String,
    val phone: String,
    val active: Boolean = true
)
