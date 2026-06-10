package com.pos54link.app.di

import android.content.Context
import com.pos54link.app.BuildConfig
import com.pos54link.app.data.api.*
import com.pos54link.app.data.api.interceptors.AuthInterceptor
import com.pos54link.app.offline.OfflineDatabase
import com.pos54link.app.offline.OfflineManager
import com.pos54link.app.printer.ReceiptPrinterService
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {

    @Provides
    @Singleton
    fun provideOkHttpClient(authInterceptor: AuthInterceptor): OkHttpClient {
        return OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .addInterceptor(authInterceptor)
            .apply {
                if (BuildConfig.DEBUG) {
                    addInterceptor(
                        HttpLoggingInterceptor().apply {
                            level = HttpLoggingInterceptor.Level.BODY
                        }
                    )
                }
            }
            .build()
    }

    @Provides
    @Singleton
    fun provideRetrofit(okHttpClient: OkHttpClient): Retrofit {
        return Retrofit.Builder()
            .baseUrl(BuildConfig.API_BASE_URL)
            .client(okHttpClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
    }

    @Provides
    @Singleton
    fun provideTransactionService(retrofit: Retrofit): TransactionService {
        return retrofit.create(TransactionService::class.java)
    }

    @Provides
    @Singleton
    fun providePosService(retrofit: Retrofit): PosService {
        return retrofit.create(PosService::class.java)
    }

    @Provides
    @Singleton
    fun provideAuthService(retrofit: Retrofit): AuthService {
        return retrofit.create(AuthService::class.java)
    }

    @Provides
    @Singleton
    fun provideOfflineDatabase(@ApplicationContext context: Context): OfflineDatabase {
        return OfflineDatabase.getDatabase(context)
    }

    @Provides
    @Singleton
    fun provideOfflineManager(
        @ApplicationContext context: Context,
        database: OfflineDatabase
    ): OfflineManager {
        return OfflineManager(context, database)
    }

    @Provides
    @Singleton
    fun provideReceiptPrinterService(@ApplicationContext context: Context): ReceiptPrinterService {
        return ReceiptPrinterService(context)
    }
}
