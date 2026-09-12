"use client";

/**
 * Build Your Own Plant — blank industrial canvas → wired plant → run the SAME
 * engine → inject a fault → watch the SAME agent pipeline respond.
 * This page proves generalization: no prebuilt dataset involved.
 */
import { type PointerEvent as ReactPointerEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button, Panel, StatusDot, Tag } from "@/components/ui/primitives";
import { Icon, type IconName } from "@/components/ui/Icon";
import { SchematicCanvas, emptyRuntime, runtimeFromEngine } from "@/components/sim/SchematicCanvas";
import { AgentCommandCenter } from "@/components/sim/AgentCommandCenter";
import { SimSymbol, symbolForEquipment } from "@/lib/sim/symbols";
import { simAdapter, asEmbedded, asLive, DATA_MODE } from "@/lib/sim/adapter";
import { consoleData } from "@/lib/data/console";
import { useSimulation } from "@/lib/sim/store";
import { assemblePlant, defaultSensors, makeConnection, makeEquipment, FM_BY_KIND, FAILURE_MODES } from "@/lib/sim/custom";
import { validatePlant, type PlantValidation } from "@/lib/sim/validate";
import { RELATION_BY_ID, relationOf, validRelations } from "@/lib/sim/relations";
import type { RelationType } from "@/lib/sim/types";
import { BUILDER_TEMPLATES, type PlantTemplate } from "@/lib/sim/templates";
import type { EquipmentDef, EquipmentKind, PlantDef } from "@/lib/sim/types";

/**
 * A reusable building block saved from the canvas.
 *
 * Saving the whole plant is a coarse unit of reuse; what an engineer actually
 * wants to keep is smaller — one instrumented asset, or one relation between
 * two of them ("these two are redundant"). An item stores a deep copy, so the
 * original can be edited or deleted without touching the saved copy. A
 * connection stores the two end tags plus the relation rather than raw ids, so
 * it can be re-applied after the units have been re-created.
 *
 * Session-scoped like every other operator change: a reload clears the library.
 */
interface SavedItem {
  id: string;
  label: string;
  detail: string;
  kind: "item" | "connection";
  /** Dedup key — the tag for an item, source|target|relation for a connection. */
  key: string;
  equipment?: EquipmentDef;
  connection?: { sourceTag: string; targetTag: string; relation: RelationType };
}


const PALETTE: { group: string; icon: IconName; items: { kind: EquipmentKind; label: string }[] }[] = [
  {
    group: "Process", icon: "equipment",
    items: [
      { kind: "tank", label: "Storage Tank" }, { kind: "vessel", label: "Vessel" },
      { kind: "column", label: "Column" }, { kind: "exchanger", label: "Heat Exchanger" },
      { kind: "furnace", label: "Furnace" },
    ],
  },
  {
    group: "Flow", icon: "pulse",
    items: [
      { kind: "pump", label: "Centrifugal Pump" }, { kind: "valve", label: "Valve" },
      { kind: "compressor", label: "Compressor" }, { kind: "motor", label: "Motor" },
      { kind: "conveyor", label: "Conveyor" },
    ],
  },
  {
    group: "Safety & utility", icon: "shield",
    items: [
      { kind: "safety", label: "ESD / Detector Station" }, { kind: "utility", label: "Utility Package" },
    ],
  },
];

export default function BuilderPage() {
  const [equipment, setEquipment] = useState<EquipmentDef[]>([]);
  const [connections, setConnections] = useState<PlantDef["connections"]>([]);
  const [armed, setArmed] = useState<EquipmentKind | null>(null);
  const [connectFrom, setConnectFrom] = useState<string | null>(null);
  const [selected, setSelected] = useState<EquipmentDef | null>(null);
  const [running, setRunning] = useState(false);
  const [seq, setSeq] = useState(1);
  const [connSeq, setConnSeq] = useState(1);
  const dropRef = useRef<HTMLDivElement>(null);

  const [plant, setPlant] = useState<PlantDef | null>(null);
  const sim = useSimulation(running && plant ? "custom" : null);
  const embedded = asEmbedded(simAdapter);
  const live = asLive(simAdapter);
  const [saveState, setSaveState] = useState<{ tone: "ok" | "err" | "busy"; text: string } | null>(null);
  /** Right-hand asset dock. Collapsible so the canvas can be fully open. */
  const [dockOpen, setDockOpen] = useState(true);
  /** Result of the last VALIDATE PLANT run, or null if never run. */
  const [report, setReport] = useState<PlantValidation | null>(null);
  /** A connection awaiting confirmation, so the relation can be chosen. */
  const [pending, setPending] = useState<{ source: EquipmentDef; target: EquipmentDef } | null>(null);
  const [relation, setRelation] = useState<RelationType>("MATERIAL_FLOW");
  const [savedPlants, setSavedPlants] = useState<string[]>([]);
  const [library, setLibrary] = useState<SavedItem[]>([]);
  const [libOpen, setLibOpen] = useState(false);
  /** Equipment tag requested by the Knowledge Universe deep link (?focus=). */
  const [focusTag, setFocusTag] = useState<string | null>(null);
  const materialised = useRef(false);

  useEffect(() => {
    setFocusTag(new URLSearchParams(window.location.search).get("focus"));
  }, []);

  // ?focus=C-3 — start from the refinery template if the canvas is empty, so
  // the graph's "Open in simulation" lands in a populated, running plant
  // rather than an empty canvas.
  useEffect(() => {
    if (!focusTag) return;
    const tpl = BUILDER_TEMPLATES.find((t) => t.id === "template-refinery");
    if (!tpl) return;
    setEquipment((cur) => {
      if (cur.length) return cur;
      const assembled = assemblePlant(tpl.equipment, tpl.connections);
      setConnections(assembled.connections);
      return assembled.equipment;
    });
  }, [focusTag]);

  // Select the requested unit. The builder templates are a simplified set
  // (TK-100, P-110 …) that does not ship every unit the knowledge graph knows
  // about, so when the tag is missing we materialise the real record from the
  // console's equipment set and drop it on the canvas. The deep link must land
  // on the actual unit, not silently do nothing.
  useEffect(() => {
    if (!focusTag || !equipment.length) return;

    const hit = equipment.find(
      (e) => e.tag === focusTag || e.id === focusTag || e.id === `e-${focusTag}`,
    );
    if (hit) {
      setSelected(hit);
      return;
    }
    if (materialised.current) return;

    let cancelled = false;
    consoleData.equipment
      .list()
      .then((list) => {
        if (cancelled) return;
        const rec = list.find((x) => x.id === focusTag);
        if (!rec) return;
        materialised.current = true;
        const KIND: Record<string, EquipmentKind> = {
          pump: "pump", tank: "tank", compressor: "compressor",
          exchanger: "exchanger", valve: "valve",
        };
        const kind = KIND[rec.kind] ?? "vessel";
        const id = `e-${rec.id}`;
        const def: EquipmentDef = {
          id,
          tag: rec.id,
          name: rec.name,
          kind,
          area_id: "custom",
          x: 140,
          y: 140,
          criticality: 2,
          capacity: 100,
          state: "normal",
          sensors: defaultSensors(kind, id, rec.id.replace(/^[A-Z]+-/, "")),
          failure_modes: FM_BY_KIND[kind],
          manufacturer: "Project 117 Synthetic Plant",
          model: "SIM-2026",
          installed: "2026-09-11",
          last_inspection: "2026-09-11",
        };
        setEquipment((cur) => (cur.some((e) => e.id === id) ? cur : [...cur, def]));
        setSelected(def);
      })
      .catch(() => undefined);

    return () => { cancelled = true; };
  }, [focusTag, equipment]);

  // Saved plants come from the backend database, never from browser storage.
  useEffect(() => {
    if (!live) return;
    let alive = true;
    live
      .listPlants()
      .then((list) => {
        if (alive) setSavedPlants(list.filter((p) => p.origin === "builder").map((p) => p.id));
      })
      .catch(() => undefined);
  }, [live, saveState]);

  /** Persist the current canvas: session store for the console, backend when live. */
  const savePlant = async () => {
    const name = window.prompt("Plant name to save as", "My Plant");
    if (!name) return;
    const id = `builder-${name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")}`;
    const p = { ...assemblePlant(equipment, connections), id, name };
    // Session-scoped record so the topology is visible to the rest of the
    // console (the Knowledge Graph) immediately. In-memory only: it does not
    // survive a reload, and the message below says so.
    await consoleData.customPlants.save(p);
    if (!live) {
      setSaveState({ tone: "ok", text: `Saved for this session as ${id} (not persisted across reload)` });
      return;
    }
    setSaveState({ tone: "busy", text: `Saving ${id}...` });
    try {
      await live.savePlant(p);
      setSaveState({ tone: "ok", text: `Saved to database as ${id}` });
    } catch (err) {
      setSaveState({ tone: "err", text: `Saved for this session as ${id}; database write failed: ${(err as Error).message}` });
    }
  };

  /** Load a previously saved plant straight out of the database. */
  const loadPlant = async (id: string) => {
    if (!live) return;
    setSaveState({ tone: "busy", text: `Loading ${id}...` });
    try {
      const loaded = await live.loadSavedPlant(id);
      setEquipment(loaded.equipment);
      setConnections(loaded.connections);
      setPlant(null);
      setRunning(false);
      setSaveState({ tone: "ok", text: `Loaded ${id} from database (${loaded.equipment.length} assets)` });
    } catch (err) {
      setSaveState({ tone: "err", text: `Load failed: ${(err as Error).message}` });
    }
  };

  const applyTemplate = (template: PlantTemplate) => {
    setEquipment(template.equipment);
    setConnections(template.connections);
    setPlant(null);
    setRunning(false);
    setSelected(null);
    setConnectFrom(null);
    setSaveState({ tone: "ok", text: `Loaded template: ${template.name}` });
  };

  const runtime = useMemo(() => {
    if (!plant) return emptyRuntime(assemblePlant(equipment, connections));
    if (embedded && running) {
      try {
        return runtimeFromEngine(plant, embedded.engine("custom"));
      } catch {
        return emptyRuntime(plant);
      }
    }
    return emptyRuntime(plant);
  }, [plant, equipment, connections, embedded, running, sim.tick]);

  const drop = useCallback(
    (e: ReactPointerEvent) => {
      if (!armed || !dropRef.current || running) return;
      const rect = dropRef.current.getBoundingClientRect();
      const x = Math.round(((e.clientX - rect.left) / rect.width) * 1800) + 60;
      const y = Math.round(((e.clientY - rect.top) / rect.height) * 1000) + 60;
      const label = PALETTE.flatMap((g) => g.items).find((i) => i.kind === armed)?.label ?? armed;
      setEquipment((cur) => [...cur, makeEquipment(armed, label, x, y, seq)]);
      setSeq((s) => s + 1);
      setArmed(null);
    },
    [armed, running, seq],
  );

  /**
   * Click behaviour in connect mode, kept to two clicks with no hidden step:
   *   "__arm__"  → this unit becomes the SOURCE
   *   a real id  → this unit becomes the TARGET and the relation dialog opens
   * Outside connect mode a click simply selects.
   */
  const onSelect = useCallback(
    (eq: EquipmentDef) => {
      if (running) {
        setSelected(eq);
        return;
      }
      if (connectFrom === "__arm__") {
        setConnectFrom(eq.id);
        setSelected(eq);
        return;
      }
      if (connectFrom && connectFrom !== eq.id) {
        const source = equipment.find((e) => e.id === connectFrom);
        if (source) {
          const allowed = validRelations("equipment", "equipment");
          setRelation(allowed[0]?.id ?? "MATERIAL_FLOW");
          setPending({ source, target: eq });
          setConnectFrom(null);
          return;
        }
      }
      setSelected(eq);
    },
    [connectFrom, equipment, running],
  );

  /** Commit the staged connection with the chosen relation. */
  const commitConnection = () => {
    if (!pending) return;
    setConnections((cur) => [...cur, makeConnection(pending.source.id, pending.target.id, connSeq, relation)]);
    setConnSeq((n) => n + 1);
    setPending(null);
  };

  // --- saved building blocks ----------------------------------------------

  /** Keep a copy of one asset. Saving twice is a no-op, not a duplicate. */
  const saveItem = (eq: EquipmentDef) => {
    setLibrary((cur) =>
      cur.some((x) => x.kind === "item" && x.key === eq.tag)
        ? cur
        : [
            {
              id: `lib-item-${eq.tag}`,
              label: eq.tag,
              detail: `${eq.name} · ${eq.sensors.length} sensors`,
              kind: "item" as const,
              key: eq.tag,
              equipment: structuredClone(eq),
            },
            ...cur,
          ],
    );
    setLibOpen(true);
  };

  /** Keep one relation, identified by its ends and its meaning. */
  const saveConnection = (c: PlantDef["connections"][number]) => {
    const src = equipment.find((e) => e.id === c.source);
    const tgt = equipment.find((e) => e.id === c.target);
    const rel = relationOf(c);
    const key = `${c.source}|${c.target}|${rel}`;
    setLibrary((cur) =>
      cur.some((x) => x.kind === "connection" && x.key === key)
        ? cur
        : [
            {
              id: `lib-conn-${key}`,
              label: `${src?.tag ?? c.source} → ${tgt?.tag ?? c.target}`,
              detail: RELATION_BY_ID[rel]?.label ?? rel,
              kind: "connection" as const,
              key,
              connection: { sourceTag: src?.tag ?? "", targetTag: tgt?.tag ?? "", relation: rel },
            },
            ...cur,
          ],
    );
    setLibOpen(true);
  };

  /**
   * Put a saved block back on the canvas.
   *
   * An asset is re-created with fresh ids and tag so the copy can never collide
   * with the original (or with a previous copy), and is offset slightly so it
   * does not land exactly on top of what is already there. A connection is
   * resolved by tag against the units currently on the canvas — which is the
   * point of storing tags: it still works after they have been rebuilt.
   */
  const addFromLibrary = (entry: SavedItem) => {
    if (entry.kind === "item" && entry.equipment) {
      const n = seq;
      const tag = `${entry.equipment.tag}-C${n}`;
      setEquipment((cur) => [
        ...cur,
        {
          ...structuredClone(entry.equipment!),
          id: `e-${tag}`,
          tag,
          sensors: entry.equipment!.sensors.map((s) => ({ ...s, id: `${s.id}-c${n}`, equipment_id: `e-${tag}` })),
          x: entry.equipment!.x + 40,
          y: entry.equipment!.y + 40,
        },
      ]);
      setSeq((v) => v + 1);
      setSaveState({ tone: "ok", text: `Added ${tag} from saved items` });
      return;
    }
    if (entry.kind === "connection" && entry.connection) {
      const { sourceTag, targetTag, relation: rel } = entry.connection;
      const src = equipment.find((e) => e.tag === sourceTag);
      const tgt = equipment.find((e) => e.tag === targetTag);
      if (!src || !tgt) {
        setSaveState({
          tone: "err",
          text: `Cannot add ${sourceTag} → ${targetTag}: both units must be on the canvas`,
        });
        return;
      }
      setConnections((cur) => [...cur, makeConnection(src.id, tgt.id, connSeq, rel)]);
      setConnSeq((v) => v + 1);
      setSaveState({ tone: "ok", text: `Added ${sourceTag} → ${targetTag}` });
    }
  };

  const dropFromLibrary = (id: string) => setLibrary((cur) => cur.filter((x) => x.id !== id));

  const run = async () => {
    if (equipment.length === 0) return;
    const p = assemblePlant(equipment, connections);
    setPlant(p);
    try {
      // The backend only knows plants it has been told about. In live mode the
      // custom topology exists solely in this browser, so it must be registered
      // before it can be started — otherwise the start call 404s and Run is a
      // dead button, which is exactly what it was.
      if (embedded) embedded.registerCustomPlant(p);
      else if (live) await live.savePlant(p);
      await simAdapter.start(p.id);
      setRunning(true);
      setSaveState({ tone: "ok", text: `Running ${p.equipment.length} units on the engine` });
    } catch (err) {
      setRunning(false);
      setSaveState({ tone: "err", text: `Run failed: ${(err as Error).message}` });
    }
  };

  /** Real topology validation over the current canvas — pure, no engine. */
  const validate = () => {
    setReport(validatePlant(assemblePlant(equipment, connections)));
  };

  const reset = () => {
    void simAdapter.pause(plant?.id ?? "custom");
    setRunning(false);
    setPlant(null);
    setSelected(null);
  };

  const inject = (equipmentId: string, modeId: string) => {
    void simAdapter.injectFailure(plant?.id ?? "custom", equipmentId, modeId);
  };

  const displayPlant = plant ?? assemblePlant(equipment, connections);

  return (
    <div className="sm-stage">
      {/* ---- the process canvas: full bleed, infinite-feeling ---- */}
      <div
        ref={dropRef}
        className={`sm-stage__canvas${armed ? " is-armed" : ""}`}
        onPointerDown={drop}
        role="application"
        aria-label="Plant builder canvas"
      >
        {equipment.length === 0 ? (
          <div className="sm-template-entry">
            <div className="sm-template-entry__grid" aria-hidden="true" />
            <div className="sm-template-entry__inner">
              <p className="cs-mono cs-text-cyan" style={{ fontSize: 10, letterSpacing: "0.3em", textTransform: "uppercase", margin: "0 0 10px" }}>
                Select a starting topology
              </p>
              <h2>Build a plant, then break it.</h2>
              <p>
                Start from a coherent refinery or steel flow, or choose custom and place equipment manually.
                Every asset arrives with sensors, failure modes and the same response engine.
              </p>
              <div className="sm-template-actions">
                {BUILDER_TEMPLATES.filter((tpl) => tpl.id === "template-refinery" || tpl.id === "template-steel").map((tpl) => (
                  <button key={tpl.id} type="button" onClick={(e) => { e.stopPropagation(); applyTemplate(tpl); }}>
                    <span>{tpl.name}</span>
                    <small>{tpl.equipment.length} assets · {tpl.connections.length} process links</small>
                  </button>
                ))}
                <button type="button" onClick={(e) => { e.stopPropagation(); setSaveState({ tone: "ok", text: "Custom builder ready. Arm a symbol and click the canvas." }); }}>
                  <span>Custom Plant</span>
                  <small>Empty canvas · manual topology</small>
                </button>
              </div>
            </div>
          </div>
        ) : (
          <SchematicCanvas
            plant={displayPlant}
            runtime={runtime}
            selectedId={selected?.id ?? connectFrom}
            affected={sim.activeIncident?.affected ?? []}
            onSelect={onSelect}
            onHover={() => undefined}
            onBackground={() => {
              setSelected(null);
            }}
          />
        )}
      </div>

      {/* ---- floating identity + scenario controls, top left ---- */}
      <div className="sm-float sm-float--tl">
        <span className="sm-float__kicker">Simulation / Build Your Own</span>
        <h1 className="sm-float__title">
          Custom Plant
          {running ? <Tag tone="ok">running · real engine</Tag> : <Tag>editing</Tag>}
          <Tag tone={DATA_MODE === "live" ? "ok" : "warn"}>{DATA_MODE === "live" ? "live backend" : "mock (dev)"}</Tag>
          {saveState && (
            <Tag tone={saveState.tone === "ok" ? "ok" : saveState.tone === "err" ? "bad" : undefined}>{saveState.text}</Tag>
          )}
        </h1>
        <div className="sm-float__row">
          {!running ? (
            <>
              <select
                className="cs-select"
                defaultValue=""
                onChange={(e) => {
                  const tpl = BUILDER_TEMPLATES.find((t) => t.id === e.target.value);
                  if (tpl) applyTemplate(tpl);
                  e.currentTarget.value = "";
                }}
                aria-label="Load starter template"
              >
                <option value="">Starter templates…</option>
                {BUILDER_TEMPLATES.map((tpl) => (
                  <option key={tpl.id} value={tpl.id}>
                    Template: {tpl.name}
                  </option>
                ))}
              </select>
              <Button variant={connectFrom ? "primary" : "ghost"} onClick={() => setConnectFrom(connectFrom ? null : "__arm__")}>
                <Icon name="workflow" size={13} /> {connectFrom ? "Cancel connect" : "Connect mode"}
              </Button>
              <Button variant="ghost" onClick={validate} disabled={equipment.length === 0}>
                <Icon name="check" size={13} /> Validate plant
              </Button>
              <Button variant="ghost" onClick={savePlant} disabled={equipment.length === 0}>
                <Icon name="doc" size={13} /> Save plant
              </Button>
              {savedPlants.length > 0 && (
                <select
                  className="cs-select"
                  defaultValue=""
                  onChange={(e) => {
                    if (e.target.value) void loadPlant(e.target.value);
                    e.currentTarget.value = "";
                  }}
                  aria-label="Load saved plant"
                >
                  <option value="">Load saved plant…</option>
                  {savedPlants.map((id) => (
                    <option key={id} value={id}>{id}</option>
                  ))}
                </select>
              )}
              <Button variant="primary" onClick={run} disabled={equipment.length === 0}>
                <Icon name="play" size={13} /> Run simulation
              </Button>
            </>
          ) : (
            <Button variant="ghost" onClick={reset}>
              <Icon name="refresh" size={13} /> Stop &amp; edit
            </Button>
          )}
          <Button
            variant={libOpen ? "primary" : "ghost"}
            onClick={() => setLibOpen((v) => !v)}
            title="Building blocks saved from this canvas"
          >
            ★ Saved {library.length > 0 ? `(${library.length})` : ""}
          </Button>
        </div>
      </div>

      {/* ---- saved building blocks: one unit, or one connection ---- */}
      {libOpen && (
        <aside className="sm-float sm-float--library" aria-label="Saved building blocks">
          <header className="sm-lib__head">
            <span className="sm-lib__title">Saved blocks</span>
            <span className="cs-mono cs-dim" style={{ fontSize: 9 }}>{library.length} kept</span>
            <button className="sm-panel__close" onClick={() => setLibOpen(false)} aria-label="Close saved blocks">×</button>
          </header>
          {library.length === 0 ? (
            <p className="sm-lib__empty">
              Nothing saved yet. Select a unit and choose <b>Save this unit for reuse</b>, or press
              the <b>★</b> beside any connection in the unit panel. Saved blocks live in this
              session only — a reload clears them.
            </p>
          ) : (
            <ul className="sm-lib__list">
              {library.map((entry) => (
                <li key={entry.id} className="sm-lib__row">
                  <span className={`sm-lib__kind sm-lib__kind--${entry.kind}`}>
                    {entry.kind === "item" ? "UNIT" : "LINK"}
                  </span>
                  <div className="sm-lib__meta">
                    <b className="cs-mono">{entry.label}</b>
                    <span className="cs-mono cs-dim">{entry.detail}</span>
                  </div>
                  <button
                    className="sm-lib__add"
                    onClick={() => addFromLibrary(entry)}
                    title="Add a copy to the canvas"
                  >
                    Add
                  </button>
                  <button
                    className="sm-panel__unlink"
                    onClick={() => dropFromLibrary(entry.id)}
                    aria-label={`Forget saved ${entry.label}`}
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>
      )}

      {/* ---- floating asset palette, right ---- */}
      <aside className={`sm-float sm-float--dock${dockOpen ? " is-open" : ""}`} aria-label="Asset palette">
        <header className="sm-dock__head">
          <span className="sm-dock__title">Assets</span>
          <span className="cs-mono cs-dim" style={{ fontSize: 9 }}>{equipment.length} placed</span>
          <button
            className="sm-dock__toggle"
            onClick={() => setDockOpen((v) => !v)}
            aria-expanded={dockOpen}
            aria-label={dockOpen ? "Collapse asset palette" : "Expand asset palette"}
          >
            {dockOpen ? "›" : "‹"}
          </button>
        </header>
        {dockOpen && (
          <div className="sm-dock__body">
            {PALETTE.map((g) => (
              <section key={g.group} className="sm-dock__group">
                <h4>{g.group}</h4>
                {g.items.map((item) => (
                  <button
                    key={item.kind}
                    className={`sm-palette-item${armed === item.kind ? " is-armed" : ""}`}
                    onClick={() => setArmed(armed === item.kind ? null : item.kind)}
                    disabled={running}
                    title={armed === item.kind ? "Click the canvas to place" : `Place a ${item.label}`}
                  >
                    <SimSymbol type={symbolForEquipment(item.kind, item.label)} size={22} />
                    {item.label}
                    <span className="cs-mono cs-dim" style={{ marginLeft: "auto", fontSize: 8.5 }}>
                      {defaultSensors(item.kind, "x", "0").length}
                    </span>
                  </button>
                ))}
              </section>
            ))}
            <p className="sm-dock__hint">
              Arm a symbol, then click the canvas to place it. Select a unit to wire or fault it.
            </p>
          </div>
        )}
      </aside>

      {/* ---- connect confirmation: source -> target -> relation ---- */}
      {pending && (
        <aside className="sm-float sm-float--connect" role="dialog" aria-label="Create connection">
          <header className="sm-connect__head">
            <span className="sm-connect__title">Create connection</span>
            <button className="sm-panel__close" onClick={() => setPending(null)} aria-label="Cancel">×</button>
          </header>

          <div className="sm-connect__pair">
            <span className="sm-connect__node">{pending.source.tag}</span>
            <span className="sm-connect__arrow" aria-hidden="true">↓</span>
            <span className="sm-connect__node">{pending.target.tag}</span>
          </div>

          <p className="sm-connect__label">Type</p>
          <div className="sm-connect__relations" role="radiogroup" aria-label="Connection type">
            {validRelations("equipment", "equipment").map((r) => (
              <label key={r.id} className={`sm-connect__opt${relation === r.id ? " is-on" : ""}`}>
                <input
                  type="radio"
                  name="relation"
                  value={r.id}
                  checked={relation === r.id}
                  onChange={() => setRelation(r.id)}
                />
                <span className="sm-connect__opt-label">{r.label}</span>
                <span className="sm-connect__opt-hint">{r.hint}</span>
              </label>
            ))}
          </div>

          <div className="sm-connect__actions">
            <button className="btn btn--ghost" onClick={() => setPending(null)}>Cancel</button>
            <button className="btn btn--primary" onClick={commitConnection}>Connect</button>
          </div>
        </aside>
      )}

      {/* ---- floating spatial panel for the selected unit ---- */}
      {selected && (
        <aside className="sm-float sm-float--panel" aria-label={`${selected.tag} controls`}>
          <header className="sm-panel__head">
            <span className="sm-panel__tag">{selected.tag}</span>
            <button className="sm-panel__close" onClick={() => setSelected(null)} aria-label="Close panel">×</button>
          </header>
          <p className="sm-panel__name">{selected.name}</p>
          {connections.filter((c) => c.source === selected.id || c.target === selected.id).length > 0 && (
            <ul className="sm-panel__links">
              {connections
                .filter((c) => c.source === selected.id || c.target === selected.id)
                .map((c) => {
                  const otherId = c.source === selected.id ? c.target : c.source;
                  const other = equipment.find((e) => e.id === otherId);
                  const meta = RELATION_BY_ID[relationOf(c)];
                  return (
                    <li key={c.id}>
                      <span className={`sm-link sm-link--${relationOf(c)}`}>{meta?.label ?? relationOf(c)}</span>
                      <span className="sm-panel__link-target">{c.source === selected.id ? "→" : "←"} {other?.tag ?? otherId}</span>
                      <button
                        className="sm-panel__save"
                        onClick={() => saveConnection(c)}
                        title="Save this connection to reuse it later"
                        aria-label={`Save ${meta?.label ?? ""} link to ${other?.tag ?? otherId}`}
                      >
                        ★
                      </button>
                      <button
                        className="sm-panel__unlink"
                        onClick={() => setConnections((cur) => cur.filter((x) => x.id !== c.id))}
                        aria-label={`Remove ${meta?.label ?? ""} link to ${other?.tag ?? otherId}`}
                      >
                        ×
                      </button>
                    </li>
                  );
                })}
            </ul>
          )}
          <div className="cs-chips" style={{ marginBottom: 12 }}>
            <span className="cs-chip" style={{ cursor: "default" }}>{selected.sensors.length} sensors</span>
            <span className="cs-chip" style={{ cursor: "default" }}>{selected.failure_modes.length} faults</span>
          </div>

          {/* Instrumentation inspector. Every field below is read from the
              sensor's own SensorDef — bands, sampling and redundancy are the
              values the engine actually evaluates against. */}
          {selected.sensors.length > 0 && (
            <div className="sm-sensors">
              <p className="sm-sensors__label">Instrumentation</p>
              {selected.sensors.map((sn) => {
                const twins = selected.sensors.filter(
                  (o) => o.id !== sn.id && o.measurement === sn.measurement,
                );
                const linked = connections.filter(
                  (c) =>
                    (c.source === selected.id && c.target === sn.id) ||
                    (c.target === selected.id && c.source === sn.id),
                );
                return (
                  <details key={sn.id} className="sm-sensor">
                    <summary>
                      <span className="sm-sensor__tag">{sn.tag}</span>
                      <span className="sm-sensor__type">{sn.measurement}</span>
                      <span className="sm-sensor__cur">
                        {sn.nominal} {sn.unit}
                      </span>
                      {twins.length > 0 && <span className="sm-sensor__redun" title="Redundant partner available">redundant</span>}
                    </summary>
                    <dl className="sm-sensor__body">
                      <div><dt>ID</dt><dd className="cs-mono">{sn.id}</dd></div>
                      <div><dt>Equipment</dt><dd className="cs-mono">{selected.tag}</dd></div>
                      <div><dt>Measurement</dt><dd>{sn.measurement}</dd></div>
                      <div><dt>Unit</dt><dd>{sn.unit}</dd></div>
                      <div><dt>Normal</dt><dd className="cs-mono">{sn.normal_min}–{sn.normal_max}</dd></div>
                      <div><dt>Warning</dt><dd className="cs-mono">{sn.warning_min}–{sn.warning_max}</dd></div>
                      <div><dt>Critical</dt><dd className="cs-mono">{sn.critical_min}–{sn.critical_max}</dd></div>
                      <div><dt>Sampling</dt><dd className="cs-mono">{sn.sampling_ms} ms</dd></div>
                      <div>
                        <dt>Redundant</dt>
                        <dd className="cs-mono">{twins.length ? twins.map((t) => t.tag).join(", ") : "none declared"}</dd>
                      </div>
                      <div><dt>Wired</dt><dd>{linked.length ? `${linked.length} link(s)` : "not wired"}</dd></div>
                    </dl>
                  </details>
                );
              })}
              <p className="sm-sensors__hint">
                Wire instruments with Connect mode, or attach them to the unit — the engine reads both.
              </p>
            </div>
          )}

          {!running ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
              {connectFrom === "__arm__" && (
                <Button variant="primary" onClick={() => setConnectFrom(selected.id)}>
                  <Icon name="workflow" size={12} /> Pipe from {selected.tag}
                </Button>
              )}
              <Button variant="ghost" onClick={() => saveItem(selected)}>
                <Icon name="plus" size={12} /> Save this unit for reuse
              </Button>
              <Button
                variant="reject"
                onClick={() => {
                  setEquipment((cur) => cur.filter((e) => e.id !== selected.id));
                  setConnections((cur) => cur.filter((c) => c.source !== selected.id && c.target !== selected.id));
                  setSelected(null);
                }}
              >
                <Icon name="x" size={12} /> Remove
              </Button>
            </div>
          ) : (
            <>
              <p className="sm-panel__label">Inject fault</p>
              <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                {selected.failure_modes.map((fm) => {
                  const mode = FAILURE_MODES.find((m) => m.id === fm);
                  return (
                    <button key={fm} className="sm-scenario" onClick={() => inject(selected.id, fm)} title={mode?.description}>
                      <Icon name="alert" size={12} /> {mode?.name ?? fm}
                    </button>
                  );
                })}
              </div>
            </>
          )}
        </aside>
      )}

      {/* ---- connect-mode hint: always says what the next click does ---- */}
      {connectFrom && !pending && (
        <div className="sm-float sm-float--hint" role="status">
          <span className="sm-hint__dot" aria-hidden="true" />
          {connectFrom === "__arm__" ? (
            <>Select the <b>source</b> unit</>
          ) : (
            <>
              Source <b>{equipment.find((e) => e.id === connectFrom)?.tag ?? connectFrom}</b> — now select the{" "}
              <b>target</b>
            </>
          )}
          <button onClick={() => setConnectFrom(null)}>Cancel</button>
        </div>
      )}

      {/* ---- floating validation report ---- */}
      {report && (
        <aside className="sm-float sm-float--report" aria-label="Plant validation report">
          <header className="sm-report__head">
            <span className="sm-report__title">Plant validation</span>
            <span className={`sm-report__verdict sm-report__verdict--${report.ok ? "ok" : "bad"}`}>
              {report.ok ? "PASS" : "BLOCKED"}
            </span>
            <button className="sm-panel__close" onClick={() => setReport(null)} aria-label="Close report">×</button>
          </header>

          <ul className="sm-report__counts">
            <li><b>{report.counts.equipment}</b> equipment</li>
            <li><b>{report.counts.sensors}</b> sensors</li>
            <li><b>{report.counts.connections}</b> connections</li>
            <li className={report.counts.orphanSensors ? "is-warn" : ""}><b>{report.counts.orphanSensors}</b> orphan sensors</li>
            <li className={report.counts.invalidConnections ? "is-bad" : ""}><b>{report.counts.invalidConnections}</b> invalid connections</li>
            <li className={report.counts.orphanEquipment ? "is-warn" : ""}><b>{report.counts.orphanEquipment}</b> disconnected units</li>
          </ul>

          {report.errors.length > 0 && (
            <div className="sm-report__group">
              <h5>Errors — these block a coherent simulation</h5>
              <ul>
                {report.errors.map((e, i) => (
                  <li key={`e-${i}`} className="sm-report__item is-error">
                    {e.message}
                    {e.ids.length > 0 && (
                      <span className="sm-report__ids">
                        {e.ids.slice(0, 3).map((id) => {
                          const unit = equipment.find((x) => x.id === id);
                          return unit ? (
                            <button key={id} onClick={() => setSelected(unit)}>{unit.tag}</button>
                          ) : null;
                        })}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {report.warnings.length > 0 && (
            <div className="sm-report__group">
              <h5>{report.warnings.length} warning{report.warnings.length === 1 ? "" : "s"}</h5>
              <ul>
                {report.warnings.slice(0, 12).map((w, i) => (
                  <li key={`w-${i}`} className="sm-report__item is-warn">
                    {w.message}
                    {w.ids.length > 0 && (
                      <span className="sm-report__ids">
                        {w.ids.slice(0, 2).map((id) => {
                          const unit = equipment.find((x) => x.id === id);
                          return unit ? (
                            <button key={id} onClick={() => setSelected(unit)}>{unit.tag}</button>
                          ) : null;
                        })}
                      </span>
                    )}
                  </li>
                ))}
                {report.warnings.length > 12 && (
                  <li className="sm-report__more">+{report.warnings.length - 12} more</li>
                )}
              </ul>
            </div>
          )}
        </aside>
      )}

      {/* ---- floating incident response ---- */}
      {running && sim.activeIncident && (
        <aside className="sm-float sm-float--incident">
          <Panel title="Incident response" hud glow pad>
            <AgentCommandCenter
              incident={sim.activeIncident}
              tasks={sim.tasks}
              plan={sim.plan}
              now={sim.t}
              onDecide={(approved) => void simAdapter.decide("custom", sim.activeIncident!.id, approved)}
            />
          </Panel>
        </aside>
      )}

      {/* ---- floating event spine ---- */}
      {running && (
        <div className="sm-float sm-float--spine">
          <div className="sm-spine__head">
            <span className="cs-panel__title">Event spine — custom plant</span>
            <span className="cs-mono cs-dim" style={{ fontSize: 9, letterSpacing: "0.18em" }}>
              {sim.events.length} EVENTS
            </span>
          </div>
          <div className="sm-events">
            {[...sim.events].reverse().slice(0, 30).map((ev) => (
              <div key={ev.seq} className="sm-event">
                <span className="sm-event__t">#{ev.seq}</span>
                <span className="sm-event__type" style={{ color: "var(--blue)" }}>{ev.type}</span>
                <span className="sm-event__detail">{String(ev.payload.tag ?? ev.payload.title ?? ev.payload.equipment_id ?? "")}</span>
              </div>
            ))}
            {sim.events.length === 0 && (
              <p className="cs-dim cs-mono" style={{ fontSize: 10, alignSelf: "center", padding: "0 12px" }}>LISTENING…</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
