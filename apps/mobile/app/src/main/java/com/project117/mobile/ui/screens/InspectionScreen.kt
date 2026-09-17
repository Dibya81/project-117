package com.project117.mobile.ui.screens
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
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
import androidx.compose.ui.graphics.Color
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
import com.project117.mobile.data.local.dao.LocalEvidenceDao
import com.project117.mobile.data.local.entities.LocalEvidenceEntity
import com.project117.mobile.data.local.preferences.SessionManager
import com.project117.mobile.data.sync.SyncManager
import com.project117.mobile.domain.backend.FieldBackend
import com.project117.mobile.domain.model.AppMode
import com.project117.mobile.domain.model.BackendResult
import com.project117.mobile.domain.model.EvidenceType
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
class InspectionViewModel @Inject constructor(
    private val fieldBackend: FieldBackend,
    private val syncManager: SyncManager,
    private val localEvidenceDao: LocalEvidenceDao,
    private val sessionManager: SessionManager,
    savedStateHandle: SavedStateHandle
) : ViewModel() {

    val appMode: StateFlow<AppMode> = sessionManager.appMode

    val workOrderId: String = savedStateHandle["workOrderId"] ?: "WO-2026-0891"
    val equipmentId: String = savedStateHandle["equipmentId"] ?: "EQ-P102"

    val vibrationReading = MutableStateFlow("7.8")
    val temperatureReading = MutableStateFlow("82.4")
    val inspectionNotes = MutableStateFlow("Outboard bearing housing shows visible heat discoloration and oil seepage around seal interface.")

    private val _capturedPhotoUri = MutableStateFlow<Uri?>(null)
    val capturedPhotoUri: StateFlow<Uri?> = _capturedPhotoUri.asStateFlow()

    private var currentPhotoFile: File? = null

    private val _submitState = MutableStateFlow<InspectionSubmitState>(InspectionSubmitState.Idle)
    val submitState: StateFlow<InspectionSubmitState> = _submitState.asStateFlow()

    fun onPhotoCaptured(uri: Uri, file: File) {
        _capturedPhotoUri.value = uri
        currentPhotoFile = file
    }

    fun submitInspection() {
        viewModelScope.launch {
            _submitState.value = InspectionSubmitState.Submitting
            val photoPath = currentPhotoFile?.absolutePath ?: "evidence/simulated_p102_bearing.jpg"

            // Save in local evidence DB
            localEvidenceDao.insert(
                LocalEvidenceEntity(
                    localId = "LOC-EV-${System.currentTimeMillis()}",
                    localPath = photoPath,
                    type = EvidenceType.PHOTO.name,
                    equipmentId = equipmentId,
                    workOrderId = workOrderId,
                    caption = "Vibration spectrum port inspection on $equipmentId: ${vibrationReading.value} mm/s",
                    capturedAt = System.currentTimeMillis(),
                    syncStatus = "SAVED_LOCALLY"
                )
            )

            // Attempt upload
            when (val res = fieldBackend.uploadEvidence(
                localPath = photoPath,
                type = EvidenceType.PHOTO,
                equipmentId = equipmentId,
                workOrderId = workOrderId,
                caption = inspectionNotes.value
            )) {
                is BackendResult.Success -> {
                    localEvidenceDao.updateSyncStatusByPath(photoPath, "SYNCED", res.data)
                    _submitState.value = InspectionSubmitState.Success("Evidence submitted successfully! (ID: ${res.data})")
                }
                is BackendResult.BackendOffline -> {
                    // Queue for offline sync
                    syncManager.queueEvidenceUpload(
                        localPath = photoPath,
                        type = EvidenceType.PHOTO,
                        equipmentId = equipmentId,
                        workOrderId = workOrderId,
                        caption = inspectionNotes.value
                    )
                    _submitState.value = InspectionSubmitState.QueuedOffline("Backend offline: Inspection saved locally & queued for sync.")
                }
                else -> {
                    syncManager.queueEvidenceUpload(
                        localPath = photoPath,
                        type = EvidenceType.PHOTO,
                        equipmentId = equipmentId,
                        workOrderId = workOrderId,
                        caption = inspectionNotes.value
                    )
                    _submitState.value = InspectionSubmitState.QueuedOffline("Queued for sync.")
                }
            }
        }
    }
}

sealed class InspectionSubmitState {
    object Idle : InspectionSubmitState()
    object Submitting : InspectionSubmitState()
    data class Success(val message: String) : InspectionSubmitState()
    data class QueuedOffline(val message: String) : InspectionSubmitState()
    data class Error(val message: String) : InspectionSubmitState()
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InspectionScreen(
    workOrderId: String,
    equipmentId: String,
    onNavigateBack: () -> Unit,
    viewModel: InspectionViewModel = hiltViewModel()
) {
    val context = LocalContext.current
    val mode by viewModel.appMode.collectAsState()
    val vib by viewModel.vibrationReading.collectAsState()
    val temp by viewModel.temperatureReading.collectAsState()
    val notes by viewModel.inspectionNotes.collectAsState()
    val photoUri by viewModel.capturedPhotoUri.collectAsState()
    val submitState by viewModel.submitState.collectAsState()

    // Honest capture completeness: readings, observations and photo evidence.
    val captureProgress = (
        listOf(vib.isNotBlank(), temp.isNotBlank()).count { it } +
            (if (notes.isNotBlank()) 1 else 0) +
            (if (photoUri != null) 1 else 0)
        ) / 4f

    val submittedState: Pair<String, StatusTone>? = when (submitState) {
        is InspectionSubmitState.Success -> "SUBMITTED" to StatusTone.SUCCESS
        is InspectionSubmitState.QueuedOffline -> "QUEUED OFFLINE" to StatusTone.WARNING
        is InspectionSubmitState.Error -> "ERROR" to StatusTone.CRITICAL
        else -> null
    }

    var tempPhotoUri by remember { mutableStateOf<Uri?>(null) }
    var tempPhotoFile by remember { mutableStateOf<File?>(null) }

    val cameraLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.TakePicture()
    ) { success ->
        if (success && tempPhotoUri != null && tempPhotoFile != null) {
            viewModel.onPhotoCaptured(tempPhotoUri!!, tempPhotoFile!!)
        }
    }

    Scaffold(
        topBar = {
            AppTopBar(
                title = "Record Field Inspection",
                subtitle = "$workOrderId · $equipmentId",
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
                // Captured state — shown only once a submission result exists.
                if (submittedState != null) {
                    InspectionCard(
                        title = "Evidence capture",
                        context = "$workOrderId · $equipmentId",
                        progress = captureProgress,
                        stateLabel = submittedState.first,
                        stateTone = submittedState.second
                    )
                }

                // Header context
                P117Card(
                    modifier = Modifier.fillMaxWidth(),
                    cardType = P117CardType.INSPECTION
                ) {
                    Column(modifier = Modifier.padding(CardContentPadding)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            P117IconContainer(
                                icon = Icons.Default.FactCheck,
                                tint = IndustrialTeal,
                                size = 40.dp
                            )
                            Spacer(modifier = Modifier.width(12.dp))
                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    text = "Target Equipment",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = IndustrialTextSecondary
                                )
                                Spacer(modifier = Modifier.height(6.dp))
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    EquipmentTag(tag = equipmentId)
                                    Text("Pump P-102", style = MaterialTheme.typography.bodySmall, color = IndustrialTextSecondary)
                                }
                            }
                        }
                        Spacer(modifier = Modifier.height(12.dp))
                        P117Divider()
                        Spacer(modifier = Modifier.height(10.dp))
                        KeyValueRow(label = "Associated work order", value = workOrderId)
                    }
                }

                // Measurement inputs — read as instruments on a capture card.
                P117Card(
                    modifier = Modifier.fillMaxWidth(),
                    cardType = P117CardType.INSPECTION
                ) {
                    Column(modifier = Modifier.padding(CardContentPadding)) {
                        P117Eyebrow("PHYSICAL MEASUREMENTS")
                        Spacer(modifier = Modifier.height(4.dp))
                        P117MetaRow(
                            text = "Enter each reading exactly as the instrument displays it.",
                            icon = Icons.Default.Straighten,
                            tint = IndustrialTeal,
                            maxLines = 2
                        )
                        Spacer(modifier = Modifier.height(12.dp))

                        OutlinedTextField(
                            value = vib,
                            onValueChange = { viewModel.vibrationReading.value = it },
                            label = { Text("Vibration Spectrum Velocity (mm/s RMS)") },
                            supportingText = { Text("Nominal baseline: 2.5 mm/s | Threshold: 4.5 mm/s") },
                            textStyle = EquipmentTagStyle,
                            modifier = Modifier.fillMaxWidth(),
                            singleLine = true
                        )

                        Spacer(modifier = Modifier.height(12.dp))

                        OutlinedTextField(
                            value = temp,
                            onValueChange = { viewModel.temperatureReading.value = it },
                            label = { Text("Bearing Housing Temperature (°C)") },
                            supportingText = { Text("Warning: > 80.0 °C") },
                            textStyle = EquipmentTagStyle,
                            modifier = Modifier.fillMaxWidth(),
                            singleLine = true
                        )
                    }
                }

                // Field observations
                P117Card(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(CardContentPadding)) {
                        P117Eyebrow("FIELD OBSERVATIONS")
                        Spacer(modifier = Modifier.height(12.dp))
                        OutlinedTextField(
                            value = notes,
                            onValueChange = { viewModel.inspectionNotes.value = it },
                            label = { Text("Field Observations & Findings") },
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(120.dp),
                            maxLines = 4
                        )
                    }
                }

                // Photo Evidence Section
                SectionHeader(text = "Photo Evidence")

                if (photoUri != null) {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(180.dp)
                            .clip(MaterialTheme.shapes.small)
                            .background(IndustrialDarkSurfaceSunken),
                        contentAlignment = Alignment.Center
                    ) {
                        Image(
                            painter = rememberAsyncImagePainter(photoUri),
                            contentDescription = "Evidence Photo",
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
                    Icon(Icons.Default.CameraAlt, contentDescription = null, tint = IndustrialTeal)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(if (photoUri == null) "Capture Bearing Photo Evidence" else "Retake Photo Evidence")
                }

                // Submission Section
                Spacer(modifier = Modifier.height(4.dp))

                AppButton(
                    onClick = { viewModel.submitInspection() },
                    modifier = Modifier.fillMaxWidth(),
                    enabled = submitState !is InspectionSubmitState.Submitting
                ) {
                    if (submitState is InspectionSubmitState.Submitting) {
                        CircularProgressIndicator(modifier = Modifier.size(20.dp), color = MaterialTheme.colorScheme.onPrimary)
                    } else {
                        Icon(Icons.Default.Check, contentDescription = null)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("Submit Inspection & Readings", fontWeight = FontWeight.Bold)
                    }
                }

                when (val s = submitState) {
                    is InspectionSubmitState.Success -> {
                        StatusBanner(text = s.message, tone = StatusTone.SUCCESS)
                    }
                    is InspectionSubmitState.QueuedOffline -> {
                        StatusBanner(text = s.message, tone = StatusTone.WARNING)
                    }
                    else -> Unit
                }
            }
        }
    }
}
