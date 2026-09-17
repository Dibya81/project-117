"use client";

/**
 * LucideIcon — the console's icon vocabulary, mapped onto Lucide.
 *
 * The shell and the redesigned pages use Lucide glyphs, but hundreds of call
 * sites pass the existing `IconName` union (`"home"`, `"workorder"`, …) which is
 * also what the nav tables and scenario data carry. Rather than rewrite every
 * caller, this adapter keeps the semantic name and swaps the drawing: one map,
 * so a name means the same glyph everywhere and a missing glyph is a type error
 * at build time rather than a blank square at runtime.
 */
import {
  Activity,
  ArrowRight,
  BarChart3,
  Bell,
  ChevronRight,
  CircleCheck,
  ClipboardList,
  Clock,
  Cpu,
  Database,
  Download,
  Eye,
  Factory,
  File,
  FileText,
  Gauge,
  Globe,
  History,
  Home,
  Layers,
  Lock,
  MessageSquare,
  MoreHorizontal,
  Pause,
  Play,
  Plus,
  Printer,
  RefreshCw,
  Search,
  Send,
  Shield,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Terminal,
  TriangleAlert,
  Upload,
  User,
  Wrench,
  X,
  Zap,
  Workflow,
  type LucideIcon as LucideIconType,
} from "lucide-react";
import type { IconName } from "@/components/ui/Icon";

export const LUCIDE_BY_NAME: Record<IconName, LucideIconType> = {
  home: Home,
  chat: MessageSquare,
  check: CircleCheck,
  doc: FileText,
  graph: Sparkles,
  history: History,
  equipment: Factory,
  workorder: ClipboardList,
  insights: BarChart3,
  admin: ShieldCheck,
  bell: Bell,
  search: Search,
  user: User,
  x: X,
  arrow: ArrowRight,
  download: Download,
  upload: Upload,
  plus: Plus,
  shield: Shield,
  cpu: Cpu,
  file: File,
  send: Send,
  filter: SlidersHorizontal,
  layers: Layers,
  gauge: Gauge,
  pulse: Activity,
  lock: Lock,
  database: Database,
  workflow: Workflow,
  wrench: Wrench,
  alert: TriangleAlert,
  clock: Clock,
  chevron: ChevronRight,
  refresh: RefreshCw,
  eye: Eye,
  zap: Zap,
  terminal: Terminal,
  globe: Globe,
  pause: Pause,
  play: Play,
  dots: MoreHorizontal,
  printer: Printer,
};

/**
 * Resolve a semantic icon name to its Lucide component.
 * Falls back to `Activity` so an unknown name degrades to a neutral glyph
 * rather than crashing a render.
 */
export function lucideFor(name: IconName | string): LucideIconType {
  return LUCIDE_BY_NAME[name as IconName] ?? Activity;
}

/**
 * A Lucide glyph resolved from the console's semantic icon name.
 *
 * Why this wrapper exists: Lucide derives part of its `class` attribute from the
 * icon's own alias data, and its CJS and ESM builds disagreed about it (`Home`
 * rendered as `lucide lucide-house` on the server and `lucide lucide-house
 * lucide-home` in the browser), which React reported as a hydration mismatch.
 * The fix is in `next.config.mjs` — `transpilePackages: ["lucide-react"]` makes
 * both environments compile the same ESM source. This wrapper deliberately does
 * NOT suppress hydration warnings: if markup ever diverges again, the console
 * should say so.
 */
export function Lucide({
  name,
  size = 16,
  strokeWidth = 2,
  className,
  style,
  ...rest
}: {
  name: IconName | string;
  size?: number;
  strokeWidth?: number;
  className?: string;
  style?: React.CSSProperties;
} & Omit<React.SVGProps<SVGSVGElement>, "name" | "size" | "strokeWidth" | "className" | "style">) {
  const Glyph = lucideFor(name);
  return <Glyph size={size} strokeWidth={strokeWidth} className={className} style={style} {...rest} />;
}

