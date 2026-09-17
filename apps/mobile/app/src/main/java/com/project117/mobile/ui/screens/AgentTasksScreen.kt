package com.project117.mobile.ui.screens
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.PrecisionManufacturing
import androidx.compose.material.icons.filled.SmartToy
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
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
class AgentTasksViewModel @Inject constructor(
    private val fieldBackend: FieldBackend,
    private val sessionManager: SessionManager
) : ViewModel() {

    val appMode: StateFlow<AppMode> = sessionManager.appMode

    private val _agentTasks = MutableStateFlow<List<AgentTask>>(emptyList())
    val agentTasks: StateFlow<List<AgentTask>> = _agentTasks.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    init {
        loadAgentTasks()
    }

    fun loadAgentTasks() {
        viewModelScope.launch {
            _isLoading.value = true
            when (val res = fieldBackend.getAgentTasks()) {
                is BackendResult.Success -> _agentTasks.value = res.data
                else -> Unit
            }
            _isLoading.value = false
        }
    }

    fun acknowledgeTask(id: String) {
        viewModelScope.launch {
            fieldBackend.acknowledgeAgentTask(id)
            loadAgentTasks()
        }
    }

    fun completeTask(id: String) {
        viewModelScope.launch {
            fieldBackend.completeAgentTask(id, "On-site verification complete. Vibration spectrum confirmed at 7.8 mm/s.", listOf("EVID-001"))
            loadAgentTasks()
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AgentTasksScreen(
    onNavigateBack: () -> Unit,
    onNavigateToInspection: (String, String) -> Unit,
    viewModel: AgentTasksViewModel = hiltViewModel()
) {
    val mode by viewModel.appMode.collectAsState()
    val tasks by viewModel.agentTasks.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()

    Scaffold(
        topBar = {
            AppTopBar(
                title = "Agent Field Tasks",
                subtitle = "AUTONOMOUS DISPATCH",
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

            if (isLoading) {
                LoadingStateView("Loading agent tasks…")
            } else if (tasks.isEmpty()) {
                P117EmptyState(
                    icon = Icons.Default.PrecisionManufacturing,
                    title = "No agent tasks dispatched"
                )
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(ScreenPadding),
                    verticalArrangement = Arrangement.spacedBy(ListItemSpacing)
                ) {
                    items(tasks) { task ->
                        val (statusTone, statusText) = when (task.status) {
                            AgentTaskStatus.PENDING -> Pair(StatusTone.WARNING, "PENDING")
                            AgentTaskStatus.ACKNOWLEDGED -> Pair(StatusTone.INFO, "ACKNOWLEDGED")
                            AgentTaskStatus.IN_PROGRESS -> Pair(StatusTone.INFO, "IN PROGRESS")
                            AgentTaskStatus.COMPLETED -> Pair(StatusTone.SUCCESS, "COMPLETED")
                            AgentTaskStatus.FAILED -> Pair(StatusTone.CRITICAL, "FAILED")
                        }

                        P117Card(
                            modifier = Modifier.fillMaxWidth(),
                            cardType = P117CardType.ASSISTANT,
                            accentColor = statusToneColor(statusTone)
                        ) {
                            Column(modifier = Modifier.padding(CardContentPadding)) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Row(
                                        modifier = Modifier.weight(1f),
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        P117IconContainer(
                                            icon = Icons.Default.SmartToy,
                                            tint = IndustrialTeal,
                                            size = 36.dp
                                        )
                                        Spacer(modifier = Modifier.width(10.dp))
                                        EquipmentTag(tag = task.id)
                                    }
                                    Spacer(modifier = Modifier.width(8.dp))
                                    StatusChip(label = statusText, tone = statusTone)
                                }

                                Spacer(modifier = Modifier.height(12.dp))
                                Text(
                                    text = task.title,
                                    style = MaterialTheme.typography.titleMedium,
                                    color = IndustrialTextPrimary
                                )
                                Spacer(modifier = Modifier.height(6.dp))
                                Text(
                                    text = task.description,
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = IndustrialTextSecondary
                                )
                                Spacer(modifier = Modifier.height(10.dp))
                                KeyValueRow(label = "Originating agent", value = task.source, monoValue = false)
                                KeyValueRow(label = "Target equipment", value = "${task.equipmentName ?: "N/A"} · ${task.equipmentId ?: "N/A"}", monoValue = false)

                                Spacer(modifier = Modifier.height(12.dp))
                                // Machine-authored note: a sunken, teal-railed well so the
                                // agent's own words read differently from operator copy.
                                P117Card(
                                    colors = CardDefaults.cardColors(containerColor = IndustrialDarkSurfaceSunken),
                                    border = BorderStroke(1.dp, IndustrialBorderSubtle),
                                    cardType = P117CardType.ASSISTANT,
                                    accentColor = IndustrialTeal,
                                    modifier = Modifier.fillMaxWidth()
                                ) {
                                    Column(modifier = Modifier.padding(12.dp)) {
                                        P117Eyebrow(
                                            text = "AUTONOMOUS AGENT INSTRUCTIONS",
                                            color = IndustrialTeal
                                        )
                                        Spacer(modifier = Modifier.height(6.dp))
                                        Text(
                                            text = task.instructions,
                                            style = MaterialTheme.typography.bodySmall,
                                            color = IndustrialTextPrimary
                                        )
                                    }
                                }

                                Spacer(modifier = Modifier.height(14.dp))

                                when (task.status) {
                                    AgentTaskStatus.PENDING -> {
                                        AppButton(
                                            onClick = { viewModel.acknowledgeTask(task.id) },
                                            modifier = Modifier.fillMaxWidth()
                                        ) {
                                            Text("Acknowledge & Accept Task", fontWeight = FontWeight.Bold)
                                        }
                                    }
                                    AgentTaskStatus.IN_PROGRESS, AgentTaskStatus.ACKNOWLEDGED -> {
                                        Row(
                                            modifier = Modifier.fillMaxWidth(),
                                            horizontalArrangement = Arrangement.spacedBy(ListItemSpacing)
                                        ) {
                                            AppOutlinedButton(
                                                onClick = {
                                                    onNavigateToInspection(task.workOrderId ?: "WO-2026-0891", task.equipmentId ?: "EQ-P102")
                                                },
                                                contentPadding = PaddingValues(horizontal = 12.dp, vertical = 12.dp),
                                                modifier = Modifier.weight(1f)
                                            ) {
                                                Text("Capture Evidence", maxLines = 1)
                                            }

                                            AppButton(
                                                onClick = { viewModel.completeTask(task.id) },
                                                colors = p117SuccessButtonColors(),
                                                contentPadding = PaddingValues(horizontal = 12.dp, vertical = 12.dp),
                                                modifier = Modifier.weight(1f)
                                            ) {
                                                Text("Complete Task", color = IndustrialTextOnAccent, fontWeight = FontWeight.Bold, maxLines = 1)
                                            }
                                        }
                                    }
                                    AgentTaskStatus.COMPLETED -> {
                                        StatusBanner(
                                            text = "Results delivered to AI Orchestrator",
                                            tone = StatusTone.SUCCESS
                                        )
                                    }
                                    else -> Unit
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
