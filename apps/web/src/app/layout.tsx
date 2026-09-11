import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Project 117 — Sovereign Industrial AI",
  description:
    "Sovereign Industrial AI for Manufacturing Operations. From information to action. On-prem. In your hands.",
};

export const viewport: Viewport = {
  themeColor: "#070a0e",
  colorScheme: "dark",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
