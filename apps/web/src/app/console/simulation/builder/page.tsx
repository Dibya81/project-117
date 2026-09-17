"use client";

/**
 * Build Your Own Plant — blank industrial canvas → wired plant → run the SAME
 * engine → inject a fault → watch the SAME agent pipeline respond.
 * This page proves generalization: no prebuilt dataset involved.
 */
import { type PointerEvent as ReactPointerEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronRight } from "lucide-react";
import { Button, Panel, StatusDot, Tag } from "@/components/ui/primitives";
import { Icon, type IconName } from "@/components/ui/Icon";
import { emptyRuntime, runtimeFromEngine } from "@/components/sim/SchematicCanvas";
import { snapToGrid } from "@/components/sim/ProcessMap";
import { MeridianRefineryView } from "@/components/sim/MeridianRefineryView";
import { AgentCommandCenter } from "@/components/sim/AgentCommandCenter";
import { SimSymbol, symbolForEquipment } from "@/lib/sim/symbols";
import { simAdapter, asEmbedded, asLive, DATA_MODE } from "@/lib/sim/adapter";
import { consoleData } from "@/lib/data/console";
import { useSimulation } from "@/lib/sim/store";
import { assemblePlant, defaultSensors, makeConnection, makeEquipment, makeSensorOf, SENSOR_MEASUREMENTS, FM_BY_KIND, FAILURE_MODES } from "@/lib/sim/custom";
import { validatePlant, type PlantValidation } from "@/lib/sim/validate";
import { RELATION_BY_ID, portOf, relationOf, validRelations } from "@/lib/sim/relations";
import { lucideFor } from "@/components/ui/LucideIcon";
import { SPRING } from "@/lib/ui/motion";
import type { RelationType } from "@/lib/sim/types";
import { BUILDER_TEMPLATES, type PlantTemplate } from "@/lib/sim/templates";
import type { EquipmentDef, EquipmentKind, PlantDef, SensorDef } from "@/lib/sim/types";

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


interface PaletteItem {
  id: string;
  kind: EquipmentKind;
  label: string;
}

const PALETTE: { group: string; icon: IconName; items: PaletteItem[] }[] = [
  {
    group: "Crude & Distillation",
    icon: "equipment",
    items: [
      { id: "crude_tank", kind: "tank", label: "Crude Storage Tank" },
      { id: "desalter", kind: "vessel", label: "Desalter Unit" },
      { id: "furnace", kind: "furnace", label: "Crude Furnace" },
      { id: "atm_col", kind: "column", label: "Atmospheric Distillation" },
      { id: "vac_col", kind: "column", label: "Vacuum Distillation" },
      { id: "exchanger", kind: "exchanger", label: "Heat Exchanger" },
    ],
  },
  {
    group: "Conversion & Treating",
    icon: "pulse",
    items: [
      { id: "fcc", kind: "column", label: "FCC Unit" },
      { id: "hydrocracker", kind: "vessel", label: "Hydrocracker Reactor" },
      { id: "amine", kind: "vessel", label: "Amine Treating Unit" },
      { id: "sru", kind: "vessel", label: "SRU Sulfur Recovery" },
      { id: "hydrotreater", kind: "vessel", label: "Hydrotreater" },
      { id: "compressor", kind: "compressor", label: "Gas Compressor" },
    ],
  },
  {
    group: "Flow, Utilities & Safety",
    icon: "shield",
    items: [
      { id: "pump", kind: "pump", label: "Crude Charge Pump A/B" },
      { id: "valve", kind: "valve", label: "Process Control Valve" },
      { id: "cooling_tower", kind: "utility", label: "Cooling Tower" },
      { id: "boiler", kind: "furnace", label: "Industrial Boiler" },
      { id: "power_gen", kind: "motor", label: "Power Generator" },
      { id: "flare", kind: "safety", label: "Flare Stack & ESD" },
      { id: "lpg_tank", kind: "tank", label: "LPG Spherical Tank" },
      { id: "product_tank", kind: "tank", label: "Refined Product Tank" },
    ],
  },
];

export default function BuilderPage() {
  const router = useRouter();
  const [equipment, setEquipment] = useState<EquipmentDef[]>([]);
  const [connections, setConnections] = useState<PlantDef["connections"]>([]);
  const [armed, setArmed] = useState<PaletteItem | null>(null);
  /** Connect mode: units show their in/out ports and pipes are made port-to-port. */
  const [connectMode, setConnectMode] = useState(false);
  /** The output port that has been armed, waiting for a target input. */
  const [connectFrom, setConnectFrom] = useState<string | null>(null);
  const [selected, setSelected] = useState<EquipmentDef | null>(null);
  /** The line picked on the drawing, for the connection inspector. */
  const [selectedLineId, setSelectedLineId] = useState<string | null>(null);
  /** A connection being re-pointed: the next port click moves this end. */
  const [reconnect, setReconnect] = useState<{ id: string; end: "source" | "target" } | null>(null);
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
  /**
   * Which palette categories are open. The first is open on load so the drawer
   * never opens empty; the rest are collapsed, which is what makes a 30-symbol
   * library scannable instead of a wall.
   */
  const [openGroups, setOpenGroups] = useState<string[]>(() => [PALETTE[0]?.group ?? ""]);
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
          sensors: defaultSensors(kind, id, rec.id),
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
      setSelected(null);
      setSelectedLineId(null);
      setReconnect(null);
      setConnectFrom(null);
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
    setSelectedLineId(null);
    setReconnect(null);
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

  /** Drop a palette symbol at a screen point, snapped to the drawing grid. */
  const placeAt = useCallback(
    (item: PaletteItem, clientX: number, clientY: number) => {
      const el = dropRef.current;
      if (!el || running) return;
      const rect = el.getBoundingClientRect();
      const x = snapToGrid(((clientX - rect.left) / rect.width) * 1800 + 60);
      const y = snapToGrid(((clientY - rect.top) / rect.height) * 1000 + 60);
      setEquipment((cur) => [...cur, makeEquipment(item.kind, item.label, x, y, seq)]);
      setSeq((s) => s + 1);
      setArmed(null);
    },
    [running, seq],
  );

  const drop = useCallback(
    (e: ReactPointerEvent) => {
      if (!armed) return;
      placeAt(armed, e.clientX, e.clientY);
    },
    [armed, placeAt],
  );

  /**
   * Canvas click. In connect mode the wiring is done on the ports (see
   * `onPortClick`), so a body click always just selects — the two operations
   * never contend for the same gesture.
   */
  const onSelect = useCallback((eq: EquipmentDef) => {
    setSelected(eq);
    setSelectedLineId(null);
    // A body click is a selection, never a wiring gesture, so it cancels a
    // half-finished re-point instead of leaving it armed behind the scenes.
    setReconnect(null);
  }, []);

  /**
   * A line was picked on the drawing.
   *
   * A connection is a first-class selectable object, not a side effect of the
   * unit panel: the operator clicks the pipe they mean and gets its record.
   */
  const onSelectLine = useCallback((id: string | null) => {
    setSelectedLineId(id);
    if (id) setSelected(null);
  }, []);

  /** Duplicate a unit: same design, new tag, new ids, offset on the grid. */
  const duplicateEquipment = useCallback(
    (eq: EquipmentDef) => {
      const taken = new Set(equipment.map((e) => e.tag));
      let tag = `${eq.tag}-C`;
      let n = 2;
      while (taken.has(tag)) tag = `${eq.tag}-C${n++}`;
      const copy: EquipmentDef = {
        ...structuredClone(eq),
        id: `e-${tag}`,
        tag,
        name: `${eq.name} (copy)`,
        x: eq.x + 60,
        y: eq.y + 60,
        sensors: eq.sensors.map((sn) => ({
          ...sn,
          id: `s-${sn.tag.replace(eq.tag, tag)}`,
          equipment_id: `e-${tag}`,
          tag: sn.tag.replace(eq.tag, tag),
        })),
      };
      setEquipment((cur) => [...cur, copy]);
      setSelected(copy);
      setSaveState({ tone: "ok", text: `Duplicated ${eq.tag} as ${tag}` });
    },
    [equipment],
  );

  /** Move a unit on the drawing. Already snapped by the renderer. */
  const moveEquipment = useCallback((id: string, x: number, y: number) => {
    setEquipment((cur) => cur.map((e) => (e.id === id ? { ...e, x, y } : e)));
    setSelected((s) => (s && s.id === id ? { ...s, x, y } : s));
  }, []);

  /** Edit a unit's own fields (tag, name, position, …). */
  const updateEquipment = useCallback((id: string, patch: Partial<EquipmentDef>) => {
    setEquipment((cur) => cur.map((e) => (e.id === id ? { ...e, ...patch } : e)));
    setSelected((s) => (s && s.id === id ? { ...s, ...patch } : s));
  }, []);

  /**
   * Change a unit's type. The canonical asset follows the type, and so must the
   * instrumentation and the failure modes — they are properties of the KIND, so
   * leaving a pump's points on a tank would be a lie the engine then reads.
   */
  const changeKind = useCallback((id: string, kind: EquipmentKind) => {
    setEquipment((cur) =>
      cur.map((e) => {
        if (e.id !== id) return e;
        return {
          ...e,
          kind,
          // Keyed on the unit's own tag: two units of different kinds can share
          // a number, and deriving the suffix from the number collided their
          // instruments onto one id.
          sensors: defaultSensors(kind, e.id, e.tag || String(seq)),
          failure_modes: FM_BY_KIND[kind],
        };
      }),
    );
  }, [seq]);

  const addSensor = useCallback((eq: EquipmentDef, measurement: SensorDef["measurement"]) => {
    const n = eq.sensors.length + 1;
    const tag = `${measurement.slice(0, 2).toUpperCase()}-${eq.tag}-${n}`;
    const sensor = makeSensorOf(eq.id, tag, measurement);
    setEquipment((cur) => cur.map((e) => (e.id === eq.id ? { ...e, sensors: [...e.sensors, sensor] } : e)));
    setSelected((s) => (s && s.id === eq.id ? { ...s, sensors: [...s.sensors, sensor] } : s));
  }, []);

  const removeSensor = useCallback((eq: EquipmentDef, sensorId: string) => {
    setEquipment((cur) =>
      cur.map((e) => (e.id === eq.id ? { ...e, sensors: e.sensors.filter((s) => s.id !== sensorId) } : e)),
    );
    setSelected((s) => (s && s.id === eq.id ? { ...s, sensors: s.sensors.filter((x) => x.id !== sensorId) } : s));
  }, []);

  /** Tags must be unique: the id is derived from the tag and the plant is keyed by it. */
  const duplicateTags = useMemo(() => {
    const seen = new Map<string, number>();
    for (const e of equipment) seen.set(e.tag, (seen.get(e.tag) ?? 0) + 1);
    return new Set([...seen.entries()].filter(([, n]) => n > 1).map(([t]) => t));
  }, [equipment]);

  /**
   * A port was clicked. Output arms the source; input completes the pipe.
   *
   * Direction is structural, not incidental: a pipe always leaves an OUTPUT and
   * enters an INPUT, so an input→input or output→output attempt is refused
   * rather than silently reversed. When a line is being re-pointed the same
   * gesture moves that end of the EXISTING record instead of creating a second
   * one — the id, the relation and the other end are all kept.
   */
  const onPortClick = useCallback(
    (id: string, port: "in" | "out") => {
      const eq = equipment.find((e) => e.id === id);
      if (!eq) return;

      if (reconnect) {
        const line = connections.find((c) => c.id === reconnect.id);
        if (!line) {
          setReconnect(null);
          return;
        }
        const otherEnd = reconnect.end === "source" ? line.target : line.source;
        if (otherEnd === id) {
          setSaveState({ tone: "err", text: `${eq.tag} cannot feed itself.` });
          return;
        }
        const next = reconnect.end === "source"
          ? { ...line, source: id }
          : { ...line, target: id };
        if (connections.some((c) => c.id !== line.id && c.source === next.source && c.target === next.target)) {
          setSaveState({ tone: "err", text: "That link already exists — refusing a duplicate." });
          return;
        }
        setConnections((cur) => cur.map((c) => (c.id === line.id ? next : c)));
        setSaveState({
          tone: "ok",
          text: `${line.id} re-pointed: ${equipment.find((e) => e.id === next.source)?.tag ?? next.source} → ${equipment.find((e) => e.id === next.target)?.tag ?? next.target}`,
        });
        setReconnect(null);
        setConnectFrom(null);
        return;
      }

      if (port === "out") {
        setConnectFrom(id);
        setSelected(eq);
        setSelectedLineId(null);
        setSaveState({ tone: "busy", text: `${eq.tag} output armed — now click a unit's input port` });
        return;
      }
      if (!connectFrom) {
        setSaveState({ tone: "err", text: "That is an input. Start from a unit's output port (the right-hand dot)." });
        return;
      }
      if (connectFrom === id) {
        setSaveState({ tone: "err", text: `${eq.tag} cannot feed itself.` });
        return;
      }
      const source = equipment.find((e) => e.id === connectFrom);
      if (!source) return;
      if (connections.some((c) => c.source === connectFrom && c.target === id)) {
        setSaveState({ tone: "err", text: `${source.tag} → ${eq.tag} already exists.` });
        return;
      }
      const allowed = validRelations("equipment", "equipment");
      setRelation(allowed[0]?.id ?? "MATERIAL_FLOW");
      setPending({ source, target: eq });
      setConnectFrom(null);
    },
    [connectFrom, connections, equipment, reconnect],
  );

  /** Drop one line. Nothing else changes — no unit is touched. */
  const removeConnection = useCallback(
    (id: string) => {
      setConnections((cur) => cur.filter((c) => c.id !== id));
      setSelectedLineId((cur) => (cur === id ? null : cur));
      setSaveState({ tone: "ok", text: `Removed ${id}` });
    },
    [],
  );

  /** Commit the staged connection with the chosen relation. */
  const commitConnection = () => {
    if (!pending) return;
    // Defensive: the port flow already refuses duplicates, but a commit must
    // never be able to create two identical links from any path.
    if (connections.some((c) => c.source === pending.source.id && c.target === pending.target.id)) {
      setSaveState({ tone: "err", text: `${pending.source.tag} → ${pending.target.tag} already exists.` });
      setPending(null);
      return;
    }
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

  /**
   * Save the built plant, start it, then open it in LIVE mode.
   *
   * This is the whole point of the builder: what was designed becomes the
   * running plant. The definition is the SAME object the canvas is made of —
   * equipment, positions, sensors and connections — saved to the store and then
   * loaded by the live screen through the ordinary plant route, so nothing is
   * recreated or hardcoded on the way.
   */
  const run = async () => {
    if (equipment.length === 0) return;
    const p = assemblePlant(equipment, connections);
    setPlant(p);
    try {
      if (embedded) embedded.registerCustomPlant(p);
      else if (live) await live.savePlant(p);
      await simAdapter.start(p.id);
      setRunning(true);
      setSaveState({ tone: "ok", text: `Running ${p.equipment.length} units — opening the live plant` });
      router.push(`/console/simulation/plant/${encodeURIComponent(p.id)}`);
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
    setSelectedLineId(null);
    setReconnect(null);
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
        className={`sm-stage__canvas${armed ? " is-armed" : ""}${connectMode ? " is-wiring" : ""}`}
        onPointerDown={drop}
        onDragOver={(e) => {
          if (armed) e.preventDefault();
        }}
        onDrop={(e) => {
          e.preventDefault();
          const id = e.dataTransfer.getData("text/plain");
          const item = PALETTE.flatMap((g) => g.items).find((i) => i.id === id) ?? armed;
          if (item) placeAt(item, e.clientX, e.clientY);
        }}
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
          <>
          {/* The Builder draws the plant with the same renderer the live
              refinery uses. A plant built here must look identical when it is
              opened for operation, so there is one renderer with two modes
              rather than two renderers that drift. */}
          <MeridianRefineryView
            plant={displayPlant}
            runtime={runtime}
            readings={{}}
            selected={selected ?? null}
            onSelectEquipment={(eq) => onSelect(eq)}
            viewMode="overview"
            onViewModeChange={() => undefined}
            failover={null}
            activeIncident={sim.activeIncident}
            tasks={[]}
            models={{}}
            editable={!running}
            onEquipmentMove={moveEquipment}
            connectMode={connectMode && !running}
            connectFromId={connectFrom}
            onPortClick={onPortClick}
            selectedLineId={selectedLineId}
            onSelectLine={onSelectLine}
          />
          </>
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
              <Button
                variant={connectMode ? "primary" : "ghost"}
                onClick={() => {
                  setConnectMode((v) => !v);
                  setConnectFrom(null);
                  // Leaving connect mode abandons a half-finished re-point:
                  // the next port click must never silently move a line.
                  setReconnect(null);
                }}
                title="Show every unit's in/out ports, then wire output → input"
              >
                <Icon name="workflow" size={13} /> {connectMode ? "Exit connect" : "Connect mode"}
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
            {PALETTE.map((g) => {
              const isOpen = openGroups.includes(g.group);
              const GroupIcon = lucideFor(g.icon);
              return (
                <section key={g.group} className={`sm-dock__group${isOpen ? " is-open" : ""}`}>
                  <button
                    type="button"
                    className="sm-dock__grouphead"
                    aria-expanded={isOpen}
                    onClick={() =>
                      setOpenGroups((cur) =>
                        cur.includes(g.group) ? cur.filter((x) => x !== g.group) : [...cur, g.group],
                      )
                    }
                  >
                    <GroupIcon size={13} strokeWidth={2} aria-hidden="true" />
                    <span>{g.group}</span>
                    <span className="sm-dock__groupcount">{g.items.length}</span>
                    <motion.span
                      className="sm-dock__chev"
                      animate={{ rotate: isOpen ? 90 : 0 }}
                      transition={SPRING.panel}
                      aria-hidden="true"
                    >
                      <ChevronRight size={12} strokeWidth={2.6} />
                    </motion.span>
                  </button>
                  <AnimatePresence initial={false}>
                    {isOpen && (
                      <motion.div
                        className="sm-dock__groupbody"
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={SPRING.surface}
                        style={{ overflow: "hidden" }}
                      >
                        {/* Plain <button> elements, deliberately: these rows
                            are native HTML5 drag sources, and Framer Motion's
                            `motion.button` claims onDragStart for its own pan
                            gesture, which would fight the native drag. The hover
                            shift is CSS instead. */}
                        {g.items.map((item) => (
                          <button
                            key={item.id}
                            className={`sm-palette-item${armed?.id === item.id ? " is-armed" : ""}`}
                            onClick={() => setArmed(armed?.id === item.id ? null : item)}
                            draggable={!running}
                            onDragStart={(e) => {
                              e.dataTransfer.setData("text/plain", item.id);
                              e.dataTransfer.effectAllowed = "copy";
                              // A real drag ghost: the canvas shows the symbol
                              // being carried rather than a browser-default
                              // snapshot of the list row.
                              const ghost = document.createElement("div");
                              ghost.className = "sm-dragghost";
                              ghost.innerHTML = `<span>${item.label}</span>`;
                              document.body.appendChild(ghost);
                              e.dataTransfer.setDragImage(ghost, 18, 18);
                              window.setTimeout(() => ghost.remove(), 0);
                              setArmed(item);
                            }}
                            disabled={running}
                            title={
                              armed?.id === item.id
                                ? "Click the canvas to place"
                                : "Drag onto the canvas, or arm and click"
                            }
                          >
                            <SimSymbol type={symbolForEquipment(item.kind, item.label)} size={22} />
                            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                              {item.label}
                            </span>
                            <span className="cs-mono cs-dim" style={{ marginLeft: "auto", fontSize: 8.5 }}>
                              {defaultSensors(item.kind, "x", "0").length}
                            </span>
                          </button>
                        ))}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </section>
              );
            })}
            <p className="sm-dock__hint">
              Arm a symbol, then click the canvas to place it. Select a unit to wire or fault it.
            </p>
          </div>
        )}
      </aside>

      {/* ---- selected line: the connection's own record ---- */}
      {!running && (() => {
        const line = connections.find((c) => c.id === selectedLineId);
        if (!line) return null;
        const src = equipment.find((e) => e.id === line.source);
        const tgt = equipment.find((e) => e.id === line.target);
        const meta = RELATION_BY_ID[relationOf(line)];
        const rePointing = reconnect?.id === line.id;
        return (
          <aside
            className="sm-float sm-float--line"
            role="dialog"
            aria-label={`Connection ${line.id}`}
            data-testid="connection-inspector"
          >
            <header className="sm-panel__head">
              <span className="sm-panel__tag">{line.id}</span>
              <button className="sm-panel__close" onClick={() => { setSelectedLineId(null); setReconnect(null); }} aria-label="Close line panel">×</button>
            </header>
            <p className="sm-panel__name">
              {src?.tag ?? line.source} <span className="cs-dim">→</span> {tgt?.tag ?? line.target}
            </p>

            <dl className="sm-line__facts">
              <div><dt>From</dt><dd className="cs-mono">{src?.tag ?? line.source} · port <b>{portOf(line, "source")}</b></dd></div>
              <div><dt>To</dt><dd className="cs-mono">{tgt?.tag ?? line.target} · port <b>{portOf(line, "target")}</b></dd></div>
              <div><dt>Type</dt><dd>{meta?.label ?? relationOf(line)} <span className="cs-dim">({meta?.hint ?? relationOf(line)})</span></dd></div>
              <div><dt>Carrier</dt><dd>{line.kind}</dd></div>
              <div><dt>Medium</dt><dd className="cs-mono">{line.medium}</dd></div>
              <div><dt>Capacity</dt><dd className="cs-mono">{line.capacity}</dd></div>
            </dl>

            {rePointing ? (
              <p className="sm-panel__hint" data-testid="line-reconnect-hint">
                Re-pointing the <b>{reconnect.end}</b> end of <b>{line.id}</b>: click the{" "}
                <b>{reconnect.end === "source" ? "output" : "input"}</b> port of the unit that should
                take its place. The id, the type and the other end are kept.
              </p>
            ) : (
              <div className="sm-line__actions">
                <button
                  className="btn btn--ghost"
                  onClick={() => { setConnectMode(true); setConnectFrom(null); setReconnect({ id: line.id, end: "source" }); }}
                >
                  <Icon name="workflow" size={12} /> Reconnect from…
                </button>
                <button
                  className="btn btn--ghost"
                  onClick={() => { setConnectMode(true); setConnectFrom(null); setReconnect({ id: line.id, end: "target" }); }}
                >
                  <Icon name="workflow" size={12} /> Reconnect to…
                </button>
                <Button variant="reject" onClick={() => removeConnection(line.id)}>
                  <Icon name="x" size={12} /> Delete line
                </Button>
              </div>
            )}
          </aside>
        );
      })()}

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

          {/* Equipment properties. Everything here is written straight into the
              plant definition the canvas is built from, so the drawing, the
              validation, the saved record and the running engine all agree. */}
          {!running && (
            <div className="sm-props">
              <label className="sm-props__field">
                <span>Tag</span>
                <input
                  className="cs-mono"
                  value={selected.tag}
                  aria-label="Equipment tag"
                  onChange={(e) => updateEquipment(selected.id, { tag: e.target.value })}
                />
              </label>
              <label className="sm-props__field">
                <span>Name</span>
                <input
                  value={selected.name}
                  aria-label="Equipment name"
                  onChange={(e) => updateEquipment(selected.id, { name: e.target.value })}
                />
              </label>
              <label className="sm-props__field">
                <span>Type</span>
                <select
                  value={selected.kind}
                  aria-label="Equipment type"
                  onChange={(e) => changeKind(selected.id, e.target.value as EquipmentKind)}
                >
                  {(["tank", "vessel", "column", "furnace", "pump", "compressor", "valve", "exchanger", "motor", "utility", "safety"] as EquipmentKind[]).map((k) => (
                    <option key={k} value={k}>{k}</option>
                  ))}
                </select>
              </label>
              <div className="sm-props__row">
                <label className="sm-props__field">
                  <span>X</span>
                  <input
                    type="number"
                    value={selected.x}
                    aria-label="Equipment X"
                    onChange={(e) => updateEquipment(selected.id, { x: Number(e.target.value) })}
                  />
                </label>
                <label className="sm-props__field">
                  <span>Y</span>
                  <input
                    type="number"
                    value={selected.y}
                    aria-label="Equipment Y"
                    onChange={(e) => updateEquipment(selected.id, { y: Number(e.target.value) })}
                  />
                </label>
              </div>
              {duplicateTags.has(selected.tag) && (
                <p className="sm-props__warn">Tag <b>{selected.tag}</b> is used by another unit — tags must be unique.</p>
              )}
              <p className="sm-props__note">
                Status <b>{selected.state}</b> · {selected.failure_modes.length} failure mode(s) · drag on the canvas to move (snaps to {20}-unit grid)
              </p>
            </div>
          )}
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
                      <span className="cs-mono cs-dim sm-panel__link-id" title={`${c.id} · ${c.medium} · ${c.kind}`}>
                        {c.id}
                      </span>
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
                    {!running && (
                      <button
                        type="button"
                        className="sm-sensor__del"
                        onClick={(ev) => {
                          ev.preventDefault();
                          removeSensor(selected, sn.id);
                        }}
                        aria-label={`Remove ${sn.tag} from ${selected.tag}`}
                      >
                        Remove this point
                      </button>
                    )}
                  </details>
                );
              })}
              {!running && (
                <form
                  className="sm-sensor__add"
                  onSubmit={(ev) => {
                    ev.preventDefault();
                    const data = new FormData(ev.currentTarget);
                    const m = String(data.get("measurement") ?? "pressure") as SensorDef["measurement"];
                    addSensor(selected, m);
                    setSaveState({ tone: "ok", text: `Added a ${m} point to ${selected.tag}` });
                  }}
                >
                  <select name="measurement" aria-label="Sensor measurement" defaultValue="temperature">
                    {SENSOR_MEASUREMENTS.map((m) => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                  <button type="submit" className="sm-sensor__addbtn">
                    <Icon name="plus" size={11} /> Add sensor
                  </button>
                </form>
              )}
              <p className="sm-sensors__hint">
                Wire instruments with Connect mode, or attach them to the unit — the engine reads both.
              </p>
            </div>
          )}

          {!running ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
              {connectMode && (
                <p className="sm-panel__hint">
                  Connect mode: click <b>{selected.tag}</b>&apos;s output port (right dot), then a target&apos;s input port.
                </p>
              )}
              <Button variant="ghost" onClick={() => saveItem(selected)}>
                <Icon name="plus" size={12} /> Save this unit for reuse
              </Button>
              <Button variant="ghost" onClick={() => duplicateEquipment(selected)}>
                <Icon name="layers" size={12} /> Duplicate unit
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
      {connectMode && !pending && (
        <div className="sm-float sm-float--hint" role="status">
          <span className="sm-hint__dot" aria-hidden="true" />
          {connectFrom ? (
            <>
              Output <b>{equipment.find((e) => e.id === connectFrom)?.tag ?? connectFrom}</b> armed — click a
              target&apos;s <b>input</b> port
            </>
          ) : (
            <>
              Click a unit&apos;s <b>output</b> port (right dot) to start a pipe
            </>
          )}
          {connectFrom && <button onClick={() => setConnectFrom(null)}>Cancel</button>}
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
