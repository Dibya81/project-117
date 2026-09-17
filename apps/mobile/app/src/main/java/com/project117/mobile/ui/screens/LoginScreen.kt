package com.project117.mobile.ui.screens

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.foundation.layout.heightIn
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
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
class LoginViewModel @Inject constructor(
    private val sessionManager: SessionManager,
    private val fieldBackend: FieldBackend
) : ViewModel() {

    val appMode: StateFlow<AppMode> = sessionManager.appMode
    val username = MutableStateFlow("technician")
    val password = MutableStateFlow("demo123")

    private val _loginState = MutableStateFlow<LoginUiState>(LoginUiState.Idle)
    val loginState: StateFlow<LoginUiState> = _loginState.asStateFlow()

    fun selectPresetRole(roleName: String) {
        username.value = roleName
        password.value = "demo123"
    }

    fun login() {
        val user = username.value.trim()
        val pass = password.value.trim()
        if (user.isBlank()) {
            _loginState.value = LoginUiState.Error("Username is required")
            return
        }

        viewModelScope.launch {
            _loginState.value = LoginUiState.Loading
            val deviceToken = sessionManager.getDeviceToken() ?: "DEV-TOKEN-TEMP"
            when (val res = fieldBackend.login(user, pass, deviceToken)) {
                is BackendResult.Success -> {
                    sessionManager.saveSession(res.data)
                    _loginState.value = LoginUiState.Success
                }
                is BackendResult.BackendOffline -> {
                    _loginState.value = LoginUiState.Error("Backend offline. Set mode to DEMO in Settings to evaluate.")
                }
                is BackendResult.Unauthorized -> {
                    _loginState.value = LoginUiState.Error("Invalid credentials")
                }
                is BackendResult.Error -> {
                    _loginState.value = LoginUiState.Error(res.message)
                }
                else -> {
                    _loginState.value = LoginUiState.Error("Authentication failed")
                }
            }
        }
    }
}

sealed class LoginUiState {
    object Idle : LoginUiState()
    object Loading : LoginUiState()
    object Success : LoginUiState()
    data class Error(val message: String) : LoginUiState()
}

/*
 * Sign-in — visual identity: "access control".
 *
 * The brand lockup sits on the page background, and the credential form is the
 * single white card on the screen with a blue accent rail. Sign In is the only
 * filled button; "Enrol this device" is the secondary outline; the demo role
 * presets are a clearly-labelled tertiary block at the bottom so they can never
 * be mistaken for production credentials.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LoginScreen(
    onLoginSuccess: () -> Unit,
    onNavigateToSettings: () -> Unit,
    onNavigateToEnrollment: () -> Unit,
    viewModel: LoginViewModel = hiltViewModel()
) {
    val mode by viewModel.appMode.collectAsState()
    val username by viewModel.username.collectAsState()
    val password by viewModel.password.collectAsState()
    val state by viewModel.loginState.collectAsState()

    LaunchedEffect(state) {
        if (state is LoginUiState.Success) {
            onLoginSuccess()
        }
    }

    Scaffold(
        topBar = {
            AppTopBar(
                title = "Sign In",
                subtitle = "PROJECT 117 FIELD CLIENT",
                actions = {
                    IconButton(onClick = onNavigateToSettings) {
                        Icon(Icons.Default.Settings, contentDescription = "Settings")
                    }
                }
            )
        }
    ) { padding ->
        val scrollState = rememberScrollState()
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(scrollState)
                // Consume the IME inset so the form scrolls above the keyboard.
                //
                // The activity is `adjustResize` + edge-to-edge. With edge-to-edge
                // the window no longer resizes the Compose content for the IME, so
                // nothing moved when the keyboard opened and the password field
                // sat behind it. `imePadding()` is what makes the IME inset reach
                // this layout; `verticalScroll` then lets the form move up while
                // the focused field stays visible.
                //
                // Order matters: imePadding AFTER the scroll modifier would pad
                // the scrolling viewport, so it is applied to the scrollable
                // content instead — the content grows by the keyboard height and
                // can be scrolled clear of it.
                .imePadding()
                .padding(ScreenPadding),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            DemoModeBanner(mode)
            Spacer(modifier = Modifier.height(ScreenSectionSpacing))

            // Official Project 117 lockup. The shipped artwork already carries
            // the wordmark, so it replaces the previous text-only brand row
            // rather than sitting beside a duplicate of the same name.
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Image(
                    painter = painterResource(R.drawable.ic_project117_logo),
                    contentDescription = stringResource(R.string.app_name),
                    modifier = Modifier
                        .fillMaxWidth(0.62f)
                        .heightIn(max = 168.dp)
                )
                Spacer(modifier = Modifier.height(14.dp))
                Text(
                    text = "Authentication",
                    style = MaterialTheme.typography.headlineSmall,
                    color = IndustrialTextPrimary
                )
                Spacer(modifier = Modifier.height(6.dp))
                Text(
                    text = "Sign in to access your assigned field workspace.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = IndustrialTextSecondary
                )
            }

            Spacer(modifier = Modifier.height(22.dp))

            // ---- Credential card ----------------------------------------
            P117Card(
                modifier = Modifier.fillMaxWidth(),
                cardType = P117CardType.EQUIPMENT,
                accentColor = IndustrialCyan
            ) {
                Column(modifier = Modifier.padding(CardContentPadding)) {
                    P117Eyebrow(text = "Operator credentials")
                    Spacer(modifier = Modifier.height(10.dp))

                    OutlinedTextField(
                        value = username,
                        onValueChange = { viewModel.username.value = it },
                        label = { Text("Username") },
                        leadingIcon = { Icon(Icons.Default.Person, contentDescription = null) },
                        textStyle = EquipmentTagStyle,
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true
                    )

                    Spacer(modifier = Modifier.height(14.dp))

                    OutlinedTextField(
                        value = password,
                        onValueChange = { viewModel.password.value = it },
                        label = { Text("Password") },
                        leadingIcon = { Icon(Icons.Default.Lock, contentDescription = null) },
                        visualTransformation = PasswordVisualTransformation(),
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true
                    )

                    Spacer(modifier = Modifier.height(20.dp))

                    AppButton(
                        onClick = { viewModel.login() },
                        modifier = Modifier.fillMaxWidth(),
                        enabled = state !is LoginUiState.Loading
                    ) {
                        if (state is LoginUiState.Loading) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(20.dp),
                                color = MaterialTheme.colorScheme.onPrimary
                            )
                        } else {
                            Icon(Icons.Default.Lock, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("Sign In", fontWeight = FontWeight.Bold)
                        }
                    }

                    if (state is LoginUiState.Error) {
                        Spacer(modifier = Modifier.height(14.dp))
                        StatusBanner(
                            text = (state as LoginUiState.Error).message,
                            tone = StatusTone.CRITICAL
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Enrolment entry point. A live backend rejects a login from a device
            // it has never enrolled, so this has to be reachable from here or the
            // only way in is DEMO mode.
            AppOutlinedButton(
                onClick = onNavigateToEnrollment,
                modifier = Modifier.fillMaxWidth()
            ) {
                Icon(Icons.Default.Settings, contentDescription = null, modifier = Modifier.size(18.dp))
                Spacer(modifier = Modifier.width(8.dp))
                Text("Enrol this device")
            }

            Spacer(modifier = Modifier.height(24.dp))

            // Quick Role Switcher for Demonstration
            P117Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = IndustrialDarkSurfaceSunken)
            ) {
                Column(modifier = Modifier.padding(CardContentPadding)) {
                    SectionHeader(text = "Quick demo role presets")
                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        text = "Evaluation only — these presets fill the form with a demo credential.",
                        style = MaterialTheme.typography.bodySmall,
                        color = IndustrialTextMuted
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        AppOutlinedButton(
                            onClick = { viewModel.selectPresetRole("technician") },
                            modifier = Modifier.weight(1f),
                            contentPadding = PaddingValues(horizontal = 6.dp, vertical = 12.dp)
                        ) {
                            Text("Technician", maxLines = 1, fontSize = 12.sp)
                        }
                        AppOutlinedButton(
                            onClick = { viewModel.selectPresetRole("supervisor") },
                            modifier = Modifier.weight(1f),
                            contentPadding = PaddingValues(horizontal = 6.dp, vertical = 12.dp)
                        ) {
                            Text("Supervisor", maxLines = 1, fontSize = 12.sp)
                        }
                        AppOutlinedButton(
                            onClick = { viewModel.selectPresetRole("operator") },
                            modifier = Modifier.weight(1f),
                            contentPadding = PaddingValues(horizontal = 6.dp, vertical = 12.dp)
                        ) {
                            Text("Operator", maxLines = 1, fontSize = 12.sp)
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(ScreenSectionSpacing))
        }
    }
}
