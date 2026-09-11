/** Typography primitives for the landing scenes — the editorial voice of
 * the page lives here so scenes stay declarative. */
import type { ReactNode } from "react";

export function Kicker({ children, tone = "cyan" }: { children: ReactNode; tone?: "cyan" | "orange" }) {
  return <p className={`p117-kicker${tone === "orange" ? " p117-kicker--orange" : ""}`}>{children}</p>;
}

export function Headline({ children }: { children: ReactNode }) {
  return <h2 className="p117-headline">{children}</h2>;
}

export function Sub({ children }: { children: ReactNode }) {
  return <p className="p117-sub">{children}</p>;
}

export function MonoLine({ children }: { children: ReactNode }) {
  return <p className="p117-mono-line">{children}</p>;
}
