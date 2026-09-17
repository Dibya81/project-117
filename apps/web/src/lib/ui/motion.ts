/**
 * Shared motion vocabulary for the console.
 *
 * Every animated surface reads its spring from here so the shell, the pages and
 * the canvas move with one physical feel instead of each inventing its own
 * duration. Values are deliberately few: a UI that uses six different springs
 * reads as six different products.
 *
 * `SPRING.panel` is the one the spec names explicitly (stiffness 300, damping
 * 30) — the sidebar collapse, the drawer and the segmented control all use it.
 */
import type { Transition, Variants } from "framer-motion";

/**
 * BARE spring parameters.
 *
 * `useSpring` (which drives the sidebar width) takes `SpringOptions` — just
 * stiffness/damping/mass — while `<motion.div transition>` takes a `Transition`,
 * which also carries `type: "spring"`. Keeping the numbers in one place and
 * deriving both shapes from them means the hook and the component cannot drift
 * apart.
 */
export const SPRING_OPTIONS = {
  panel: { stiffness: 300, damping: 30 },
  surface: { stiffness: 220, damping: 28 },
  micro: { stiffness: 520, damping: 26 },
  glide: { stiffness: 380, damping: 34 },
} as const;

export const SPRING = {
  /** Named in the shell spec: snappy, no visible overshoot on a 232px column. */
  panel: { type: "spring", ...SPRING_OPTIONS.panel } as Transition,
  /** Softer, for large surfaces where a hard stop looks mechanical. */
  surface: { type: "spring", ...SPRING_OPTIONS.surface } as Transition,
  /** Micro-interactions only — hover lifts, icon scales. */
  micro: { type: "spring", ...SPRING_OPTIONS.micro } as Transition,
  /** Layout transitions between sibling tabs. */
  glide: { type: "spring", ...SPRING_OPTIONS.glide } as Transition,
} as const;

/** Pointer-driven micro-interaction: icons grow 5% and glow. */
export const ICON_HOVER = { scale: 1.05 } as const;

/** Shared hover lift for cards. */
export const LIFT_HOVER = { y: -4 } as const;

export const fadeSlide = (distance = 8): Variants => ({
  initial: { opacity: 0, y: distance },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -distance },
});

/** Cross-fade used by the workspace inspection tabs. */
export const TAB_PANEL: Variants = {
  initial: { opacity: 0, x: 12 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: -12 },
};

/**
 * The neon glow an icon wears on hover.
 *
 * Kept as a filter string rather than a box-shadow because the icons are inline
 * SVG strokes: a drop-shadow follows the glyph instead of drawing a rectangle
 * around it.
 */
export function iconGlow(hex: string, strength = 0.55): string {
  return `drop-shadow(0 0 4px ${hex}${Math.round(strength * 255).toString(16).padStart(2, "0")})`;
}
