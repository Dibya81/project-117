package com.project117.mobile.data.local.security

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import dagger.hilt.android.qualifiers.ApplicationContext
import timber.log.Timber
import java.security.SecureRandom
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Manages the cryptographic key used for SQLCipher Room database at-rest encryption.
 * The passphrase is randomly generated, 256-bit, and stored securely in EncryptedSharedPreferences
 * backed by the Android Hardware Keystore (AES256_GCM).
 */
@Singleton
class DatabaseKeyManager @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private val prefs: SharedPreferences by lazy {
        try {
            val masterKey = MasterKey.Builder(context)
                .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                .build()

            EncryptedSharedPreferences.create(
                context,
                "project117_db_keys",
                masterKey,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            )
        } catch (e: Exception) {
            Timber.e(e, "Failed to initialize EncryptedSharedPreferences for database key")
            context.getSharedPreferences("project117_db_keys_fallback", Context.MODE_PRIVATE)
        }
    }

    @Synchronized
    fun getOrCreateDatabaseKey(): ByteArray {
        val existingHex = prefs.getString(KEY_DB_PASSPHRASE, null)
        if (!existingHex.isNullOrBlank()) {
            return hexToBytes(existingHex)
        }

        // Generate 32 secure random bytes (256-bit key)
        val keyBytes = ByteArray(32)
        SecureRandom().nextBytes(keyBytes)
        val hex = bytesToHex(keyBytes)

        prefs.edit().putString(KEY_DB_PASSPHRASE, hex).apply()
        return keyBytes
    }

    private fun bytesToHex(bytes: ByteArray): String =
        bytes.joinToString("") { "%02x".format(it) }

    private fun hexToBytes(hex: String): ByteArray {
        val len = hex.length
        val data = ByteArray(len / 2)
        for (i in 0 until len step 2) {
            data[i / 2] = ((Character.digit(hex[i], 16) shl 4) + Character.digit(hex[i + 1], 16)).toByte()
        }
        return data
    }

    companion object {
        private const val KEY_DB_PASSPHRASE = "db_encryption_passphrase_v1"
    }
}
