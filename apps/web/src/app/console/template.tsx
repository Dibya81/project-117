"use client";

/**
 * Route transition — a fast spatial "warp" between environments.
 * The destination announces itself (e.g. KNOWLEDGE UNIVERSE) while the new
 * page rises in. 420ms, never blocks interaction, reduced-motion → off.
 */
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";

const LABELS: [RegExp, string][] = [
  [/^\/console\/home/, "Command Center"],
  [/^\/console\/workspace/, "AI Investigation"],
  [/^\/console\/documents/, "Document Intelligence"],
  [/^\/console\/knowledge/, "Knowledge Universe"],
  [/^\/console\/history/, "Organizational Memory"],
  [/^\/console\/equipment\/[^/]+/, "Digital Twin"],
  [/^\/console\/equipment/, "Plant Assets"],
  [/^\/console\/work-orders\/[^/]+/, "Execution Narrative"],
  [/^\/console\/work-orders/, "Action System"],
  [/^\/console\/insights/, "Intelligence Lab"],
  [/^\/console\/approvals/, "Governance Chamber"],
  [/^\/console\/admin/, "Sovereignty Control"],
];

export default function ConsoleTemplate({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [warp, setWarp] = useState<string | null>(null);
  const first = useRef(true);

  useEffect(() => {
    // no warp on first mount (shell intro) or reduced motion
    if (first.current) {
      first.current = false;
      return;
    }
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const label = LABELS.find(([re]) => re.test(pathname))?.[1];
    if (!label) return;
    setWarp(label);
    const t = setTimeout(() => setWarp(null), 430);
    return () => clearTimeout(t);
  }, [pathname]);

  return (
    <>
      {warp && (
        <div className="cs-warp" aria-hidden="true">
          <span className="cs-warp__label">{warp}</span>
        </div>
      )}
      <div key={pathname} className="cs-page">
        {children}
      </div>
    </>
  );
}
