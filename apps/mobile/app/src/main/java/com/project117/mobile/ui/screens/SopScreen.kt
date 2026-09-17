package com.project117.mobile.ui.screens
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.MenuBook
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.project117.mobile.data.local.preferences.SessionManager
import com.project117.mobile.domain.backend.FieldBackend
import com.project117.mobile.domain.model.AppMode
import com.project117.mobile.domain.model.BackendResult
import com.project117.mobile.domain.model.Sop
import com.project117.mobile.ui.components.*
import com.project117.mobile.ui.theme.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class SopViewModel @Inject constructor(
    private val fieldBackend: FieldBackend,
    private val sessionManager: SessionManager,
    savedStateHandle: SavedStateHandle
) : ViewModel() {

    val appMode: StateFlow<AppMode> = sessionManager.appMode

    private val _sopList = MutableStateFlow<List<Sop>>(emptyList())
    val sopList: StateFlow<List<Sop>> = _sopList.asStateFlow()

    private val _selectedSop = MutableStateFlow<Sop?>(null)
    val selectedSop: StateFlow<Sop?> = _selectedSop.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    val searchQuery = MutableStateFlow("")

    init {
        val sopId: String? = savedStateHandle["sopId"]
        if (sopId != null) {
            loadSopDetail(sopId)
        } else {
            loadSopList()
        }
    }

    fun loadSopList() {
        viewModelScope.launch {
            _isLoading.value = true
            when (val res = fieldBackend.getSopList()) {
                is BackendResult.Success -> _sopList.value = res.data
                else -> Unit
            }
            _isLoading.value = false
        }
    }

    fun loadSopDetail(id: String) {
        viewModelScope.launch {
            _isLoading.value = true
            when (val res = fieldBackend.getSop(id)) {
                is BackendResult.Success -> _selectedSop.value = res.data
                else -> Unit
            }
            _isLoading.value = false
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SopListScreen(
    onNavigateBack: () -> Unit,
    onNavigateToDetail: (String) -> Unit,
    viewModel: SopViewModel = hiltViewModel()
) {
    val mode by viewModel.appMode.collectAsState()
    val list by viewModel.sopList.collectAsState()
    val query by viewModel.searchQuery.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()

    val filtered = remember(list, query) {
        if (query.isBlank()) list else list.filter {
            it.title.contains(query, ignoreCase = true) ||
            it.id.contains(query, ignoreCase = true) ||
            it.category.contains(query, ignoreCase = true) ||
            it.tags.any { tag -> tag.contains(query, ignoreCase = true) }
        }
    }

    Scaffold(
        topBar = {
            AppTopBar(
                title = "Standard Operating Procedures",
                subtitle = "CONTROLLED DOCUMENTS",
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

            OutlinedTextField(
                value = query,
                onValueChange = { viewModel.searchQuery.value = it },
                placeholder = { Text("Search procedures, tags, or IDs…") },
                leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(ScreenPadding),
                singleLine = true
            )

            if (isLoading) {
                LoadingStateView("Loading SOP library…")
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
                    items(filtered) { sop ->
                        P117Card(
                            modifier = Modifier.fillMaxWidth(),
                            cardType = P117CardType.PLAIN,
                            onClick = { onNavigateToDetail(sop.id) }
                        ) {
                            Column(modifier = Modifier.padding(CardContentPadding)) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    P117IconContainer(
                                        icon = Icons.Default.MenuBook,
                                        tint = IndustrialCyan,
                                        size = 40.dp
                                    )
                                    Spacer(modifier = Modifier.width(12.dp))
                                    Column(modifier = Modifier.weight(1f)) {
                                        Row(
                                            modifier = Modifier.fillMaxWidth(),
                                            horizontalArrangement = Arrangement.SpaceBetween,
                                            verticalAlignment = Alignment.CenterVertically
                                        ) {
                                            EquipmentTag(tag = sop.id)
                                            Text(sop.version, style = MonoMetaStyle, color = IndustrialTextSecondary)
                                        }
                                        Spacer(modifier = Modifier.height(8.dp))
                                        Text(
                                            sop.title,
                                            style = MaterialTheme.typography.titleMedium,
                                            color = IndustrialTextPrimary
                                        )
                                        Spacer(modifier = Modifier.height(6.dp))
                                        Text(
                                            sop.summary,
                                            style = MaterialTheme.typography.bodySmall,
                                            color = IndustrialTextSecondary,
                                            maxLines = 2
                                        )
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

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SopDetailScreen(
    sopId: String,
    onNavigateBack: () -> Unit,
    viewModel: SopViewModel = hiltViewModel()
) {
    val mode by viewModel.appMode.collectAsState()
    val sop by viewModel.selectedSop.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()

    LaunchedEffect(sopId) {
        viewModel.loadSopDetail(sopId)
    }

    Scaffold(
        topBar = {
            AppTopBar(
                title = sop?.id ?: "SOP Detail",
                subtitle = sop?.title,
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

            if (isLoading || sop == null) {
                LoadingStateView("Loading procedure…")
            } else {
                val item = sop!!
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .verticalScroll(rememberScrollState())
                        .padding(ScreenPadding),
                    verticalArrangement = Arrangement.spacedBy(ScreenSectionSpacing)
                ) {
                    P117Card(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(CardContentPadding)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                P117IconContainer(
                                    icon = Icons.Default.MenuBook,
                                    tint = IndustrialCyan,
                                    size = 44.dp
                                )
                                Spacer(modifier = Modifier.width(12.dp))
                                Column(modifier = Modifier.weight(1f)) {
                                    P117Eyebrow("Controlled document")
                                    Spacer(modifier = Modifier.height(6.dp))
                                    EquipmentTag(tag = item.id)
                                }
                            }
                            Spacer(modifier = Modifier.height(12.dp))
                            Text(
                                item.title,
                                style = MaterialTheme.typography.headlineSmall,
                                color = IndustrialTextPrimary
                            )
                            Spacer(modifier = Modifier.height(12.dp))
                            P117Divider()
                            Spacer(modifier = Modifier.height(10.dp))
                            KeyValueRow(label = "Category", value = item.category, monoValue = false)
                            KeyValueRow(label = "Version", value = item.version)
                            KeyValueRow(label = "Last updated", value = item.lastUpdated)
                        }
                    }

                    P117Card(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(CardContentPadding)) {
                            P117Eyebrow("PROTOCOL INSTRUCTIONS")
                            Spacer(modifier = Modifier.height(12.dp))
                            Box(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clip(MaterialTheme.shapes.small)
                                    .background(IndustrialDarkSurfaceSunken)
                                    .padding(16.dp)
                            ) {
                                Text(
                                    text = item.content,
                                    style = MaterialTheme.typography.bodyLarge,
                                    lineHeight = 26.sp,
                                    color = IndustrialTextPrimary
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}
