package com.project117.mobile.data.remote

import com.project117.mobile.data.local.preferences.SessionManager
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.Interceptor
import okhttp3.Response
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthInterceptor @Inject constructor(
    private val sessionManager: SessionManager
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val originalRequest = chain.request()
        val requestBuilder = originalRequest.newBuilder()

        // 1. Dynamic host rewrite if configured
        val dynamicBaseUrl = sessionManager.getServerUrl().toHttpUrlOrNull()
        if (dynamicBaseUrl != null) {
            val newUrl = originalRequest.url.newBuilder()
                .scheme(dynamicBaseUrl.scheme)
                .host(dynamicBaseUrl.host)
                .port(dynamicBaseUrl.port)
                .build()
            requestBuilder.url(newUrl)
        }

        // 2. Inject Authorization Token
        sessionManager.userSession.value?.accessToken?.let { token ->
            if (token.isNotBlank()) {
                requestBuilder.header("Authorization", "Bearer $token")
            }
        }

        // 3. Inject Device Token
        sessionManager.getDeviceToken()?.let { deviceToken ->
            if (deviceToken.isNotBlank()) {
                requestBuilder.header("X-Device-Token", deviceToken)
            }
        }

        requestBuilder.header("Accept", "application/json")
        requestBuilder.header("User-Agent", "Project117-Mobile-Client/1.0.0")

        return chain.proceed(requestBuilder.build())
    }
}
