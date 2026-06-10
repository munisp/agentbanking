package com.pos54link.app.models

data class Transaction(
    val id: String,
    val type: String,
    val amount: Double,
    val currency: String,
    val status: String,
    val recipientName: String?,
    val reference: String,
    val narration: String?,
    val fee: Double,
    val commission: Double,
    val createdAt: String
)
