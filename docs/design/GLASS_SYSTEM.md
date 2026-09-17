# Console glass design system

The shared contract for every redesigned console surface. Read this before
touching a page. It exists so seven workstreams land as one product instead of
seven.

## Stack

| Concern | Use |
|---|---|
| Layout / surface | Tailwind utility classes, inline in the TSX |
| Icons | `lucide-react` via `@/components/ui/LucideIcon` (`<Lucide name="home" />` or `lucideFor(name)`) |
| Motion | `framer-motion` + the presets in `@/lib/ui/motion` |
| Existing behaviour | The `cs-*` / `pmap__*` / `sm-*` class names stay. They carry geometry the whole app (and the Playwright gates) depend on. |

**Never** rewrite a page's data wiring, props or event handlers to get a visual
result. Restyle around them.

## Surfaces

```txt
page background      GlassBackdrop (already mounted by AppShell) — do not add another
floating panel       rounded-2xl border border-slate-200/80 bg-white/80 backdrop-blur-xl
                     shadow-sm
inner card           rounded-xl border border-slate-200/60 bg-white/60 backdrop-blur-md
row / list item      rounded-lg hover:bg-slate-50/80 transition-colors
```

`border-slate-200/80` + `bg-white/80` + `backdrop-blur-xl` + `shadow-sm` is the
exact shell recipe. Match it.

## Colour semantics

Colour is meaning, never decoration.

| Meaning | Tone |
|---|---|
| Intelligence / AI / live data | cyan — `cyan-500/600`, `#0891b2` |
| Verified / healthy | emerald — `emerald-500/600` |
| Human decision pending | amber — `amber-500/600` |
| Anomaly / critical | red — `red-500/600` |
| Knowledge / memory | violet — `violet-500/600` |
| Hot stream / high temperature | orange — `orange-500` |
| Cold stream / coolant | blue — `blue-500` |
| Neutral text | `slate-900` heading, `slate-600` body, `slate-400` meta |

Text on glass: headings `text-slate-900`, body `text-slate-600`, meta
`text-slate-400`. Never pure black.

## Motion

Import from `@/lib/ui/motion` — do not invent springs.

```ts
SPRING_OPTIONS.panel   // { stiffness: 300, damping: 30 }  → useSpring(...) and the sidebar
SPRING.panel           // the same thing as a <motion> transition
SPRING.surface         // large surfaces
SPRING.micro           // hover lifts, icon scales
SPRING.glide           // sibling layout transitions
ICON_HOVER             // { scale: 1.05 }
LIFT_HOVER             // { y: -4 }
fadeSlide(d)           // variants: initial/animate/exit
TAB_PANEL              // cross-fade variant for tab panels
iconGlow(hex, a)       // drop-shadow string for icon hover
```

Rules:

- **Hover micro-interaction on an icon** = `whileHover="hover"` on the parent
  with `variants={{ hover: ICON_HOVER }}` on the wrapper and
  `variants={{ hover: { filter: iconGlow(...) } }}` on the glyph. See `Rail.tsx`.
- **Active tab / segment indicator** = one `<motion.span layoutId="…" />`
  rendered by the active item only. `layoutId` must be unique per component
  instance — pass it as a prop if the component can mount twice.
- **Page/tab content switch** = `<AnimatePresence mode="wait">` + `TAB_PANEL`.
- Respect `prefers-reduced-motion` for anything that loops forever. One-shot
  transitions are fine.

## Live data is not optional

Every number, badge, status and trend must come from the existing data source
(`consoleData`, `useSimulation`, the adapter). If a value is loading or absent,
render an honest placeholder (`—`, "Connecting") — never a hardcoded green dot, a
random number, or a fake sparkline. Several gates exist specifically to catch
fabricated status; see `.p117-audit/posture.mjs`.

## Verifying your work

From the repo root:

```bash
pnpm run typecheck          # must be clean
pnpm run lint               # 0 errors (warnings are pre-existing, don't add more)
```

Then screenshot your page with Playwright against `http://127.0.0.1:3017` and
check the console for errors. A page that throws a hydration warning or a page
error is not done.

Gates that must keep passing (do not run them concurrently with each other —
each one resets the backend plant):

```bash
node .p117-audit/simulation-views.mjs     # 31 checks
node .p117-audit/process-map.mjs          # 18 checks
node .p117-audit/sensor-failover.mjs      # 13 checks
node .p117-audit/posture.mjs              # 9 checks
node .p117-audit/verify.mjs               # 29 checks
node .p117-audit/mock-banner.mjs          # 9 checks
```

The dev server is already running on port 3017. Do **not** start another one.
