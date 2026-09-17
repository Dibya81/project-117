"use client";

/**
 * Simulation Hub — the gateway: Build Your Own · Oil Refinery · Steel.
 * Every card reports real dataset statistics (loaded from the generated
 * canonical datasets), not marketing copy.
 */
import { useEffect, useState } from "react";
import type { KeyboardEvent } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Boxes, Factory, Layers } from "lucide-react";
import { Panel, SkeletonRows } from "@/components/ui/primitives";
import { Tilt } from "@/components/fx/Tilt";
import { SPRING } from "@/lib/ui/motion";
import { simAdapter } from "@/lib/sim/adapter";
import { SchematicCanvas, emptyRuntime } from "@/components/sim/SchematicCanvas";
import { assemblePlant } from "@/lib/sim/custom";
import type { PlantDef, PlantListItem } from "@/lib/sim/types";

/**
 * A plant preview drawn as a plan rather than a picture.
 *
 * The `SchematicCanvas` is a real render of the real topology, laid back on an
 * isometric plane so the card reads as a site plan. It stays the same component
 * and the same data — only the projection changes.
 */
function IsometricPreview({ plant }: { plant: PlantDef }) {
  return (
    <div className="sm-card-preview" aria-hidden="true">
      <div className="sm-card-preview__plane">
        <SchematicCanvas
          plant={plant}
          runtime={emptyRuntime(plant)}
          selectedId={null}
          affected={[]}
          onSelect={() => undefined}
          onHover={() => undefined}
          // A thumbnail: draw the topology, attach nothing. Passing no-op
          // handlers still mounted handlers on every node, twice per page.
          decorative
        />
      </div>
      <span className="sm-card-preview__glow" />
    </div>
  );
}

/** One status badge. The pulse is the live claim; the label is the measured one. */
function StatusBadge({ tone, label }: { tone: "ok" | "ai" | "warn"; label: string }) {
  return (
    <span className="sm-badge" data-tone={tone}>
      <span className="sm-badge__pulse" />
      {label}
    </span>
  );
}

export default function SimulationHub() {
  const router = useRouter();
  const [plants, setPlants] = useState<PlantListItem[] | null>(null);

  // The hub cards are divs with role="button" rather than <button> elements.
  // Each one embeds a decorative <SchematicCanvas>, which renders its own
  // <button>s, and a button inside a button is invalid HTML — React reported a
  // hydration error on this route because of it. `.sm-hubcard` already sets
  // every button default (display, width, text-align, font, cursor), so only
  // the semantics and keyboard activation have to be supplied here.
  const hubActivate =
    (run: () => void) => (event: KeyboardEvent<HTMLDivElement>) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        run();
      }
    };

  useEffect(() => {
    simAdapter.listPlants().then(setPlants).catch(() => setPlants([]));
  }, []);

  const refinery = plants?.find((p) => p.id === "refinery");
  const steel = plants?.find((p) => p.id === "steel");
  /**
   * The real plant definitions, for the card previews.
   *
   * These used to render `BUILDER_TEMPLATES`, whose refinery topology is a
   * ten-node teaching schematic with invented tags (TK-100, P-110, DS-120). The
   * card is labelled with the real plant's name and asset count, so it was
   * previewing ten units that do not exist in a 58-unit plant.
   */
  const [defs, setDefs] = useState<Record<string, PlantDef>>({});
  useEffect(() => {
    let alive = true;
    Promise.all(
      ["refinery", "steel"].map((id) =>
        simAdapter
          // A card preview draws the topology; it does not operate the plant, so
          // it does not need the runtime snapshot (127 KB per plant) or the
          // scenarios. Two cards were pulling ~475 KB to render two thumbnails.
          .loadPlant(id, { topologyOnly: true })
          .then((r) => [id, r.plant] as const)
          .catch(() => null),
      ),
    ).then((rows) => {
      if (!alive) return;
      setDefs(Object.fromEntries(rows.filter(Boolean) as [string, PlantDef][]));
    });
    return () => {
      alive = false;
    };
  }, []);
  const refineryDef = defs.refinery;
  const steelDef = defs.steel;

  return (
    <>
      <div className="cs-pagehead">
        <div>
          <span className="cs-pagehead__kicker">Simulation</span>
          <h1>Plant Simulation Lab</h1>
        </div>
        <span className="cs-pagehead__meta">
          Build a plant. Break a system. Watch Project 117 respond.
        </span>
      </div>

      {!plants ? (
        <Panel><SkeletonRows rows={5} label="Loading plant datasets…" /></Panel>
      ) : (
        <div className="sm-lab">
          <div className="sm-lab__hero">
            <div>
              <p className="cs-mono cs-text-cyan" style={{ margin: "0 0 10px", fontSize: 10, letterSpacing: "0.3em", textTransform: "uppercase" }}>
                Deterministic industrial twin · {simAdapter.transport} transport
              </p>
              <h2>Choose a topology, inject failure, follow the agent response.</h2>
            </div>
            <div className="sm-response-chain" aria-label="Simulation response chain">
              {["Sensor", "Anomaly", "AI agent", "Analysis", "Recommendation"].map((step) => <span key={step}>{step}</span>)}
            </div>
          </div>
          <div className="sm-hub-grid">
          {/* Build your own */}
          <Tilt max={4}>
            <div
              className="sm-hubcard"
              role="button"
              tabIndex={0}
              onClick={() => router.push("/console/simulation/builder")}
              onKeyDown={hubActivate(() => router.push("/console/simulation/builder"))}
            >
              <motion.span
                className="sm-hubcard__glyph"
                whileHover={{ scale: 1.08, rotate: -4 }}
                transition={SPRING.micro}
                aria-hidden="true"
              >
                <Boxes size={28} strokeWidth={1.5} />
              </motion.span>
              <p className="cs-mono cs-text-ember" style={{ margin: "0 0 8px", fontSize: 10, letterSpacing: "0.3em", textTransform: "uppercase" }}>
                Custom plant
              </p>
              <div className="sm-mini-topology sm-mini-topology--custom" aria-hidden="true">
                <span /><span /><span /><span /><span />
              </div>
              <h2 style={{ margin: "0 0 8px", fontSize: 21, letterSpacing: "-0.01em" }}>Build Your Own Plant</h2>
              <p style={{ margin: 0, color: "var(--ink-2)", fontSize: 13, lineHeight: 1.65, maxWidth: 300 }}>
                Drag equipment, wire the process, inject a fault, and watch the same
                engine and the same five agents respond. Proves the system generalizes.
              </p>
              <div className="sm-hubcard__stats">
                <span className="sm-hubcard__stat"><b>30+</b>symbols</span>
                <span className="sm-hubcard__stat"><b>12</b>failure modes</span>
                <span className="sm-hubcard__stat"><b>∞</b>topologies</span>
              </div>
              <div className="sm-hubcard__foot">
                <span className="sm-hubcard__cta">
                  Open builder <span aria-hidden="true">→</span>
                </span>
                <StatusBadge tone="warn" label="Design mode" />
              </div>
            </div>
          </Tilt>

          {/* Refinery */}
          {refinery && (
            <Tilt max={4}>
              <div
                className="sm-hubcard"
                role="button"
                tabIndex={0}
                onClick={() => router.push("/console/simulation/plant/refinery")}
                onKeyDown={hubActivate(() => router.push("/console/simulation/plant/refinery"))}
              >
                <motion.span
                  className="sm-hubcard__glyph"
                  whileHover={{ scale: 1.08, rotate: -4 }}
                  transition={SPRING.micro}
                  aria-hidden="true"
                >
                  <Factory size={28} strokeWidth={1.5} />
                </motion.span>
                <p className="cs-mono cs-text-cyan" style={{ margin: "0 0 8px", fontSize: 10, letterSpacing: "0.3em", textTransform: "uppercase" }}>
                  Synthetic demonstration plant
                </p>
                <h2 style={{ margin: "0 0 8px", fontSize: 21, letterSpacing: "-0.01em" }}>{refinery.name}</h2>
                {refineryDef && (
                  <IsometricPreview
                    plant={assemblePlant(refineryDef.equipment, refineryDef.connections)}
                  />
                )}
                <p style={{ margin: 0, color: "var(--ink-2)", fontSize: 13, lineHeight: 1.65, maxWidth: 300 }}>
                  Crude receiving to product storage — 18 process areas, a live causal
                  graph, and the PT-1042A redundancy story.
                </p>
                <div className="sm-hubcard__stats">
                  <span className="sm-hubcard__stat"><b>{refinery.assets}</b>assets</span>
                  <span className="sm-hubcard__stat"><b>{refinery.sensors}</b>sensors</span>
                  <span className="sm-hubcard__stat"><b>{refinery.areas}</b>areas</span>
                  <span className="sm-hubcard__stat"><b>{refinery.scenarios}</b>scenarios</span>
                </div>
                <div className="sm-hubcard__foot">
                  <span className="sm-hubcard__cta">
                    Launch refinery <span aria-hidden="true">→</span>
                  </span>
                  <StatusBadge tone="ok" label="Deterministic" />
                </div>
              </div>
            </Tilt>
          )}

          {/* Steel */}
          {steel && (
            <Tilt max={4}>
              <div
                className="sm-hubcard"
                role="button"
                tabIndex={0}
                onClick={() => router.push("/console/simulation/plant/steel")}
                onKeyDown={hubActivate(() => router.push("/console/simulation/plant/steel"))}
              >
                <motion.span
                  className="sm-hubcard__glyph"
                  whileHover={{ scale: 1.08, rotate: -4 }}
                  transition={SPRING.micro}
                  aria-hidden="true"
                >
                  <Layers size={28} strokeWidth={1.5} />
                </motion.span>
                <p className="cs-mono cs-text-cyan" style={{ margin: "0 0 8px", fontSize: 10, letterSpacing: "0.3em", textTransform: "uppercase" }}>
                  Synthetic demonstration plant
                </p>
                <h2 style={{ margin: "0 0 8px", fontSize: 21, letterSpacing: "-0.01em" }}>{steel.name}</h2>
                {steelDef && (
                  <IsometricPreview
                    plant={assemblePlant(steelDef.equipment, steelDef.connections)}
                  />
                )}
                <p style={{ margin: 0, color: "var(--ink-2)", fontSize: 13, lineHeight: 1.65, maxWidth: 300 }}>
                  Raw material to finished coil — blast furnace, BOF, casting and the
                  hot-rolling line, all causally connected.
                </p>
                <div className="sm-hubcard__stats">
                  <span className="sm-hubcard__stat"><b>{steel.assets}</b>assets</span>
                  <span className="sm-hubcard__stat"><b>{steel.sensors}</b>sensors</span>
                  <span className="sm-hubcard__stat"><b>{steel.areas}</b>areas</span>
                  <span className="sm-hubcard__stat"><b>{steel.scenarios}</b>scenarios</span>
                </div>
                <div className="sm-hubcard__foot">
                  <span className="sm-hubcard__cta">
                    Launch steel plant <span aria-hidden="true">→</span>
                  </span>
                  <StatusBadge tone="ok" label="Deterministic" />
                </div>
              </div>
            </Tilt>
          )}
          </div>
        </div>
      )}

      <Panel title="How this works" style={{ marginTop: 18 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))", gap: 16, fontSize: 12.5, color: "var(--ink-2)", lineHeight: 1.65 }}>
          <div>
            <p className="cs-mono cs-text-cyan" style={{ margin: "0 0 6px", fontSize: 9.5, letterSpacing: "0.26em" }}>REAL ENGINE</p>
            A seeded, deterministic state machine. Telemetry is computed, failures
            propagate through the pipe topology, and verification fails closed.
            Nothing is pre-recorded.
          </div>
          <div>
            <p className="cs-mono cs-text-cyan" style={{ margin: "0 0 6px", fontSize: 9.5, letterSpacing: "0.26em" }}>REAL AGENT PIPELINE</p>
            Incidents decompose into an observable task DAG — orchestrator, data
            analysis, maintenance, operations, safety, documentation — with tools,
            evidence and dependencies you can inspect.
          </div>
          <div>
            <p className="cs-mono cs-text-cyan" style={{ margin: "0 0 6px", fontSize: 9.5, letterSpacing: "0.26em" }}>SOVEREIGN BY DESIGN</p>
            Runs fully embedded for zero-infrastructure demos, or streams the backend
            engine over SSE when the Project 117 API is running. Same contracts, same UI.
          </div>
        </div>
      </Panel>
    </>
  );
}
