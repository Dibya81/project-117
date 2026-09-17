package com.project117.mobile.ui.screens
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.CloudDone
import androidx.compose.material.icons.filled.CloudOff
import androidx.compose.material.icons.filled.CloudSync
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Sync
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
import com.project117.mobile.data.local.entities.PendingActionEntity
import com.project117.mobile.data.local.preferences.SessionManager
import com.project117.mobile.data.sync.SyncManager
import com.project117.mobile.domain.model.AppMode
import com.project117.mobile.ui.components.*
import com.project117.mobile.ui.theme.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.*
import javax.inject.Inject

@HiltViewModel
class SyncStatusViewModel @Inject constructor(
    private val syncManager: SyncManager,
    private val sessionManager: SessionManager
) : ViewModel() {

    val appMode: StateFlow<AppMode> = sessionManager.appMode
    val isSyncing: StateFlow<Boolean> = syncManager.isSyncing

    private val _actions = MutableStateFlow<List<PendingActionEntity>>(emptyList())
    val actions: StateFlow<List<PendingActionEntity>> = _actions.asStateFlow()

    init {
        observeQueue()
    }

    private fun observeQueue() {
        viewModelScope.launch {
            syncManager.observeAllActions().collect { list ->
                _actions.value = list
            }
        }
    }

    fun triggerSync() {
        viewModelScope.launch {
            syncManager.syncAll()
        }
    }

    fun retryAction(id: Long) {
        viewModelScope.launch {
            syncManager.retryAction(id)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SyncStatusScreen(
    onNavigateBack: () -> Unit,
    viewModel: SyncStatusViewModel = hiltViewModel()
) {
    val mode by viewModel.appMode.collectAsState()
    val isSyncing by viewModel.isSyncing.collectAsState()
    val list by viewModel.actions.collectAsState()

    val pendingCount = remember(list) { list.count { it.status == "PENDING" || it.status == "SYNCING" } }
    val syncedCount = list.count { it.status == "SYNCED" }
    val totalCount = list.size
    // Anything that is not one of the three known en-route states is reported by
    // the queue rows as FAILED, so the hero must call it failed too.
    val anyFailed = list.any { it.status != "PENDING" && it.status != "SYNCING" && it.status != "SYNCED" }
    val progress = if (totalCount == 0) 0f else syncedCount.toFloat() / totalCount

    val heroTone = when {
        anyFailed -> StatusTone.CRITICAL
        isSyncing -> StatusTone.INFO
        pendingCount > 0 -> StatusTone.WARNING
        else -> StatusTone.SUCCESS
    }
    val heroIcon = when {
        anyFailed -> Icons.Default.CloudOff
        isSyncing -> Icons.Default.CloudSync
        totalCount == 0 -> Icons.Default.CloudDone
        else -> Icons.Default.CloudSync
    }

    Scaffold(
        topBar = {
            AppTopBar(
                title = "Synchronization Queue",
                subtitle = "STORE & FORWARD",
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

            P117Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(ScreenPadding)
            ) {
                Column(modifier = Modifier.padding(CardContentPadding)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            P117Eyebrow("STORE & FORWARD")
                            Spacer(modifier = Modifier.height(6.dp))
                            Text(
                                text = "Queued Operations",
                                style = MaterialTheme.typography.titleMedium,
                                color = IndustrialTextPrimary
                            )
                            Spacer(modifier = Modifier.height(8.dp))
                            StatusChip(
                                label = if (pendingCount > 0) "$pendingCount AWAITING SYNC" else "ALL SYNCHRONIZED",
                                tone = if (pendingCount > 0) StatusTone.WARNING else StatusTone.SUCCESS
                            )
                        }

                        Spacer(modifier = Modifier.width(12.dp))

                        P117IconContainer(
                            icon = heroIcon,
                            tint = statusToneColor(heroTone),
                            size = 48.dp
                        )
                    }

                    Spacer(modifier = Modifier.height(14.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.Bottom
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            P117Eyebrow("PENDING")
                            Spacer(modifier = Modifier.height(3.dp))
                            ReadingValue(
                                value = pendingCount.toString().padStart(2, '0'),
                                color = statusToneColor(heroTone)
                            )
                        }
                        Column(horizontalAlignment = Alignment.End) {
                            P117Eyebrow("SYNCED")
                            Spacer(modifier = Modifier.height(3.dp))
                            Text(
                                text = "$syncedCount / $totalCount",
                                style = EquipmentTagStyle,
                                color = IndustrialTextSecondary
                            )
                        }
                    }

                    if (totalCount > 0) {
                        Spacer(modifier = Modifier.height(10.dp))
                        P117ProgressBar(
                            progress = progress,
                            color = if (progress >= 1f) IndustrialNominalGreen else IndustrialCyan
                        )
                    }

                    Spacer(modifier = Modifier.height(14.dp))

                    AppButton(
                        onClick = { viewModel.triggerSync() },
                        enabled = !isSyncing,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        if (isSyncing) {
                            CircularProgressIndicator(modifier = Modifier.size(18.dp), color = MaterialTheme.colorScheme.onPrimary)
                        } else {
                            Icon(Icons.Default.Sync, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("Sync Now", fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }

            if (list.isEmpty()) {
                P117EmptyState(
                    icon = Icons.Default.CloudDone,
                    title = "Offline queue is empty",
                    modifier = Modifier.weight(1f)
                )
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
                    items(list) { action ->
                        val dateStr = SimpleDateFormat("HH:mm:ss dd-MMM", Locale.US).format(Date(action.createdAt))
                        val (statusTone, statusText) = when (action.status) {
                            "PENDING" -> Pair(StatusTone.WARNING, "PENDING")
                            "SYNCING" -> Pair(StatusTone.INFO, "SYNCING")
                            "SYNCED" -> Pair(StatusTone.SUCCESS, "SYNCED")
                            else -> Pair(StatusTone.CRITICAL, "FAILED")
                        }

                        SyncQueueCard(
                            reference = "#${action.id}",
                            actionLabel = action.actionType.replace("_", " ").uppercase(),
                            statusLabel = statusText,
                            statusTone = statusTone,
                            createdAt = dateStr,
                            retryLabel = "${action.retryCount}/${action.maxRetries}",
                            errorMessage = action.lastError,
                            onRetry = { viewModel.retryAction(action.id) }
                        )
                    }
                }
            }
        }
    }
}
