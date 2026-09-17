package com.project117.mobile.ui.screens
import android.app.Activity
import android.content.Intent
import android.speech.RecognizerIntent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
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
import java.util.*
import javax.inject.Inject

@HiltViewModel
class VoiceAssistantViewModel @Inject constructor(
    private val fieldBackend: FieldBackend,
    private val sessionManager: SessionManager
) : ViewModel() {

    val appMode: StateFlow<AppMode> = sessionManager.appMode

    private val _messages = MutableStateFlow<List<ChatMessage>>(
        listOf(
            ChatMessage(
                id = "MSG-001",
                content = "Hello! I am your sovereign on-premise industrial assistant. Ask me about machine telemetry, SOP guidelines, or active work orders.",
                role = MessageRole.ASSISTANT,
                timestamp = "Now"
            )
        )
    )
    val messages: StateFlow<List<ChatMessage>> = _messages.asStateFlow()

    val inputText = MutableStateFlow("")

    private val _isProcessing = MutableStateFlow(false)
    val isProcessing: StateFlow<Boolean> = _isProcessing.asStateFlow()

    fun sendMessage(text: String) {
        val trimmed = text.trim()
        if (trimmed.isBlank() || _isProcessing.value) return

        val userMsg = ChatMessage(
            id = "MSG-${System.currentTimeMillis()}",
            content = trimmed,
            role = MessageRole.USER,
            timestamp = "Just now"
        )
        _messages.value = _messages.value + userMsg
        inputText.value = ""

        viewModelScope.launch {
            _isProcessing.value = true
            when (val res = fieldBackend.sendMessage(trimmed, AssistantContext(equipmentId = "EQ-P102", workOrderId = "WO-2026-0891"))) {
                is BackendResult.Success -> {
                    val aiMsg = ChatMessage(
                        id = "MSG-${System.currentTimeMillis() + 1}",
                        content = res.data,
                        role = MessageRole.ASSISTANT,
                        timestamp = "Just now"
                    )
                    _messages.value = _messages.value + aiMsg
                }
                is BackendResult.BackendOffline -> {
                    val errMsg = ChatMessage(
                        id = "MSG-${System.currentTimeMillis() + 1}",
                        content = "Assistant offline: Cannot reach on-premise AI orchestrator. Switch to DEMO MODE to evaluate canned responses.",
                        role = MessageRole.ASSISTANT,
                        timestamp = "Just now",
                        isError = true
                    )
                    _messages.value = _messages.value + errMsg
                }
                else -> {
                    val errMsg = ChatMessage(
                        id = "MSG-${System.currentTimeMillis() + 1}",
                        content = "Error processing request.",
                        role = MessageRole.ASSISTANT,
                        timestamp = "Just now",
                        isError = true
                    )
                    _messages.value = _messages.value + errMsg
                }
            }
            _isProcessing.value = false
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VoiceAssistantScreen(
    onNavigateBack: () -> Unit,
    viewModel: VoiceAssistantViewModel = hiltViewModel()
) {
    val mode by viewModel.appMode.collectAsState()
    val messages by viewModel.messages.collectAsState()
    val input by viewModel.inputText.collectAsState()
    val isProcessing by viewModel.isProcessing.collectAsState()

    val listState = rememberLazyListState()

    val speechLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            val spoken = result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull()
            if (!spoken.isNullOrBlank()) {
                viewModel.sendMessage(spoken)
            }
        }
    }

    LaunchedEffect(messages.size) {
        if (messages.isNotEmpty()) {
            listState.animateScrollToItem(messages.size - 1)
        }
    }

    Scaffold(
        topBar = {
            AppTopBar(
                title = "Field Assistant",
                subtitle = "ON-PREMISE AI · OFFLINE-CAPABLE",
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

            // Quick suggestion chips
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState())
                    .padding(horizontal = ScreenPadding, vertical = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                listOf(
                    "Pump P-102 status?",
                    "Applicable SOP?",
                    "Why assigned?"
                ).forEach { prompt ->
                    SuggestionChip(
                        onClick = { viewModel.sendMessage(prompt) },
                        label = {
                            Text(
                                text = prompt,
                                maxLines = 1,
                                style = MaterialTheme.typography.labelMedium,
                                color = IndustrialCyan
                            )
                        },
                        shape = MaterialTheme.shapes.small,
                        colors = SuggestionChipDefaults.suggestionChipColors(
                            containerColor = IndustrialCyanContainer,
                            labelColor = IndustrialCyan
                        ),
                        border = BorderStroke(1.dp, IndustrialCyanDim)
                    )
                }
            }

            // Message stream
            LazyColumn(
                state = listState,
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .padding(horizontal = ScreenPadding),
                verticalArrangement = Arrangement.spacedBy(ListItemSpacing),
                contentPadding = PaddingValues(vertical = 12.dp)
            ) {
                items(messages) { msg ->
                    val isUser = msg.role == MessageRole.USER
                    Column(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalAlignment = if (isUser) Alignment.End else Alignment.Start
                    ) {
                        // Author + timestamp in the mono register, not a chat bubble.
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                text = if (isUser) "OPERATOR" else "ASSISTANT",
                                style = MaterialTheme.typography.labelSmall,
                                color = when {
                                    msg.isError -> IndustrialCriticalStrong
                                    isUser -> IndustrialTextSecondary
                                    else -> IndustrialTeal
                                }
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                text = msg.timestamp,
                                style = MonoMetaStyle,
                                color = IndustrialTextMuted
                            )
                        }
                        Spacer(modifier = Modifier.height(6.dp))
                        Box(
                            modifier = Modifier
                                .widthIn(max = 320.dp)
                                .clip(MaterialTheme.shapes.small)
                                .background(
                                    when {
                                        msg.isError -> statusToneContainer(StatusTone.CRITICAL)
                                        isUser -> IndustrialCyanContainer
                                        else -> IndustrialDarkSurface
                                    }
                                )
                                .border(
                                    width = 1.dp,
                                    color = when {
                                        msg.isError -> IndustrialCriticalRed
                                        isUser -> IndustrialCyan
                                        else -> IndustrialDarkSurfaceBorder
                                    },
                                    shape = MaterialTheme.shapes.small
                                )
                                .padding(14.dp)
                        ) {
                            Text(
                                text = msg.content,
                                style = MaterialTheme.typography.bodyMedium,
                                color = if (msg.isError) IndustrialCriticalStrong else IndustrialTextPrimary
                            )
                        }
                    }
                }
            }

            if (isProcessing) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = ScreenPadding, vertical = 4.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(16.dp),
                        color = IndustrialCyan,
                        trackColor = IndustrialCyanContainer
                    )
                    Spacer(modifier = Modifier.width(10.dp))
                    Text(
                        "Processing on-premise query…",
                        style = MaterialTheme.typography.bodySmall,
                        color = IndustrialTextSecondary
                    )
                }
            }

            // Bottom Input bar — white chrome with a hairline top edge.
            Surface(
                color = IndustrialDarkSurface,
                modifier = Modifier.fillMaxWidth()
            ) {
                Column {
                    P117Divider()
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 8.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        IconButton(
                            onClick = {
                                val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                                    putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                                    putExtra(RecognizerIntent.EXTRA_PROMPT, "Ask field assistant…")
                                }
                                try {
                                    speechLauncher.launch(intent)
                                } catch (e: Exception) {
                                    // Fallback
                                }
                            }
                        ) {
                            Icon(Icons.Default.Mic, contentDescription = "Voice Input", tint = IndustrialCyan)
                        }

                        OutlinedTextField(
                            value = input,
                            onValueChange = { viewModel.inputText.value = it },
                            placeholder = { Text("Ask about equipment, SOP, status…") },
                            modifier = Modifier.weight(1f),
                            singleLine = true
                        )

                        Spacer(modifier = Modifier.width(4.dp))

                        IconButton(
                            onClick = { viewModel.sendMessage(input) },
                            enabled = input.isNotBlank() && !isProcessing
                        ) {
                            Icon(
                                Icons.Default.Send,
                                contentDescription = "Send",
                                tint = if (input.isNotBlank() && !isProcessing) IndustrialCyan else IndustrialTextMuted
                            )
                        }
                    }
                }
            }
        }
    }
}
