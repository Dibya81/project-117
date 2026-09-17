package com.project117.mobile.ui.screens
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
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
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.project117.mobile.data.local.preferences.SessionManager
import com.project117.mobile.domain.backend.FieldBackend
import com.project117.mobile.domain.model.AppMode
import com.project117.mobile.domain.model.AppNotification
import com.project117.mobile.domain.model.BackendResult
import com.project117.mobile.domain.model.NotificationType
import com.project117.mobile.ui.components.*
import com.project117.mobile.ui.theme.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class NotificationsViewModel @Inject constructor(
    private val fieldBackend: FieldBackend,
    private val sessionManager: SessionManager
) : ViewModel() {

    val appMode: StateFlow<AppMode> = sessionManager.appMode

    private val _notifications = MutableStateFlow<List<AppNotification>>(emptyList())
    val notifications: StateFlow<List<AppNotification>> = _notifications.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    init {
        loadNotifications()
    }

    fun loadNotifications() {
        viewModelScope.launch {
            _isLoading.value = true
            when (val res = fieldBackend.getNotifications()) {
                is BackendResult.Success -> _notifications.value = res.data
                else -> Unit
            }
            _isLoading.value = false
        }
    }

    fun markAsRead(id: String) {
        viewModelScope.launch {
            fieldBackend.markNotificationRead(id)
            loadNotifications()
        }
    }
}

/**
 * Compact summary strip above the event feed. The unread count is read straight
 * off the real list — the screen never invents a total — and its tone escalates
 * with what is actually waiting: a red unread plant alert outranks any number of
 * unread routine events, and a fully-read feed reports success.
 */
@Composable
private fun NotificationsSummaryCard(
    unreadCount: Int,
    totalCount: Int,
    tone: StatusTone,
    modifier: Modifier = Modifier
) {
    P117Card(modifier = modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(CardContentPadding),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column(modifier = Modifier.weight(1f)) {
                P117Eyebrow("PLANT EVENT FEED")
                Spacer(modifier = Modifier.height(6.dp))
                Text(
                    text = if (totalCount == 0) "No events in the feed" else "$unreadCount of $totalCount unread",
                    style = MaterialTheme.typography.bodySmall,
                    color = IndustrialTextSecondary
                )
                Spacer(modifier = Modifier.height(8.dp))
                StatusChip(
                    label = if (unreadCount > 0) "$unreadCount UNREAD" else "NO UNREAD EVENTS",
                    tone = tone
                )
            }
            Spacer(modifier = Modifier.width(12.dp))
            ReadingValue(
                value = unreadCount.toString().padStart(2, '0'),
                color = statusToneColor(tone)
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NotificationsScreen(
    onNavigateBack: () -> Unit,
    viewModel: NotificationsViewModel = hiltViewModel()
) {
    val mode by viewModel.appMode.collectAsState()
    val list by viewModel.notifications.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()

    // Derived only from the real feed. An unread ALERT is the loudest thing the
    // feed can hold, so it drives the summary to CRITICAL.
    val unreadCount = list.count { !it.isRead }
    val hasUnreadAlert = list.any { !it.isRead && it.type == NotificationType.ALERT }
    val summaryTone = when {
        hasUnreadAlert -> StatusTone.CRITICAL
        unreadCount > 0 -> StatusTone.WARNING
        else -> StatusTone.SUCCESS
    }

    Scaffold(
        topBar = {
            AppTopBar(
                title = "Notifications & Alerts",
                subtitle = "PLANT EVENT FEED",
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
                LoadingStateView("Loading notifications…")
            } else if (list.isEmpty()) {
                Column(modifier = Modifier.fillMaxSize()) {
                    NotificationsSummaryCard(
                        unreadCount = unreadCount,
                        totalCount = list.size,
                        tone = summaryTone,
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(ScreenPadding)
                    )
                    P117EmptyState(
                        icon = Icons.Default.NotificationsNone,
                        title = "No notifications",
                        modifier = Modifier.weight(1f)
                    )
                }
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(ScreenPadding),
                    verticalArrangement = Arrangement.spacedBy(ListItemSpacing)
                ) {
                    item {
                        NotificationsSummaryCard(
                            unreadCount = unreadCount,
                            totalCount = list.size,
                            tone = summaryTone
                        )
                    }
                    items(list) { notif ->
                        val tone = when (notif.type) {
                            NotificationType.ALERT -> StatusTone.CRITICAL
                            NotificationType.APPROVAL_REQUIRED -> StatusTone.WARNING
                            NotificationType.AGENT_TASK -> StatusTone.INFO
                            else -> StatusTone.NEUTRAL
                        }

                        AlertCard(
                            title = notif.title,
                            message = notif.body,
                            timestamp = notif.timestamp,
                            tone = tone,
                            icon = when (notif.type) {
                                NotificationType.ALERT -> Icons.Default.Warning
                                NotificationType.APPROVAL_REQUIRED -> Icons.Default.Gavel
                                NotificationType.AGENT_TASK -> Icons.Default.PrecisionManufacturing
                                else -> Icons.Default.Notifications
                            },
                            isRead = notif.isRead,
                            onMarkRead = { viewModel.markAsRead(notif.id) }
                        )
                    }
                }
            }
        }
    }
}
