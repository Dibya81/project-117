/**
 * Builder.
 *
 * Empty canvas → drag from the palette → wire it → validate → inject a fault.
 * The canvas starts genuinely empty; nothing is pre-populated, and the only
 * nodes present are the ones the user placed. The starting zone compartment is
 * created with the empty plant so drops always have somewhere to land.
 */
import { useEffect } from "react";
import { Shell } from "../components/Shell";
import { Canvas } from "../components/Canvas";
import { Palette } from "../components/Palette";
import { ValidationPanel } from "../components/ValidationPanel";
import { ContextMenu } from "../components/ContextMenu";
import { InfoDrawer } from "../components/InfoDrawer";
import { AgentTracePanel } from "../components/AgentTracePanel";
import { useSim } from "../store/simStore";
import { useFaultInjection } from "../hooks/useFaultInjection";

export function Builder() {
  const clear = useSim((s) => s.clear);
  const resetFaults = useSim((s) => s.resetFaults);
  const nodes = useSim((s) => s.nodes);
  const edges = useSim((s) => s.edges);
  const inject = useFaultInjection();

  // A fresh builder session every time this page is opened.
  useEffect(() => {
    clear();
  }, [clear]);

  const unitCount = nodes.filter((n) => n.type === "equipment").length;
  const sensorCount = nodes.filter((n) => n.type === "sensor").length;

  return (
    <Shell
      title="Builder"
      subtitle="Drag units and instruments onto the canvas, wire them, validate the circuit, then inject a fault."
      actions={
        <>
          <span className="chip">{unitCount} units</span>
          <span className="chip">{sensorCount} sensors</span>
          <span className="chip">{edges.length} connections</span>
          <button className="btn btn--ghost" onClick={resetFaults}>Reset faults</button>
        </>
      }
    >
      <div className="workspace">
        <Palette />

        <div className="workspace__center">
          <Canvas mode="build" />
          <ContextMenu onInject={inject} />
        </div>

        <div className="workspace__side">
          <ValidationPanel />
          <InfoDrawer />
        </div>
      </div>

      <AgentTracePanel />
    </Shell>
  );
}
