"use client";

/**
 * KnowledgeCoreOrbital — the Home page's centre of gravity.
 *
 * Project 117 is an intelligence system wrapped around a plant, not a dashboard
 * with widgets. The composition says that: a single core at the centre, and the
 * capabilities that feed it and draw from it arranged on orbital rings with
 * real depth.
 *
 * The orbit is a projection, not decoration. Each node has a radius, a phase and
 * a tilt; its position on screen comes from those three numbers, and its depth
 * (z) drives scale, opacity and blur so a node at the back sits behind the core
 * and a node at the front passes over it. That is what makes it read as a
 * mechanism rather than a ring of chips.
 *
 * Every count is live. The nodes are built from consoleData — equipment,
 * sensors, agents, documents, work orders, approvals, jobs, history — so the
 * composition reflects the plant's actual state, and a node with nothing behind
 * it says so rather than showing a plausible number.
 *
 * Motion: one requestAnimationFrame loop writes CSS variables on the container;
 * React never re-renders for the animation. Reduced motion renders a static
 * frame.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Icon, type IconName } from "@/components/ui/Icon";

export interface OrbitNode {
  id: string;
  label: string;
  /** Short line shown on hover — what this capability actually is. */
  detail: string;
  href: string;
  icon: IconName;
  /** Live figure from the plant, or null when there is nothing to count. */
  count: number | null;
  countLabel: string;
  /** Ring: 1 is the inner ring, 2 the outer. */
  ring: 1 | 2;
  /** Start angle in radians, so nodes do not stack. */
  phase: number;
  tone: "intel" | "ok" | "warn" | "ai";
}

export function KnowledgeCoreOrbital({
  nodes,
  reduced = false,
}: {
  nodes: OrbitNode[];
  reduced?: boolean;
}) {
  const router = useRouter();
  const wrapRef = useRef<HTMLDivElement>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  // Depth is a client measurement. Rendering it on the server produced a
  // hydration mismatch on every load, so the first client frame applies it.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const [coreOpen, setCoreOpen] = useState(false);
  const raf = useRef<number | null>(null);

  // Each node's orbit parameters are fixed for the session; only the clock
  // moves, so the composition is stable and only the motion is live.
  const placed = useMemo(
    () =>
      nodes.map((n, i) => ({
        ...n,
        // Radii are in percent of the half-extent, so the orbits scale with the
        // panel rather than needing a resize handler.
        // Radii as a share of the half-extent. The inner ring clears the core's
        // own footprint; the outer ring sits near the edge. At the first pass
        // these were small enough that every node piled on top of the core.
        radius: n.ring === 1 ? 52 + (i % 3) * 4 : 76 + (i % 3) * 4,
        tiltY: n.ring === 1 ? 0.42 : 0.34,
        // A slow drift, not an orbit you have to chase. At these speeds a node
        // crosses its ring in about a minute, so it reads as continuous
        // intelligence processing while staying a stationary target to click.
        speed: (n.ring === 1 ? 0.000035 : 0.000024) * (i % 2 === 0 ? 1 : -1),
      })),
    [nodes],
  );

  // Holding a node still while it is hovered is a usability requirement, not a
  // nicety: an element that moves under the cursor is one you cannot click.
  const heldRef = useRef(false);
  heldRef.current = hovered !== null;

  useEffect(() => {
    const el = wrapRef.current;
    if (!el || reduced) return;
    let last = performance.now();
    let t = 0;
    // Translating by a percentage moves an element by a share of its OWN size,
    // not the container's, which piled every node at the centre. Positions are
    // therefore computed in px from the measured half-extent.
    let halfW = el.clientWidth / 2;
    let halfH = el.clientHeight / 2;
    const measure = () => {
      halfW = el.clientWidth / 2;
      halfH = el.clientHeight / 2;
    };
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    const tick = (now: number) => {
      // Freeze the clock rather than skipping frames, so nothing jumps when the
      // pointer leaves.
      if (!heldRef.current) t += now - last;
      last = now;
      for (const n of placed) {
        const a = n.phase + t * n.speed;
        // Circular orbit compressed on Y is a tilted ring; z is the depth that
        // decides what is in front of the core.
        const x = Math.cos(a) * n.radius;
        const z = Math.sin(a);
        const y = z * n.radius * n.tiltY;
        const depth = (z + 1) / 2; // 0 back .. 1 front
        const node = el.querySelector<HTMLElement>(`[data-orbit="${n.id}"]`);
        if (!node) continue;
        node.style.setProperty("--ox", `${((x / 100) * halfW).toFixed(1)}px`);
        node.style.setProperty("--oy", `${((y / 100) * halfH * 0.72).toFixed(1)}px`);
        node.style.setProperty("--od", depth.toFixed(3));
      }
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => {
      if (raf.current) cancelAnimationFrame(raf.current);
      ro.disconnect();
    };
  }, [placed, reduced]);

  // A static frame when motion is reduced, so the composition still reads.
  const staticPos = (n: (typeof placed)[number]) => {
    const z = Math.sin(n.phase);
    return {
      x: Math.cos(n.phase) * n.radius,
      y: z * n.radius * n.tiltY,
      d: Number(((z + 1) / 2).toFixed(3)),
    };
  };

  const dimmed = (id: string) => hovered !== null && hovered !== id;

  return (
    <div className="kc" ref={wrapRef} data-testid="knowledge-core">
      {/* The orbital paths, drawn as ellipses so the plane is legible. */}
      <svg className="kc__rings" viewBox="-100 -100 200 200" aria-hidden="true">
        <ellipse cx="0" cy="0" rx="56" ry="22" />
        <ellipse cx="0" cy="0" rx="82" ry="28" />
      </svg>

      {/* The core itself. */}
      <button
        type="button"
        className={`kc__core${coreOpen ? " is-open" : ""}`}
        onClick={() => setCoreOpen((v) => !v)}
        aria-expanded={coreOpen}
        aria-label="Knowledge core — reveal its layers"
        data-testid="knowledge-core-button"
      >
        <span className="kc__core-slab" aria-hidden="true" />
        <span className="kc__core-inner">
          <Icon name="graph" size={26} />
          <b>Knowledge Core</b>
          <em>{coreOpen ? "layers" : "click to open"}</em>
        </span>
      </button>

      {/* The core's internal layers, revealed on click. */}
      {coreOpen && (
        <div className="kc__layers" role="dialog" aria-label="Knowledge core layers">
          {[
            ["Knowledge graph", "Equipment, sensors and documents as one topology"],
            ["Documents", "Procedures and manuals behind every citation"],
            ["Operational memory", "What happened, what was decided, what was verified"],
            ["Equipment relationships", "Upstream and downstream, from the plant model"],
            ["Agent knowledge", "What the workforce has learned and reuses"],
          ].map(([title, detail]) => (
            <div key={title} className="kc__layer">
              <b>{title}</b>
              <span>{detail}</span>
            </div>
          ))}
        </div>
      )}

      {/* Orbiting capability nodes. */}
      {placed.map((n) => {
        const sp = staticPos(n);
        return (
          <button
            key={n.id}
            type="button"
            data-orbit={n.id}
            data-tone={n.tone}
            className={`kc__node${dimmed(n.id) ? " is-dim" : ""}${hovered === n.id ? " is-hot" : ""}`}
            style={mounted ? ({ "--od": sp.d } as React.CSSProperties) : undefined}
            onMouseEnter={() => setHovered(n.id)}
            onMouseLeave={() => setHovered(null)}
            onFocus={() => setHovered(n.id)}
            onBlur={() => setHovered(null)}
            onClick={() => router.push(n.href)}
            aria-label={`${n.label} — ${n.detail}`}
          >
            {/* A hairline from the node toward the core: the relationship the
                composition is about. It brightens on hover. */}
            <span className="kc__spoke" aria-hidden="true" />
            <span className="kc__node-icon">
              <Icon name={n.icon} size={17} />
            </span>
            <span className="kc__node-body">
              <b>{n.label}</b>
              <span className="kc__node-count">
                {n.count == null ? "—" : n.count.toLocaleString()} {n.countLabel}
              </span>
              <em className="kc__node-detail">{n.detail}</em>
            </span>
          </button>
        );
      })}
    </div>
  );
}
