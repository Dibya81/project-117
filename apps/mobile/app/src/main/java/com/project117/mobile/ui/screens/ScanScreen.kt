package com.project117.mobile.ui.screens
import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.QrCodeScanner
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.project117.mobile.domain.backend.FieldBackend
import com.project117.mobile.domain.model.BackendResult
import com.project117.mobile.ui.camera.BarcodeAnalyzer
import com.project117.mobile.ui.components.*
import com.project117.mobile.ui.theme.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.util.concurrent.Executors
import javax.inject.Inject

@HiltViewModel
class ScanViewModel @Inject constructor(
    private val fieldBackend: FieldBackend
) : ViewModel() {

    private val _scanResult = MutableStateFlow<ScanState>(ScanState.Idle)
    val scanResult: StateFlow<ScanState> = _scanResult.asStateFlow()

    val manualCode = MutableStateFlow("EQ-P102-VIB")

    fun onCodeScanned(code: String) {
        if (_scanResult.value is ScanState.Processing || _scanResult.value is ScanState.Success) return
        processCode(code)
    }

    fun processCode(code: String) {
        viewModelScope.launch {
            _scanResult.value = ScanState.Processing(code)
            when (val res = fieldBackend.identifyEquipment(code)) {
                is BackendResult.Success -> {
                    _scanResult.value = ScanState.Success(res.data.id, res.data.name)
                }
                else -> {
                    _scanResult.value = ScanState.NotFound("Equipment not found for tag '$code'")
                }
            }
        }
    }

    fun reset() {
        _scanResult.value = ScanState.Idle
    }
}

sealed class ScanState {
    object Idle : ScanState()
    data class Processing(val code: String) : ScanState()
    data class Success(val equipmentId: String, val equipmentName: String) : ScanState()
    data class NotFound(val message: String) : ScanState()
}

/*
 * Optical tag reader.
 *
 * Visual identity: the viewport is the one deliberately DARK surface left in the
 * app, because it is an instrument — a dark frame makes the live camera feed
 * read like a viewfinder instead of a web page, and it stops the preview edges
 * from showing. Everything around it is the light surface: a corner-bracket
 * reticle in light blue, a live read-state chip pinned to the top of the
 * viewport, and a white manual-entry panel below for when the tag is scuffed or
 * the lens is fogged.
 *
 * The camera bind, permission flow and the success-triggered navigation are
 * untouched.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ScanScreen(
    onNavigateBack: () -> Unit,
    onEquipmentIdentified: (String) -> Unit,
    viewModel: ScanViewModel = hiltViewModel()
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val scanState by viewModel.scanResult.collectAsState()
    val manualInput by viewModel.manualCode.collectAsState()

    var hasCameraPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED
        )
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { granted ->
        hasCameraPermission = granted
    }

    LaunchedEffect(Unit) {
        if (!hasCameraPermission) {
            permissionLauncher.launch(Manifest.permission.CAMERA)
        }
    }

    LaunchedEffect(scanState) {
        if (scanState is ScanState.Success) {
            val id = (scanState as ScanState.Success).equipmentId
            onEquipmentIdentified(id)
        }
    }

    Scaffold(
        topBar = {
            AppTopBar(
                title = "Scan Equipment Tag",
                subtitle = "OPTICAL TAG READER",
                onNavigateBack = onNavigateBack
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f)
                    .background(ViewportBackdrop),
                contentAlignment = Alignment.Center
            ) {
                if (hasCameraPermission) {
                    AndroidView(
                        factory = { ctx ->
                            val previewView = PreviewView(ctx)
                            val cameraProviderFuture = ProcessCameraProvider.getInstance(ctx)
                            cameraProviderFuture.addListener({
                                val cameraProvider = cameraProviderFuture.get()
                                val preview = Preview.Builder().build().also {
                                    it.setSurfaceProvider(previewView.surfaceProvider)
                                }
                                val imageAnalyzer = ImageAnalysis.Builder()
                                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                                    .build()
                                    .also {
                                        it.setAnalyzer(
                                            Executors.newSingleThreadExecutor(),
                                            BarcodeAnalyzer { barcode ->
                                                viewModel.onCodeScanned(barcode)
                                            }
                                        )
                                    }

                                try {
                                    cameraProvider.unbindAll()
                                    cameraProvider.bindToLifecycle(
                                        lifecycleOwner,
                                        CameraSelector.DEFAULT_BACK_CAMERA,
                                        preview,
                                        imageAnalyzer
                                    )
                                } catch (e: Exception) {
                                    timber.log.Timber.e(e, "Use case binding failed")
                                }
                            }, ContextCompat.getMainExecutor(ctx))
                            previewView
                        },
                        modifier = Modifier.fillMaxSize()
                    )

                    // Targeting reticle: four corner brackets rather than a closed
                    // box, so the operator can see the whole tag through the frame.
                    ScanReticle(
                        modifier = Modifier.size(260.dp),
                        color = IndustrialCyanDim
                    )

                    // Live read state, pinned to the top of the viewport so the
                    // operator sees it without looking away from the frame.
                    StatusChip(
                        label = when (val s = scanState) {
                            is ScanState.Processing -> "READING ${s.code}"
                            is ScanState.NotFound -> "NO MATCH"
                            else -> "AWAITING TAG"
                        },
                        tone = when (scanState) {
                            is ScanState.Processing -> StatusTone.INFO
                            is ScanState.NotFound -> StatusTone.CRITICAL
                            else -> StatusTone.NEUTRAL
                        },
                        modifier = Modifier
                            .align(Alignment.TopCenter)
                            .padding(top = ScreenPadding)
                    )
                } else {
                    // Permission state on the dark viewport backdrop: light-blue
                    // glyph and near-white copy, both well above 4.5 : 1 on navy.
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        modifier = Modifier.padding(24.dp)
                    ) {
                        Box(
                            modifier = Modifier
                                .size(64.dp)
                                .background(IndustrialCyanDim.copy(alpha = 0.16f), RoundedCornerShape(18.dp))
                                .border(1.dp, IndustrialCyanDim.copy(alpha = 0.35f), RoundedCornerShape(18.dp)),
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(
                                Icons.Default.CameraAlt,
                                contentDescription = null,
                                tint = IndustrialCyanDim,
                                modifier = Modifier.size(32.dp)
                            )
                        }
                        Spacer(modifier = Modifier.height(14.dp))
                        Text(
                            text = "Camera permission required for QR scanning",
                            style = MaterialTheme.typography.bodyMedium,
                            color = ViewportTextPrimary,
                            textAlign = TextAlign.Center
                        )
                        Spacer(modifier = Modifier.height(18.dp))
                        AppButton(onClick = { permissionLauncher.launch(Manifest.permission.CAMERA) }) {
                            Text("Grant Permission", fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }

            // ---- Manual fallback & status --------------------------------
            Surface(
                color = P117ChromeSurface,
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(ScreenPadding)) {
                    P117Divider()
                    Spacer(modifier = Modifier.height(12.dp))
                    SectionHeader(text = "Manual tag entry")
                    Spacer(modifier = Modifier.height(10.dp))

                    OutlinedTextField(
                        value = manualInput,
                        onValueChange = { viewModel.manualCode.value = it },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                        textStyle = EquipmentTagStyle,
                        leadingIcon = { Icon(Icons.Default.QrCodeScanner, contentDescription = null) },
                        placeholder = { Text("e.g. EQ-P102-VIB") }
                    )

                    Spacer(modifier = Modifier.height(10.dp))

                    AppButton(
                        onClick = { viewModel.processCode(manualInput) },
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Icon(Icons.Default.Check, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(modifier = Modifier.width(6.dp))
                        Text("Lookup Tag", fontWeight = FontWeight.Bold)
                    }

                    Spacer(modifier = Modifier.height(12.dp))

                    when (val s = scanState) {
                        is ScanState.Processing -> {
                            StatusBanner(text = "Identifying '${s.code}'…", tone = StatusTone.INFO)
                        }
                        is ScanState.NotFound -> {
                            StatusBanner(text = s.message, tone = StatusTone.CRITICAL)
                        }
                        else -> {
                            P117MetaRow(
                                text = "Point camera at machine QR tag (e.g. Pump P-102: EQ-P102-VIB)",
                                icon = Icons.Default.QrCodeScanner,
                                maxLines = 2
                            )
                        }
                    }
                }
            }
        }
    }
}

/** Four corner brackets — an open reticle that reads as an optical finder. */
@Composable
private fun ScanReticle(modifier: Modifier = Modifier, color: Color) {
    Box(modifier = modifier) {
        val thickness = 3.dp
        val arm = 34.dp
        val cornerShape = RoundedCornerShape(4.dp)

        // Top-left
        Box(
            modifier = Modifier
                .align(Alignment.TopStart)
                .size(width = arm, height = thickness)
                .background(color, cornerShape)
        )
        Box(
            modifier = Modifier
                .align(Alignment.TopStart)
                .size(width = thickness, height = arm)
                .background(color, cornerShape)
        )
        // Top-right
        Box(
            modifier = Modifier
                .align(Alignment.TopEnd)
                .size(width = arm, height = thickness)
                .background(color, cornerShape)
        )
        Box(
            modifier = Modifier
                .align(Alignment.TopEnd)
                .size(width = thickness, height = arm)
                .background(color, cornerShape)
        )
        // Bottom-left
        Box(
            modifier = Modifier
                .align(Alignment.BottomStart)
                .size(width = arm, height = thickness)
                .background(color, cornerShape)
        )
        Box(
            modifier = Modifier
                .align(Alignment.BottomStart)
                .size(width = thickness, height = arm)
                .background(color, cornerShape)
        )
        // Bottom-right
        Box(
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .size(width = arm, height = thickness)
                .background(color, cornerShape)
        )
        Box(
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .size(width = thickness, height = arm)
                .background(color, cornerShape)
        )
    }
}

/*
 * The scan viewport is the single dark surface in the light theme. It exists
 * only to frame a live camera feed, so it needs its own two colours rather than
 * borrowing the light palette: the navy page-ink as backdrop, and a near-white
 * for copy that sits on it (white on #0F172A is 17.85 : 1).
 */
private val ViewportBackdrop = Color(0xFF0F172A)
private val ViewportTextPrimary = Color(0xFFF1F5F9)
