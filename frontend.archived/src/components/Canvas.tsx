/**
 * Canvas.
 *
 * One React Flow instance shared by all three pages. Builder mode adds drop
 * handling and connection rules; view mode is read-only. Everything else —
 * node types, edge types, status glow, trace highlighting — is identical, so a
 * prebuilt plant and a hand-built one behave the same way.
 */
import { useCallback, useMemo, useRef } from "react";
import ReactFlow, {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlowProvider,
  useReactFlow,
  type Node,
  type NodeMouseHandler,
  type OnConnect,
} from "reactflow";
import "reactflow/dist/style.css";

import { useSim } from "../store/simStore";
import { useOrchestrator } from "../ws/orchestrator";
import { EquipmentNode, SensorNode, ZoneNode } from "./nodes";
import { FlowEdge } from "./FlowEdge";
import { isValidConnection } from "../sim/validate";
import type { EquipmentType, SensorType } from "../types";

const nodeTypes = { equipment: EquipmentNode, sensor: SensorNode, zone: ZoneNode };
const edgeTypes = { flow: FlowEdge };

/** Drag payload keys used between the palette and the canvas. */
export const DND_EQUIPMENT = "application/project117.equipment";
export const DND_SENSOR = "application/project117.sensor";

function Flow({ mode }: { mode: "view" | "build" }) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const { project } = useReactFlow();

  const {
    nodes,
    edges,
    onNodesChange,
    onEdgesChange,
    onConnect: connect,
    openMenu,
    closeMenu,
    select,
    addEquipment,
    addSensor,
    runValidation,
  } = useSim();

  const activeEquipmentId = useOrchestrator((s) => s.activeEquipmentId);
  const status = useOrchestrator((s) => s.status);

  /**
   * Trace highlighting is derived, not stored: a unit is traced when the
   * orchestrator's current equipment matches it, and any edge touching that
   * unit goes active so its dashes animate.
   */
  const { viewNodes, viewEdges } = useMemo(() => {
    const tracedIds = new Set<string>();
    if (activeEquipmentId) {
      tracedIds.add(activeEquipmentId);
      for (const s of nodes) {
        if (s.type === "sensor" && nodes.find((n) => n.id === activeEquipmentId)?.id) {
          const belongsTo = edges.some(
            (e) =>
              (e.source === s.id && e.target === activeEquipmentId) ||
              (e.target === s.id && e.source === activeEquipmentId),
          );
          if (belongsTo) tracedIds.add(s.id);
        }
      }
    }

    // Defensive: React Flow throws — and takes the whole canvas with it — if a
    // node's `parentId` names a node that is not in the array. Rather than
    // trust every caller, drop the parent link here and let the node render
    // unparented.
    const ids = new Set(nodes.map((n) => n.id));
    const safe = nodes.map((n) =>
      n.parentId && !ids.has(n.parentId) ? { ...n, parentId: undefined, extent: undefined } : n,
    );

    // Compartment counts are derived from the nodes actually parented to each
    // zone, not from what the layout saw when it ran. Otherwise a zone created
    // on an empty canvas keeps reporting zero units as you drop them in.
    const childCounts = new Map<string, { units: number; sensors: number }>();
    for (const n of safe) {
      if (!n.parentId) continue;
      const c = childCounts.get(n.parentId) ?? { units: 0, sensors: 0 };
      if (n.type === "equipment") c.units += 1;
      if (n.type === "sensor") c.sensors += 1;
      childCounts.set(n.parentId, c);
    }

    const viewNodes: Node[] = safe.map((n) => {
      const withTrace = tracedIds.has(n.id) ? { ...n, data: { ...n.data, traced: true } } : n;
      if (n.type !== "zone") return withTrace;
      const c = childCounts.get(n.id) ?? { units: 0, sensors: 0 };
      return { ...withTrace, data: { ...withTrace.data, unitCount: c.units, sensorCount: c.sensors } };
    });
    const viewEdges = edges.map((e) =>
      activeEquipmentId && (e.source === activeEquipmentId || e.target === activeEquipmentId)
        ? { ...e, data: { ...e.data, active: true } }
        : { ...e, data: { ...e.data, active: false } },
    );
    return { viewNodes, viewEdges };
  }, [nodes, edges, activeEquipmentId]);

  const onNodeClick: NodeMouseHandler = useCallback(
    (event, node) => {
      if (node.type === "zone") return;
      select(node.id);
      // The menu is available in both modes: fault injection and inspection
      // apply to a prebuilt plant just as much as to a hand-built one.
      openMenu(node.id, event.clientX, event.clientY);
    },
    [openMenu, select],
  );

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      if (mode !== "build") return;
      event.preventDefault();
      const bounds = wrapRef.current?.getBoundingClientRect();
      if (!bounds) return;
      const position = project({
        x: event.clientX - bounds.left,
        y: event.clientY - bounds.top,
      });

      const eq = event.dataTransfer.getData(DND_EQUIPMENT);
      if (eq) {
        addEquipment(eq as EquipmentType, position.x, position.y);
        return;
      }
      const sen = event.dataTransfer.getData(DND_SENSOR);
      if (sen) addSensor(sen as SensorType, position.x, position.y);
    },
    [mode, project, addEquipment, addSensor],
  );

  const onDragOver = useCallback(
    (event: React.DragEvent) => {
      if (mode !== "build") return;
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
    },
    [mode],
  );

  const handleConnect: OnConnect = useCallback(
    (conn) => {
      connect(conn);
      // Re-run the report so the panel reflects the graph the user just drew.
      setTimeout(runValidation, 0);
    },
    [connect, runValidation],
  );

  return (
    <div className="canvas" ref={wrapRef}>
      <ReactFlow
        nodes={viewNodes}
        edges={viewEdges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={mode === "build" ? onNodesChange : undefined}
        onEdgesChange={mode === "build" ? onEdgesChange : undefined}
        onConnect={mode === "build" ? handleConnect : undefined}
        onNodeClick={onNodeClick}
        onPaneClick={closeMenu}
        onDrop={onDrop}
        onDragOver={onDragOver}
        isValidConnection={(c) => isValidConnection(c, nodes, edges)}
        nodesDraggable={mode === "build"}
        nodesConnectable={mode === "build"}
        elementsSelectable
        fitView
        fitViewOptions={{ padding: 0.16, maxZoom: 1.1 }}
        minZoom={0.08}
        maxZoom={2.2}
        proOptions={{ hideAttribution: true }}
        className={`rf-canvas${status === "mock" ? " rf-canvas--mock" : ""}`}
      >
        <Background variant={BackgroundVariant.Dots} gap={26} size={1} color="#1d2836" />
        <Controls showInteractive={mode === "build"} position="bottom-left" />
        <MiniMap
          position="bottom-right"
          pannable
          zoomable
          nodeColor={(n) => {
            if (n.type === "zone") return "#141c26";
            if (n.type === "sensor") return "#2b6f8f";
            const st = (n.data as { status?: string })?.status;
            return st === "critical" ? "#ff5d5d" : st === "warning" ? "#ffb454" : st === "disabled" ? "#54606e" : "#3f8fb5";
          }}
          maskColor="rgba(6,10,16,0.72)"
          style={{ background: "#0a1017", border: "1px solid #1b2532" }}
        />
      </ReactFlow>
    </div>
  );
}

export function Canvas({ mode }: { mode: "view" | "build" }) {
  return (
    <ReactFlowProvider>
      <Flow mode={mode} />
    </ReactFlowProvider>
  );
}
