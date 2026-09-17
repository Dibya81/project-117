package com.project117.mobile.ui.screens
import android.os.Build
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.QrCodeScanner
import androidx.compose.material.icons.filled.Security
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.project117.mobile.R
import com.project117.mobile.data.local.preferences.SessionManager
import com.project117.mobile.domain.backend.FieldBackend
import com.project117.mobile.domain.model.AppMode
import com.project117.mobile.domain.model.BackendResult
import com.project117.mobile.ui.components.*
import com.project117.mobile.ui.theme.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class EnrollmentViewModel @Inject constructor(
    private val sessionManager: SessionManager,
    private val fieldBackend: FieldBackend
) : ViewModel() {

    val appMode: StateFlow<AppMode> = sessionManager.appMode
    val isEnrolled = sessionManager.isDeviceEnrolled()

    val codeInput = MutableStateFlow(if (sessionManager.appMode.value == AppMode.DEMO) "ENROLL-P117-DEMO" else "")

    private val _enrollState = MutableStateFlow<EnrollUiState>(EnrollUiState.Idle)
    val enrollState: StateFlow<EnrollUiState> = _enrollState.asStateFlow()

    fun updateCode(newCode: String) {
        codeInput.value = newCode
    }

    fun enrollDevice() {
        val code = codeInput.value.trim()
        if (code.isBlank()) {
            _enrollState.value = EnrollUiState.Error("Please enter an enrollment code")
            return
        }

        viewModelScope.launch {
            _enrollState.value = EnrollUiState.Loading
            val deviceId = "${Build.MANUFACTURER}_${Build.MODEL}_${Build.ID}".replace(" ", "_")
            when (val res = fieldBackend.enroll(deviceId, code)) {
                is BackendResult.Success -> {
                    sessionManager.saveDeviceEnrollment(res.data)
                    _enrollState.value = EnrollUiState.Success
                }
                is BackendResult.BackendOffline -> {
                    _enrollState.value = EnrollUiState.Error("Backend offline. Switch to DEMO MODE or check network.")
                }
                is BackendResult.Error -> {
                    _enrollState.value = EnrollUiState.Error(res.message)
                }
                else -> {
                    _enrollState.value = EnrollUiState.Error("Device enrollment failed")
                }
            }
        }
    }
}

sealed class EnrollUiState {
    object Idle : EnrollUiState()
    object Loading : EnrollUiState()
    object Success : EnrollUiState()
    data class Error(val message: String) : EnrollUiState()
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EnrollmentScreen(
    onEnrollmentSuccess: () -> Unit,
    onNavigateToSettings: () -> Unit,
    onNavigateToScan: () -> Unit,
    viewModel: EnrollmentViewModel = hiltViewModel()
) {
    val mode by viewModel.appMode.collectAsState()
    val code by viewModel.codeInput.collectAsState()
    val state by viewModel.enrollState.collectAsState()

    LaunchedEffect(state) {
        if (state is EnrollUiState.Success) {
            onEnrollmentSuccess()
        }
    }

    Scaffold(
        topBar = {
            AppTopBar(
                title = "Device Enrollment",
                subtitle = "TRUST PROVISIONING",
                actions = {
                    IconButton(onClick = onNavigateToSettings) {
                        Icon(Icons.Default.Settings, contentDescription = "Settings")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(ScreenPadding),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            DemoModeBanner(mode)
            Spacer(modifier = Modifier.height(ScreenSectionSpacing))

            P117IconContainer(
                icon = Icons.Default.Security,
                tint = IndustrialCyan,
                size = 72.dp,
                contentDescription = "Security"
            )

            Spacer(modifier = Modifier.height(18.dp))

            Text(
                text = stringResource(R.string.app_name) + " Field Client",
                style = MaterialTheme.typography.headlineSmall,
                color = IndustrialTextPrimary,
                textAlign = androidx.compose.ui.text.style.TextAlign.Center
            )

            Spacer(modifier = Modifier.height(8.dp))

            Text(
                text = "Register this device with Main Manager command center.",
                style = MaterialTheme.typography.bodyMedium,
                color = IndustrialTextSecondary,
                textAlign = androidx.compose.ui.text.style.TextAlign.Center
            )

            Spacer(modifier = Modifier.height(28.dp))

            // Descriptive section label only — it reports no enrollment state.
            P117Eyebrow(
                text = "Provisioning Checklist",
                modifier = Modifier.fillMaxWidth(),
                color = IndustrialCyan
            )

            Spacer(modifier = Modifier.height(8.dp))

            P117Card(
                modifier = Modifier.fillMaxWidth(),
                cardType = P117CardType.PLAIN,
                accentColor = IndustrialCyan
            ) {
                Column(modifier = Modifier.padding(CardContentPadding)) {
                    OutlinedTextField(
                        value = code,
                        onValueChange = { viewModel.updateCode(it) },
                        label = { Text("Enrollment Code") },
                        textStyle = EquipmentTagStyle,
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                        trailingIcon = {
                            IconButton(onClick = onNavigateToScan) {
                                Icon(Icons.Default.QrCodeScanner, contentDescription = "Scan QR", tint = IndustrialCyan)
                            }
                        }
                    )

                    Spacer(modifier = Modifier.height(18.dp))

                    AppButton(
                        onClick = { viewModel.enrollDevice() },
                        modifier = Modifier.fillMaxWidth(),
                        enabled = state !is EnrollUiState.Loading
                    ) {
                        if (state is EnrollUiState.Loading) {
                            CircularProgressIndicator(modifier = Modifier.size(20.dp), color = MaterialTheme.colorScheme.onPrimary)
                        } else {
                            Icon(Icons.Default.Security, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("Authorize & Enroll Device", fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            if (mode == AppMode.DEMO) {
                AppTextButton(onClick = onEnrollmentSuccess) {
                    Text("Skip to Sign-In (Demo Pre-Enrolled)", color = IndustrialCyan)
                }
            }

            if (state is EnrollUiState.Error) {
                Spacer(modifier = Modifier.height(16.dp))
                StatusBanner(
                    text = (state as EnrollUiState.Error).message,
                    tone = StatusTone.CRITICAL
                )
            }
        }
    }
}
