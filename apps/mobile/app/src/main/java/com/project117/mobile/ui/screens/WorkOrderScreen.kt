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
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.project117.mobile.data.local.preferences.SessionManager
import com.project117.mobile.domain.backend.FieldBackend
import com.project117.mobile.domain.model.*
import com.project117.mobile.ui.components.*
import com.project117.mobile.ui.theme.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class WorkOrderViewModel @Inject constructor(
    private val fieldBackend: FieldBackend,
    private val sessionManager: SessionManager,
    savedStateHandle: SavedStateHandle
) : ViewModel() {

    val appMode: StateFlow<AppMode> = sessionManager.appMode
    val userSession: StateFlow<UserSession?> = sessionManager.userSession

    private val _workOrders = MutableStateFlow<List<WorkOrder>>(emptyList())
    val workOrders: StateFlow<List<WorkOrder>> = _workOrders.asStateFlow()

    private val _selectedWorkOrder = MutableStateFlow<WorkOrder?>(null)
    val selectedWorkOrder: StateFlow<WorkOrder?> = _selectedWorkOrder.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    val selectedFilter = MutableStateFlow("ALL")

    init {
        val woId: String? = savedStateHandle["workOrderId"]
        if (woId != null) {
            loadWorkOrderDetail(woId)
        } else {
            loadWorkOrders()
        }
    }

    fun loadWorkOrders() {
        viewModelScope.launch {
            _isLoading.value = true
            when (val res = fieldBackend.getWorkOrders()) {
                is BackendResult.Success -> _workOrders.value = res.data
                else -> Unit
            }
            _isLoading.value = false
        }
    }

    fun loadWorkOrderDetail(id: String) {
        viewModelScope.launch {
            _isLoading.value = true
            when (val res = fieldBackend.getWorkOrder(id)) {
                is BackendResult.Success -> _selectedWorkOrder.value = res.data
                else -> Unit
            }
            _isLoading.value = false
        }
    }

    fun updateStatus(newStatus: WorkOrderStatus) {
        val wo = _selectedWorkOrder.value ?: return
        viewModelScope.launch {
            _isLoading.value = true
            when (val res = fieldBackend.updateWorkOrder(wo.id, newStatus, null)) {
                is BackendResult.Success -> {
                    _selectedWorkOrder.value = res.data
                    loadWorkOrders()
                }
                else -> Unit
            }
            _isLoading.value = false
        }
    }

    fun toggleStepCompletion(stepNumber: Int) {
        val wo = _selectedWorkOrder.value ?: return
        val updatedSteps = wo.steps.map { step ->
            if (step.stepNumber == stepNumber) step.copy(isCompleted = !step.isCompleted) else step
        }
        _selectedWorkOrder.value = wo.copy(steps = updatedSteps)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WorkOrderListScreen(
    onNavigateBack: () -> Unit,
    onNavigateToDetail: (String) -> Unit,
    viewModel: WorkOrderViewModel = hiltViewModel()
) {
    val mode by viewModel.appMode.collectAsState()
    val list by viewModel.workOrders.collectAsState()
    val filter by viewModel.selectedFilter.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()

    val filtered = remember(list, filter) {
        when (filter) {
            "IN_PROGRESS" -> list.filter { it.status == WorkOrderStatus.IN_PROGRESS }
            "CRITICAL" -> list.filter { it.priority == WorkOrderPriority.CRITICAL }
            else -> list
        }
    }

    Scaffold(
        topBar = {
            AppTopBar(
                title = "Work Orders",
                subtitle = "FIELD QUEUE",
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

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = ScreenPadding, vertical = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                FilterChip(
                    selected = filter == "ALL",
                    onClick = { viewModel.selectedFilter.value = "ALL" },
                    label = { Text("All (${list.size})") }
                )
                FilterChip(
                    selected = filter == "IN_PROGRESS",
                    onClick = { viewModel.selectedFilter.value = "IN_PROGRESS" },
                    label = { Text("In Progress") }
                )
                FilterChip(
                    selected = filter == "CRITICAL",
                    onClick = { viewModel.selectedFilter.value = "CRITICAL" },
                    label = { Text("Critical") }
                )
            }

            if (isLoading) {
                LoadingStateView("Loading work orders…")
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(
                        start = ScreenPadding,
                        end = ScreenPadding,
                        bottom = ScreenPadding
                    ),
                    verticalArrangement = Arrangement.spacedBy(ListItemSpacing)
                ) {
                    items(filtered) { wo ->
                        WorkOrderCard(
                            workOrder = wo,
                            onClick = { onNavigateToDetail(wo.id) },
                            modifier = Modifier.fillMaxWidth()
                        )
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WorkOrderDetailScreen(
    workOrderId: String,
    onNavigateBack: () -> Unit,
    onNavigateToInspection: (String, String) -> Unit,
    onNavigateToSop: () -> Unit,
    viewModel: WorkOrderViewModel = hiltViewModel()
) {
    val mode by viewModel.appMode.collectAsState()
    val wo by viewModel.selectedWorkOrder.collectAsState()
    val session by viewModel.userSession.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()

    var showCompleteDialog by remember { mutableStateOf(false) }

    LaunchedEffect(workOrderId) {
        viewModel.loadWorkOrderDetail(workOrderId)
    }

    if (showCompleteDialog) {
        ConsequentialActionDialog(
            title = "Complete Work Order?",
            message = "Marking ${wo?.id} as COMPLETED indicates all safety inspections and evidence submissions have been satisfied.",
            confirmText = "Complete Order",
            onConfirm = {
                showCompleteDialog = false
                viewModel.updateStatus(WorkOrderStatus.COMPLETED)
            },
            onDismiss = { showCompleteDialog = false }
        )
    }

    Scaffold(
        topBar = {
            AppTopBar(
                title = wo?.id ?: "Work Order",
                subtitle = wo?.title,
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

            if (isLoading || wo == null) {
                LoadingStateView("Loading work order details…")
            } else {
                val item = wo!!
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .verticalScroll(rememberScrollState())
                        .padding(ScreenPadding),
                    verticalArrangement = Arrangement.spacedBy(ScreenSectionSpacing)
                ) {
                    P117Card(
                        modifier = Modifier.fillMaxWidth(),
                        cardType = P117CardType.WORK_ORDER,
                        accentColor = priorityAccent(item.priority)
                    ) {
                        Column(modifier = Modifier.padding(CardContentPadding)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                P117IconContainer(
                                    icon = Icons.Default.Assignment,
                                    tint = IndustrialWarningAmber,
                                    size = 44.dp
                                )
                                Spacer(modifier = Modifier.width(12.dp))
                                Column(modifier = Modifier.weight(1f)) {
                                    P117Eyebrow("Work order")
                                    Spacer(modifier = Modifier.height(4.dp))
                                    Text(
                                        text = item.title,
                                        style = MaterialTheme.typography.headlineSmall,
                                        color = IndustrialTextPrimary
                                    )
                                }
                            }
                            Spacer(modifier = Modifier.height(12.dp))
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                PriorityBadge(item.priority)
                                StatusChip(
                                    label = item.status.name,
                                    tone = when (item.status) {
                                        WorkOrderStatus.COMPLETED -> StatusTone.SUCCESS
                                        WorkOrderStatus.IN_PROGRESS -> StatusTone.INFO
                                        WorkOrderStatus.CANCELLED -> StatusTone.NEUTRAL
                                        else -> StatusTone.WARNING
                                    }
                                )
                            }
                            Spacer(modifier = Modifier.height(12.dp))
                            Text(
                                item.description,
                                style = MaterialTheme.typography.bodyMedium,
                                color = IndustrialTextSecondary
                            )
                            Spacer(modifier = Modifier.height(14.dp))
                            P117Divider()
                            Spacer(modifier = Modifier.height(10.dp))
                            KeyValueRow(label = "Target equipment", value = item.equipmentName ?: "N/A", monoValue = false)
                            KeyValueRow(label = "Equipment ID", value = item.equipmentId ?: "N/A")
                            KeyValueRow(label = "Assigned to", value = item.assignedTo ?: "Unassigned", monoValue = false)
                            KeyValueRow(label = "Due", value = item.dueDate ?: "None")
                        }
                    }

                    // Checklist Steps Section
                    SectionHeader(text = "Inspection Steps & Checklist")

                    val completedSteps = item.steps.count { it.isCompleted }
                    val totalSteps = item.steps.size
                    if (totalSteps > 0) {
                        P117Card(modifier = Modifier.fillMaxWidth()) {
                            Column(modifier = Modifier.padding(CardContentPadding)) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    P117Eyebrow("Checklist progress")
                                    Text(
                                        text = "$completedSteps / $totalSteps steps",
                                        style = EquipmentTagStyle,
                                        color = IndustrialTextSecondary
                                    )
                                }
                                Spacer(modifier = Modifier.height(8.dp))
                                P117ProgressBar(
                                    progress = completedSteps.toFloat() / totalSteps,
                                    color = if (completedSteps == totalSteps) IndustrialNominalGreen else IndustrialWarningAmber
                                )
                            }
                        }
                    }

                    item.steps.forEach { step ->
                        P117Card(
                            modifier = Modifier.fillMaxWidth(),
                            cardType = P117CardType.WORK_ORDER,
                            accentColor = if (step.isCompleted) IndustrialNominalGreen else IndustrialWarningAmber
                        ) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(horizontal = 8.dp, vertical = 8.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Checkbox(
                                    checked = step.isCompleted,
                                    onCheckedChange = { viewModel.toggleStepCompletion(step.stepNumber) }
                                )
                                Spacer(modifier = Modifier.width(4.dp))
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(
                                        text = "${step.stepNumber}. ${step.title}",
                                        style = MaterialTheme.typography.titleSmall,
                                        color = IndustrialTextPrimary
                                    )
                                    Spacer(modifier = Modifier.height(2.dp))
                                    Text(
                                        step.description,
                                        style = MaterialTheme.typography.bodySmall,
                                        color = IndustrialTextSecondary
                                    )
                                    if (step.evidenceRequired) {
                                        Spacer(modifier = Modifier.height(6.dp))
                                        StatusChip(label = "EVIDENCE REQUIRED — PHOTO / MEASUREMENT", tone = StatusTone.WARNING)
                                    }
                                }
                            }
                        }
                    }

                    // Action Buttons
                    AppButton(
                        onClick = {
                            onNavigateToInspection(item.id, item.equipmentId ?: "EQ-P102")
                        },
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Icon(Icons.Default.CameraAlt, contentDescription = null)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("Open Inspection & Capture Evidence", fontWeight = FontWeight.Bold, color = IndustrialTextOnAccent)
                    }

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(ListItemSpacing)
                    ) {
                        AppOutlinedButton(
                            onClick = onNavigateToSop,
                            modifier = Modifier.weight(1f)
                        ) {
                            Text("Open SOP")
                        }

                        if (item.status != WorkOrderStatus.COMPLETED) {
                            AppButton(
                                onClick = { showCompleteDialog = true },
                                colors = p117SuccessButtonColors(),
                                modifier = Modifier.weight(1f)
                            ) {
                                Text("Complete Order", fontWeight = FontWeight.Bold, color = IndustrialTextOnAccent)
                            }
                        }
                    }
                }
            }
        }
    }
}
