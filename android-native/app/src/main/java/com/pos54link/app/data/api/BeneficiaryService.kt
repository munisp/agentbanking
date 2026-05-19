package com.pos54link.app.data.api

import com.pos54link.app.models.*
import retrofit2.Response
import retrofit2.http.*

interface BeneficiaryService {
    
    @GET("beneficiaries")
    suspend fun getBeneficiaries(): Response<BeneficiariesResponse>
    
    @POST("beneficiaries")
    suspend fun addBeneficiary(@Body request: AddBeneficiaryRequest): Response<BeneficiaryResponse>
    
    @PUT("beneficiaries/{id}")
    suspend fun updateBeneficiary(
        @Path("id") beneficiaryId: String,
        @Body request: UpdateBeneficiaryRequest
    ): Response<BeneficiaryResponse>
    
    @DELETE("beneficiaries/{id}")
    suspend fun deleteBeneficiary(@Path("id") beneficiaryId: String): Response<MessageResponse>
    
    @POST("beneficiaries/verify")
    suspend fun verifyBeneficiary(@Body request: VerifyBeneficiaryRequest): Response<VerifyBeneficiaryResponse>
}

interface NotificationService {
    
    @POST("notifications/register-device")
    suspend fun registerDevice(@Body request: RegisterDeviceRequest): Response<MessageResponse>
    
    @GET("notifications")
    suspend fun getNotifications(
        @Query("page") page: Int = 1,
        @Query("limit") limit: Int = 20,
        @Query("unreadOnly") unreadOnly: Boolean = false
    ): Response<NotificationsResponse>
    
    @PUT("notifications/{id}/read")
    suspend fun markAsRead(@Path("id") notificationId: String): Response<MessageResponse>
    
    @PUT("notifications/read-all")
    suspend fun markAllAsRead(): Response<MessageResponse>
    
    @GET("notifications/preferences")
    suspend fun getPreferences(): Response<NotificationPreferencesResponse>
    
    @PUT("notifications/preferences")
    suspend fun updatePreferences(@Body request: UpdatePreferencesRequest): Response<MessageResponse>
}

interface ProfileService {
    
    @GET("profile")
    suspend fun getProfile(): Response<ProfileResponse>
    
    @PUT("profile/update")
    suspend fun updateProfile(@Body request: UpdateProfileRequest): Response<ProfileResponse>
    
    @POST("profile/change-password")
    suspend fun changePassword(@Body request: ChangePasswordRequest): Response<MessageResponse>
    
    @POST("profile/upload-document")
    suspend fun uploadDocument(@Body request: UploadDocumentRequest): Response<DocumentResponse>
    
    @GET("profile/documents")
    suspend fun getDocuments(): Response<DocumentsResponse>
    
    @POST("profile/enable-2fa")
    suspend fun enable2FA(): Response<Enable2FAResponse>
    
    @POST("profile/verify-2fa")
    suspend fun verify2FA(@Body request: Verify2FARequest): Response<MessageResponse>
    
    @POST("profile/disable-2fa")
    suspend fun disable2FA(@Body request: Disable2FARequest): Response<MessageResponse>
}

interface PaymentService {
    
    // PAPSS
    @POST("payments/papss/transfer")
    suspend fun papssTransfer(@Body request: PAPSSTransferRequest): Response<PaymentResponse>
    
    // CIPS
    @POST("payments/cips/transfer")
    suspend fun cipsTransfer(@Body request: CIPSTransferRequest): Response<PaymentResponse>
    
    // PIX
    @POST("payments/pix/transfer")
    suspend fun pixTransfer(@Body request: PIXTransferRequest): Response<PaymentResponse>
    
    @POST("payments/pix/qr-code")
    suspend fun pixGenerateQR(@Body request: PIXQRRequest): Response<PIXQRResponse>
    
    // UPI
    @POST("payments/upi/transfer")
    suspend fun upiTransfer(@Body request: UPITransferRequest): Response<PaymentResponse>
    
    @POST("payments/upi/verify-vpa")
    suspend fun upiVerifyVPA(@Body request: UPIVerifyRequest): Response<UPIVerifyResponse>
    
    // Mojaloop
    @POST("payments/mojaloop/transfer")
    suspend fun mojaloopTransfer(@Body request: MojaloopTransferRequest): Response<PaymentResponse>
    
    // NIBSS
    @POST("payments/nibss/transfer")
    suspend fun nibssTransfer(@Body request: NIBSSTransferRequest): Response<PaymentResponse>
    
    @POST("payments/nibss/ussd")
    suspend fun nibssUSSD(@Body request: NIBSSUSSDRequest): Response<NIBSSUSSDResponse>
}

// Beneficiary Models
data class AddBeneficiaryRequest(
    val name: String,
    val accountNumber: String,
    val bankName: String,
    val bankCode: String,
    val country: String,
    val currency: String,
    val email: String? = null,
    val phoneNumber: String? = null
)

data class UpdateBeneficiaryRequest(
    val name: String?,
    val email: String?,
    val phoneNumber: String?
)

data class VerifyBeneficiaryRequest(
    val accountNumber: String,
    val bankCode: String,
    val country: String
)

data class BeneficiariesResponse(
    val success: Boolean,
    val data: List<Beneficiary>
)

data class Beneficiary(
    val id: String,
    val name: String,
    val accountNumber: String,
    val bankName: String,
    val bankCode: String,
    val country: String,
    val currency: String,
    val email: String? = null,
    val phoneNumber: String? = null,
    val verified: Boolean,
    val createdAt: String
)

data class BeneficiaryResponse(
    val success: Boolean,
    val data: Beneficiary
)

data class VerifyBeneficiaryResponse(
    val success: Boolean,
    val data: VerifyBeneficiaryData
)

data class VerifyBeneficiaryData(
    val accountName: String,
    val accountNumber: String,
    val bankName: String,
    val verified: Boolean
)

// Notification Models
data class RegisterDeviceRequest(
    val deviceToken: String,
    val deviceType: String, // ios, android
    val deviceName: String
)

data class NotificationsResponse(
    val success: Boolean,
    val data: NotificationsData
)

data class NotificationsData(
    val notifications: List<Notification>,
    val unreadCount: Int,
    val pagination: Pagination
)

data class Notification(
    val id: String,
    val type: String,
    val title: String,
    val message: String,
    val data: Map<String, Any>?,
    val read: Boolean,
    val createdAt: String
)

data class NotificationPreferencesResponse(
    val success: Boolean,
    val data: NotificationPreferences
)

data class NotificationPreferences(
    val emailNotifications: Boolean,
    val pushNotifications: Boolean,
    val smsNotifications: Boolean,
    val transactionAlerts: Boolean,
    val securityAlerts: Boolean,
    val promotionalAlerts: Boolean
)

data class UpdatePreferencesRequest(
    val emailNotifications: Boolean?,
    val pushNotifications: Boolean?,
    val smsNotifications: Boolean?,
    val transactionAlerts: Boolean?,
    val securityAlerts: Boolean?,
    val promotionalAlerts: Boolean?
)

// Profile Models
data class ProfileResponse(
    val success: Boolean,
    val data: UserProfile
)

data class UserProfile(
    val id: String,
    val email: String,
    val firstName: String,
    val lastName: String,
    val phoneNumber: String,
    val country: String,
    val dateOfBirth: String? = null,
    val address: Address? = null,
    val kycStatus: String,
    val twoFactorEnabled: Boolean,
    val emailVerified: Boolean,
    val phoneVerified: Boolean,
    val createdAt: String
)

data class Address(
    val street: String,
    val city: String,
    val state: String,
    val postalCode: String,
    val country: String
)

data class UpdateProfileRequest(
    val firstName: String?,
    val lastName: String?,
    val phoneNumber: String?,
    val dateOfBirth: String?,
    val address: Address?
)

data class ChangePasswordRequest(
    val currentPassword: String,
    val newPassword: String
)

data class UploadDocumentRequest(
    val documentType: String,
    val documentData: String // Base64 encoded
)

data class DocumentResponse(
    val success: Boolean,
    val data: Document
)

data class Document(
    val id: String,
    val type: String,
    val status: String,
    val uploadedAt: String
)

data class DocumentsResponse(
    val success: Boolean,
    val data: List<Document>
)

data class Enable2FAResponse(
    val success: Boolean,
    val data: Enable2FAData
)

data class Enable2FAData(
    val qrCode: String,
    val secret: String
)

data class Verify2FARequest(
    val code: String
)

data class Disable2FARequest(
    val code: String,
    val password: String
)

// Payment System Models
data class PAPSSTransferRequest(
    val beneficiaryId: String,
    val amount: Double,
    val currency: String,
    val description: String?
)

data class CIPSTransferRequest(
    val beneficiaryId: String,
    val amount: Double,
    val description: String?
)

data class PIXTransferRequest(
    val pixKey: String,
    val amount: Double,
    val description: String?
)

data class PIXQRRequest(
    val amount: Double,
    val description: String?
)

data class PIXQRResponse(
    val success: Boolean,
    val data: PIXQRData
)

data class PIXQRData(
    val qrCode: String,
    val qrCodeImage: String,
    val expiresAt: String
)

data class UPITransferRequest(
    val vpa: String,
    val amount: Double,
    val description: String?
)

data class UPIVerifyRequest(
    val vpa: String
)

data class UPIVerifyResponse(
    val success: Boolean,
    val data: UPIVerifyData
)

data class UPIVerifyData(
    val vpa: String,
    val name: String,
    val verified: Boolean
)

data class MojaloopTransferRequest(
    val beneficiaryId: String,
    val amount: Double,
    val currency: String,
    val description: String?
)

data class NIBSSTransferRequest(
    val beneficiaryId: String,
    val amount: Double,
    val description: String?
)

data class NIBSSUSSDRequest(
    val phoneNumber: String,
    val amount: Double
)

data class NIBSSUSSDResponse(
    val success: Boolean,
    val data: NIBSSUSSDData
)

data class NIBSSUSSDData(
    val ussdCode: String,
    val instructions: String
)

data class PaymentResponse(
    val success: Boolean,
    val data: PaymentData
)

data class PaymentData(
    val transactionId: String,
    val status: String,
    val reference: String,
    val estimatedCompletionTime: String
)
