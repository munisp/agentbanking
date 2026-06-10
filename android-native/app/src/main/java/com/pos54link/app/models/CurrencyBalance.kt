package com.pos54link.app.models

data class CurrencyBalance(
    val currency: String,
    val balance: Double,
    val currencySymbol: String,
    val countryFlag: String
)
