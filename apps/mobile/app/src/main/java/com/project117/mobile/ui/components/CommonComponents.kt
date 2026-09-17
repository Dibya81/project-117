package com.project117.mobile.ui.components

import android.provider.Settings
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.AnimationSpec
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.snap
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.LocalIndication
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.project117.mobile.domain.model.AppMode
import com.project117.mobile.domain.model.EquipmentStatus
import com.project117.mobile.domain.model.WorkOrderPriority
import com.project117.mobile.ui.theme.*

/*
 * Shared field-software component set — LIGHT theme.
 *
 * Everything visual that more than one screen needs lives here so a single
 * change lands everywhere. Public names and signatures are stable: screens
 * import these directly, and new behaviour is added as a defaulted parameter or
 * a new composable rather than by changing an existing signature.
 *
 * Design rules enforced by this file:
 *   - Cards are white on a near-white page with a hairline border and a soft
 *     resting shadow. A card *type* adds a coloured accent rail on the leading
 *     edge so equipment / work-order / alert / inspection / sync cards are
 *     visually distinguishable at a glance.
 *   - Status colour is a tinted container + a coloured accent + a written
 *     label. Body text on a tint uses the deeper "ink" shade of the same hue so
 *     it stays above 4.5 : 1 (see Color.kt).
 *   - Interactive surfaces get ripple + a 1.5 % scale + a small elevation lift,
 *     at 110 ms. That is the whole motion budget for a press.
 *   - Every button keeps a 48dp minimum touch target.
 */

/** Horizontal / vertical inset for scrollable screen content. */
val ScreenPadding: Dp = 16.dp

/** Vertical gap between major sections on a screen. */
val ScreenSectionSpacing: Dp = 20.dp

/** Inner padding for a standard card. */
val CardContentPadding: Dp = 16.dp

/** Gap between cards in a list. */
val ListItemSpacing: Dp = 12.dp

/** The one button radius used app-wide. Material's default is a pill. */
val AppButtonShape = RoundedCornerShape(10.dp)

/** Minimum touch target height — 48dp so a gloved thumb can hit it outdoors. */
private val MinTouchTarget = 48.dp

// ---------------------------------------------------------------------------
// Reduced motion
// ---------------------------------------------------------------------------

/**
 * True when the platform animator duration scale is 0 — the system-wide
 * "remove animations" switch. The previous dark theme had no motion at all, so
 * this is the one place the app opts in: every animation introduced by the
 * light redesign checks this and falls back to a hard cut.
 */
@Composable
fun rememberP117ReducedMotion(): Boolean {
    val context = LocalContext.current
    return remember(context) {
        runCatching {
            Settings.Global.getFloat(
                context.contentResolver,
                Settings.Global.ANIMATOR_DURATION_SCALE,
                1f
            ) == 0f
        }.getOrDefault(false)
    }
}

/** Duration for a press transition. Deliberately short — never "game-like". */
private const val PressDurationMs = 110

/** Duration for a status / progress transition. */
private const val StateDurationMs = 220

// ---------------------------------------------------------------------------
// Status tone system — the single source of semantic colour.
// ---------------------------------------------------------------------------

/**
 * Semantic meaning of a status, independent of the domain model behind it.
 *
 * The brief's six operational states map on as:
 * NORMAL -> SUCCESS · WARNING -> WARNING · CRITICAL -> CRITICAL ·
 * INFORMATION -> INFO · SYNCING -> INFO · OFFLINE -> NEUTRAL.
 * The enum is kept at five members because screens `when` over it exhaustively
 * and adding members would be a source-breaking change, not a visual one.
 */
enum class StatusTone { NEUTRAL, INFO, SUCCESS, WARNING, CRITICAL }

/**
 * @param accent the saturated hue: dots, icons, rails, progress fills. Always
 *   >= 4.5 : 1 on a white card, so it is safe as a glyph and as large text.
 * @param container the tinted background of a chip or banner. Opaque, so the
 *   measured ink ratio holds on any surface underneath.
 * @param border a low-alpha edge that keeps the chip from floating.
 * @param ink the text colour used *on* [container]; the deep shade of the same
 *   hue, measured >= 4.5 : 1 against it.
 */
private class TonePalette(
    val accent: Color,
    val container: Color,
    val border: Color,
    val ink: Color
)

private fun tonePalette(tone: StatusTone): TonePalette = when (tone) {
    StatusTone.NEUTRAL -> TonePalette(
        IndustrialOfflineSlate,
        P117ContainerNeutral,
        IndustrialBorderStrong.copy(alpha = 0.40f),
        P117InkNeutral
    )
    StatusTone.INFO -> TonePalette(
        IndustrialCyan,
        P117ContainerInfo,
        IndustrialCyan.copy(alpha = 0.32f),
        P117InkInfo
    )
    StatusTone.SUCCESS -> TonePalette(
        IndustrialNominalGreen,
        P117ContainerSuccess,
        IndustrialNominalGreen.copy(alpha = 0.32f),
        P117InkSuccess
    )
    StatusTone.WARNING -> TonePalette(
        IndustrialWarningAmber,
        P117ContainerWarning,
        IndustrialWarningAmber.copy(alpha = 0.32f),
        P117InkWarning
    )
    StatusTone.CRITICAL -> TonePalette(
        IndustrialCriticalRed,
        P117ContainerCritical,
        IndustrialCriticalRed.copy(alpha = 0.34f),
        P117InkCritical
    )
}

private fun toneIcon(tone: StatusTone): ImageVector = when (tone) {
    StatusTone.SUCCESS -> Icons.Default.CheckCircle
    StatusTone.WARNING -> Icons.Default.Warning
    StatusTone.CRITICAL -> Icons.Default.ErrorOutline
    StatusTone.INFO -> Icons.Default.Info
    StatusTone.NEUTRAL -> Icons.Default.Info
}

/** Accent colour for a [StatusTone], for call sites that tint their own glyph. */
fun statusToneColor(tone: StatusTone): Color = tonePalette(tone).accent

/** Container colour for a [StatusTone], for call sites that build their own tint. */
fun statusToneContainer(tone: StatusTone): Color = tonePalette(tone).container

/**
 * Compact status pill. Colour is always paired with the written label and a
 * leading indicator dot, so status never depends on colour alone. The container
 * and label cross-fade when the tone changes, which is the app's only
 * status-change transition.
 */
@Composable
fun StatusChip(
    label: String,
    tone: StatusTone,
    modifier: Modifier = Modifier,
    showDot: Boolean = true
) {
    val palette = tonePalette(tone)
    val reduced = rememberP117ReducedMotion()
    val spec: AnimationSpec<Color> = if (reduced) snap() else tween(StateDurationMs)

    val container by animateColorAsState(palette.container, spec, label = "chipContainer")
    val ink by animateColorAsState(palette.ink, spec, label = "chipInk")
    val border by animateColorAsState(palette.border, spec, label = "chipBorder")
    val dot by animateColorAsState(palette.accent, spec, label = "chipDot")

    Row(
        modifier = modifier
            .clip(RoundedCornerShape(6.dp))
            .background(container)
            .border(1.dp, border, RoundedCornerShape(6.dp))
            .padding(horizontal = 8.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        if (showDot) {
            Box(
                modifier = Modifier
                    .size(6.dp)
                    .background(dot, CircleShape)
            )
            Spacer(modifier = Modifier.width(6.dp))
        }
        Text(
            text = label,
            style = MaterialTheme.typography.labelSmall,
            color = ink,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )
    }
}

/** Small haloed status dot for dense rows. Never the only signal — always labelled. */
@Composable
fun P117StatusDot(
    tone: StatusTone,
    modifier: Modifier = Modifier,
    size: Dp = 10.dp
) {
    val palette = tonePalette(tone)
    Box(
        modifier = modifier
            .size(size)
            .background(palette.accent.copy(alpha = 0.20f), CircleShape),
        contentAlignment = Alignment.Center
    ) {
        Box(
            modifier = Modifier
                .size(size * 0.6f)
                .background(palette.accent, CircleShape)
        )
    }
}

/** Full-width inline banner for form results, warnings and blocking errors. */
@Composable
fun StatusBanner(
    text: String,
    tone: StatusTone,
    modifier: Modifier = Modifier,
    icon: ImageVector? = null
) {
    val palette = tonePalette(tone)
    Row(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(10.dp))
            .background(palette.container)
            .border(1.dp, palette.border, RoundedCornerShape(10.dp))
            .padding(horizontal = 14.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            imageVector = icon ?: toneIcon(tone),
            contentDescription = null,
            tint = palette.accent,
            modifier = Modifier.size(20.dp)
        )
        Spacer(modifier = Modifier.width(10.dp))
        Text(
            text = text,
            style = MaterialTheme.typography.bodyMedium,
            color = palette.ink,
            fontWeight = FontWeight.SemiBold
        )
    }
}

// ---------------------------------------------------------------------------
// Motion helper — press feedback
// ---------------------------------------------------------------------------

/**
 * Ripple + a 1.5 % scale + an elevation lift while pressed. Returns a modifier
 * that must be applied to the *same* node as the clickable that owns
 * [interactionSource], otherwise `collectIsPressedAsState` never fires.
 */
@Composable
private fun Modifier.p117PressFeedback(
    interactionSource: MutableInteractionSource,
    restingElevation: Dp,
    shape: androidx.compose.ui.graphics.Shape
): Modifier {
    val pressed by interactionSource.collectIsPressedAsState()
    val reduced = rememberP117ReducedMotion()
    val active = pressed && !reduced

    val scale by animateFloatAsState(
        targetValue = if (active) 0.985f else 1f,
        animationSpec = tween(PressDurationMs, easing = FastOutSlowInEasing),
        label = "p117PressScale"
    )
    val elevation by animateDpAsState(
        targetValue = if (active) (restingElevation + 2.dp) else restingElevation,
        animationSpec = tween(PressDurationMs, easing = FastOutSlowInEasing),
        label = "p117PressElevation"
    )

    return this
        .graphicsLayer {
            scaleX = scale
            scaleY = scale
            shadowElevation = elevation.toPx()
            this.shape = shape
            clip = true
        }
}

// ---------------------------------------------------------------------------
// Chrome: app bar, section headers, cards, buttons
// ---------------------------------------------------------------------------

/**
 * Standard screen app bar: a single clear title, an optional monospace context
 * line, and comfortable 48dp icon targets. Every screen uses this so the
 * navigation treatment is identical everywhere.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AppTopBar(
    title: String,
    modifier: Modifier = Modifier,
    subtitle: String? = null,
    onNavigateBack: (() -> Unit)? = null,
    actions: @Composable RowScope.() -> Unit = {}
) {
    Column(modifier = modifier) {
        TopAppBar(
            title = {
                Column(modifier = Modifier.fillMaxWidth()) {
                    Text(
                        text = title,
                        style = MaterialTheme.typography.titleLarge,
                        color = IndustrialTextPrimary,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    if (subtitle != null) {
                        Text(
                            text = subtitle,
                            style = MonoMetaStyle,
                            color = IndustrialTextMuted,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                }
            },
            navigationIcon = {
                if (onNavigateBack != null) {
                    IconButton(onClick = onNavigateBack) {
                        Icon(
                            imageVector = Icons.Default.ArrowBack,
                            contentDescription = "Back",
                            tint = IndustrialTextPrimary
                        )
                    }
                }
            },
            actions = actions,
            colors = TopAppBarDefaults.topAppBarColors(
                containerColor = P117ChromeSurface,
                titleContentColor = IndustrialTextPrimary,
                navigationIconContentColor = IndustrialTextPrimary,
                actionIconContentColor = IndustrialTextSecondary
            )
        )
        P117Divider()
    }
}

/**
 * Section header with an accent tick. `trailing` hosts an optional action such
 * as a "View all" text button.
 */
@Composable
fun SectionHeader(
    text: String,
    modifier: Modifier = Modifier,
    trailing: (@Composable () -> Unit)? = null
) {
    Row(
        modifier = modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Row(
            modifier = Modifier.weight(1f),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(width = 3.dp, height = 16.dp)
                    .background(IndustrialCyan, RoundedCornerShape(2.dp))
            )
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                text = text.uppercase(),
                style = MaterialTheme.typography.labelMedium,
                color = IndustrialTextSecondary,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
        }
        if (trailing != null) {
            Spacer(modifier = Modifier.width(8.dp))
            trailing()
        }
    }
}

/** Uppercase eyebrow used inside cards (e.g. "OPERATIONAL CONSEQUENCE"). */
@Composable
fun P117Eyebrow(
    text: String,
    modifier: Modifier = Modifier,
    color: Color = IndustrialTextMuted
) {
    Text(
        text = text.uppercase(),
        style = MaterialTheme.typography.labelSmall,
        color = color,
        maxLines = 1,
        overflow = TextOverflow.Ellipsis,
        modifier = modifier
    )
}

/** Hairline divider. Decorative — never the only signal for any state. */
@Composable
fun P117Divider(
    modifier: Modifier = Modifier,
    color: Color = IndustrialDarkSurfaceBorder
) {
    Box(
        modifier = modifier
            .fillMaxWidth()
            .height(1.dp)
            .background(color)
    )
}

/**
 * What kind of record a card represents. The type chooses the accent rail
 * colour and the resting elevation, which is what makes an equipment card look
 * different from an alert card without any screen-level styling.
 */
enum class P117CardType {
    /** No rail. Used for chrome, forms and generic containers. */
    PLAIN,

    /** Asset record: blue rail, flat. */
    EQUIPMENT,

    /** Work order: amber rail, slightly raised. */
    WORK_ORDER,

    /** Plant alert: red rail — the loudest card in the app. */
    ALERT,

    /** Inspection / evidence capture: teal rail. */
    INSPECTION,

    /** Offline queue entry: green rail (or red when the action failed). */
    SYNC,

    /** Assistant / advisory surface: teal rail. */
    ASSISTANT
}

private val P117CardType.railWidth: Dp
    get() = if (this == P117CardType.PLAIN) 0.dp else 4.dp

private val P117CardType.restingElevation: Dp
    get() = when (this) {
        P117CardType.PLAIN -> 1.dp
        P117CardType.EQUIPMENT -> 1.dp
        P117CardType.ALERT -> 1.dp
        else -> 2.dp
    }

private val P117CardType.defaultAccent: Color
    get() = when (this) {
        P117CardType.PLAIN -> Color.Transparent
        P117CardType.EQUIPMENT -> IndustrialCyan
        P117CardType.WORK_ORDER -> IndustrialWarningAmber
        P117CardType.ALERT -> IndustrialCriticalRed
        P117CardType.INSPECTION -> IndustrialTeal
        P117CardType.SYNC -> IndustrialNominalGreen
        P117CardType.ASSISTANT -> IndustrialTeal
    }

/**
 * Standard card: one radius, one hairline border, one white surface.
 *
 * Call sites choose the surface colour, an optional accent rail ([accentColor])
 * and the record [cardType]. Passing [onClick] turns the card into a pressed
 * surface with ripple, a subtle scale and a small elevation lift — the card is
 * no longer `Modifier.clickable`, which is why press feedback is uniform.
 */
@Composable
fun P117Card(
    modifier: Modifier = Modifier,
    colors: CardColors = CardDefaults.cardColors(containerColor = P117CardSurface),
    border: BorderStroke? = BorderStroke(1.dp, IndustrialDarkSurfaceBorder),
    cardType: P117CardType = P117CardType.PLAIN,
    accentColor: Color? = null,
    onClick: (() -> Unit)? = null,
    content: @Composable ColumnScope.() -> Unit
) {
    val shape = MaterialTheme.shapes.medium
    val accent = accentColor ?: cardType.defaultAccent
    val interactionSource = remember { MutableInteractionSource() }

    val pressModifier = if (onClick != null) {
        Modifier
            .p117PressFeedback(interactionSource, cardType.restingElevation, shape)
            .clip(shape)
            .clickable(
                interactionSource = interactionSource,
                indication = LocalIndication.current,
                onClick = onClick
            )
    } else {
        Modifier
    }

    Card(
        modifier = modifier.then(pressModifier),
        shape = shape,
        colors = colors,
        elevation = CardDefaults.cardElevation(defaultElevation = cardType.restingElevation),
        border = border
    ) {
        val railWidth = cardType.railWidth
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .then(
                    if (railWidth > 0.dp) {
                        Modifier.drawBehind {
                            drawRect(
                                color = accent,
                                size = Size(railWidth.toPx(), size.height)
                            )
                        }
                    } else {
                        Modifier
                    }
                )
        ) {
            content()
        }
    }
}

/** Rounded tinted square that holds a card's leading glyph. */
@Composable
fun P117IconContainer(
    icon: ImageVector,
    tint: Color,
    modifier: Modifier = Modifier,
    size: Dp = 44.dp,
    contentDescription: String? = null
) {
    val shape = RoundedCornerShape(size * 0.30f)
    Box(
        modifier = modifier
            .size(size)
            .clip(shape)
            .background(tint.copy(alpha = 0.12f))
            .border(1.dp, tint.copy(alpha = 0.20f), shape),
        contentAlignment = Alignment.Center
    ) {
        Icon(
            imageVector = icon,
            contentDescription = contentDescription,
            tint = tint,
            modifier = Modifier.size(size * 0.48f)
        )
    }
}

/** Muted metadata row with an optional leading icon (location, due date, origin). */
@Composable
fun P117MetaRow(
    text: String,
    modifier: Modifier = Modifier,
    icon: ImageVector? = null,
    tint: Color = IndustrialTextMuted,
    maxLines: Int = 1
) {
    Row(
        modifier = modifier,
        verticalAlignment = Alignment.CenterVertically
    ) {
        if (icon != null) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = tint,
                modifier = Modifier.size(14.dp)
            )
            Spacer(modifier = Modifier.width(6.dp))
        }
        Text(
            text = text,
            style = MaterialTheme.typography.bodySmall,
            color = IndustrialTextSecondary,
            maxLines = maxLines,
            overflow = TextOverflow.Ellipsis
        )
    }
}

/**
 * Thin progress rail. Used for work-order step completion, inspection capture
 * and sync queue drain. Animates to the new value; snaps under reduced motion.
 */
@Composable
fun P117ProgressBar(
    progress: Float,
    modifier: Modifier = Modifier,
    color: Color = IndustrialCyan,
    trackColor: Color = IndustrialDarkSurfaceSunken
) {
    val reduced = rememberP117ReducedMotion()
    val clamped = progress.coerceIn(0f, 1f)
    val animated by animateFloatAsState(
        targetValue = clamped,
        animationSpec = tween(420, easing = FastOutSlowInEasing),
        label = "p117Progress"
    )
    val shown = if (reduced) clamped else animated

    LinearProgressIndicator(
        progress = { shown },
        modifier = modifier
            .fillMaxWidth()
            .height(6.dp)
            .clip(CircleShape),
        color = color,
        trackColor = trackColor,
        strokeCap = StrokeCap.Round,
        gapSize = 0.dp,
        drawStopIndicator = {}
    )
}

/** Honest empty state — says what is missing, never claims success. */
@Composable
fun P117EmptyState(
    icon: ImageVector,
    title: String,
    modifier: Modifier = Modifier,
    message: String? = null,
    tone: StatusTone = StatusTone.NEUTRAL
) {
    val accent = statusToneColor(tone)
    Box(
        modifier = modifier
            .fillMaxSize()
            .padding(24.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            P117IconContainer(icon = icon, tint = accent, size = 64.dp)
            Spacer(modifier = Modifier.height(14.dp))
            Text(
                text = title,
                style = MaterialTheme.typography.titleMedium,
                color = IndustrialTextPrimary,
                textAlign = TextAlign.Center
            )
            if (message != null) {
                Spacer(modifier = Modifier.height(6.dp))
                Text(
                    text = message,
                    style = MaterialTheme.typography.bodySmall,
                    color = IndustrialTextSecondary,
                    textAlign = TextAlign.Center
                )
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Buttons — four clear tiers, one shared 48dp touch target.
//
//   primary      AppButton           filled blue    one per screen
//   secondary    AppOutlinedButton   blue outline   alternative actions
//   tertiary     AppTextButton       blue text      inline / trailing
//   destructive  AppButton(p117DestructiveButtonColors())  solid red
// ---------------------------------------------------------------------------

/** Primary (filled) button colours. */
@Composable
fun p117PrimaryButtonColors(): ButtonColors = ButtonDefaults.buttonColors(
    containerColor = IndustrialCyan,
    contentColor = IndustrialTextOnAccent,
    disabledContainerColor = P117DisabledFill,
    disabledContentColor = P117TextDisabled
)

/** Secondary (outlined) button colours. */
@Composable
fun p117SecondaryButtonColors(): ButtonColors = ButtonDefaults.outlinedButtonColors(
    contentColor = IndustrialCyan,
    disabledContentColor = P117TextDisabled
)

/** Tertiary (text / inline) button colours. */
@Composable
fun p117TertiaryButtonColors(): ButtonColors = ButtonDefaults.textButtonColors(
    contentColor = IndustrialCyan,
    disabledContentColor = P117TextDisabled
)

/** Destructive button colours — solid red with a white label. */
@Composable
fun p117DestructiveButtonColors(): ButtonColors = ButtonDefaults.buttonColors(
    containerColor = IndustrialCriticalStrong,
    contentColor = IndustrialTextOnAccent,
    disabledContainerColor = P117DisabledFill,
    disabledContentColor = P117TextDisabled
)

/** Positive-confirmation button colours (approve, complete, resolve). */
@Composable
fun p117SuccessButtonColors(): ButtonColors = ButtonDefaults.buttonColors(
    containerColor = IndustrialNominalGreen,
    contentColor = IndustrialTextOnAccent,
    disabledContainerColor = P117DisabledFill,
    disabledContentColor = P117TextDisabled
)

/** Warning-tinted filled button (report issue, queue-for-later). */
@Composable
fun p117WarningButtonColors(): ButtonColors = ButtonDefaults.buttonColors(
    containerColor = IndustrialWarningAmber,
    contentColor = IndustrialTextOnAccent,
    disabledContainerColor = P117DisabledFill,
    disabledContentColor = P117TextDisabled
)

/** Primary action button — one clear primary action per screen. */
@Composable
fun AppButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    colors: ButtonColors = p117PrimaryButtonColors(),
    contentPadding: PaddingValues = PaddingValues(horizontal = 20.dp, vertical = 12.dp),
    content: @Composable RowScope.() -> Unit
) {
    Button(
        onClick = onClick,
        modifier = modifier.defaultMinSize(minHeight = MinTouchTarget),
        enabled = enabled,
        shape = AppButtonShape,
        colors = colors,
        contentPadding = contentPadding,
        content = content
    )
}

/** Secondary action button. */
@Composable
fun AppOutlinedButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    colors: ButtonColors = p117SecondaryButtonColors(),
    border: BorderStroke? = null,
    contentPadding: PaddingValues = PaddingValues(horizontal = 20.dp, vertical = 12.dp),
    content: @Composable RowScope.() -> Unit
) {
    OutlinedButton(
        onClick = onClick,
        modifier = modifier.defaultMinSize(minHeight = MinTouchTarget),
        enabled = enabled,
        shape = AppButtonShape,
        colors = colors,
        border = border,
        contentPadding = contentPadding,
        content = content
    )
}

/** Tertiary / inline text action. Still keeps a 48dp touch target. */
@Composable
fun AppTextButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    colors: ButtonColors = p117TertiaryButtonColors(),
    contentPadding: PaddingValues = PaddingValues(horizontal = 12.dp, vertical = 8.dp),
    content: @Composable RowScope.() -> Unit
) {
    TextButton(
        onClick = onClick,
        modifier = modifier.defaultMinSize(minHeight = MinTouchTarget),
        enabled = enabled,
        shape = AppButtonShape,
        colors = colors,
        contentPadding = contentPadding,
        content = content
    )
}

// ---------------------------------------------------------------------------
// Machine-data register — tags, readings, timestamps
// ---------------------------------------------------------------------------

/** Equipment tag / asset ID in the monospace register. */
@Composable
fun EquipmentTag(
    tag: String,
    modifier: Modifier = Modifier,
    color: Color = IndustrialCyan
) {
    Text(
        text = tag,
        style = EquipmentTagStyle,
        color = color,
        maxLines = 1,
        overflow = TextOverflow.Ellipsis,
        modifier = modifier
            .clip(RoundedCornerShape(6.dp))
            .background(IndustrialDarkSurfaceSunken)
            .border(1.dp, IndustrialBorderSubtle, RoundedCornerShape(6.dp))
            .padding(horizontal = 8.dp, vertical = 4.dp)
    )
}

/** Large at-a-glance sensor reading. */
@Composable
fun ReadingValue(
    value: String,
    color: Color,
    modifier: Modifier = Modifier,
    style: TextStyle = ReadingValueStyle
) {
    Text(text = value, style = style, color = color, modifier = modifier)
}

/** Label / value row used on detail screens. */
@Composable
fun KeyValueRow(
    label: String,
    value: String,
    modifier: Modifier = Modifier,
    valueColor: Color = IndustrialTextPrimary,
    monoValue: Boolean = true
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .padding(vertical = 3.dp),
        verticalAlignment = Alignment.Top
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            color = IndustrialTextSecondary,
            modifier = Modifier.weight(1f)
        )
        Spacer(modifier = Modifier.width(12.dp))
        Text(
            text = value,
            style = if (monoValue) EquipmentTagStyle else MaterialTheme.typography.bodyMedium,
            color = valueColor,
            textAlign = TextAlign.End,
            modifier = Modifier.weight(1f)
        )
    }
}

// ---------------------------------------------------------------------------
// App-wide bars and state views
// ---------------------------------------------------------------------------

@Composable
fun DemoModeBanner(mode: AppMode) {
    if (mode == AppMode.DEMO) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .background(DemoBannerBackground)
                .padding(vertical = 6.dp, horizontal = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.Center
        ) {
            Icon(
                imageVector = Icons.Default.Warning,
                contentDescription = "Demo Mode",
                tint = DemoBannerText,
                modifier = Modifier.size(16.dp)
            )
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                text = "DEMO MODE — Operating on local industrial scenario",
                color = DemoBannerText,
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.Bold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
        }
    }
}

@Composable
fun ConnectionStatusBar(
    mode: AppMode,
    isOnline: Boolean = true,
    isSyncing: Boolean = false,
    pendingSyncCount: Int = 0
) {
    val (tone, label) = when {
        mode == AppMode.DEMO -> Pair(StatusTone.WARNING, "DEMO MODE")
        !isOnline -> Pair(StatusTone.CRITICAL, "BACKEND OFFLINE")
        isSyncing -> Pair(StatusTone.INFO, "SYNCING…")
        else -> Pair(StatusTone.SUCCESS, "CONNECTED")
    }
    val palette = tonePalette(tone)

    Surface(
        color = P117ChromeSurface,
        modifier = Modifier.fillMaxWidth()
    ) {
        Column {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = ScreenPadding, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    P117StatusDot(tone = tone, size = 10.dp)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = label,
                        style = MaterialTheme.typography.labelSmall,
                        color = palette.ink,
                        maxLines = 1
                    )
                }

                if (pendingSyncCount > 0) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            imageVector = Icons.Default.Sync,
                            contentDescription = "Pending Sync",
                            tint = IndustrialCyan,
                            modifier = Modifier.size(14.dp)
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = "$pendingSyncCount pending sync",
                            style = EquipmentTagStyle,
                            color = IndustrialTextSecondary
                        )
                    }
                }
            }
            P117Divider()
        }
    }
}

// ---------------------------------------------------------------------------
// Domain badges — thin mappings onto [StatusChip]
// ---------------------------------------------------------------------------

@Composable
fun EquipmentStatusBadge(status: EquipmentStatus) {
    val (tone, label) = when (status) {
        EquipmentStatus.OPERATIONAL -> Pair(StatusTone.SUCCESS, "OPERATIONAL")
        EquipmentStatus.DEGRADED -> Pair(StatusTone.WARNING, "DEGRADED")
        EquipmentStatus.OFFLINE -> Pair(StatusTone.CRITICAL, "OFFLINE")
        EquipmentStatus.UNDER_MAINTENANCE -> Pair(StatusTone.INFO, "MAINTENANCE")
        EquipmentStatus.UNKNOWN -> Pair(StatusTone.NEUTRAL, "UNKNOWN")
    }
    StatusChip(label = label, tone = tone)
}

@Composable
fun PriorityBadge(priority: WorkOrderPriority) {
    val tone = when (priority) {
        WorkOrderPriority.CRITICAL -> StatusTone.CRITICAL
        WorkOrderPriority.HIGH -> StatusTone.WARNING
        WorkOrderPriority.MEDIUM -> StatusTone.INFO
        WorkOrderPriority.LOW -> StatusTone.NEUTRAL
    }
    StatusChip(label = priority.name, tone = tone)
}

/** Accent colour for a work-order priority — for card rails and glyph tints. */
fun priorityAccent(priority: WorkOrderPriority): Color = when (priority) {
    WorkOrderPriority.CRITICAL -> IndustrialCriticalRed
    WorkOrderPriority.HIGH -> IndustrialWarningAmber
    WorkOrderPriority.MEDIUM -> IndustrialCyan
    WorkOrderPriority.LOW -> IndustrialOfflineSlate
}

/** Accent colour for an equipment status — for card rails and glyph tints. */
fun equipmentStatusAccent(status: EquipmentStatus): Color = when (status) {
    EquipmentStatus.OPERATIONAL -> IndustrialNominalGreen
    EquipmentStatus.DEGRADED -> IndustrialWarningAmber
    EquipmentStatus.OFFLINE -> IndustrialCriticalRed
    EquipmentStatus.UNDER_MAINTENANCE -> IndustrialCyan
    EquipmentStatus.UNKNOWN -> IndustrialOfflineSlate
}

// ---------------------------------------------------------------------------
// Confirmation dialog
// ---------------------------------------------------------------------------

@Composable
fun ConsequentialActionDialog(
    title: String,
    message: String,
    confirmText: String = "Confirm Action",
    onConfirm: () -> Unit,
    onDismiss: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        shape = RoundedCornerShape(22.dp),
        containerColor = MaterialTheme.colorScheme.surface,
        titleContentColor = IndustrialTextPrimary,
        textContentColor = IndustrialTextSecondary,
        icon = {
            P117IconContainer(
                icon = Icons.Default.Warning,
                tint = IndustrialCriticalRed,
                size = 48.dp,
                contentDescription = "Warning"
            )
        },
        title = {
            Text(
                text = title,
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold
            )
        },
        text = {
            Column {
                Text(text = message, style = MaterialTheme.typography.bodyMedium)
                Spacer(modifier = Modifier.height(12.dp))
                StatusBanner(
                    text = "This action directly affects operational equipment state and cannot be undone.",
                    tone = StatusTone.CRITICAL
                )
            }
        },
        confirmButton = {
            AppButton(
                onClick = onConfirm,
                colors = p117DestructiveButtonColors()
            ) {
                Text(text = confirmText, fontWeight = FontWeight.Bold)
            }
        },
        dismissButton = {
            AppOutlinedButton(onClick = onDismiss) {
                Text("Cancel")
            }
        }
    )
}

// ---------------------------------------------------------------------------
// Loading / error states
// ---------------------------------------------------------------------------

@Composable
fun LoadingStateView(message: String = "Loading data…") {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            CircularProgressIndicator(
                color = IndustrialCyan,
                trackColor = IndustrialCyanContainer
            )
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = message.uppercase(),
                style = MaterialTheme.typography.labelMedium,
                color = IndustrialTextSecondary,
                textAlign = TextAlign.Center
            )
        }
    }
}

@Composable
fun ErrorStateView(
    message: String,
    onRetry: (() -> Unit)? = null
) {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            P117IconContainer(
                icon = Icons.Default.ErrorOutline,
                tint = IndustrialCriticalRed,
                size = 64.dp,
                contentDescription = "Error"
            )
            Spacer(modifier = Modifier.height(14.dp))
            Text(
                text = message,
                style = MaterialTheme.typography.bodyMedium,
                color = IndustrialTextPrimary,
                textAlign = TextAlign.Center
            )
            if (onRetry != null) {
                Spacer(modifier = Modifier.height(18.dp))
                AppButton(onClick = onRetry) {
                    Text("Retry")
                }
            }
        }
    }
}
