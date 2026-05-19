package com.pos54link.app.data.api

import com.pos54link.app.models.*
import retrofit2.Response
import retrofit2.http.*

interface AuthService {
    
    @POST("auth/login")
    suspend fun login(@Body request: LoginRequest): Response<AuthResponse>
    
    @POST("auth/register")
    suspend fun register(@Body request: RegisterRequest): Response<AuthResponse>
    
    @POST("auth/refresh")
    suspend fun refreshToken(@Body request: RefreshTokenRequest): Response<AuthResponse>
    
    @POST("auth/logout")
    suspend fun logout(): Response<Unit>
    
    @POST("auth/biometric/register")
    suspend fun registerBiometric(@Body request: BiometricRegisterRequest): Response<BiometricResponse>
    
    @POST("auth/biometric/verify")
    suspend fun verifyBiometric(@Body request: BiometricVerifyRequest): Response<AuthResponse>
    
    @POST("auth/forgot-password")
    suspend fun forgotPassword(@Body request: ForgotPasswordRequest): Response<MessageResponse>
    
    @POST("auth/reset-password")
    suspend fun resetPassword(@Body request: ResetPasswordRequest): Response<MessageResponse>
    
    @POST("auth/verify-email")
    suspend fun verifyEmail(@Body request: VerifyEmailRequest): Response<MessageResponse>
    
    @POST("auth/resend-verification")
    suspend fun resendVerification(@Body request: ResendVerificationRequest): Response<MessageResponse>
}

// Request Models
data class LoginRequest(
    val email: String,
    val password: String,
    val deviceId: String? = null,
    val deviceName: String? = null
)

data class RegisterRequest(
    val email: String,
    val password: String,
    val firstName: String,
    val lastName: String,
    val phoneNumber: String,
    val country: String,
    val deviceId: String? = null,
    val deviceName: String? = null
)

data class RefreshTokenRequest(
    val refreshToken: String
)

data class BiometricRegisterRequest(
    val publicKey: String,
    val deviceId: String
)

data class BiometricVerifyRequest(
    val signature: String,
    val challenge: String,
    val deviceId: String
)

data class ForgotPasswordRequest(
    val email: String
)

data class ResetPasswordRequest(
    val email: String,
    val token: String,
    val newPassword: String
)

data class VerifyEmailRequest(
    val email: String,
    val token: String
)

data class ResendVerificationRequest(
    val email: String
)

// Response Models
data class AuthResponse(
    val success: Boolean,
    val message: String? = null,
    val data: AuthData
)

data class AuthData(
    val user: User,
    val accessToken: String,
    val refreshToken: String,
    val expiresIn: Long
)

data class BiometricResponse(
    val success: Boolean,
    val message: String? = null,
    val data: BiometricData
)

data class BiometricData(
    val challenge: String,
    val publicKeyId: String
)

data class MessageResponse(
    val success: Boolean,
    val message: String
)
