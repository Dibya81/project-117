package com.project117.mobile.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Error
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.project117.mobile.data.local.preferences.SessionManager
import com.project117.mobile.data.local.preferences.UrlValidationResult
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
class ServerConfigViewModel @Inject constructor(
    private val sessionManager: SessionManager,
    private val fieldBackend: FieldBackend
) : ViewModel() {

    val currentMode: StateFlow<AppMode> = sessionManager.appMode

    private val _currentUrl = MutableStateFlow(sessionManager.getServerUrl())
    val currentUrl: StateFlow<String> = _currentUrl.asStateFlow()

    private val _testStatus = MutableStateFlow<TestStatus>(TestStatus.Idle)
    val testStatus: StateFlow<TestStatus> = _testStatus.asStateFlow()

    /** The environment default currently selected, shown as guidance in the UI. */
    fun defaultUrlFor(mode: AppMode): String = sessionManager.defaultServerUrl(mode)

    fun updateUrl(newUrl: String) {
        _currentUrl.value = newUrl
        // Editing the URL invalidates a previous result — it no longer describes
        // the text in the field.
        if (_testStatus.value !is TestStatus.Testing) {
            _testStatus.value = TestStatus.Idle
        }
    }

    fun setMode(mode: AppMode) {
        sessionManager.setAppMode(mode)
        // setAppMode resolves this environment's own custom/default URL, so mirror
        // it back into the editor instead of carrying the previous mode's text.
        _currentUrl.value = sessionManager.getServerUrl()
        _testStatus.value = TestStatus.Idle
    }

    fun useDefaultUrl() {
        sessionManager.clearServerUrlOverride()
        _currentUrl.value = sessionManager.getServerUrl()
        _testStatus.value = TestStatus.Idle
    }

    /** @return true when the URL was accepted and persisted. */
    fun saveConfiguration(): Boolean {
        return when (val result = sessionManager.setServerUrl(_currentUrl.value)) {
            is UrlValidationResult.Valid -> {
                _currentUrl.value = sessionManager.getServerUrl()
                true
            }
            is UrlValidationResult.Invalid -> {
                _testStatus.value = TestStatus.Failed(result.reason)
                false
            }
        }
    }

    fun testConnection() {
        // Validate against the selected environment first: testing a URL that
        // could never be saved would only produce a confusing network error.
        val validation = sessionManager.validateServerUrl(currentMode.value, _currentUrl.value)
        if (validation is UrlValidationResult.Invalid) {
            _testStatus.value = TestStatus.Failed(validation.reason)
            return
        }

        viewModelScope.launch {
            _testStatus.value = TestStatus.Testing
            if (!saveConfiguration()) return@launch

            // The only networking path available to a screen is FieldBackend.
            when (val res = fieldBackend.checkHealth()) {
                is BackendResult.Success -> {
                    _testStatus.value = if (res.data) {
                        TestStatus.Connected("Connected — backend health check passed")
                    } else {
                        TestStatus.Failed("Server reachable but reported an unhealthy status")
                    }
                }
                is BackendResult.BackendOffline -> {
                    _testStatus.value = TestStatus.Offline(
                        "Offline — no response from ${sessionManager.getServerUrl()}"
                    )
                }
                is BackendResult.Error -> {
                    val code = if (res.code != 0) " (HTTP ${res.code})" else ""
                    _testStatus.value = TestStatus.Failed("Failed: ${res.message}$code")
                }
                is BackendResult.Unauthorized -> {
                    _testStatus.value = TestStatus.Failed("Failed: server rejected the request (401 Unauthorized)")
                }
                is BackendResult.NotFound -> {
                    _testStatus.value = TestStatus.Failed(
                        "Failed: health endpoint not found (404) — check the /api/v1/ path"
                    )
                }
            }
        }
    }
}

sealed class TestStatus {
    object Idle : TestStatus()
    object Testing : TestStatus()

    /** The health check reached the server and it reported OK. */
    data class Connected(val message: String) : TestStatus()

    /** The request never reached the server (I/O failure / unreachable host). */
    data class Offline(val message: String) : TestStatus()

    /** The server answered but the check failed, or the URL itself is invalid. */
    data class Failed(val error: String) : TestStatus()
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ServerConfigScreen(
    onNavigateBack: () -> Unit,
    viewModel: ServerConfigViewModel = hiltViewModel()
) {
    val mode by viewModel.currentMode.collectAsState()
    val url by viewModel.currentUrl.collectAsState()
    val testStatus by viewModel.testStatus.collectAsState()
    val defaultUrl = viewModel.defaultUrlFor(mode)
    val isDemo = mode == AppMode.DEMO

    Scaffold(
        topBar = {
            AppTopBar(
                title = "Server & Operation Mode",
                onNavigateBack = onNavigateBack
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(ScreenPadding),
            verticalArrangement = Arrangement.spacedBy(ScreenSectionSpacing)
        ) {
            DemoModeBanner(mode)

            // ---- Operation Mode -------------------------------------------------
            P117Card(
                modifier = Modifier.fillMaxWidth(),
                cardType = P117CardType.PLAIN,
                accentColor = IndustrialCyan
            ) {
                Column(modifier = Modifier.padding(CardContentPadding)) {
                    SectionHeader(text = "Operation Mode")
                    Spacer(modifier = Modifier.height(10.dp))
                    Text(
                        text = "DEMO runs entirely on-device. LOCAL connects to the backend over your LAN " +
                            "(cleartext http). PRODUCTION connects over HTTPS. A live backend that is " +
                            "unreachable is shown as offline and queued — it never falls back to DEMO.",
                        style = MaterialTheme.typography.bodySmall,
                        color = IndustrialTextSecondary
                    )
                    Spacer(modifier = Modifier.height(14.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        ModeButton(
                            label = "DEMO",
                            target = AppMode.DEMO,
                            selected = mode,
                            selectedColor = IndustrialWarningAmber,
                            modifier = Modifier.weight(1f),
                            onSelect = viewModel::setMode
                        )
                        ModeButton(
                            label = "LOCAL",
                            target = AppMode.LOCAL,
                            selected = mode,
                            selectedColor = IndustrialCyan,
                            modifier = Modifier.weight(1f),
                            onSelect = viewModel::setMode
                        )
                        ModeButton(
                            label = "PRODUCTION",
                            target = AppMode.PRODUCTION,
                            selected = mode,
                            selectedColor = IndustrialNominalGreen,
                            modifier = Modifier.weight(1f),
                            onSelect = viewModel::setMode
                        )
                    }
                }
            }

            // ---- Backend Server URL ---------------------------------------------
            P117Card(
                modifier = Modifier.fillMaxWidth(),
                cardType = P117CardType.PLAIN,
                accentColor = IndustrialCyan
            ) {
                Column(modifier = Modifier.padding(CardContentPadding)) {
                    SectionHeader(text = "Backend Server URL")
                    Spacer(modifier = Modifier.height(10.dp))
                    Text(
                        text = if (isDemo) {
                            "DEMO is in-process — no server URL is used."
                        } else {
                            "Environment default: $defaultUrl"
                        },
                        style = MaterialTheme.typography.bodySmall,
                        color = IndustrialTextSecondary
                    )
                    Spacer(modifier = Modifier.height(10.dp))

                    OutlinedTextField(
                        value = url,
                        onValueChange = viewModel::updateUrl,
                        label = { Text(urlHintFor(mode)) },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                        enabled = !isDemo,
                        isError = testStatus is TestStatus.Failed
                    )

                    if (!isDemo) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.End
                        ) {
                            AppTextButton(onClick = viewModel::useDefaultUrl) {
                                Text("Use environment default", fontSize = 12.sp)
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(8.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        AppOutlinedButton(
                            onClick = { viewModel.testConnection() },
                            modifier = Modifier.weight(1f),
                            enabled = testStatus !is TestStatus.Testing
                        ) {
                            if (testStatus is TestStatus.Testing) {
                                CircularProgressIndicator(
                                    modifier = Modifier.size(16.dp),
                                    color = IndustrialCyan,
                                    trackColor = IndustrialCyanContainer
                                )
                            } else {
                                Text("Test Connection")
                            }
                        }

                        AppButton(
                            onClick = {
                                if (viewModel.saveConfiguration()) onNavigateBack()
                            },
                            modifier = Modifier.weight(1f)
                        ) {
                            Text("Save & Apply")
                        }
                    }

                    Spacer(modifier = Modifier.height(10.dp))
                    P117Divider()
                    Spacer(modifier = Modifier.height(10.dp))

                    when (val s = testStatus) {
                        is TestStatus.Connected -> StatusLine(
                            icon = Icons.Default.CheckCircle,
                            tint = IndustrialNominalGreen,
                            message = s.message
                        )
                        is TestStatus.Offline -> StatusLine(
                            icon = Icons.Default.Warning,
                            tint = IndustrialWarningAmber,
                            message = s.message
                        )
                        is TestStatus.Failed -> StatusLine(
                            icon = Icons.Default.Error,
                            tint = IndustrialCriticalRed,
                            message = s.error
                        )
                        else -> Unit
                    }
                }
            }
        }
    }
}

@Composable
private fun ModeButton(
    label: String,
    target: AppMode,
    selected: AppMode,
    selectedColor: Color,
    modifier: Modifier = Modifier,
    onSelect: (AppMode) -> Unit
) {
    val isSelected = selected == target

    // Selected = a saturated fill with an on-accent (white) label; unselected =
    // an outlined secondary treatment so the chosen mode is unmistakable.
    if (isSelected) {
        AppButton(
            onClick = { onSelect(target) },
            modifier = modifier,
            colors = ButtonDefaults.buttonColors(
                containerColor = selectedColor,
                contentColor = IndustrialTextOnAccent
            ),
            contentPadding = PaddingValues(horizontal = 4.dp, vertical = 8.dp)
        ) {
            Text(
                text = label,
                color = IndustrialTextOnAccent,
                fontWeight = FontWeight.Bold,
                fontSize = 10.sp,
                maxLines = 1,
                softWrap = false
            )
        }
    } else {
        AppOutlinedButton(
            onClick = { onSelect(target) },
            modifier = modifier,
            colors = p117SecondaryButtonColors(),
            border = BorderStroke(1.dp, IndustrialBorderStrong),
            contentPadding = PaddingValues(horizontal = 4.dp, vertical = 8.dp)
        ) {
            Text(
                text = label,
                color = IndustrialTextPrimary,
                fontWeight = FontWeight.Bold,
                fontSize = 10.sp,
                maxLines = 1,
                softWrap = false
            )
        }
    }
}

@Composable
private fun StatusLine(icon: ImageVector, tint: Color, message: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(icon, contentDescription = null, tint = tint, modifier = Modifier.size(18.dp))
        Spacer(modifier = Modifier.width(6.dp))
        Text(message, color = tint, fontSize = 13.sp, lineHeight = 18.sp)
    }
}

private fun urlHintFor(mode: AppMode): String = when (mode) {
    AppMode.DEMO -> "Not used in DEMO mode"
    AppMode.LOCAL -> "http://your-lan-ip:8000/api/v1/"
    AppMode.PRODUCTION -> "https://api.project117.com/api/v1/"
}
