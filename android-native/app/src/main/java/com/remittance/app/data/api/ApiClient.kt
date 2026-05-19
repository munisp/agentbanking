package com.pos54link.app.data.api

import com.google.gson.Gson
import com.google.gson.GsonBuilder
import com.pos54link.app.BuildConfig
import com.pos54link.app.data.api.interceptors.AuthInterceptor
import com.pos54link.app.data.api.interceptors.ErrorInterceptor
import com.pos54link.app.data.api.interceptors.LoggingInterceptor
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ApiClient @Inject constructor(
    private val authInterceptor: AuthInterceptor,
    private val errorInterceptor: ErrorInterceptor
) {
    
    private val gson: Gson = GsonBuilder()
        .setLenient()
        .setDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'")
        .create()
    
    private val okHttpClient: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .addInterceptor(authInterceptor)
            .addInterceptor(errorInterceptor)
            .apply {
                if (BuildConfig.DEBUG) {
                    addInterceptor(LoggingInterceptor())
                    addInterceptor(
                        HttpLoggingInterceptor().apply {
                            level = HttpLoggingInterceptor.Level.BODY
                        }
                    )
                }
            }
            .build()
    }
    
    private val retrofit: Retrofit by lazy {
        Retrofit.Builder()
            .baseUrl(BuildConfig.BASE_URL)
            .client(okHttpClient)
            .addConverterFactory(GsonConverterFactory.create(gson))
            .build()
    }
    
    // API Services
    val authService: AuthService by lazy {
        retrofit.create(AuthService::class.java)
    }
    
    val walletService: WalletService by lazy {
        retrofit.create(WalletService::class.java)
    }
    
    val transferService: TransferService by lazy {
        retrofit.create(TransferService::class.java)
    }
    
    val beneficiaryService: BeneficiaryService by lazy {
        retrofit.create(BeneficiaryService::class.java)
    }
    
    val notificationService: NotificationService by lazy {
        retrofit.create(NotificationService::class.java)
    }
    
    val profileService: ProfileService by lazy {
        retrofit.create(ProfileService::class.java)
    }
    
    val paymentService: PaymentService by lazy {
        retrofit.create(PaymentService::class.java)
    }
}
