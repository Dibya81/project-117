package com.project117.mobile.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.project117.mobile.domain.model.Equipment
import com.project117.mobile.domain.model.WorkOrder
import com.project117.mobile.ui.theme.*

/*
 * Typed field cards.
 *
 * Each record type in the app gets its own card anatomy rather than a generic
 * "title + two lines" box. The differences are deliberate and consistent:
 *
 *   EquipmentCard    icon container · name · status badge · tag · location ·
 *                    the worst live reading pulled out as a big mono value
 *   WorkOrderCard    priority badge · order id · equipment · checklist progress
 *   AlertCard        full-height severity rail · severity icon · equipment ·
 *                    timestamp · unread dot
 *   InspectionCard   capture progress · state chip · evidence requirement
 *   SyncQueueCard    connectivity glyph · action type · queue id · retry state
 *
 * All five sit on [P117Card], so press feedback, radii, borders and elevation
 * are identical everywhere; only the anatomy differs.
 */

// ---------------------------------------------------------------------------
// Equipment
// ---------------------------------------------------------------------------

/** Maps a free-text equipment type onto a glyph. Falls back to a generic mark. */
private fun equipmentGlyph(type: String): ImageVector = when {
    type.contains("pump", ignoreCase = true) -> Icons.Default.WaterDrop
    type.contains("motor", ignoreCase = true) -> Icons.Default.Bolt
    type.contains("valve", ignoreCase = true) -> Icons.Default.Settings
    type.contains("compressor", ignoreCase = true) -> Icons.Default.Factory
    type.contains("fan", ignoreCase = true) -> Icons.Default.Air
    type.contains("sensor", ignoreCase = true) -> Icons.Default.Speed
    else -> Icons.Default.PrecisionManufacturing
}

/**
 * Asset card. The rail and the icon container take the *equipment status*
 * colour, so a degraded asset is amber down its whole leading edge.
 */
@Composable
fun EquipmentCard(
    equipment: Equipment,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val accent = equipmentStatusAccent(equipment.status)
    P117Card(
        modifier = modifier.fillMaxWidth(),
        cardType = P117CardType.EQUIPMENT,
        accentColor = accent,
        onClick = onClick
    ) {
        Column(modifier = Modifier.padding(CardContentPadding)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                P117IconContainer(
                    icon = equipmentGlyph(equipment.type),
                    tint = accent,
                    size = 44.dp
                )
                Spacer(modifier = Modifier.width(12.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = equipment.name,
                        style = MaterialTheme.typography.titleMedium,
                        color = IndustrialTextPrimary,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    Spacer(modifier = Modifier.height(3.dp))
                    Text(
                        text = equipment.type,
                        style = MaterialTheme.typography.bodySmall,
                        color = IndustrialTextSecondary,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
                Spacer(modifier = Modifier.width(8.dp))
                EquipmentStatusBadge(equipment.status)
            }

            Spacer(modifier = Modifier.height(12.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                EquipmentTag(tag = equipment.id, color = accent)
                P117MetaRow(
                    text = equipment.location,
                    icon = Icons.Default.Place,
                    modifier = Modifier.weight(1f)
                )
            }

            // The single most important number on the asset: the first reading
            // that is out of spec, or the first reading if everything is fine.
            val keyReading = equipment.readings.firstOrNull { !it.isNominal }
                ?: equipment.readings.firstOrNull()
            if (keyReading != null) {
                Spacer(modifier = Modifier.height(12.dp))
                P117Divider()
                Spacer(modifier = Modifier.height(10.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.Bottom
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        P117Eyebrow(
                            text = if (keyReading.isNominal) "KEY READING" else "OUT OF SPEC",
                            color = if (keyReading.isNominal) IndustrialTextMuted else IndustrialCriticalRed
                        )
                        Spacer(modifier = Modifier.height(3.dp))
                        Text(
                            text = keyReading.parameter,
                            style = MaterialTheme.typography.bodySmall,
                            color = IndustrialTextSecondary,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                    Spacer(modifier = Modifier.width(10.dp))
                    ReadingValue(
                        value = "${keyReading.value} ${keyReading.unit}",
                        color = if (keyReading.isNominal) IndustrialNominalGreen else IndustrialCriticalRed
                    )
                }
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Work order
// ---------------------------------------------------------------------------

/**
 * Work-order card. Priority drives the rail colour and the badge; the checklist
 * progress bar is the card's second axis of meaning.
 */
@Composable
fun WorkOrderCard(
    workOrder: WorkOrder,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val accent = priorityAccent(workOrder.priority)
    val total = workOrder.steps.size
    val done = workOrder.steps.count { it.isCompleted }
    val progress = if (total == 0) 0f else done.toFloat() / total

    P117Card(
        modifier = modifier.fillMaxWidth(),
        cardType = P117CardType.WORK_ORDER,
        accentColor = accent,
        onClick = onClick
    ) {
        Column(modifier = Modifier.padding(CardContentPadding)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                PriorityBadge(workOrder.priority)
                EquipmentTag(tag = workOrder.id)
            }

            Spacer(modifier = Modifier.height(10.dp))

            Text(
                text = workOrder.title,
                style = MaterialTheme.typography.titleMedium,
                color = IndustrialTextPrimary,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis
            )

            Spacer(modifier = Modifier.height(5.dp))

            P117MetaRow(
                text = workOrder.equipmentName ?: workOrder.equipmentId ?: "Unassigned asset",
                icon = Icons.Default.PrecisionManufacturing,
                tint = accent
            )

            if (total > 0) {
                Spacer(modifier = Modifier.height(12.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    P117Eyebrow("Checklist")
                    Text(
                        text = "$done / $total steps",
                        style = EquipmentTagStyle,
                        color = IndustrialTextSecondary
                    )
                }
                Spacer(modifier = Modifier.height(6.dp))
                P117ProgressBar(
                    progress = progress,
                    color = if (progress >= 1f) IndustrialNominalGreen else accent
                )
            }

            Spacer(modifier = Modifier.height(12.dp))
            P117Divider()
            Spacer(modifier = Modifier.height(10.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "Status: ${workOrder.status.name}",
                    style = MaterialTheme.typography.bodySmall,
                    color = IndustrialTextSecondary
                )
                Text(
                    text = "Due: ${workOrder.dueDate ?: "N/A"}",
                    style = MonoMetaStyle,
                    color = IndustrialTextSecondary
                )
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Alert / notification
// ---------------------------------------------------------------------------

/**
 * Alert card: the loudest card in the app. A full-height severity rail, a
 * severity glyph, the equipment reference and a mono timestamp. Unread entries
 * get a filled dot and a tinted body; read entries are flat white.
 */
@Composable
fun AlertCard(
    title: String,
    message: String,
    timestamp: String,
    tone: StatusTone,
    icon: ImageVector,
    modifier: Modifier = Modifier,
    isRead: Boolean = true,
    onOpen: (() -> Unit)? = null,
    onMarkRead: (() -> Unit)? = null
) {
    val accent = statusToneColor(tone)
    P117Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = if (isRead) P117CardSurface else statusToneContainer(tone)
        ),
        cardType = P117CardType.ALERT,
        accentColor = accent,
        onClick = onOpen
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(CardContentPadding),
            verticalAlignment = Alignment.Top
        ) {
            P117IconContainer(icon = icon, tint = accent, size = 40.dp)
            Spacer(modifier = Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = title,
                        style = MaterialTheme.typography.titleSmall,
                        color = IndustrialTextPrimary,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = timestamp,
                        style = MonoMetaStyle,
                        color = IndustrialTextMuted
                    )
                }

                Spacer(modifier = Modifier.height(6.dp))

                Text(
                    text = message,
                    style = MaterialTheme.typography.bodySmall,
                    color = IndustrialTextSecondary
                )

                Spacer(modifier = Modifier.height(10.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        if (!isRead) {
                            P117StatusDot(tone = tone, size = 8.dp)
                            Spacer(modifier = Modifier.width(6.dp))
                        }
                        StatusChip(
                            label = if (isRead) "READ" else "UNREAD",
                            tone = if (isRead) StatusTone.NEUTRAL else tone,
                            showDot = false
                        )
                    }
                    if (!isRead && onMarkRead != null) {
                        AppTextButton(
                            onClick = onMarkRead,
                            contentPadding = PaddingValues(horizontal = 10.dp, vertical = 6.dp)
                        ) {
                            Text("Mark as Read")
                        }
                    }
                }
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Inspection
// ---------------------------------------------------------------------------

/**
 * Inspection / evidence card. The progress rail is capture completeness and the
 * chip is the *honest* submit state — it says "Queued offline" rather than
 * "Saved" when nothing reached the server.
 */
@Composable
fun InspectionCard(
    title: String,
    context: String,
    progress: Float,
    stateLabel: String,
    stateTone: StatusTone,
    modifier: Modifier = Modifier,
    progressColor: Color = IndustrialTeal,
    onOpen: (() -> Unit)? = null
) {
    P117Card(
        modifier = modifier.fillMaxWidth(),
        cardType = P117CardType.INSPECTION,
        accentColor = statusToneColor(stateTone),
        onClick = onOpen
    ) {
        Column(modifier = Modifier.padding(CardContentPadding)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                P117Eyebrow("Field Inspection")
                StatusChip(label = stateLabel, tone = stateTone)
            }
            Spacer(modifier = Modifier.height(10.dp))
            Text(
                text = title,
                style = MaterialTheme.typography.titleMedium,
                color = IndustrialTextPrimary,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
            Spacer(modifier = Modifier.height(4.dp))
            P117MetaRow(text = context, icon = Icons.Default.Assignment)
            Spacer(modifier = Modifier.height(12.dp))
            P117ProgressBar(progress = progress, color = progressColor)
            Spacer(modifier = Modifier.height(6.dp))
            Text(
                text = "${(progress.coerceIn(0f, 1f) * 100).toInt()}% captured",
                style = EquipmentTagStyle,
                color = IndustrialTextSecondary
            )
        }
    }
}

// ---------------------------------------------------------------------------
// Sync queue
// ---------------------------------------------------------------------------

/**
 * Offline queue entry. The glyph answers "is this thing on the wire or not":
 * a cloud-with-arrow while pending/syncing, a cloud-with-slash when it failed.
 */
@Composable
fun SyncQueueCard(
    reference: String,
    actionLabel: String,
    statusLabel: String,
    statusTone: StatusTone,
    createdAt: String,
    retryLabel: String,
    modifier: Modifier = Modifier,
    errorMessage: String? = null,
    onRetry: (() -> Unit)? = null
) {
    val accent = statusToneColor(statusTone)
    val failed = statusTone == StatusTone.CRITICAL

    P117Card(
        modifier = modifier.fillMaxWidth(),
        cardType = P117CardType.SYNC,
        accentColor = accent
    ) {
        Column(modifier = Modifier.padding(CardContentPadding)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                P117IconContainer(
                    icon = if (failed) Icons.Default.CloudOff else Icons.Default.CloudSync,
                    tint = accent,
                    size = 40.dp
                )
                Spacer(modifier = Modifier.width(12.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = actionLabel.uppercase(),
                        style = MaterialTheme.typography.titleSmall,
                        color = IndustrialTextPrimary,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    Spacer(modifier = Modifier.height(3.dp))
                    EquipmentTag(tag = reference)
                }
                Spacer(modifier = Modifier.width(8.dp))
                StatusChip(label = statusLabel, tone = statusTone)
            }

            Spacer(modifier = Modifier.height(12.dp))
            P117Divider()
            Spacer(modifier = Modifier.height(10.dp))

            KeyValueRow(label = "Queued at", value = createdAt)
            KeyValueRow(label = "Retries", value = retryLabel)

            if (!errorMessage.isNullOrBlank()) {
                Spacer(modifier = Modifier.height(10.dp))
                StatusBanner(text = errorMessage, tone = StatusTone.CRITICAL)
            }

            if (onRetry != null && (failed || statusTone == StatusTone.WARNING)) {
                Spacer(modifier = Modifier.height(12.dp))
                AppOutlinedButton(
                    onClick = onRetry,
                    contentPadding = PaddingValues(horizontal = 14.dp, vertical = 10.dp)
                ) {
                    Icon(
                        Icons.Default.Refresh,
                        contentDescription = null,
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Retry Action", fontWeight = FontWeight.SemiBold)
                }
            }
        }
    }
}
