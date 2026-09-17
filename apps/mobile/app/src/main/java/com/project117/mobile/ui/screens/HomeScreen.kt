package com.project117.mobile.ui.screens
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.project117.mobile.data.local.preferences.SessionManager
import com.project117.mobile.data.sync.SyncManager
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
class HomeViewModel @Inject constructor(
    private val sessionManager: SessionManager,
    private val syncManager: SyncManager,
    private val fieldBackend: FieldBackend
) : ViewModel() {

    val appMode: StateFlow<AppMode> = sessionManager.appMode
    val userSession: StateFlow<UserSession?> = sessionManager.userSession

    private val _pendingSyncCount = MutableStateFlow(0)
    val pendingSyncCount: StateFlow<Int> = _pendingSyncCount.asStateFlow()

    private val _workOrders = MutableStateFlow<List<WorkOrder>>(emptyList())
    val workOrders: StateFlow<List<WorkOrder>> = _workOrders.asStateFlow()

    private val _agentTasks = MutableStateFlow<List<AgentTask>>(emptyList())
    val agentTasks: StateFlow<List<AgentTask>> = _agentTasks.asStateFlow()

    private val _approvals = MutableStateFlow<List<Approval>>(emptyList())
    val approvals: StateFlow<List<Approval>> = _approvals.asStateFlow()

    private val _notifications = MutableStateFlow<List<AppNotification>>(emptyList())
    val notifications: StateFlow<List<AppNotification>> = _notifications.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    init {
        loadDashboardData()
        observeSyncCount()
    }

    private fun observeSyncCount() {
        viewModelScope.launch {
            syncManager.observePendingCount().collect { count ->
                _pendingSyncCount.value = count
            }
        }
    }

    fun loadDashboardData() {
        viewModelScope.launch {
            _isLoading.value = true
            when (val res = fieldBackend.getWorkOrders()) {
                is BackendResult.Success -> _workOrders.value = res.data
                else -> Unit
            }
            when (val res = fieldBackend.getAgentTasks()) {
                is BackendResult.Success -> _agentTasks.value = res.data
                else -> Unit
            }
            when (val res = fieldBackend.getApprovals()) {
                is BackendResult.Success -> _approvals.value = res.data
                else -> Unit
            }
            when (val res = fieldBackend.getNotifications()) {
                is BackendResult.Success -> _notifications.value = res.data
                else -> Unit
            }
            _isLoading.value = false
        }
    }

    fun logout() {
        sessionManager.clearSession()
    }
}

/*
 * Home is the field-operations command centre.
 *
 * Visual identity: a white "shift board" on the near-white page. The operator
 * identity sits at the top in a blue-accented card, three large quick-action
 * tiles carry the only saturated colour on the screen, and the two attention
 * banners below them (supervisor decisions / agent dispatch) are the only cards
 * on the screen allowed to shout — red for a human decision that is blocking,
 * teal for an autonomous dispatch. Everything else is quiet white.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    onNavigateToScan: () -> Unit,
    onNavigateToEquipment: () -> Unit,
    onNavigateToWorkOrders: () -> Unit,
    onNavigateToWorkOrderDetail: (String) -> Unit,
    onNavigateToApprovals: () -> Unit,
    onNavigateToAgentTasks: () -> Unit,
    onNavigateToReportIssue: () -> Unit,
    onNavigateToSop: () -> Unit,
    onNavigateToNotifications: () -> Unit,
    onNavigateToAssistant: () -> Unit,
    onNavigateToSyncStatus: () -> Unit,
    onNavigateToSettings: () -> Unit,
    onLogout: () -> Unit,
    viewModel: HomeViewModel = hiltViewModel()
) {
    val mode by viewModel.appMode.collectAsState()
    val session by viewModel.userSession.collectAsState()
    val syncCount by viewModel.pendingSyncCount.collectAsState()
    val workOrders by viewModel.workOrders.collectAsState()
    val agentTasks by viewModel.agentTasks.collectAsState()
    val approvals by viewModel.approvals.collectAsState()
    val notifications by viewModel.notifications.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()

    val role = session?.role ?: UserRole.TECHNICIAN
    val unreadCount = notifications.count { !it.isRead }
    val pendingApprovals = approvals.filter { it.status == ApprovalStatus.PENDING }
    val pendingTasks = agentTasks.filter { it.status != AgentTaskStatus.COMPLETED }
    val openWorkOrders = workOrders.filter { it.status != WorkOrderStatus.COMPLETED }

    Scaffold(
        topBar = {
            AppTopBar(
                title = "Project 117",
                subtitle = session?.displayName ?: "Field Operations",
                actions = {
                    IconButton(onClick = onNavigateToNotifications) {
                        BadgedBox(
                            badge = {
                                if (unreadCount > 0) {
                                    Badge { Text("$unreadCount") }
                                }
                            }
                        ) {
                            Icon(Icons.Default.Notifications, contentDescription = "Notifications")
                        }
                    }
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
        ) {
            DemoModeBanner(mode)
            ConnectionStatusBar(
                mode = mode,
                isOnline = true,
                pendingSyncCount = syncCount
            )

            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(rememberScrollState())
                    .padding(ScreenPadding),
                verticalArrangement = Arrangement.spacedBy(ScreenSectionSpacing)
            ) {
                // ---- Operator identity -------------------------------------
                P117Card(modifier = Modifier.fillMaxWidth()) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(CardContentPadding),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        P117IconContainer(
                            icon = Icons.Default.Engineering,
                            tint = IndustrialCyan,
                            size = 48.dp
                        )
                        Spacer(modifier = Modifier.width(12.dp))
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = session?.displayName ?: "Field Operator",
                                style = MaterialTheme.typography.titleMedium,
                                color = IndustrialTextPrimary,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis
                            )
                            Spacer(modifier = Modifier.height(6.dp))
                            StatusChip(label = "ROLE: ${role.name}", tone = StatusTone.INFO)
                        }
                        Spacer(modifier = Modifier.width(8.dp))
                        AppOutlinedButton(
                            onClick = {
                                viewModel.logout()
                                onLogout()
                            },
                            contentPadding = PaddingValues(horizontal = 14.dp, vertical = 10.dp)
                        ) {
                            Text("Sign Out", maxLines = 1)
                        }
                    }
                }

                // ---- Quick action grid -------------------------------------
                SectionHeader(text = "Quick Field Actions")

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(ListItemSpacing)
                ) {
                    QuickActionCard(
                        icon = Icons.Default.QrCodeScanner,
                        title = "Scan QR",
                        subtitle = "Identify Asset",
                        color = IndustrialCyan,
                        onClick = onNavigateToScan,
                        modifier = Modifier.weight(1f)
                    )
                    QuickActionCard(
                        icon = Icons.Default.ReportProblem,
                        title = "Report Issue",
                        subtitle = "Flag Anomaly",
                        color = IndustrialWarningAmber,
                        onClick = onNavigateToReportIssue,
                        modifier = Modifier.weight(1f)
                    )
                    QuickActionCard(
                        icon = Icons.Default.SmartToy,
                        title = "Assistant",
                        subtitle = "Ask AI",
                        color = IndustrialTeal,
                        onClick = onNavigateToAssistant,
                        modifier = Modifier.weight(1f)
                    )
                }

                // ---- Supervisor decision queue (role gated) -----------------
                if (role == UserRole.SUPERVISOR || role == UserRole.ADMIN) {
                    val blocked = pendingApprovals.isNotEmpty()
                    P117Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(
                            containerColor = if (blocked) {
                                statusToneContainer(StatusTone.CRITICAL)
                            } else {
                                P117CardSurface
                            }
                        ),
                        cardType = P117CardType.ALERT,
                        accentColor = if (blocked) IndustrialCriticalRed else IndustrialNominalGreen,
                        onClick = onNavigateToApprovals
                    ) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(16.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            P117IconContainer(
                                icon = Icons.Default.Gavel,
                                tint = if (blocked) IndustrialCriticalRed else IndustrialTextMuted,
                                size = 44.dp,
                                contentDescription = "Approvals"
                            )
                            Spacer(modifier = Modifier.width(12.dp))
                            Column(modifier = Modifier.weight(1f)) {
                                P117Eyebrow(
                                    text = if (blocked) "Decision required" else "Decision queue",
                                    color = if (blocked) IndustrialCriticalRed else IndustrialTextMuted
                                )
                                Spacer(modifier = Modifier.height(4.dp))
                                Text(
                                    text = "Pending Supervisor Approvals",
                                    style = MaterialTheme.typography.titleSmall,
                                    color = IndustrialTextPrimary,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis
                                )
                                Spacer(modifier = Modifier.height(3.dp))
                                Text(
                                    text = if (blocked) "${pendingApprovals.size} require decision (e.g. Pump P-102)" else "No pending approvals",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = IndustrialTextSecondary,
                                    maxLines = 2,
                                    overflow = TextOverflow.Ellipsis
                                )
                            }
                            Spacer(modifier = Modifier.width(8.dp))
                            Icon(
                                imageVector = Icons.Default.ChevronRight,
                                contentDescription = null,
                                tint = IndustrialTextMuted
                            )
                        }
                    }
                }

                // ---- Autonomous agent dispatch ------------------------------
                if (pendingTasks.isNotEmpty()) {
                    val task = pendingTasks.first()
                    P117Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(
                            containerColor = statusToneContainer(StatusTone.INFO)
                        ),
                        cardType = P117CardType.ASSISTANT,
                        accentColor = IndustrialTeal,
                        onClick = onNavigateToAgentTasks
                    ) {
                        Column(modifier = Modifier.padding(CardContentPadding)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Icon(
                                        Icons.Default.PrecisionManufacturing,
                                        contentDescription = null,
                                        tint = IndustrialTeal,
                                        modifier = Modifier.size(18.dp)
                                    )
                                    Spacer(modifier = Modifier.width(6.dp))
                                    Text(
                                        "AGENT FIELD TASK",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = IndustrialTeal
                                    )
                                }
                                Text(
                                    "ID: ${task.id}",
                                    style = MonoMetaStyle,
                                    color = IndustrialTextMuted
                                )
                            }
                            Spacer(modifier = Modifier.height(8.dp))
                            Text(
                                task.title,
                                style = MaterialTheme.typography.titleSmall,
                                color = IndustrialTextPrimary,
                                maxLines = 2,
                                overflow = TextOverflow.Ellipsis
                            )
                            Spacer(modifier = Modifier.height(2.dp))
                            Text(
                                task.description,
                                style = MaterialTheme.typography.bodySmall,
                                color = IndustrialTextSecondary,
                                maxLines = 2,
                                overflow = TextOverflow.Ellipsis
                            )
                        }
                    }
                }

                // ---- Assigned work orders ----------------------------------
                SectionHeader(
                    text = "Assigned Work Orders",
                    trailing = {
                        AppTextButton(onClick = onNavigateToWorkOrders) {
                            Text("View All (${workOrders.size})")
                        }
                    }
                )

                if (workOrders.isEmpty()) {
                    P117Card(modifier = Modifier.fillMaxWidth()) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(CardContentPadding),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            P117IconContainer(
                                icon = Icons.Default.Assignment,
                                tint = IndustrialTextMuted,
                                size = 40.dp
                            )
                            Spacer(modifier = Modifier.width(12.dp))
                            Text(
                                text = "No work orders assigned",
                                style = MaterialTheme.typography.bodyMedium,
                                color = IndustrialTextSecondary
                            )
                        }
                    }
                } else {
                    workOrders.take(2).forEach { wo ->
                        WorkOrderCard(
                            workOrder = wo,
                            onClick = { onNavigateToWorkOrderDetail(wo.id) }
                        )
                    }
                }

                // ---- Secondary navigation hub -------------------------------
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(ListItemSpacing)
                ) {
                    AppOutlinedButton(
                        onClick = onNavigateToEquipment,
                        modifier = Modifier.weight(1f),
                        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 12.dp)
                    ) {
                        Icon(Icons.Default.Build, contentDescription = null, modifier = Modifier.size(16.dp))
                        Spacer(modifier = Modifier.width(6.dp))
                        Text("Equipment", fontSize = 12.sp, maxLines = 1)
                    }
                    AppOutlinedButton(
                        onClick = onNavigateToSop,
                        modifier = Modifier.weight(1f),
                        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 12.dp)
                    ) {
                        Icon(Icons.Default.MenuBook, contentDescription = null, modifier = Modifier.size(16.dp))
                        Spacer(modifier = Modifier.width(6.dp))
                        Text("SOPs", fontSize = 12.sp, maxLines = 1)
                    }
                    AppOutlinedButton(
                        onClick = onNavigateToSyncStatus,
                        modifier = Modifier.weight(1f),
                        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 12.dp)
                    ) {
                        Icon(Icons.Default.Sync, contentDescription = null, modifier = Modifier.size(16.dp))
                        Spacer(modifier = Modifier.width(6.dp))
                        Text("Sync Queue", fontSize = 12.sp, maxLines = 1)
                    }
                }

                if (isLoading && openWorkOrders.isEmpty()) {
                    Text(
                        text = "Refreshing field assignments…",
                        style = MaterialTheme.typography.bodySmall,
                        color = IndustrialTextMuted
                    )
                }
            }
        }
    }
}

/**
 * Large tap target for the three highest-frequency field actions. The icon sits
 * in a tinted container so the tile reads as a physical button, and the whole
 * card is the touch target with ripple + press scale from [P117Card].
 */
@Composable
fun QuickActionCard(
    icon: ImageVector,
    title: String,
    subtitle: String,
    color: Color,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    P117Card(
        modifier = modifier,
        cardType = P117CardType.EQUIPMENT,
        accentColor = color,
        onClick = onClick
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 10.dp, vertical = CardContentPadding),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Box(
                modifier = Modifier
                    .size(44.dp)
                    .background(
                        color = color.copy(alpha = 0.12f),
                        shape = RoundedCornerShape(12.dp)
                    ),
                contentAlignment = Alignment.Center
            ) {
                Icon(icon, contentDescription = title, tint = color, modifier = Modifier.size(22.dp))
            }
            Spacer(modifier = Modifier.height(10.dp))
            Text(
                title,
                style = MaterialTheme.typography.labelLarge,
                color = IndustrialTextPrimary,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                subtitle,
                style = MaterialTheme.typography.bodySmall,
                color = IndustrialTextSecondary,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
        }
    }
}
