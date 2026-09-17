package com.project117.mobile.data.local.preferences

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.project117.mobile.BuildConfig
import com.project117.mobile.domain.model.AppMode
import com.project117.mobile.domain.model.UserRole
import com.project117.mobile.domain.model.UserSession
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import timber.log.Timber
import java.util.Locale
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Outcome of validating a backend URL against the rules of an [AppMode].
 *
 * A dedicated type rather than a Boolean so the UI can show the actual reason a
 * URL was refused instead of a generic "invalid URL" message.
 */
sealed class UrlValidationResult {
    object Valid : UrlValidationResult()
    data class Invalid(val reason: String) : UrlValidationResult()
}

@Singleton
class SessionManager @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private val prefs: SharedPreferences by lazy {
        try {
            val masterKey = MasterKey.Builder(context)
                .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                .build()

            EncryptedSharedPreferences.create(
                context,
                "project117_secure_prefs",
                masterKey,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            )
        } catch (e: Exception) {
            Timber.e(e, "Failed to initialize EncryptedSharedPreferences, falling back to standard private prefs")
            context.getSharedPreferences("project117_fallback_prefs", Context.MODE_PRIVATE)
        }
    }

    private val _appMode = MutableStateFlow(getSavedAppMode())
    val appMode: StateFlow<AppMode> = _appMode.asStateFlow()

    private val _userSession = MutableStateFlow(getSavedSession())
    val userSession: StateFlow<UserSession?> = _userSession.asStateFlow()

    private val _serverUrl = MutableStateFlow(resolveServerUrl(_appMode.value))
    val serverUrl: StateFlow<String> = _serverUrl.asStateFlow()

    // ─── Backend URL ──────────────────────────────────────────────────────────

    fun getServerUrl(): String = _serverUrl.value

    /**
     * Persists [url] as the *custom* URL for the currently selected environment.
     *
     * The validation outcome is returned and an invalid URL is never written to
     * prefs, so the app can always hand Retrofit a base URL it accepts.
     */
    fun setServerUrl(url: String): UrlValidationResult {
        val validation = validateServerUrl(_appMode.value, url)
        if (validation is UrlValidationResult.Invalid) return validation
        // DEMO never dials out, so there is nothing worth remembering for it.
        if (_appMode.value == AppMode.DEMO) return UrlValidationResult.Valid

        val sanitized = sanitizeServerUrl(url)
        if (sanitized == defaultServerUrl(_appMode.value)) {
            // Testing or saving the environment default must not pin it, or a
            // later change to the BuildConfig default would never be picked up.
            prefs.edit().remove(serverUrlKey(_appMode.value)).apply()
        } else {
            prefs.edit().putString(serverUrlKey(_appMode.value), sanitized).apply()
        }
        _serverUrl.value = sanitized
        return UrlValidationResult.Valid
    }

    /**
     * Forgets the custom URL for the current environment so the BuildConfig
     * default applies again. Only the active environment is affected — a LAN
     * address typed for another environment is deliberately left alone.
     */
    fun clearServerUrlOverride() {
        prefs.edit().remove(serverUrlKey(_appMode.value)).apply()
        _serverUrl.value = defaultServerUrl(_appMode.value)
    }

    fun setAppMode(mode: AppMode) {
        prefs.edit().putString(KEY_APP_MODE, mode.name).apply()
        _appMode.value = mode
        // Follow the environment's own resolved URL. Because each environment
        // keeps its own override, switching LOCAL → PRODUCTION → LOCAL restores
        // the LAN address that was typed under LOCAL instead of losing it.
        _serverUrl.value = resolveServerUrl(mode)
    }

    private fun getSavedAppMode(): AppMode {
        val raw = prefs.getString(KEY_APP_MODE, AppMode.DEMO.name)?.uppercase(Locale.ROOT)
        return when (raw) {
            // "LIVE" predates the LOCAL/PRODUCTION split. Map it to a live
            // environment rather than letting an unknown value fall through to
            // DEMO — an upgrade must never silently demote a live install.
            "LIVE" -> AppMode.LOCAL
            AppMode.LOCAL.name -> AppMode.LOCAL
            AppMode.PRODUCTION.name -> AppMode.PRODUCTION
            else -> AppMode.DEMO
        }
    }

    /**
     * The URL an environment starts from.
     *
     * LOCAL and PRODUCTION come from the BuildConfig fields, which a developer
     * overrides with -PP117_LOCAL_BACKEND_URL / -PP117_PRODUCTION_BACKEND_URL or
     * a gitignored local.properties — never by editing a tracked source file.
     *
     * DEMO makes no network calls at all, but Retrofit still needs a
     * syntactically valid base URL at construction time, so the LOCAL default is
     * used as an inert placeholder there.
     */
    fun defaultServerUrl(mode: AppMode): String = sanitizeServerUrl(
        when (mode) {
            AppMode.DEMO -> BuildConfig.LOCAL_BACKEND_URL
            AppMode.LOCAL -> BuildConfig.LOCAL_BACKEND_URL
            AppMode.PRODUCTION -> BuildConfig.PRODUCTION_BACKEND_URL
        }
    )

    private fun resolveServerUrl(mode: AppMode): String {
        val custom = prefs.getString(serverUrlKey(mode), null)
        if (custom.isNullOrBlank()) return defaultServerUrl(mode)
        // A persisted URL can predate a validation rule or a changed default.
        // Never hand Retrofit a value we would reject today.
        return if (validateServerUrl(mode, custom) is UrlValidationResult.Valid) {
            sanitizeServerUrl(custom)
        } else {
            defaultServerUrl(mode)
        }
    }

    private fun serverUrlKey(mode: AppMode) = "$KEY_SERVER_URL_PREFIX${mode.name.lowercase(Locale.ROOT)}"

    /**
     * Retrofit requires the base URL to end in "/" and every route this app
     * calls is mounted under "/api/v1/", so both are normalised here once
     * instead of relying on every caller. Whitespace is trimmed because the
     * value usually arrives straight from a text field.
     */
    fun sanitizeServerUrl(url: String): String {
        val trimmed = url.trim()
        if (trimmed.isEmpty()) return trimmed
        val withTrailingSlash = if (trimmed.endsWith("/")) trimmed else "$trimmed/"
        return when {
            withTrailingSlash.endsWith("/api/v1/") -> withTrailingSlash
            withTrailingSlash.endsWith("/api/v1") -> "$withTrailingSlash/"
            else -> "${withTrailingSlash}api/v1/"
        }
    }

    /**
     * Environment-specific URL validation:
     * - anything that is not http:// or https:// is refused,
     * - LOCAL must be cleartext http (a LAN server has no certificate),
     * - PRODUCTION must be https,
     * - DEMO needs no URL at all.
     *
     * A release build denies cleartext to everything except the emulator/loopback
     * hosts (see res/xml/network_security_config.xml), so a LAN address is
     * refused up front there rather than failing later with an opaque
     * "cleartext not permitted" I/O error. ALLOW_CLEARTEXT is what distinguishes
     * the debug (permissive) and release (strict) builds.
     */
    fun validateServerUrl(mode: AppMode, url: String): UrlValidationResult {
        if (mode == AppMode.DEMO) return UrlValidationResult.Valid

        val trimmed = url.trim()
        if (trimmed.isEmpty()) {
            return UrlValidationResult.Invalid("Enter the ${mode.name.lowercase(Locale.ROOT)} backend URL")
        }

        val parsed = sanitizeServerUrl(trimmed).toHttpUrlOrNull()
            ?: return UrlValidationResult.Invalid("URL must start with http:// or https:// and include a host")

        return when (mode) {
            AppMode.LOCAL -> when {
                parsed.scheme != "http" ->
                    UrlValidationResult.Invalid(
                        "LOCAL must be a cleartext http:// address, e.g. http://your-lan-ip:8000/api/v1/"
                    )
                !BuildConfig.ALLOW_CLEARTEXT && parsed.host !in CLEARTEXT_DEBUG_HOSTS ->
                    UrlValidationResult.Invalid(
                        "This release build refuses cleartext to ${parsed.host}; " +
                            "use https:// or one of ${CLEARTEXT_DEBUG_HOSTS.joinToString()}"
                    )
                else -> UrlValidationResult.Valid
            }
            AppMode.PRODUCTION ->
                if (parsed.scheme == "https") {
                    UrlValidationResult.Valid
                } else {
                    UrlValidationResult.Invalid("PRODUCTION must use https:// — cleartext is refused at runtime")
                }
            AppMode.DEMO -> UrlValidationResult.Valid
        }
    }

    // ─── Device enrollment ────────────────────────────────────────────────────

    fun saveDeviceEnrollment(token: String) {
        prefs.edit()
            .putString(KEY_DEVICE_TOKEN, token)
            .putBoolean(KEY_IS_ENROLLED, true)
            .apply()
    }

    fun getDeviceToken(): String? {
        return prefs.getString(KEY_DEVICE_TOKEN, null)
    }

    fun isDeviceEnrolled(): Boolean {
        return prefs.getBoolean(KEY_IS_ENROLLED, false)
    }

    // ─── User session ─────────────────────────────────────────────────────────

    fun saveSession(session: UserSession) {
        prefs.edit()
            .putString(KEY_USER_ID, session.userId)
            .putString(KEY_USERNAME, session.username)
            .putString(KEY_DISPLAY_NAME, session.displayName)
            .putString(KEY_ROLE, session.role.name)
            .putStringSet(KEY_PERMISSIONS, session.permissions)
            .putString(KEY_ACCESS_TOKEN, session.accessToken)
            .putString(KEY_REFRESH_TOKEN, session.refreshToken)
            .apply()
        _userSession.value = session
    }

    fun clearSession() {
        prefs.edit()
            .remove(KEY_USER_ID)
            .remove(KEY_USERNAME)
            .remove(KEY_DISPLAY_NAME)
            .remove(KEY_ROLE)
            .remove(KEY_PERMISSIONS)
            .remove(KEY_ACCESS_TOKEN)
            .remove(KEY_REFRESH_TOKEN)
            .apply()
        _userSession.value = null
    }

    fun updateTokens(accessToken: String, refreshToken: String? = null) {
        val editor = prefs.edit().putString(KEY_ACCESS_TOKEN, accessToken)
        if (refreshToken != null) {
            editor.putString(KEY_REFRESH_TOKEN, refreshToken)
        }
        editor.apply()
        _userSession.value?.let { current ->
            _userSession.value = current.copy(
                accessToken = accessToken,
                refreshToken = refreshToken ?: current.refreshToken
            )
        }
    }

    private fun getSavedSession(): UserSession? {
        val token = prefs.getString(KEY_ACCESS_TOKEN, null) ?: return null
        val userId = prefs.getString(KEY_USER_ID, "") ?: ""
        val username = prefs.getString(KEY_USERNAME, "") ?: ""
        val displayName = prefs.getString(KEY_DISPLAY_NAME, "") ?: ""
        val roleStr = prefs.getString(KEY_ROLE, UserRole.UNKNOWN.name)
        val role = try {
            UserRole.valueOf(roleStr ?: UserRole.UNKNOWN.name)
        } catch (e: Exception) {
            UserRole.UNKNOWN
        }
        val permissions = prefs.getStringSet(KEY_PERMISSIONS, emptySet()) ?: emptySet()
        val refreshToken = prefs.getString(KEY_REFRESH_TOKEN, "") ?: ""

        return UserSession(
            userId = userId,
            username = username,
            displayName = displayName,
            role = role,
            permissions = permissions,
            accessToken = token,
            refreshToken = refreshToken
        )
    }

    companion object {
        /** One persisted URL per environment, so switching never loses an override. */
        private const val KEY_SERVER_URL_PREFIX = "server_url_"
        private const val KEY_APP_MODE = "app_mode"
        private const val KEY_DEVICE_TOKEN = "device_token"
        private const val KEY_IS_ENROLLED = "is_enrolled"
        private const val KEY_USER_ID = "user_id"
        private const val KEY_USERNAME = "username"
        private const val KEY_DISPLAY_NAME = "display_name"
        private const val KEY_ROLE = "role"
        private const val KEY_PERMISSIONS = "permissions"
        private const val KEY_ACCESS_TOKEN = "access_token"
        private const val KEY_REFRESH_TOKEN = "refresh_token"

        /**
         * Hosts a release build still allows cleartext to (emulator loopback and
         * adb-reverse). Must stay in sync with res/xml/network_security_config.xml.
         */
        private val CLEARTEXT_DEBUG_HOSTS = setOf("10.0.2.2", "localhost", "127.0.0.1")
    }
}
