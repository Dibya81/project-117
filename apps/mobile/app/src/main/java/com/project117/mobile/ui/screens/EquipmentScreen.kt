package com.project117.mobile.ui.screens
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.project117.mobile.data.local.preferences.SessionManager
import com.project117.mobile.domain.backend.FieldBackend
import com.project117.mobile.domain.model.AppMode
import com.project117.mobile.domain.model.BackendResult
import com.project117.mobile.domain.model.Equipment
import com.project117.mobile.domain.model.EquipmentReading
import com.project117.mobile.ui.components.*
import com.project117.mobile.ui.theme.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class EquipmentViewModel @Inject constructor(
    private val fieldBackend: FieldBackend,
    private val sessionManager: SessionManager,
    savedStateHandle: SavedStateHandle
) : ViewModel() {

    val appMode: StateFlow<AppMode> = sessionManager.appMode

    private val _equipmentList = MutableStateFlow<List<Equipment>>(emptyList())
    val equipmentList: StateFlow<List<Equipment>> = _equipmentList.asStateFlow()

    private val _selectedEquipment = MutableStateFlow<Equipment?>(null)
    val selectedEquipment: StateFlow<Equipment?> = _selectedEquipment.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    val searchQuery = MutableStateFlow("")

    init {
        val eqId: String? = savedStateHandle["equipmentId"]
        if (eqId != null) {
            loadEquipmentDetail(eqId)
        } else {
            loadEquipmentList()
        }
    }

    fun loadEquipmentList() {
        viewModelScope.launch {
            _isLoading.value = true
            when (val res = fieldBackend.getEquipmentList()) {
                is BackendResult.Success -> _equipmentList.value = res.data
                else -> Unit
            }
            _isLoading.value = false
        }
    }

    fun loadEquipmentDetail(id: String) {
        viewModelScope.launch {
            _isLoading.value = true
            when (val res = fieldBackend.getEquipment(id)) {
                is BackendResult.Success -> _selectedEquipment.value = res.data
                else -> Unit
            }
            _isLoading.value = false
        }
    }
}

/*
 * Equipment registry — visual identity: "asset directory".
 *
 * Blue is the asset identity colour. Every row is an [EquipmentCard] whose rail
 * and icon container carry the *live* equipment status, so a degraded pump is
 * amber down its leading edge without reading a word.
 *
 * The detail screen turns each sensor into a single-purpose instrument tile:
 * one big monospace reading, one status chip, one timestamp, rail coloured by
 * whether the reading is in spec. Nothing is invented — the summary strip counts
 * only readings that actually came back from the backend.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EquipmentListScreen(
    onNavigateBack: () -> Unit,
    onNavigateToDetail: (String) -> Unit,
    onNavigateToScan: () -> Unit,
    viewModel: EquipmentViewModel = hiltViewModel()
) {
    val mode by viewModel.appMode.collectAsState()
    val list by viewModel.equipmentList.collectAsState()
    val search by viewModel.searchQuery.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()

    val filteredList = remember(list, search) {
        if (search.isBlank()) list else list.filter {
            it.name.contains(search, ignoreCase = true) ||
            it.id.contains(search, ignoreCase = true) ||
            it.type.contains(search, ignoreCase = true) ||
            it.location.contains(search, ignoreCase = true)
        }
    }

    val degradedCount = remember(list) {
        list.count { it.status != com.project117.mobile.domain.model.EquipmentStatus.OPERATIONAL }
    }

    Scaffold(
        topBar = {
            AppTopBar(
                title = "Equipment Registry",
                subtitle = "ASSET DIRECTORY",
                onNavigateBack = onNavigateBack,
                actions = {
                    IconButton(onClick = onNavigateToScan) {
                        Icon(Icons.Default.QrCodeScanner, contentDescription = "Scan")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            DemoModeBanner(mode)

            // Registry summary — counts derived from the loaded list only.
            if (list.isNotEmpty()) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = ScreenPadding, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    StatusChip(label = "${list.size} ASSETS", tone = StatusTone.INFO)
                    StatusChip(
                        label = if (degradedCount == 0) "ALL OPERATIONAL" else "$degradedCount NEED ATTENTION",
                        tone = if (degradedCount == 0) StatusTone.SUCCESS else StatusTone.WARNING
                    )
                }
            }

            OutlinedTextField(
                value = search,
                onValueChange = { viewModel.searchQuery.value = it },
                placeholder = { Text("Search by name, ID, or location…") },
                leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = ScreenPadding, vertical = 4.dp),
                singleLine = true
            )

            if (isLoading) {
                LoadingStateView("Loading equipment assets…")
            } else if (filteredList.isEmpty()) {
                P117EmptyState(
                    icon = Icons.Default.SearchOff,
                    title = "No matching assets",
                    message = if (search.isBlank()) {
                        "The equipment registry returned no assets."
                    } else {
                        "Nothing in the registry matches \"$search\"."
                    },
                    tone = StatusTone.NEUTRAL
                )
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(
                        start = ScreenPadding,
                        end = ScreenPadding,
                        top = 8.dp,
                        bottom = ScreenPadding
                    ),
                    verticalArrangement = Arrangement.spacedBy(ListItemSpacing)
                ) {
                    items(filteredList) { eq ->
                        EquipmentCard(
                            equipment = eq,
                            onClick = { onNavigateToDetail(eq.id) }
                        )
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EquipmentDetailScreen(
    equipmentId: String,
    onNavigateBack: () -> Unit,
    onNavigateToReportIssue: (String) -> Unit,
    onNavigateToSop: () -> Unit,
    viewModel: EquipmentViewModel = hiltViewModel()
) {
    val mode by viewModel.appMode.collectAsState()
    val equipment by viewModel.selectedEquipment.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()

    LaunchedEffect(equipmentId) {
        viewModel.loadEquipmentDetail(equipmentId)
    }

    Scaffold(
        topBar = {
            AppTopBar(
                title = equipment?.name ?: "Equipment Detail",
                subtitle = equipmentId,
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

            if (isLoading || equipment == null) {
                LoadingStateView("Loading equipment telemetry…")
            } else {
                val eq = equipment!!
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .verticalScroll(rememberScrollState())
                        .padding(ScreenPadding),
                    verticalArrangement = Arrangement.spacedBy(ScreenSectionSpacing)
                ) {
                    // ---- Asset header (blue identity, status rail) ----------
                    P117Card(
                        modifier = Modifier.fillMaxWidth(),
                        cardType = P117CardType.EQUIPMENT,
                        accentColor = equipmentStatusAccent(eq.status)
                    ) {
                        Column(modifier = Modifier.padding(CardContentPadding)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                P117IconContainer(
                                    icon = Icons.Default.PrecisionManufacturing,
                                    tint = equipmentStatusAccent(eq.status),
                                    size = 52.dp
                                )
                                Spacer(modifier = Modifier.width(12.dp))
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(
                                        text = eq.name,
                                        style = MaterialTheme.typography.headlineSmall,
                                        color = IndustrialTextPrimary,
                                        maxLines = 2,
                                        overflow = TextOverflow.Ellipsis
                                    )
                                    Spacer(modifier = Modifier.height(4.dp))
                                    Text(
                                        text = eq.type,
                                        style = MaterialTheme.typography.bodySmall,
                                        color = IndustrialTextSecondary,
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis
                                    )
                                }
                                Spacer(modifier = Modifier.width(8.dp))
                                EquipmentStatusBadge(eq.status)
                            }

                            Spacer(modifier = Modifier.height(14.dp))
                            P117Divider()
                            Spacer(modifier = Modifier.height(12.dp))

                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(10.dp)
                            ) {
                                EquipmentTag(tag = eq.id)
                                P117MetaRow(
                                    text = eq.location,
                                    icon = Icons.Default.Place,
                                    modifier = Modifier.weight(1f)
                                )
                            }

                            Spacer(modifier = Modifier.height(12.dp))
                            KeyValueRow(label = "Location", value = eq.location, monoValue = false)
                            KeyValueRow(label = "QR tag", value = eq.qrCode ?: "None")
                            KeyValueRow(label = "Serial", value = eq.serialNumber ?: "N/A")
                            KeyValueRow(label = "Next maintenance", value = eq.nextMaintenanceDate ?: "N/A")
                        }
                    }

                    // ---- Telemetry --------------------------------------------
                    val nominalCount = eq.readings.count { it.isNominal }
                    val outOfSpecCount = eq.readings.size - nominalCount

                    SectionHeader(
                        text = "Live Telemetry & Sensor Readings",
                        trailing = {
                            if (eq.readings.isNotEmpty()) {
                                StatusChip(
                                    label = if (outOfSpecCount == 0) "ALL NOMINAL" else "$outOfSpecCount OUT OF SPEC",
                                    tone = if (outOfSpecCount == 0) StatusTone.SUCCESS else StatusTone.CRITICAL
                                )
                            }
                        }
                    )

                    eq.readings.forEach { reading ->
                        TelemetryTile(reading = reading)
                    }

                    if (eq.readings.isEmpty()) {
                        P117Card(modifier = Modifier.fillMaxWidth()) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(CardContentPadding),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                P117IconContainer(
                                    icon = Icons.Default.SensorsOff,
                                    tint = IndustrialTextMuted,
                                    size = 40.dp
                                )
                                Spacer(modifier = Modifier.width(12.dp))
                                Text(
                                    text = "No sensor readings reported for this asset",
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = IndustrialTextSecondary
                                )
                            }
                        }
                    }

                    // ---- Actions ----------------------------------------------
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(ListItemSpacing)
                    ) {
                        AppButton(
                            onClick = { onNavigateToReportIssue(eq.id) },
                            colors = p117WarningButtonColors(),
                            contentPadding = PaddingValues(horizontal = 12.dp, vertical = 12.dp),
                            modifier = Modifier.weight(1f)
                        ) {
                            Icon(Icons.Default.ReportProblem, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(6.dp))
                            Text("Report Issue", fontWeight = FontWeight.Bold, maxLines = 1)
                        }
                        AppOutlinedButton(
                            onClick = onNavigateToSop,
                            contentPadding = PaddingValues(horizontal = 12.dp, vertical = 12.dp),
                            modifier = Modifier.weight(1f)
                        ) {
                            Text("View SOPs", maxLines = 1)
                        }
                    }
                }
            }
        }
    }
}

/**
 * One sensor = one instrument tile. The rail and the chip carry the same
 * verdict, the value is the only large element, and the timestamp sits in the
 * monospace register so a column of tiles reads like a chart recorder.
 */
@Composable
private fun TelemetryTile(reading: EquipmentReading) {
    val tone = if (reading.isNominal) StatusTone.SUCCESS else StatusTone.CRITICAL
    val accent = statusToneColor(tone)

    P117Card(
        modifier = Modifier.fillMaxWidth(),
        cardType = P117CardType.INSPECTION,
        accentColor = accent
    ) {
        Column(modifier = Modifier.padding(CardContentPadding)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = reading.parameter,
                    style = MaterialTheme.typography.titleSmall,
                    color = IndustrialTextPrimary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f)
                )
                Spacer(modifier = Modifier.width(8.dp))
                StatusChip(
                    label = if (reading.isNominal) "NOMINAL" else "OUT OF SPEC",
                    tone = tone
                )
            }

            Spacer(modifier = Modifier.height(10.dp))
            P117Divider()
            Spacer(modifier = Modifier.height(10.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.Bottom
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    P117Eyebrow(text = "Last sampled")
                    Spacer(modifier = Modifier.height(3.dp))
                    Text(
                        text = reading.timestamp,
                        style = MonoMetaStyle,
                        color = IndustrialTextSecondary
                    )
                }
                Spacer(modifier = Modifier.width(10.dp))
                ReadingValue(
                    value = "${reading.value} ${reading.unit}",
                    color = accent
                )
            }
        }
    }
}
