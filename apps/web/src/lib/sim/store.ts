"use client";

/**
 * Sim store — the React bridge over the event stream.
 * Events accumulate in a ring buffer; component state syncs at 4 Hz max,
 * regardless of tick volume. The engine is the truth; this is a projection.
 */
import { useEffect, useRef, useState } from "react";
import { simAdapter, type SimAdapter, type StreamStatus } from "./adapter";
import { consoleData } from "@/lib/data/console";
import type { SimEngine } from "./engine";
import type { AgentTask, Incident, IncidentPlan, SimEvent } from "./types";

export interface SimUIState {
  t: number;
  running: boolean;
  events: SimEvent[];
  incidents: Incident[];
  activeIncident: Incident | null;
  tasks: AgentTask[];
  plan: IncidentPlan | null;
  alarms: number;
  tick: number; // bumps to re-render live values
  /** Transport health of the SSE subscription (never inferred from events). */
  stream: StreamStatus;
}

const EMPTY: SimUIState = {
  t: 0,
  running: false,
  events: [],
  incidents: [],
  activeIncident: null,
  tasks: [],
  plan: null,
  alarms: 0,
  tick: 0,
  stream: { state: "connecting", attempts: 0 },
};

export function useSimulation(plantId: string | null, adapter: SimAdapter = simAdapter) {
  const [state, setState] = useState<SimUIState>(EMPTY);
  const eventsRef = useRef<SimEvent[]>([]);
  const rafRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!plantId) return;
    let disposed = false;

    const sync = async () => {
      const eng: SimEngine | undefined =
        adapter.transport === "embedded" ? (adapter as unknown as { engine: (id: string) => SimEngine }).engine(plantId) : undefined;

      const unsubscribe = adapter.subscribe(
        plantId,
        (ev) => {
          if (disposed) return;
          // Reconnects replay from the last seen seq, so this should never
          // duplicate; the guard makes that a guarantee rather than a hope.
          const last = eventsRef.current[eventsRef.current.length - 1];
          if (last && ev.seq <= last.seq) return;
          eventsRef.current = [...eventsRef.current.slice(-400), ev];
          // Operational milestones become organizational memory; the adapter
          // filters out agent.task_* chatter so history cannot be flooded.
          consoleData.history.record(ev);
        },
        (status) => {
          if (disposed) return;
          setState((prev) =>
            prev.stream.state === status.state &&
            prev.stream.attempts === status.attempts &&
            prev.stream.detail === status.detail
              ? prev
              : { ...prev, stream: status },
          );
        },
      );

      // 4 Hz projection of engine truth into React
      rafRef.current = setInterval(() => {
        if (disposed) return;
        setState((prev) => {
          if (eng) {
            const incidents = [...eng.incidents.values()];
            const active = incidents.find((i) => i.status !== "resolved" && i.status !== "escalated") ?? null;
            return {
              t: eng.t,
              running: true,
              events: eventsRef.current,
              incidents,
              activeIncident: active,
              tasks: active ? eng.tasks.get(active.id) ?? [] : active ? [] : prev.tasks,
              plan: active ? eng.plans.get(active.id) ?? null : null,
              alarms: eng.alarms.size,
              tick: prev.tick + 1,
              stream: prev.stream,
            };
          }
          // live mode: rebuild projection from the event log + snapshot polling
          const incidents = eventsRef.current
            .filter((e) => e.type.startsWith("incident."))
            .reduce((map, e) => {
              const p = e.payload as unknown as Incident;
              if (p?.id) map.set(p.id, p);
              return map;
            }, new Map<string, Incident>());
          const list = [...incidents.values()];
          const active = list.find((i) => i.status !== "resolved" && i.status !== "escalated") ?? null;
          return {
            ...prev,
            running: true,
            events: eventsRef.current,
            incidents: list,
            activeIncident: active,
            tick: prev.tick + 1,
          };
        });
      }, 250);

      return unsubscribe;
    };

    let unsub: (() => void) | undefined;
    void sync().then((u) => {
      if (disposed) u?.();
      else unsub = u;
    });

    return () => {
      disposed = true;
      unsub?.();
      if (rafRef.current) clearInterval(rafRef.current);
      eventsRef.current = [];
    };
  }, [plantId, adapter]);

  // refresh tasks/plan when the active incident changes or tasks stream in
  const activeId = state.activeIncident?.id;
  const eventCount = state.events.length;
  useEffect(() => {
    if (!plantId || !activeId) return;
    if (adapter.transport !== "embedded") {
      adapter
        .tasks(plantId, activeId)
        .then(({ tasks, plan }) => setState((p) => ({ ...p, tasks, plan })))
        .catch(() => undefined);
    }
  }, [plantId, activeId, eventCount, adapter]);

  return state;
}
