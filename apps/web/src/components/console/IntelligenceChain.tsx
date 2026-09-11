"use client";

/**
 * IntelligenceChain — the Project 117 spine, made visible:
 * SENSOR → ANOMALY → KNOWLEDGE → AI AGENT → RECOMMENDATION → WORK ORDER → VERIFICATION
 * A pulse of "information" travels the chain; every stage is a live link
 * into its surface. This is the product thesis as an interactive element.
 */
import { useRouter } from "next/navigation";
import type { CSSProperties } from "react";
import { Icon, type IconName } from "@/components/ui/Icon";

const STAGES: { label: string; icon: IconName; color: string; href: string }[] = [
  { label: "Sensor", icon: "pulse", color: "var(--cyan)", href: "/console/equipment/C-3" },
  { label: "Anomaly", icon: "alert", color: "var(--crit)", href: "/console/equipment/C-3" },
  { label: "Knowledge", icon: "graph", color: "var(--violet)", href: "/console/knowledge" },
  { label: "AI Agent", icon: "cpu", color: "var(--cyan)", href: "/console/workspace" },
  { label: "Recommendation", icon: "zap", color: "var(--cyan)", href: "/console/work-orders/WO-8852" },
  { label: "Work Order", icon: "workorder", color: "var(--warn)", href: "/console/work-orders/WO-8852" },
  { label: "Verification", icon: "shield", color: "var(--ok)", href: "/console/approvals" },
];

export function IntelligenceChain() {
  const router = useRouter();
  return (
    <div className="cs-chain" role="img" aria-label="Intelligence chain: sensor to anomaly to knowledge to AI agent to recommendation to work order to verification">
      <div className="cs-chain__track" aria-hidden="true">
        <span className="cs-chain__pulse" />
      </div>
      {STAGES.map((s, i) => (
        <button
          key={s.label}
          className="cs-chain__stage"
          style={{ "--st-c": s.color, animationDelay: `${i * 110}ms` } as CSSProperties}
          onClick={() => router.push(s.href)}
          title={`Open: ${s.label}`}
        >
          <span className="cs-chain__node">
            <Icon name={s.icon} size={13} />
          </span>
          <span className="cs-chain__label">{s.label}</span>
        </button>
      ))}
      <style jsx>{`
        .cs-chain {
          position: relative;
          display: flex;
          justify-content: space-between;
          gap: 4px;
          padding: 22px 8px 6px;
        }
        .cs-chain__track {
          position: absolute;
          top: 34px;
          left: 5%;
          right: 5%;
          height: 2px;
          background: linear-gradient(90deg, rgba(69,213,255,.25), rgba(183,156,255,.25), rgba(255,180,84,.25), rgba(61,220,151,.3));
          border-radius: 2px;
          overflow: visible;
        }
        .cs-chain__pulse {
          position: absolute;
          top: -3px;
          left: 0;
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #fff;
          box-shadow: 0 0 14px 3px rgba(69, 213, 255, 0.8);
          animation: cs-chain-run 5.2s linear infinite;
        }
        @keyframes cs-chain-run {
          0% { left: 0; opacity: 0; }
          6% { opacity: 1; }
          94% { opacity: 1; }
          100% { left: calc(100% - 8px); opacity: 0; }
        }
        .cs-chain__stage {
          position: relative;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 9px;
          background: none;
          border: 0;
          cursor: pointer;
          color: var(--ink-2);
          animation: p117-fade-up 600ms var(--ease-out) both;
          transition: transform var(--t-fast);
        }
        .cs-chain__stage:hover { transform: translateY(-3px); }
        .cs-chain__node {
          display: grid;
          place-items: center;
          width: 30px;
          height: 30px;
          border-radius: 50%;
          border: 1.5px solid var(--st-c);
          background: var(--bg-1);
          color: var(--st-c);
          box-shadow: 0 0 14px color-mix(in srgb, var(--st-c) 40%, transparent);
          transition: box-shadow var(--t-fast), transform var(--t-fast);
        }
        .cs-chain__stage:hover .cs-chain__node {
          box-shadow: 0 0 26px color-mix(in srgb, var(--st-c) 70%, transparent);
          transform: scale(1.12);
        }
        .cs-chain__label {
          font-family: var(--font-mono);
          font-size: 8.5px;
          letter-spacing: 0.2em;
          text-transform: uppercase;
          color: var(--ink-3);
          white-space: nowrap;
        }
        .cs-chain__stage:hover .cs-chain__label { color: var(--st-c); }
        @media (max-width: 720px) {
          .cs-chain { flex-wrap: wrap; justify-content: center; gap: 14px; }
          .cs-chain__track { display: none; }
        }
        @media (prefers-reduced-motion: reduce) {
          .cs-chain__pulse { animation: none; opacity: 0; }
        }
      `}</style>
    </div>
  );
}
