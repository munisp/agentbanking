package com.pos54link.app.data.api.interceptors

import com.pos54link.app.security.TokenManager
import kotlinx.coroutines.runBlocking
import okhttp3.Interceptor
import okhttp3.Response
import timber.log.Timber
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthInterceptor @Inject constructor(
    private val tokenManager: TokenManager
) : Interceptor {
    
    override fun intercept(chain: Interceptor.Chain): Response {
        val originalRequest = chain.request()
        
        // Skip authentication for auth endpoints
        if (originalRequest.url.encodedPath.contains("/auth/")) {
            return chain.proceed(originalRequest)
        }
        
        // Add authentication token
        val token = runBlocking { tokenManager.getAccessToken() }
        
        val authenticatedRequest = if (token != null) {
            originalRequest.newBuilder()
                .header("Authorization", "Bearer $token")
                .header("Accept", "application/json")
                .header("Content-Type", "application/json")
                .build()
        } else {
            originalRequest.newBuilder()
                .header("Accept", "application/json")
                .header("Content-Type", "application/json")
                .build()
        }
        
        var response = chain.proceed(authenticatedRequest)
        
        // Handle token expiration
        if (response.code == 401 && token != null) {
            response.close()
            
            // Attempt to refresh token
            val refreshed = runBlocking {
                try {
                    tokenManager.refreshToken()
                    true
                } catch (e: Exception) {
                    Timber.e(e, "Failed to refresh token")
                    false
                }
            }
            
            if (refreshed) {
                val newToken = runBlocking { tokenManager.getAccessToken() }
                val retryRequest = originalRequest.newBuilder()
                    .header("Authorization", "Bearer $newToken")
                    .header("Accept", "application/json")
                    .header("Content-Type", "application/json")
                    .build()
                
                response = chain.proceed(retryRequest)
            }
        }
        
        return response
    }
}

@Singleton
class ErrorInterceptor @Inject constructor() : Interceptor {
    
    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        val response = chain.proceed(request)
        
        when (response.code) {
            400 -> Timber.w("Bad Request: ${request.url}")
            401 -> Timber.w("Unauthorized: ${request.url}")
            403 -> Timber.w("Forbidden: ${request.url}")
            404 -> Timber.w("Not Found: ${request.url}")
            422 -> Timber.w("Validation Error: ${request.url}")
            429 -> Timber.w("Rate Limit Exceeded: ${request.url}")
            in 500..599 -> Timber.e("Server Error ${response.code}: ${request.url}")
        }
        
        return response
    }
}

class LoggingInterceptor : Interceptor {
    
    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        
        Timber.d("📤 Request: ${request.method} ${request.url}")
        Timber.d("Headers: ${request.headers}")
        
        val startTime = System.currentTimeMillis()
        val response = chain.proceed(request)
        val duration = System.currentTimeMillis() - startTime
        
        Timber.d("📥 Response: ${response.code} ${request.url} (${duration}ms)")
        
        return response
    }
}
