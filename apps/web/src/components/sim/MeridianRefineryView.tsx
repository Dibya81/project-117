"use client";

import { useState } from "react";
import Image from "next/image";
import { Icon } from "@/components/ui/Icon";
import { MeridianRefineryCanvas } from "@/components/sim/MeridianRefineryCanvas";
import type { TopologyRecoveryDecision } from "@/components/sim/MeridianRefineryCanvas";
import type { AgentTask, EquipmentDef, PlantDef } from "@/lib/sim/types";
import type { CanvasRuntime, SpatialReading } from "@/components/sim/SchematicCanvas";

export function MeridianRefineryView({
  plant,
  runtime,
  readings,
  selected,
  onSelectEquipment,
  viewMode = "overview",
  onViewModeChange,
  failover = null,
  activeIncident = null,
  tasks = [],
  models = {},
  recoveryDecision = null,
}: {
  plant: PlantDef;
  runtime: CanvasRuntime | null;
  readings: Record<string, SpatialReading>;
  selected: EquipmentDef | null;
  onSelectEquipment: (eq: EquipmentDef) => void;
  viewMode?: "overview" | "3d" | "pid";
  onViewModeChange?: (mode: "overview" | "3d" | "pid") => void;
  failover?: { from: string; to: string } | null;
  activeIncident?: any;
  tasks?: AgentTask[];
  models?: Record<string, string | null>;
  recoveryDecision?: TopologyRecoveryDecision | null;
}) {
  const [fullscreen, setFullscreen] = useState(false);

  return (
    <div className={`mr-schematic-wrapper${fullscreen ? " is-fullscreen" : ""}`}>
      {/* Schematic Top Action Bar */}
      <div className="mr-schematic-head" style={{ justifyContent: "flex-end" }}>
        {/* View Mode Switchers */}
        <div className="mr-view-controls">
          <button
            type="button"
            className={`mr-view-btn ${viewMode === "overview" ? "is-active" : ""}`}
            onClick={() => onViewModeChange?.("overview")}
          >
            <Icon name="graph" size={13} />
            <span>Plant Overview</span>
          </button>
          <button
            type="button"
            className={`mr-view-btn ${viewMode === "3d" ? "is-active" : ""}`}
            onClick={() => onViewModeChange?.("3d")}
          >
            <Icon name="layers" size={13} />
            <span>3D View</span>
          </button>
          <button
            type="button"
            className={`mr-view-btn ${viewMode === "pid" ? "is-active" : ""}`}
            onClick={() => onViewModeChange?.("pid")}
          >
            <Icon name="workflow" size={13} />
            <span>P&amp;ID</span>
          </button>
          <button
            type="button"
            className="mr-view-btn mr-view-btn--icon"
            onClick={() => setFullscreen(!fullscreen)}
            title={fullscreen ? "Exit Fullscreen" : "Fullscreen"}
          >
            <Icon name={fullscreen ? "x" : "eye"} size={13} />
          </button>
        </div>
      </div>

      {/* Main Canvas Area */}
      <div className="mr-canvas-stage">
        {viewMode === "3d" ? (
          /* 3D ISOMETRIC TWIN VIEW */
          <div
            className="mr-3d-view-stage"
            style={{
              position: "relative",
              width: "100%",
              height: "100%",
              minHeight: 640,
              background: "#06090e",
              overflow: "hidden",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <div style={{ position: "absolute", inset: 0, opacity: 0.85 }}>
              <Image
                src="/assets/refinery/fcc_unit_c201.jpg"
                alt="3D Digital Twin Cutaway"
                fill
                priority
                style={{ objectFit: "cover" }}
              />
            </div>
            {/* Hologram Grid Overlay */}
            <div
              style={{
                position: "absolute",
                inset: 0,
                backgroundImage:
                  "radial-gradient(circle at center, rgba(6,182,212,0.12) 0%, rgba(6,9,14,0.85) 100%)",
                pointerEvents: "none",
              }}
            />

            {/* 3D Model HUD Callouts */}
            <div
              style={{
                position: "absolute",
                left: 32,
                top: 32,
                zIndex: 10,
                background: "rgba(10,16,24,0.85)",
                backdropFilter: "blur(12px)",
                border: "1px solid rgba(6,182,212,0.3)",
                borderRadius: 8,
                padding: "16px 20px",
                maxWidth: 340,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    background: "#06b6d4",
                    boxShadow: "0 0 8px #06b6d4",
                  }}
                />
                <span
                  style={{
                    fontSize: 11,
                    fontFamily: "var(--font-mono, monospace)",
                    color: "#06b6d4",
                    textTransform: "uppercase",
                    letterSpacing: "0.15em",
                  }}
                >
                  3D Digital Twin
                </span>
              </div>
              <h3 style={{ margin: "0 0 6px", fontSize: 18, color: "#fff", fontWeight: 600 }}>
                FCC Unit C-201
              </h3>
              <p style={{ margin: "0 0 12px", fontSize: 12, color: "rgba(255,255,255,0.7)", lineHeight: 1.5 }}>
                Fluid Catalytic Cracking unit with continuous catalyst regeneration and multi-cyclone separator.
              </p>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: 8,
                  fontSize: 11,
                  fontFamily: "var(--font-mono, monospace)",
                }}
              >
                <div style={{ background: "rgba(255,255,255,0.04)", padding: "6px 8px", borderRadius: 4 }}>
                  <div style={{ color: "rgba(255,255,255,0.4)" }}>BED TEMP</div>
                  <div style={{ color: "#06b6d4", fontSize: 13, fontWeight: 600 }}>520.4 °C</div>
                </div>
                <div style={{ background: "rgba(255,255,255,0.04)", padding: "6px 8px", borderRadius: 4 }}>
                  <div style={{ color: "rgba(255,255,255,0.4)" }}>PRESSURE</div>
                  <div style={{ color: "#10b981", fontSize: 13, fontWeight: 600 }}>1.82 bar</div>
                </div>
                <div style={{ background: "rgba(255,255,255,0.04)", padding: "6px 8px", borderRadius: 4 }}>
                  <div style={{ color: "rgba(255,255,255,0.4)" }}>FEED RATE</div>
                  <div style={{ color: "#f97316", fontSize: 13, fontWeight: 600 }}>18,200 bpd</div>
                </div>
                <div style={{ background: "rgba(255,255,255,0.04)", padding: "6px 8px", borderRadius: 4 }}>
                  <div style={{ color: "rgba(255,255,255,0.4)" }}>CATALYST</div>
                  <div style={{ color: "#a855f7", fontSize: 13, fontWeight: 600 }}>98.4% ACT</div>
                </div>
              </div>
            </div>

            {/* Return to Plant Overview button */}
            <div style={{ position: "absolute", bottom: 24, right: 24, zIndex: 10 }}>
              <button
                type="button"
                className="mr-view-btn is-active"
                style={{ padding: "8px 16px", borderRadius: 6 }}
                onClick={() => onViewModeChange?.("overview")}
              >
                <Icon name="graph" size={13} />
                <span>Return to Plant Overview</span>
              </button>
            </div>
          </div>
        ) : (
          /* REAL INTERACTIVE VECTOR DIGITAL TWIN */
          <MeridianRefineryCanvas
            plant={plant}
            runtime={runtime}
            readings={readings}
            selected={selected}
            onSelectEquipment={onSelectEquipment}
            failover={failover}
            activeIncident={activeIncident}
            tasks={tasks}
            models={models}
            recoveryDecision={recoveryDecision}
          />
        )}
      </div>
    </div>
  );
}
