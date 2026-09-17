package com.project117.mobile.ui.screens
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import coil.compose.rememberAsyncImagePainter
import com.project117.mobile.data.local.preferences.SessionManager
import com.project117.mobile.data.sync.SyncManager
import com.project117.mobile.domain.backend.FieldBackend
import com.project117.mobile.domain.model.*
import com.project117.mobile.ui.camera.PhotoCaptureHelper
import com.project117.mobile.ui.components.*
import com.project117.mobile.ui.theme.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.io.File
import javax.inject.Inject

@HiltViewModel
class ReportIssueViewModel @Inject constructor(
    private val fieldBackend: FieldBackend,
    private val syncManager: SyncManager,
    private val sessionManager: SessionManager,
    savedStateHandle: SavedStateHandle
) : ViewModel() {

    val appMode: StateFlow<AppMode> = sessionManager.appMode

    val equipmentId = MutableStateFlow(savedStateHandle.get<String>("equipmentId") ?: "EQ-P102")
    val description = MutableStateFlow("Excessive vibration and abnormal noise detected during routine operational walkdown.")
    val severity = MutableStateFlow(IssueSeverity.HIGH)

    private val _photoUri = MutableStateFlow<Uri?>(null)
    val photoUri: StateFlow<Uri?> = _photoUri.asStateFlow()

    private var currentPhotoFile: File? = null

    private val _submitState = MutableStateFlow<IssueSubmitUiState>(IssueSubmitUiState.Idle)
    val submitState: StateFlow<IssueSubmitUiState> = _submitState.asStateFlow()

    fun onPhotoTaken(uri: Uri, file: File) {
        _photoUri.value = uri
        currentPhotoFile = file
    }

    fun submitIssue() {
        val eq = equipmentId.value.trim()
        val desc = description.value.trim()
        if (eq.isBlank() || desc.isBlank()) {
            _submitState.value = IssueSubmitUiState.Error("Equipment ID and Description are required")
            return
        }

        viewModelScope.launch {
            _submitState.value = IssueSubmitUiState.Submitting
            when (val res = fieldBackend.reportIssue(eq, desc, severity.value, emptyList())) {
                is BackendResult.Success -> {
                    _submitState.value = IssueSubmitUiState.Success("Issue reported successfully! Reference: ${res.data.id}")
                }
                is BackendResult.BackendOffline -> {
                    syncManager.queueReportIssue(eq, desc, severity.value, emptyList())
                    _submitState.value = IssueSubmitUiState.Queued("Backend offline: Issue queued locally for synchronization.")
                }
                else -> {
                    syncManager.queueReportIssue(eq, desc, severity.value, emptyList())
                    _submitState.value = IssueSubmitUiState.Queued("Issue queued for synchronization.")
                }
            }
        }
    }
}

sealed class IssueSubmitUiState {
    object Idle : IssueSubmitUiState()
    object Submitting : IssueSubmitUiState()
    data class Success(val message: String) : IssueSubmitUiState()
    data class Queued(val message: String) : IssueSubmitUiState()
    data class Error(val message: String) : IssueSubmitUiState()
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReportIssueScreen(
    initialEquipmentId: String? = null,
    onNavigateBack: () -> Unit,
    viewModel: ReportIssueViewModel = hiltViewModel()
) {
    val context = LocalContext.current
    val mode by viewModel.appMode.collectAsState()
    val eqId by viewModel.equipmentId.collectAsState()
    val desc by viewModel.description.collectAsState()
    val sev by viewModel.severity.collectAsState()
    val photoUri by viewModel.photoUri.collectAsState()
    val state by viewModel.submitState.collectAsState()

    var tempPhotoUri by remember { mutableStateOf<Uri?>(null) }
    var tempPhotoFile by remember { mutableStateOf<File?>(null) }

    val cameraLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.TakePicture()
    ) { success ->
        if (success && tempPhotoUri != null && tempPhotoFile != null) {
            viewModel.onPhotoTaken(tempPhotoUri!!, tempPhotoFile!!)
        }
    }

    Scaffold(
        topBar = {
            AppTopBar(
                title = "Report Equipment Issue",
                subtitle = "ANOMALY CAPTURE",
                onNavigateBack = onNavigateBack
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            DemoModeBanner(mode)

            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(rememberScrollState())
                    .padding(ScreenPadding),
                verticalArrangement = Arrangement.spacedBy(ScreenSectionSpacing)
            ) {
                SectionHeader(text = "Target equipment")

                OutlinedTextField(
                    value = eqId,
                    onValueChange = { viewModel.equipmentId.value = it },
                    label = { Text("Equipment ID / asset tag") },
                    textStyle = EquipmentTagStyle,
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                P117Card(
                    modifier = Modifier.fillMaxWidth(),
                    cardType = P117CardType.ALERT,
                    accentColor = IndustrialWarningAmber
                ) {
                    Column(modifier = Modifier.padding(CardContentPadding)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            P117Eyebrow("Severity level")
                            StatusChip(
                                label = sev.name,
                                tone = when (sev) {
                                    IssueSeverity.LOW -> StatusTone.NEUTRAL
                                    IssueSeverity.MEDIUM -> StatusTone.INFO
                                    IssueSeverity.HIGH -> StatusTone.WARNING
                                    IssueSeverity.CRITICAL -> StatusTone.CRITICAL
                                }
                            )
                        }
                        Spacer(modifier = Modifier.height(12.dp))
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .horizontalScroll(rememberScrollState()),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            listOf(IssueSeverity.LOW, IssueSeverity.MEDIUM, IssueSeverity.HIGH, IssueSeverity.CRITICAL).forEach { level ->
                                FilterChip(
                                    selected = sev == level,
                                    onClick = { viewModel.severity.value = level },
                                    label = { Text(level.name) }
                                )
                            }
                        }
                    }
                }

                SectionHeader(text = "Observed condition")

                OutlinedTextField(
                    value = desc,
                    onValueChange = { viewModel.description.value = it },
                    label = { Text("Issue Description & Symptoms") },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(130.dp),
                    maxLines = 5
                )

                SectionHeader(text = "Photo evidence")

                if (photoUri != null) {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(170.dp)
                            .clip(MaterialTheme.shapes.small)
                            .background(IndustrialDarkSurfaceSunken)
                    ) {
                        Image(
                            painter = rememberAsyncImagePainter(photoUri),
                            contentDescription = "Issue Photo",
                            contentScale = ContentScale.Crop,
                            modifier = Modifier.fillMaxSize()
                        )
                    }
                }

                AppOutlinedButton(
                    onClick = {
                        val (uri, file) = PhotoCaptureHelper.createEvidenceImageUri(context)
                        tempPhotoUri = uri
                        tempPhotoFile = file
                        cameraLauncher.launch(uri)
                    },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Icon(Icons.Default.CameraAlt, contentDescription = null, tint = IndustrialCyan)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(if (photoUri == null) "Attach Photo Evidence" else "Retake Photo")
                }

                Spacer(modifier = Modifier.height(4.dp))

                AppButton(
                    onClick = { viewModel.submitIssue() },
                    modifier = Modifier.fillMaxWidth(),
                    enabled = state !is IssueSubmitUiState.Submitting,
                    colors = p117WarningButtonColors()
                ) {
                    if (state is IssueSubmitUiState.Submitting) {
                        CircularProgressIndicator(modifier = Modifier.size(20.dp), color = MaterialTheme.colorScheme.onPrimary)
                    } else {
                        Icon(Icons.Default.ReportProblem, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("Submit Issue Report", fontWeight = FontWeight.Bold)
                    }
                }

                when (val s = state) {
                    is IssueSubmitUiState.Success -> {
                        StatusBanner(text = s.message, tone = StatusTone.SUCCESS)
                    }
                    is IssueSubmitUiState.Queued -> {
                        StatusBanner(text = s.message, tone = StatusTone.WARNING)
                    }
                    is IssueSubmitUiState.Error -> {
                        StatusBanner(text = s.message, tone = StatusTone.CRITICAL)
                    }
                    else -> Unit
                }
            }
        }
    }
}
