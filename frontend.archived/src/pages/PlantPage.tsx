/**
 * Plant canvas.
 *
 * Loads a prebuilt plant from the manifest and lays out every zone. Sensors
 * render with their value against the normal band on first paint, so the state
 * of the plant is readable without interacting with anything.
 *
 * A fault can be injected here too — the same context menu and the same
 * orchestrator contract as the builder, because the canvas is the same canvas.
 */
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Shell } from "../components/Shell";
import { Canvas } from "../components/Canvas";
import { ContextMenu } from "../components/ContextMenu";
import { InfoDrawer } from "../components/InfoDrawer";
import { AgentTracePanel } from "../components/AgentTracePanel";
import { loadManifest, loadPlant } from "../data/service";
import { useSim } from "../store/simStore";
import { useFaultInjection } from "../hooks/useFaultInjection";
import { sensorLevel } from "../sim/thresholds";
import type { Plant } from "../types";

export function PlantPage() {
  const { plantId } = useParams<{ plantId: string }>();
  const setPlant = useSim((s) => s.setPlant);
  const setError = useSim((s) => s.setError);
  const setLoading = useSim((s) => s.setLoading);
  const loading = useSim((s) => s.loading);
  const error = useSim((s) => s.error);
  const plant = useSim((s) => s.plant);
  const nodes = useSim((s) => s.nodes);
  const resetFaults = useSim((s) => s.resetFaults);
  const inject = useFaultInjection();
  const [label, setLabel] = useState("");

  useEffect(() => {
    if (!plantId) return;
    let alive = true;
    setLoading(true);
    loadManifest()
      .then((list) => {
        const entry = list.find((p) => p.id === plantId);
        if (!entry) throw new Error(`no plant "${plantId}" in the manifest`);
        setLabel(entry.name);
        return loadPlant(entry);
      })
      .then((p: Plant) => {
        if (alive) setPlant(p);
      })
      .catch((err: Error) => {
        if (alive) setError(err.message);
      });
    return () => {
      alive = false;
    };
  }, [plantId, setPlant, setError, setLoading]);

  const sensors = plant?.sensors ?? [];
  const levels = sensors.reduce(
    (acc, s) => {
      acc[sensorLevel(s)] += 1;
      return acc;
    },
    { normal: 0, warning: 0, critical: 0 } as Record<string, number>,
  );
  const critUnits = nodes.filter(
    (n) => n.type === "equipment" && (n.data as { status?: string }).status === "critical",
  ).length;

  return (
    <Shell
      title={label || plantId || "Plant"}
      subtitle={
        plant
          ? `${plant.zones.length} zones · ${plant.equipment.length} units · ${plant.sensors.length} sensors · ${plant.connections.length} connections`
          : undefined
      }
      actions={
        <>
          <span className="chip chip--ok">{levels.normal} in band</span>
          <span className="chip chip--warn">{levels.warning} warning</span>
          <span className="chip chip--bad">{levels.critical} out of band</span>
          {critUnits > 0 && <span className="chip chip--bad">{critUnits} units critical</span>}
          <button className="btn btn--ghost" onClick={resetFaults}>Reset faults</button>
        </>
      }
    >
      {loading && <div className="loading">Loading {plantId}…</div>}
      {error && <div className="error">Could not load this plant — {error}</div>}

      {!loading && !error && (
        <>
          <div className="legend">
            <span><i className="legend__swatch" style={{ background: "#3ddc97" }} /> sensor in band</span>
            <span><i className="legend__swatch" style={{ background: "#ffb454" }} /> sensor warning</span>
            <span><i className="legend__swatch" style={{ background: "#ff5d5d" }} /> sensor critical</span>
            <span><i className="legend__line" /> pipe (process)</span>
            <span><i className="legend__line legend__line--wire" /> wire (signal)</span>
            <span className="legend__note">Click a unit for actions · scroll to zoom · drag to pan</span>
          </div>

          <div className="workspace workspace--view">
            <div className="workspace__center">
              <Canvas mode="view" />
              <ContextMenu onInject={inject} />
            </div>
            <div className="workspace__side">
              <InfoDrawer />
            </div>
          </div>

          <AgentTracePanel />
        </>
      )}
    </Shell>
  );
}
