"use client";

/**
 * Journey — contextual continuity across the console.
 * Pages report the entity the user is travelling through; a slim bar under
 * the topbar renders the live chain:
 *   Investigating C-3 · vibration anomaly → WO-8852 …
 * The point: navigation never feels like opening unrelated pages — you move
 * through one intelligence graph.
 */
import { createContext, useCallback, useContext, useMemo, useState, type CSSProperties, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { Icon, type IconName } from "@/components/ui/Icon";

export interface JourneyNode {
  id: string;
  label: string;
  kind: "equipment" | "document" | "workorder" | "approval" | "investigation" | "knowledge" | "insight";
  href: string;
}

const KIND_ICON: Record<JourneyNode["kind"], IconName> = {
  equipment: "equipment",
  document: "doc",
  workorder: "workorder",
  approval: "check",
  investigation: "zap",
  knowledge: "graph",
  insight: "insights",
};

const KIND_COLOR: Record<JourneyNode["kind"], string> = {
  equipment: "var(--cyan)",
  document: "var(--cyan)",
  workorder: "var(--warn)",
  approval: "var(--warn)",
  investigation: "var(--cyan)",
  knowledge: "var(--violet)",
  insight: "var(--violet)",
};

interface JourneyState {
  trail: JourneyNode[];
  visit: (node: JourneyNode) => void;
  clear: () => void;
}

const JourneyContext = createContext<JourneyState>({
  trail: [],
  visit: () => undefined,
  clear: () => undefined,
});

export function JourneyProvider({ children }: { children: ReactNode }) {
  const [trail, setTrail] = useState<JourneyNode[]>([]);

  const visit = useCallback((node: JourneyNode) => {
    setTrail((cur) => {
      // no duplicates; re-visit moves to the end
      const next = cur.filter((n) => n.id !== node.id);
      next.push(node);
      return next.slice(-6);
    });
  }, []);

  const clear = useCallback(() => setTrail([]), []);

  const value = useMemo(() => ({ trail, visit, clear }), [trail, visit, clear]);
  return <JourneyContext.Provider value={value}>{children}</JourneyContext.Provider>;
}

/** Pages call this once on mount with the entity they represent. */
export function useJourney(): JourneyState {
  return useContext(JourneyContext);
}

export function JourneyBar() {
  const { trail, clear } = useJourney();
  const router = useRouter();
  if (trail.length < 2) return null;

  return (
    <div className="cs-journey" role="navigation" aria-label="Investigation journey">
      <span className="cs-journey__lead cs-mono">JOURNEY</span>
      {trail.map((n, i) => (
        <span key={n.id} className="cs-journey__node" style={{ animationDelay: `${i * 70}ms` }}>
          {i > 0 && <span className="cs-journey__arrow">→</span>}
          <button
            className="cs-journey__link"
            style={{ "--jn-c": KIND_COLOR[n.kind] } as CSSProperties}
            onClick={() => router.push(n.href)}
            title={n.kind}
          >
            <Icon name={KIND_ICON[n.kind]} size={11} />
            {n.label}
          </button>
        </span>
      ))}
      <button className="cs-journey__clear" onClick={clear} aria-label="Clear journey">
        <Icon name="x" size={11} />
      </button>
    </div>
  );
}
