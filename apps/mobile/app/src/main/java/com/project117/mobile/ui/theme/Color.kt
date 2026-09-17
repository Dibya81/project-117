package com.project117.mobile.ui.theme

import androidx.compose.ui.graphics.Color

/*
 * Project 117 — industrial field palette, LIGHT.
 *
 * Visual language: a near-white page, true-white cards and thin hairline
 * borders; colour is spent on *status only* and never as page decoration. The
 * single brand accent is a deep, saturated blue that survives direct sunlight
 * on a glossy handset screen. Status is always a tinted background plus a
 * coloured accent bar/dot/border and a written label — never a large saturated
 * fill and never colour alone.
 *
 * ---------------------------------------------------------------------------
 * Contrast budget (WCAG 2.1 AA). Every ratio below is *measured*, not estimated.
 *
 * Body text on a white card (#FFFFFF) — requires >= 4.5 : 1
 *   IndustrialTextPrimary    #0F172A  17.85 : 1
 *   IndustrialTextSecondary  #475569   7.58 : 1
 *   IndustrialTextMuted      #5C6B7E   5.44 : 1
 *   IndustrialCyan           #175BC4   6.31 : 1
 *   IndustrialTeal           #0F766E   5.47 : 1
 *   IndustrialNominalGreen   #15803D   5.02 : 1
 *   IndustrialWarningAmber   #B45309   5.02 : 1
 *   IndustrialCriticalRed    #C0392B   5.44 : 1
 *   IndustrialOfflineSlate   #5F6E82   5.20 : 1
 *
 * Same text on the page background (#F6F8FB) — requires >= 4.5 : 1
 *   IndustrialTextPrimary    #0F172A  16.78 : 1
 *   IndustrialTextSecondary  #475569   7.12 : 1
 *   IndustrialTextMuted      #5C6B7E   5.11 : 1
 *   IndustrialCyan           #175BC4   5.93 : 1
 *   IndustrialNominalGreen   #15803D   4.71 : 1
 *   IndustrialWarningAmber   #B45309   4.72 : 1
 *   IndustrialCriticalRed    #C0392B   5.11 : 1
 *
 * Same text on a sunken/inset well (#EDF1F7) — requires >= 4.5 : 1
 *   IndustrialTextPrimary    #0F172A  15.75 : 1
 *   IndustrialTextSecondary  #475569   6.68 : 1
 *   IndustrialTextMuted      #5C6B7E   4.80 : 1
 *   IndustrialCyan           #175BC4   5.56 : 1
 *
 * Inverse — white label on a saturated fill
 *   #FFFFFF on IndustrialCyan          #175BC4   6.31 : 1
 *   #FFFFFF on IndustrialCriticalStrong#B3261E   6.54 : 1
 *   #FFFFFF on IndustrialNominalGreen  #15803D   5.02 : 1
 *   #FFFFFF on IndustrialWarningAmber  #B45309   5.02 : 1
 *
 * Status "ink" on its own 12 % tint over white (chip + banner body text)
 *   P117InkSuccess  #146C34 on #E3F0E8   5.44 : 1
 *   P117InkWarning  #96470A on #F6EAE1   5.47 : 1
 *   P117InkCritical #AB2E22 on #F7E7E6   5.51 : 1
 *   P117InkInfo     #1558BC on #E3EBF8   5.55 : 1
 *   P117InkNeutral  #516075 on #ECEEF0   5.41 : 1
 *
 * Functional UI boundaries (input outlines, button borders, focus rings and
 * card accent bars) — requires >= 3 : 1 as non-text contrast
 *   IndustrialBorderStrong   #7C8CA1 on #FFFFFF   3.43 : 1
 *   IndustrialBorderStrong   #7C8CA1 on #F6F8FB   3.22 : 1
 *
 * Decorative hairlines are deliberately below 3 : 1. WCAG 1.4.11 exempts
 * purely decorative separators; a 3 : 1 hairline between two white surfaces
 * reads as a hard box and destroys the layered light look the brief asks for.
 * They are never the only signal for any state.
 *   IndustrialDarkSurfaceBorder #E3E8EF on #FFFFFF   1.23 : 1  (decorative)
 *   IndustrialBorderSubtle      #EDF1F7 on #FFFFFF   1.14 : 1  (decorative)
 *
 * Demo caution strip (amber plant tape, dark label)
 *   DemoBannerText #7C2D12 on DemoBannerBackground #FCD34D   6.50 : 1
 * ---------------------------------------------------------------------------
 *
 * Value names are kept stable — 60+ call sites import them directly and the
 * whole app compiles against these identifiers. Several still carry a "Dark"
 * or "Cyan" name from the previous theme; the names are historical, the values
 * are the light ones. Where a name would now be actively misleading a clearly
 * named alias is added beside it rather than renaming the original.
 */

// ---------------------------------------------------------------------------
// Foundation — near-white page, true-white cards, cool grey insets.
// ---------------------------------------------------------------------------

/** Page background. Near-white, very slightly cool so white cards lift off it. */
val IndustrialDarkBackground = Color(0xFFF6F8FB)

/** Light alias for [IndustrialDarkBackground]. */
val P117PageBackground = IndustrialDarkBackground

/** App bar / chrome / sheet surface — pure white. */
val IndustrialDarkSurface = Color(0xFFFFFFFF)

/** Light alias for [IndustrialDarkSurface]. */
val P117ChromeSurface = IndustrialDarkSurface

/** Card and list-item surface — pure white, one step above the page. */
val IndustrialDarkSurfaceVariant = Color(0xFFFFFFFF)

/** Light alias for [IndustrialDarkSurfaceVariant]. */
val P117CardSurface = IndustrialDarkSurfaceVariant

/** Sunken wells: camera viewport, photo placeholders, inline code blocks. */
val IndustrialDarkSurfaceSunken = Color(0xFFEDF1F7)

/** Light alias for [IndustrialDarkSurfaceSunken]. */
val P117InsetSurface = IndustrialDarkSurfaceSunken

/** Structural hairline for cards and containers. Decorative (see header). */
val IndustrialDarkSurfaceBorder = Color(0xFFE3E8EF)

/** Hairline divider — quieter than a structural border. Decorative. */
val IndustrialBorderSubtle = Color(0xFFEDF1F7)

/**
 * Functional border: text-field outlines, button borders, focus rings, card
 * accent rails. Measured 3.43 : 1 on white, so it satisfies WCAG 1.4.11.
 */
val IndustrialBorderStrong = Color(0xFF7C8CA1)

// ---------------------------------------------------------------------------
// Accent — one deep, saturated blue. This is the only decorative colour.
// ---------------------------------------------------------------------------

/** Primary accent. Readable as body text on white (6.31 : 1) and as a fill. */
val IndustrialCyan = Color(0xFF175BC4)

/** Light blue used for progress tracks, chips and pressed containers. */
val IndustrialCyanDim = Color(0xFF9DC0EE)

/** Very light blue container for info-toned surfaces. */
val IndustrialCyanContainer = Color(0xFFDCE8F9)

/** Cool teal secondary accent (assistant / advisory surfaces). 5.47 : 1. */
val IndustrialTeal = Color(0xFF0F766E)

/** Label colour that sits on top of an accent or status fill. */
val IndustrialTextOnAccent = Color(0xFFFFFFFF)

// ---------------------------------------------------------------------------
// Status semantics — colour is meaning, never decoration. Every use is paired
// with a text label or icon so status never depends on colour alone.
//
// Mapping onto the brief's six states:
//   NORMAL       -> IndustrialNominalGreen  (StatusTone.SUCCESS)
//   WARNING      -> IndustrialWarningAmber  (StatusTone.WARNING)
//   CRITICAL     -> IndustrialCriticalRed   (StatusTone.CRITICAL)
//   INFORMATION  -> IndustrialCyan          (StatusTone.INFO)
//   SYNCING      -> IndustrialCyan          (StatusTone.INFO, animated label)
//   OFFLINE      -> IndustrialOfflineSlate  (StatusTone.NEUTRAL)
// ---------------------------------------------------------------------------

/** Healthy / nominal / verified. 5.02 : 1 as text on white. */
val IndustrialNominalGreen = Color(0xFF15803D)

/** Warning / pending human decision. 5.02 : 1 as text on white. */
val IndustrialWarningAmber = Color(0xFFB45309)

/** Critical / anomaly. 5.44 : 1 as text on white. */
val IndustrialCriticalRed = Color(0xFFC0392B)

/** Deep critical red used as a *fill* behind white label text (6.54 : 1). */
val IndustrialCriticalStrong = Color(0xFFB3261E)

/** Offline / unknown / de-emphasised neutral. 5.20 : 1 as text on white. */
val IndustrialOfflineSlate = Color(0xFF5F6E82)

// Status inks — used for text that sits on that status's own tinted container.
// The tint lifts the background toward the accent, so the label needs the
// deeper shade of the same hue to stay above 4.5 : 1.

val P117InkSuccess = Color(0xFF146C34)
val P117InkWarning = Color(0xFF96470A)
val P117InkCritical = Color(0xFFAB2E22)
val P117InkInfo = Color(0xFF1558BC)
val P117InkNeutral = Color(0xFF516075)

// Light status containers — the tinted background behind a chip or banner.
// These are opaque values (not alpha) so the measured ratios above hold
// wherever the surface sits, including on top of a sunken well.

val P117ContainerSuccess = Color(0xFFE3F0E8)
val P117ContainerWarning = Color(0xFFF6EAE1)
val P117ContainerCritical = Color(0xFFF7E7E6)
val P117ContainerInfo = Color(0xFFE3EBF8)
val P117ContainerNeutral = Color(0xFFECEEF0)

// ---------------------------------------------------------------------------
// Text
// ---------------------------------------------------------------------------

/** Primary type on light. 17.85 : 1 on white. */
val IndustrialTextPrimary = Color(0xFF0F172A)

/** Secondary type and supporting copy. 7.58 : 1 on white. */
val IndustrialTextSecondary = Color(0xFF475569)

/** Metadata only. Still 5.44 : 1 on white and 4.80 : 1 on a sunken well. */
val IndustrialTextMuted = Color(0xFF5C6B7E)

/** Placeholder / disabled type. Exempt from contrast (1.4.3 disabled). */
val P117TextDisabled = Color(0xFF94A3B8)

/** Disabled button fill. Paired with [P117TextDisabled]. */
val P117DisabledFill = Color(0xFFE2E8F0)

// ---------------------------------------------------------------------------
// Elevation / press states — light theme needs shadow + tint, not lightening.
// ---------------------------------------------------------------------------

/** Resting card shadow alpha. Kept low: layered light, not drop-shadow soup. */
val P117CardShadow = Color(0x140F172A)

/** Pressed-state wash laid over a white card. */
val P117PressedOverlay = Color(0x0F175BC4)

// ---------------------------------------------------------------------------
// Demo-mode caution strip — amber plant tape with a dark label.
// ---------------------------------------------------------------------------

val DemoBannerBackground = Color(0xFFFCD34D)
val DemoBannerText = Color(0xFF7C2D12)
