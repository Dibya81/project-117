"use client";

/**
 * Plant Graph — the refinery as one connected knowledge universe.
 *
 * Assembled at runtime from the same sources the rest of the console reads:
 *
 *   GET /api/simulation/plants/refinery/definition   the plant dataset (58
 *                                       units, 224 sensors, 18 areas, 60 process
 *                                       lines, 12 failure modes)
 *   GET /api/simulation/plants/refinery/scenarios    the 14 committed scenarios
 *   consoleData.*                       documents, work orders, anomalies,
 *                                       history, learned rules, approvals,
 *                                       agents
 *
 * The plant rows come from the backend's local SQLite store. They used to be
 * bundled JSON under public/simulation/, which meant the graph could describe
 * a different plant from the one the engine was running.
 *
 * Every edge is derived from a field that actually exists — `equipment_id`,
 * `area_id`, `applies_to`, evidence citations, `target`. Nothing is invented
 * to make the picture prettier, and each edge records where it came from.
 */
import { consoleData } from "@/lib/data/console";
import { API_BASE } from "@/lib/sim/adapter";
import { relationOf } from "@/lib/sim/relations";
import type { PlantTemplate } from "@/lib/sim/templates";
import {
  summarize,
  type KCommunity,
  type KEdge,
  type KGraph,
  type KNode,
  type Provenance,
} from "./types";

const REFINERY_ID = "refinery";

interface RefEquipment {
  id: string;
  tag: string;
  name: string;
  kind: string;
  area_id: string;
  x: number;
  y: number;
  criticality: number;
  state: string;
  sensors: RefSensor[];
}
interface RefSensor {
  id: string;
  tag: string;
  equipment_id: string;
  measurement: string;
  unit: string;
  sampling_ms: number;
  nominal: number;
  normal_min: number;
  normal_max: number;
  warning_min: number;
  warning_max: number;
  critical_min: number;
  critical_max: number;
}
interface RefArea { id: string; name: string; x: number; y: number; w: number; h: number }
interface RefConnection {
  id: string; kind: string; source: string; target: string;
  medium: string; capacity: number; status: string; enabled: boolean;
}
interface RefFailureMode {
  id: string; name: string; applies_to: string[]; mechanism: string;
  magnitude: number; description: string;
}
interface RefScenario {
  id: string; name: string; description: string;
  steps: { at_s: number; action: string; target: string; mode: string }[];
}

/** GET from the simulation API (plant rows live in its SQLite store). */
async function api<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}/api/simulation${path}`, { credentials: "same-origin" });
  if (!r.ok) throw new Error(`${path} → HTTP ${r.status}`);
  return (await r.json()) as T;
}

let cached: KGraph | null = null;
let cachedRevision = -1;
/**
 * The build in progress.
 *
 * `buildPlantGraph` is called from more than one component, and they mount in
 * the same tick — so both saw an empty cache and both ran the whole build,
 * reading the 103 KB plant definition and the scenarios twice. Caching the
 * *promise* rather than only the result makes the second caller await the first
 * one's build instead of starting its own.
 */
let inflightBuild: Promise<KGraph> | null = null;

export function cachedPlantGraph(): KGraph | null {
  return cached;
}

export async function buildPlantGraph(): Promise<KGraph> {
  // The builder's session store is the only thing that can change this graph
  // between calls, so its revision is the cache key.
  if (cached && cachedRevision === consoleData.customPlants.revision()) return cached;
  if (inflightBuild) return inflightBuild;
  inflightBuild = buildPlantGraphOnce().finally(() => {
    inflightBuild = null;
  });
  return inflightBuild;
}

async function buildPlantGraphOnce(): Promise<KGraph> {

  const def = await api<{
    plant: { id: string; name: string; industry: string } & {
      areas: RefArea[];
      equipment: RefEquipment[];
      connections: RefConnection[];
      failure_modes: RefFailureMode[];
    };
  }>(`/plants/${REFINERY_ID}/definition`);
  const { areas, equipment, connections, failure_modes: failureModes } = def.plant;
  const plant = { id: def.plant.id, name: def.plant.name, industry: def.plant.industry };
  const scenarios = await api<{ scenarios: RefScenario[] }>(`/plants/${REFINERY_ID}/scenarios`)
    .then((r) => r.scenarios)
    .catch(() => [] as RefScenario[]);

  /**
   * The materials subgraph, built by the backend from the same store the
   * materials pages read. Fetched here rather than derived client-side: a
   * relationship the console draws must be one the domain actually holds, and
   * rebuilding it in the browser would be a second definition of "requires".
   */
  const materialsGraph = await consoleData.materials.graph().catch(() => null);

  const [documents, workOrders, alerts, history, rules, approvals, agents, consoleEquipment] =
    await Promise.all([
      consoleData.documents.list(),
      consoleData.workOrders.list(),
      consoleData.alerts.active(),
      consoleData.history.list(),
      consoleData.history.rules(),
      consoleData.approvals.pending(),
      consoleData.agents.list(),
      consoleData.equipment.list(),
    ]);

  const nodes = new Map<string, KNode>();
  const edges: KEdge[] = [];
  let eid = 0;
  const add = (e: Omit<KEdge, "id">) => {
    edges.push({ ...e, id: `pe-${eid++}` });
  };
  const node = (n: KNode) => {
    if (!nodes.has(n.id)) nodes.set(n.id, n);
    return nodes.get(n.id)!;
  };

  const areaName = new Map(areas.map((a) => [a.id, a.name]));

  // ---- the plant -------------------------------------------------------
  node({
    id: `plant:${plant.id}`,
    label: plant.name,
    type: "plant",
    status: "running",
    source: "plant.json",
    facts: { industry: plant.industry, units: equipment.length, areas: areas.length },
  });

  for (const a of areas) {
    node({
      id: `area:${a.id}`,
      label: a.name,
      type: "area",
      group: a.name,
      source: "areas.json",
      // Rect centre — the plant dataset's own geometry drives the layout.
      x: a.x + a.w / 2,
      y: a.y + a.h / 2,
      facts: { units: equipment.filter((e) => e.area_id === a.id).length },
    });
    add({ from: `plant:${plant.id}`, to: `area:${a.id}`, relation: "HAS_AREA", provenance: "EXTRACTED", source: "areas.json" });
  }

  const areaRect = new Map(areas.map((a) => [a.id, a]));

  // ---- equipment + sensors --------------------------------------------
  for (const e of equipment) {
    const rect = areaRect.get(e.area_id);
    node({
      id: `equipment:${e.tag}`,
      label: `${e.name} (${e.tag})`,
      type: "equipment",
      group: areaName.get(e.area_id) ?? e.area_id,
      status: e.state,
      source: "equipment.json",
      // equipment x/y are area-relative; add the rect origin for world space.
      x: (rect?.x ?? 0) + e.x,
      y: (rect?.y ?? 0) + e.y,
      facts: {
        tag: e.tag, kind: e.kind, area: areaName.get(e.area_id) ?? e.area_id,
        criticality: e.criticality, sensors: e.sensors.length,
      },
      href: `/console/equipment/${e.tag}`,
    });
    add({ from: `area:${e.area_id}`, to: `equipment:${e.tag}`, relation: "CONTAINS", provenance: "EXTRACTED", source: "equipment.json" });

    for (const s of e.sensors) {
      node({
        id: `sensor:${s.tag}`,
        label: s.tag,
        type: "sensor",
        group: e.tag,
        source: "equipment.json",
        facts: {
          measurement: s.measurement, unit: s.unit,
          nominal: s.nominal, normal: `${s.normal_min}–${s.normal_max}`,
          sampling: `${s.sampling_ms} ms`,
        },
      });
      add({ from: `equipment:${e.tag}`, to: `sensor:${s.tag}`, relation: "HAS_SENSOR", provenance: "EXTRACTED", source: "equipment.json" });
    }
  }

  // ---- process lines ---------------------------------------------------
  const tagOf = new Map(equipment.map((e) => [e.id, e.tag]));
  for (const c of connections) {
    const a = tagOf.get(c.source);
    const b = tagOf.get(c.target);
    if (!a || !b) continue;
    add({
      from: `equipment:${a}`, to: `equipment:${b}`,
      relation: c.kind === "pipe" ? "FLOWS_TO" : c.kind.toUpperCase(),
      provenance: "SIMULATED", source: "connections.json",
    });
  }

  // ---- failure modes ---------------------------------------------------
  for (const fm of failureModes) {
    node({
      id: `failure_mode:${fm.id}`,
      label: fm.name,
      type: "failure_mode",
      source: "failure_modes.json",
      facts: { mechanism: fm.mechanism, magnitude: fm.magnitude, detail: fm.description },
    });
    // applies_to names measurements — link to the sensors that measure them.
    for (const s of equipment.flatMap((e) => e.sensors)) {
      if (fm.applies_to.includes(s.measurement)) {
        add({
          from: `sensor:${s.tag}`, to: `failure_mode:${fm.id}`,
          relation: "CAN_FAIL_WITH", provenance: "EXTRACTED", source: "failure_modes.json",
        });
      }
    }
  }

  // ---- scenarios -------------------------------------------------------
  for (const sc of scenarios) {
    node({
      id: `scenario:${sc.id}`,
      label: sc.name,
      type: "scenario",
      source: "scenarios.json",
      facts: { steps: sc.steps.length, detail: sc.description },
    });
    for (const st of sc.steps) {
      const tag = tagOf.get(st.target);
      if (!tag) continue;
      add({
        from: `scenario:${sc.id}`, to: `equipment:${tag}`,
        relation: "INJECTS", provenance: "SIMULATED", source: "scenarios.json",
      });
      add({
        from: `scenario:${sc.id}`, to: `failure_mode:${st.mode}`,
        relation: "USES_FAILURE", provenance: "SIMULATED", source: "scenarios.json",
      });
    }
  }

  // ---- narrative units (the console's own equipment set) ---------------
  // These carry the C-3 story. Any tag already present from the refinery
  // dataset is the same physical unit and is merged, not duplicated.
  //
  // NOTE the key: the refinery dataset keys a unit on its **tag** (`P-1001`),
  // while the console record carries an **id** (`e-P-1001`). These are the same
  // physical unit. This used to filter on `refineryTags.has(x.id)` — comparing a
  // tag set against an id — which never matched, so every console unit was added
  // a second time under `equipment:e-P-1001` alongside `equipment:P-1001`. That
  // doubled the graph: /console/knowledge reported 116 equipment and 448 sensors
  // for a 58-unit / 224-sensor plant.
  //
  // Matching on the tag and reusing it as the node id makes `node()` (an upsert
  // by id) merge the console record onto the refinery node, which is what the
  // comment below always claimed happened.
  const refineryTags = new Set(equipment.map((e) => e.tag));
  for (const e of consoleEquipment) {
    const canonicalId = e.tag && refineryTags.has(e.tag) ? e.tag : e.id;
    const existing = node({
      id: `equipment:${canonicalId}`,
      label: `${e.name} (${e.id})`,
      type: "equipment",
      group: e.zone,
      status: e.status,
      source: "console equipment",
      facts: { kind: e.kind, zone: e.zone, sensors: e.sensors.length },
      href: `/console/equipment/${e.id}`,
    });
    existing.status = e.status;
    existing.facts = { ...existing.facts, kind: e.kind, zone: e.zone, sensors: e.sensors.length };
    // Console sensor nodes are only for NARRATIVE units.
    //
    // A refinery-backed unit already carries its authoritative sensors from the
    // dataset — keyed `sensor:<tag>` — and the console's own key is a synthetic
    // `${signal}-${index}` that cannot be matched to them. Adding both was the
    // second half of the duplication: the graph reported 448 sensors (224 × 2)
    // for a 224-sensor plant. Where the unit came from the dataset, skip the
    // derived set and keep the real one.
    const fromDataset = canonicalId !== e.id;
    if (fromDataset) continue;
    for (const s of e.sensors) {
      const sid = `sensor:${e.id}/${s.key}`;
      node({
        id: sid, label: s.label, type: "sensor", group: e.id,
        source: "console telemetry",
        facts: { value: s.value, unit: s.unit },
      });
      add({ from: `equipment:${canonicalId}`, to: sid, relation: "HAS_SENSOR", provenance: "OBSERVED", source: "console telemetry" });
    }
  }

  // ---- builder-authored plants ----------------------------------------
  // Topology a person drew in /console/simulation/builder and saved this
  // session. It is authored knowledge, not an extraction, so every edge it
  // contributes is HUMAN-CONFIRMED. Stable ids (`equipment:<TAG>`,
  // `sensor:<TAG>`) mean a tag the prebuilt refinery already knows resolves to
  // the same node instead of a duplicate, and each drawn connection keeps its
  // real semantic relation (`relationOf`), never a generic "related".
  const customPlants = await consoleData.customPlants.list();
  for (const cp of customPlants) {
    const customArea = cp.areas[0]?.name ?? cp.name;
    /** Builder equipment/sensor id → stable graph node id. */
    const graphIdOf = new Map<string, string>();

    for (const e of cp.equipment) {
      const eqId = `equipment:${e.tag}`;
      graphIdOf.set(e.id, eqId);
      graphIdOf.set(e.tag, eqId);
      const existed = nodes.has(eqId);
      const eqNode = node({
        id: eqId,
        label: `${e.name} (${e.tag})`,
        type: "equipment",
        group: customArea,
        status: e.state,
        source: "builder topology",
        facts: {
          tag: e.tag, kind: e.kind, plant: cp.name, area: customArea,
          criticality: e.criticality, sensors: e.sensors.length,
        },
        href: `/console/equipment/${e.tag}`,
      });
      if (existed) {
        // Same physical tag the refinery dataset knows: keep its extracted
        // facts and record that a person also drew it in the builder.
        eqNode.facts = { ...eqNode.facts, builder_plant: cp.name };
      } else {
        eqNode.facts = { ...eqNode.facts, origin: "builder" };
      }

      for (const s of e.sensors) {
        const sid = `sensor:${s.tag}`;
        graphIdOf.set(s.id, sid);
        graphIdOf.set(s.tag, sid);
        node({
          id: sid, label: s.tag, type: "sensor", group: e.tag,
          source: "builder topology",
          facts: {
            measurement: s.measurement, unit: s.unit, nominal: s.nominal,
            normal: `${s.normal_min}–${s.normal_max}`, plant: cp.name,
          },
        });
        add({
          from: eqId, to: sid, relation: "HAS_SENSOR",
          provenance: "HUMAN-CONFIRMED", source: "builder topology",
        });
      }
    }

    for (const c of cp.connections) {
      const from = graphIdOf.get(c.source);
      const to = graphIdOf.get(c.target);
      if (!from || !to) continue;
      add({
        from, to,
        relation: relationOf(c),
        provenance: "HUMAN-CONFIRMED",
        source: `builder topology · ${cp.name}`,
      });
    }
  }

  // ---- documents -------------------------------------------------------
  const docIds = new Set(documents.map((d) => d.id));
  for (const d of documents) {
    node({
      id: `document:${d.id}`,
      label: d.filename,
      type: "document",
      status: d.status,
      source: "console documents",
      facts: {
        type: d.content_type.split("/").pop(),
        kb: Math.round(d.size_bytes / 1024),
        pages: (d.metadata as Record<string, unknown>)?.pages as number | undefined,
        entities: (d.metadata as Record<string, unknown>)?.entities as number | undefined,
      },
      href: `/console/documents?doc=${encodeURIComponent(d.id)}`,
    });
  }

  // ---- work orders -----------------------------------------------------
  for (const w of workOrders) {
    node({
      id: `work_order:${w.id}`,
      label: `${w.id} — ${w.title}`,
      type: "work_order",
      status: w.status,
      source: "console work orders",
      facts: { priority: w.priority, assignee: w.assignee, action: w.recommended_action },
      href: `/console/work-orders/${w.id}`,
    });
    add({ from: `work_order:${w.id}`, to: `equipment:${w.equipment_id}`, relation: "FOR_EQUIPMENT", provenance: "AI-DERIVED", source: "work order record" });
    for (const c of w.evidence) {
      if (!docIds.has(c.document_id)) continue;
      add({
        from: `work_order:${w.id}`, to: `document:${c.document_id}`,
        relation: "SUPPORTED_BY", provenance: "EXTRACTED",
        source: c.filename, confidence: 1,
      });
    }
  }

  // ---- anomalies -------------------------------------------------------
  for (const a of alerts) {
    node({
      id: `anomaly:${a.id}`,
      label: a.title,
      type: "anomaly",
      status: a.severity,
      source: "alert stream",
      facts: { severity: a.severity, detail: a.detail, at: a.at },
    });
    if (a.equipment_id) {
      add({ from: `anomaly:${a.id}`, to: `equipment:${a.equipment_id}`, relation: "OBSERVED_ON", provenance: "OBSERVED", source: "alert stream" });
    }
  }

  // ---- history ---------------------------------------------------------
  for (const h of history) {
    node({
      id: `event:${h.id}`,
      label: h.title,
      type: "event",
      status: h.kind,
      source: "operational history",
      facts: { kind: h.kind, actor: h.actor, detail: h.detail, at: h.at },
      href: `/console/history?event=${encodeURIComponent(h.id)}`,
    });
    if (h.equipment_id) {
      add({ from: `event:${h.id}`, to: `equipment:${h.equipment_id}`, relation: "ABOUT", provenance: "HUMAN-CONFIRMED", source: "operational history" });
    }
  }

  // ---- learned rules ---------------------------------------------------
  const knownTags = new Set([...nodes.keys()].filter((k) => k.startsWith("equipment:")).map((k) => k.slice(10)));
  for (const r of rules) {
    node({
      id: `rule:${r.id}`,
      label: r.rule,
      type: "rule",
      status: r.status,
      source: "learned rules",
      facts: {
        set_by: r.set_by, origin: r.origin, confidence: r.confidence,
        evidence: r.evidence_count, used: r.used_count,
      },
    });
    // Link the rule to any equipment tag named in its own text.
    const text = `${r.rule} ${r.origin ?? ""}`;
    for (const tag of knownTags) {
      if (new RegExp(`(^|[^A-Za-z0-9-])${tag.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}([^A-Za-z0-9-]|$)`).test(text)) {
        add({ from: `rule:${r.id}`, to: `equipment:${tag}`, relation: "LEARNED_FROM", provenance: "AI-DERIVED", source: "learned rule" });
      }
    }
  }

  // ---- approvals -------------------------------------------------------
  for (const a of approvals) {
    node({
      id: `approval:${a.id}`,
      label: a.action,
      type: "approval",
      status: a.status,
      source: "approval queue",
      facts: { risk: a.risk, agent: a.agent, requested_by: a.requested_by, reason: a.reason },
      href: `/console/approvals?approval=${encodeURIComponent(a.id)}`,
    });
    if (a.equipment_id) {
      add({ from: `approval:${a.id}`, to: `equipment:${a.equipment_id}`, relation: "AUTHORIZES", provenance: "HUMAN-CONFIRMED", source: "approval queue" });
    }
    for (const c of a.evidence) {
      if (docIds.has(c.document_id)) {
        add({ from: `approval:${a.id}`, to: `document:${c.document_id}`, relation: "EVIDENCE_FROM", provenance: "EXTRACTED", source: c.filename });
      }
    }
    // Tie the approval to the work order its action text names.
    const m = /WO-\d+/.exec(a.action);
    if (m && nodes.has(`work_order:${m[0]}`)) {
      add({ from: `approval:${a.id}`, to: `work_order:${m[0]}`, relation: "GOVERNS", provenance: "EXTRACTED", source: "approval record" });
    }
  }

  // ---- agents ----------------------------------------------------------
  for (const ag of agents) {
    node({
      id: `agent:${ag.kind}`,
      label: ag.name,
      type: "agent",
      status: ag.status,
      source: "agent registry",
      // `model_role` and `permissions` are not on the wire; reading them threw
      // "Cannot read properties of undefined (reading 'join')" and the whole
      // Knowledge Universe rendered as "Graph unavailable".
      facts: {
        capabilities: (ag.capabilities ?? []).join(", "),
        tools: (ag.tools ?? []).join(", "),
        grounding: ag.requires_rag ? "retrieval required" : "no retrieval",
      },
      href: "/console/workspace",
    });
    for (const w of workOrders) {
      if (w.assignee === ag.kind || w.assignee === `${ag.kind}-agent`) {
        add({ from: `agent:${ag.kind}`, to: `work_order:${w.id}`, relation: "PRODUCED", provenance: "AI-DERIVED", source: "work order assignment" });
      }
    }
    for (const a of approvals) {
      if (a.agent === ag.kind) {
        add({ from: `agent:${ag.kind}`, to: `approval:${a.id}`, relation: "REQUESTED", provenance: "AI-DERIVED", source: "approval queue" });
      }
    }
  }

  // ---- documents → equipment -------------------------------------------
  // Links are read from the document's own text, not from a pre-computed tag
  // list: the corpus extractor only recognises multi-letter tags, so a
  // single-letter unit like C-3 or P-1042 would otherwise never link. The
  // haystack is the filename, the section title, the extracted entities and
  // the body lines — all real content, nothing synthesised.
  for (const d of documents) {
    const c = (d as { content?: { entities?: string[]; lines?: string[]; title?: string } }).content;
    const haystack = [d.filename, c?.title ?? "", ...(c?.entities ?? []), ...(c?.lines ?? [])].filter(Boolean);
    for (const tag of knownTags) {
      const re = new RegExp(`(^|[^A-Za-z0-9])${tag.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}([^A-Za-z0-9]|$)`);
      const hit = haystack.find((text) => re.test(text));
      if (!hit) continue;
      add({
        from: `document:${d.id}`,
        to: `equipment:${tag}`,
        relation: "MENTIONS",
        provenance: "EXTRACTED",
        source: hit === d.filename ? d.filename : `document text · ${d.filename}`,
        confidence: hit === d.filename ? 1 : 0.9,
      });
    }
  }

  // No register/overlay crosswalk. One existed here, joining the plant's
  // register tags (C-1071, E-1063, TK-1121) to a narrative vocabulary
  // (C-3, E-340, T-118) that came from demo data since deleted. Every entry
  // was inert — the overlay side never existed — while its comments described
  // a reconciliation that could not happen. The graph is built from the real
  // register alone, so there is nothing to join.

  /* Materials are spliced in BEFORE the node/edge filter below. The filter drops
     any edge whose endpoints are not in `liveIds`, so adding them afterwards
     silently discarded every materials relationship — the graph stayed correct
     and empty of materials at the same time. */
  /**
   * Industrial materials.
   *
   * Materials are first-class nodes in the same universe as the plant: a pump
   * REQUIRES a seal kit, the kit is STOCKED_AT a warehouse, supplied by a
   * supplier, and the feedstock FLOWS_TO the unit that consumes it. Those edges
   * come from the backend's own `REQUIRES` / `STOCKED_AT` / `SUPPLIED_BY` /
   * `FLOWS_TO` / `PRODUCES` relations, not from a client-side guess.
   *
   * The mapping to plant nodes is by *tag*: the backend keys equipment as
   * `e-P-1001` and the plant graph keys it as `equipment:P-1001`, so the join is
   * made explicit here instead of hoping the two id spaces coincide.
   */
  if (materialsGraph) {
    const MATERIAL_NODE_TYPES = new Set([
      "RAW_MATERIAL",
      "INTERMEDIATE",
      "FINISHED_PRODUCT",
      "MAINTENANCE_SPARE",
    ]);
    for (const m of materialsGraph.nodes) {
      if (m.kind === "WAREHOUSE" || m.kind === "TANK") {
        node({
          id: `location:${m.id}`,
          label: m.id.startsWith("e-") ? m.id.replace(/^e-/, "") : m.id,
          type: "storage",
          group: "Materials",
          status: m.kind === "WAREHOUSE" ? "warehouse" : "tank",
          source: "materials store",
          facts: { kind: m.kind },
        });
        continue;
      }
      const isMaterial = MATERIAL_NODE_TYPES.has(m.kind);
      node({
        id: isMaterial ? `material:${m.id}` : `${m.kind.toLowerCase()}:${m.id}`,
        label: m.label,
        type: isMaterial ? "material" : m.kind.toLowerCase(),
        group: "Materials",
        status: String((m.status as string | undefined) ?? (m.kind === "SUPPLIER" ? "supplier" : "")),
        source: "materials store",
        href: isMaterial ? `/console/materials/${encodeURIComponent(m.id)}` : undefined,
        facts: {
          kind: m.kind,
          unit: m.unit as string | undefined,
          class: m.material_class as string | undefined,
          lead_time_days: m.lead_time_days as number | undefined,
        },
      });
    }
    for (const e of materialsGraph.edges) {
      // Plant edges join through the tag, because the two id spaces differ.
      const endpoint = (id: string, kind: string): string => {
        if (kind === "EQUIPMENT") return `equipment:${id.replace(/^e-/, "")}`;
        if (kind === "PROCESS_UNIT") return `equipment:${id.replace(/^e-/, "")}`;
        if (kind === "WAREHOUSE" || kind === "TANK") return `location:${id}`;
        if (kind === "SUPPLIER") return `supplier:${id}`;
        if (kind === "FINISHED_PRODUCT" || kind === "RAW_MATERIAL" || kind === "INTERMEDIATE" || kind === "MAINTENANCE_SPARE") {
          return `material:${id}`;
        }
        return `material:${id}`;
      };
      const from = endpoint(e.source, String((materialsGraph.nodes.find((n) => n.id === e.source)?.kind) ?? ""));
      const to = endpoint(e.target, String((materialsGraph.nodes.find((n) => n.id === e.target)?.kind) ?? ""));
      add({
        from,
        to,
        relation: e.relation,
        provenance: "EXTRACTED",
        source: "materials store",
      });
      // A spare's price history is an edge, not a decoration: it is what makes
      // "what has this cost done?" reachable from the asset that needs it.
      if (e.relation === "REQUIRES") {
        node({
          id: `pricehistory:${e.target}`,
          label: `Price history · ${e.target}`,
          type: "price_history",
          group: "Materials",
          status: "series",
          source: "materials store",
          href: `/console/materials/price-history?item=${encodeURIComponent(String(e.target))}`,
        });
        add({
          from: `material:${e.target}`,
          to: `pricehistory:${e.target}`,
          relation: "HAS_PRICE_HISTORY",
          provenance: "EXTRACTED",
          source: "materials store",
        });
      }
    }
  }


  const nodeList = [...nodes.values()];
  const liveIds = new Set(nodeList.map((n) => n.id));
  // Defensive dedupe: building the node set can collapse two edges onto the
  // same pair. Drop self-loops and keep one edge per (from, to, relation).
  const liveEdges: KEdge[] = [];
  const seenEdge = new Set<string>();
  for (const e of edges) {
    if (!liveIds.has(e.from) || !liveIds.has(e.to) || e.from === e.to) continue;
    const key = `${e.from}|${e.to}|${e.relation}`;
    if (seenEdge.has(key)) continue;
    seenEdge.add(key);
    liveEdges.push(e);
  }
  const edgeList = liveEdges;

  const communities: KCommunity[] = areas.map((a) => {
    const members = nodeList.filter((n) => n.group === a.name);
    return {
      id: a.id,
      name: a.name,
      size: members.length,
      major: members.slice(0, 6).map((m) => ({ id: m.id, label: m.label, kind: m.type })),
    };
  }).filter((c) => c.size > 0);

  cachedRevision = consoleData.customPlants.revision();
  cached = {
    namespace: "plant",
    nodes: nodeList,
    edges: edgeList,
    communities,
    stats: summarize(nodeList, edgeList, communities),
  };
  return cached;
}

/** Unused export kept for the template-typed contract. */
export type { PlantTemplate };
