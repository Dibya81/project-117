"use client";

/** Console icon set — inline SVG, stroke-based, 16px grid. No icon package. */
import type { SVGProps } from "react";

export type IconName =
  | "home" | "chat" | "check" | "doc" | "graph" | "history" | "equipment"
  | "workorder" | "insights" | "admin" | "bell" | "search" | "user" | "x"
  | "arrow" | "download" | "upload" | "plus" | "shield" | "cpu" | "file"
  | "send" | "filter" | "layers" | "gauge" | "pulse" | "lock" | "database"
  | "workflow" | "wrench" | "alert" | "clock" | "chevron" | "refresh"
  | "eye" | "zap" | "terminal" | "globe" | "pause" | "play" | "dots";

const PATHS: Record<IconName, string> = {
  home: "M3 8.5 8 4l5 4.5V13H3z M6.5 13v-3h3v3",
  chat: "M3 4h10v7H7l-4 3z",
  check: "M3 8.5 6.5 12 13 4.5",
  doc: "M4 2.5h5.5L12.5 6v7.5H4z M9 2.5V6h3.5",
  graph: "M4 12.5 8 3.5l4 9z M4 12.5h8",
  history: "M8 2.5a5.5 5.5 0 1 1-5.4 6.5 M2.5 5v3.5H6 M8 5.5V8l2 1.5",
  equipment: "M8 2.8a3.2 3.2 0 0 1 3.1 4L12.5 8l-1.4 1.2a3.2 3.2 0 1 1-6.2 0L3.5 8l1.4-1.2a3.2 3.2 0 0 1 3.1-4z M8 8h.01",
  workorder: "M4 2.5h8v11H4z M6.5 5.5h3 M6.5 8h3 M6.5 10.5h2",
  insights: "M2.5 13.5v-4 M6 13.5V6 M9.5 13.5V8.5 M13 13.5V3.5",
  admin: "M8 2.5 13 4.5v3c0 3-2.2 5-5 6-2.8-1-5-3-5-6v-3z",
  bell: "M4 11.5h8l-1.2-2V7a4.8 4.8 0 0 0-5.6 0v2.5z M6.8 13.5h2.4",
  search: "M7 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8z M10 10l3 3",
  user: "M8 8a2.6 2.6 0 1 0 0-5.2A2.6 2.6 0 0 0 8 8z M3 13.5c.6-2.4 2.6-3.6 5-3.6s4.4 1.2 5 3.6",
  x: "M4 4l8 8 M12 4l-8 8",
  arrow: "M2.5 8h11 M9.5 3.5 14 8l-4.5 4.5",
  download: "M8 2.5v8 M4.5 7.5 8 11l3.5-3.5 M3 13.5h10",
  upload: "M8 10.5v-8 M4.5 5.5 8 2l3.5 3.5 M3 13.5h10",
  plus: "M8 3v10 M3 8h10",
  shield: "M8 2.5 13 4.5v3c0 3-2.2 5-5 6-2.8-1-5-3-5-6v-3z M6 8l1.5 1.5L10.5 6",
  cpu: "M5 5h6v6H5z M8 2.5V5 M8 11v2.5 M2.5 8H5 M11 8h2.5",
  file: "M4 2.5h5.5L12.5 6v7.5H4z",
  send: "M2.5 8 13.5 3 9.5 13.5 7.5 9.5z M7.5 9.5 13.5 3",
  filter: "M2.5 4h11 M4.5 8h7 M6.5 12h3",
  layers: "M8 2.5 13.5 5.5 8 8.5 2.5 5.5z M2.5 8.5 8 11.5l5.5-3 M2.5 11.5 8 14l5.5-2.5",
  gauge: "M2.5 11a5.5 5.5 0 0 1 11 0 M8 11l2.5-3.5",
  pulse: "M2.5 8h2.5l1.5-4 2.5 8 1.5-4h3",
  lock: "M4.5 7V5.5a3.5 3.5 0 0 1 7 0V7 M3.5 7h9v6.5h-9z M8 10v1.5",
  database: "M8 2.5c3 0 5.5.9 5.5 2s-2.5 2-5.5 2-5.5-.9-5.5-2 2.5-2 5.5-2z M2.5 4.5v7c0 1.1 2.5 2 5.5 2s5.5-.9 5.5-2v-7 M2.5 8c0 1.1 2.5 2 5.5 2s5.5-.9 5.5-2",
  workflow: "M4 3.5a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3z M12 9.5a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3z M4 6.5v3a2 2 0 0 0 2 2h4.5",
  wrench: "M10.5 2.5a3 3 0 0 0-3.8 3.8L3 10l3 3 3.7-3.7a3 3 0 0 0 3.8-3.8L11 7 9 5z",
  alert: "M8 2.5 14 13H2z M8 6.5v3 M8 11.2v.1",
  clock: "M8 2.5a5.5 5.5 0 1 1 0 11 5.5 5.5 0 0 1 0-11z M8 5v3l2 1.5",
  chevron: "M6 3.5 10.5 8 6 12.5",
  refresh: "M13 8a5 5 0 1 1-1.6-3.6 M13 2.5v3h-3",
  eye: "M2.5 8s2-4 5.5-4 5.5 4 5.5 4-2 4-5.5 4S2.5 8 2.5 8z M8 9.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z",
  zap: "M8.5 2 3.5 9H7l-1 5 5.5-7H8z",
  terminal: "M2.5 3.5h11v9h-11z M5 6.5 7 8l-2 1.5 M8.5 10h3",
  globe: "M8 2.5a5.5 5.5 0 1 1 0 11 5.5 5.5 0 0 1 0-11z M2.5 8h11 M8 2.5c-3.5 3.5-3.5 7.5 0 11 3.5-3.5 3.5-7.5 0-11z",
  pause: "M5.5 3.5v9 M10.5 3.5v9",
  play: "M5 3.5 12 8l-7 4.5z",
  dots: "M4 8h.01 M8 8h.01 M12 8h.01",
};

export function Icon({ name, size = 16, ...rest }: { name: IconName; size?: number } & SVGProps<SVGSVGElement>) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.3"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...rest}
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
