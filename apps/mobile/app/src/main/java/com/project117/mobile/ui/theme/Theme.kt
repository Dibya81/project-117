package com.project117.mobile.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

/*
 * Project 117 is a LIGHT field client.
 *
 * The palette is intentionally light-dominant: a near-white page, white cards
 * and a deep navy type ramp, so a photograph of a nameplate, a photo of a
 * bearing and a printed work order all read the way they do on paper. Colour is
 * reserved for status (see Color.kt for the measured contrast budget).
 *
 * There is deliberately no dark scheme to switch to. `darkTheme` is kept in the
 * signature because MainActivity and any preview call sites pass it through;
 * the value is ignored — the client renders light regardless of the system
 * setting, which is what makes the sunlit-readability guarantee hold.
 */
private val LightColorScheme = lightColorScheme(
    primary = IndustrialCyan,
    onPrimary = IndustrialTextOnAccent,
    primaryContainer = IndustrialCyanContainer,
    onPrimaryContainer = Color(0xFF0B2E63),
    inversePrimary = IndustrialCyanDim,

    secondary = IndustrialTeal,
    onSecondary = IndustrialTextOnAccent,
    secondaryContainer = Color(0xFFD6EFEC),
    onSecondaryContainer = Color(0xFF06423D),

    tertiary = IndustrialWarningAmber,
    onTertiary = IndustrialTextOnAccent,
    tertiaryContainer = P117ContainerWarning,
    onTertiaryContainer = P117InkWarning,

    background = IndustrialDarkBackground,
    onBackground = IndustrialTextPrimary,

    surface = IndustrialDarkSurface,
    onSurface = IndustrialTextPrimary,
    surfaceVariant = IndustrialDarkSurfaceSunken,
    onSurfaceVariant = IndustrialTextSecondary,
    surfaceTint = IndustrialCyan,

    inverseSurface = IndustrialTextPrimary,
    inverseOnSurface = IndustrialDarkBackground,

    error = IndustrialCriticalRed,
    onError = IndustrialTextOnAccent,
    errorContainer = P117ContainerCritical,
    onErrorContainer = P117InkCritical,

    // `outline` is the functional border (text fields, outlined buttons) and is
    // therefore held at >= 3 : 1 on white. `outlineVariant` is the decorative
    // hairline between cards and is intentionally much softer.
    outline = IndustrialBorderStrong,
    outlineVariant = IndustrialDarkSurfaceBorder,
    scrim = Color(0x990F172A),

    surfaceBright = Color(0xFFFFFFFF),
    surfaceDim = Color(0xFFEDF1F7),
    surfaceContainerLowest = Color(0xFFFFFFFF),
    surfaceContainerLow = Color(0xFFFAFBFD),
    surfaceContainer = Color(0xFFFFFFFF),
    surfaceContainerHigh = Color(0xFFF2F5F9),
    surfaceContainerHighest = Color(0xFFEDF1F7)
)

/*
 * Corner language: one radius family across the app. Cards are 14dp, text
 * fields 10dp, chips 8dp, dialogs 22dp. Buttons use a shared 10dp shape from
 * `ui/components` because Material maps its default button shape to a pill,
 * which reads consumer-grade rather than industrial.
 */
val Project117Shapes = Shapes(
    extraSmall = RoundedCornerShape(10.dp),
    small = RoundedCornerShape(8.dp),
    medium = RoundedCornerShape(14.dp),
    large = RoundedCornerShape(18.dp),
    extraLarge = RoundedCornerShape(22.dp)
)

@Composable
fun Project117Theme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    // `darkTheme` is accepted for source compatibility and intentionally ignored:
    // the field client is light-only so sunlit legibility is not a user setting.
    @Suppress("UNUSED_EXPRESSION")
    darkTheme

    MaterialTheme(
        colorScheme = LightColorScheme,
        typography = Typography,
        shapes = Project117Shapes,
        content = content
    )
}
