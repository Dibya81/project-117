package com.project117.mobile.ui.screens
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Gavel
import androidx.compose.material.icons.filled.Lock
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
class ApprovalsViewModel @Inject constructor(
    private val fieldBackend: FieldBackend,
    private val sessionManager: SessionManager
) : ViewModel() {

    val appMode: StateFlow<AppMode> = sessionManager.appMode
    val userSession: StateFlow<UserSession?> = sessionManager.userSession

    private val _approvals = MutableStateFlow<List<Approval>>(emptyList())
    val approvals: StateFlow<List<Approval>> = _approvals.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    init {
        loadApprovals()
    }

    fun loadApprovals() {
        viewModelScope.launch {
            _isLoading.value = true
            when (val res = fieldBackend.getApprovals()) {
                is BackendResult.Success -> _approvals.value = res.data
                else -> Unit
            }
            _isLoading.value = false
        }
    }

    fun decideApproval(id: String, decision: ApprovalDecision, notes: String?) {
        viewModelScope.launch {
            _isLoading.value = true
            fieldBackend.decideApproval(id, decision, notes)
            loadApprovals()
            _isLoading.value = false
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ApprovalsScreen(
    onNavigateBack: () -> Unit,
    viewModel: ApprovalsViewModel = hiltViewModel()
) {
    val mode by viewModel.appMode.collectAsState()
    val session by viewModel.userSession.collectAsState()
    val list by viewModel.approvals.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()

    val isAuthorized = session?.role?.isSupervisorOrAbove == true

    var selectedApprovalForDecision by remember { mutableStateOf<Pair<Approval, ApprovalDecision>?>(null) }

    selectedApprovalForDecision?.let { (app, decision) ->
        ConsequentialActionDialog(
            title = if (decision == ApprovalDecision.APPROVE) "Confirm Shutdown Approval" else "Confirm Rejection",
            message = "You are deciding on ${app.id} (${app.title}).\nConsequence: ${app.consequence}",
            confirmText = if (decision == ApprovalDecision.APPROVE) "Authorize Shutdown" else "Reject Request",
            onConfirm = {
                viewModel.decideApproval(app.id, decision, "Supervisor authorization confirmed on mobile client.")
                selectedApprovalForDecision = null
            },
            onDismiss = { selectedApprovalForDecision = null }
        )
    }

    Scaffold(
        topBar = {
            AppTopBar(
                title = "Supervisor Approvals",
                subtitle = "HUMAN DECISION QUEUE",
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

            if (!isAuthorized) {
                P117EmptyState(
                    icon = Icons.Default.Lock,
                    title = "Access Restricted",
                    message = "Only Supervisor or Admin roles are permitted to authorize operational shutdowns or consequential engineering approvals.",
                    tone = StatusTone.CRITICAL
                )
            } else if (isLoading) {
                LoadingStateView("Loading approval requests…")
            } else if (list.isEmpty()) {
                P117EmptyState(
                    icon = Icons.Default.Gavel,
                    title = "No pending approvals"
                )
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(ScreenPadding),
                    verticalArrangement = Arrangement.spacedBy(ListItemSpacing)
                ) {
                    items(list) { app ->
                        val (statusTone, statusText) = when (app.status) {
                            ApprovalStatus.PENDING -> Pair(StatusTone.WARNING, "PENDING")
                            ApprovalStatus.APPROVED -> Pair(StatusTone.SUCCESS, "APPROVED")
                            ApprovalStatus.REJECTED -> Pair(StatusTone.CRITICAL, "REJECTED")
                            ApprovalStatus.EXPIRED -> Pair(StatusTone.NEUTRAL, "EXPIRED")
                        }

                        P117Card(
                            modifier = Modifier.fillMaxWidth(),
                            cardType = P117CardType.ALERT,
                            accentColor = statusToneColor(statusTone)
                        ) {
                            Column(modifier = Modifier.padding(CardContentPadding)) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    EquipmentTag(tag = app.id)
                                    StatusChip(label = statusText, tone = statusTone)
                                }
                                Spacer(modifier = Modifier.height(12.dp))
                                Text(
                                    text = app.title,
                                    style = MaterialTheme.typography.titleMedium,
                                    color = IndustrialTextPrimary
                                )
                                Spacer(modifier = Modifier.height(6.dp))
                                Text(
                                    text = app.description,
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = IndustrialTextSecondary
                                )
                                Spacer(modifier = Modifier.height(10.dp))
                                KeyValueRow(label = "Requested by", value = app.requestedBy.uppercase(), monoValue = false)
                                KeyValueRow(label = "Requested at", value = app.requestedAt)

                                Spacer(modifier = Modifier.height(12.dp))
                                P117Divider()
                                Spacer(modifier = Modifier.height(12.dp))

                                P117Card(
                                    colors = CardDefaults.cardColors(containerColor = P117ContainerCritical),
                                    border = BorderStroke(1.dp, IndustrialCriticalRed.copy(alpha = 0.34f)),
                                    modifier = Modifier.fillMaxWidth()
                                ) {
                                    Column(modifier = Modifier.padding(12.dp)) {
                                        P117Eyebrow(
                                            text = "OPERATIONAL CONSEQUENCE",
                                            color = IndustrialCriticalRed
                                        )
                                        Spacer(modifier = Modifier.height(6.dp))
                                        StatusBanner(
                                            text = "${app.consequence}",
                                            tone = StatusTone.CRITICAL
                                        )
                                    }
                                }

                                if (app.status == ApprovalStatus.PENDING) {
                                    Spacer(modifier = Modifier.height(14.dp))
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.spacedBy(ListItemSpacing)
                                    ) {
                                        AppButton(
                                            onClick = { selectedApprovalForDecision = Pair(app, ApprovalDecision.APPROVE) },
                                            colors = p117SuccessButtonColors(),
                                            modifier = Modifier.weight(1f)
                                        ) {
                                            Text("Approve", color = IndustrialTextOnAccent, fontWeight = FontWeight.Bold)
                                        }

                                        AppOutlinedButton(
                                            onClick = { selectedApprovalForDecision = Pair(app, ApprovalDecision.REJECT) },
                                            colors = ButtonDefaults.outlinedButtonColors(contentColor = IndustrialCriticalRed),
                                            modifier = Modifier.weight(1f)
                                        ) {
                                            Text("Reject", color = IndustrialCriticalRed)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
