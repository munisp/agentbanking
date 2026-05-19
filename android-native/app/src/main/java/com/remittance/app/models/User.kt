package com.pos54link.app.models

data class User(
    val id: String,
    val email: String,
    val firstName: String,
    val lastName: String,
    val phoneNumber: String,
    val country: String,
    val kycStatus: String,
    val emailVerified: Boolean,
    val phoneVerified: Boolean,
    val twoFactorEnabled: Boolean,
    val createdAt: String
) {
    val fullName: String
        get() = "$firstName $lastName"
}
