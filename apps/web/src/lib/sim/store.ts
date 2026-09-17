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
  /** Advances only on task/plan-relevant events — gates the task refetch. */
  taskSignal: number;
  /** Transport health of the SSE subscription (never inferred from events). */
  stream: StreamStatus;
  /**
   * Which runtime this projection describes. Bumped on every
   * `simulation.started`, so an effect can tell that an incident it holds
   * belongs to a run that is already over.
   */
  runGeneration: number;
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
  taskSignal: 0,
  stream: { state: "connecting", attempts: 0 },
  /** Bumped on every `simulation.started`: identifies the live runtime. */
  runGeneration: 0,
};

/**
 * Live-stream liveness reconciliation.
 *
 * A `POST /reset` replaces a plant's runtime wholesale. The SSE generator
 * captures the runtime object when the connection opens, so a reset performed
 * by anything other than the page that owns the connection — the audit gate,
 * a second tab, another operator — orphans the open stream: it stays open,
 * reports no error, and goes permanently silent. The console then holds a
 * frozen event spine, so the backend has the incident while the client never
 * hears about it: the "Awaiting a fault / 0 lanes" failure.
 *
 * There is no in-band signal for this (the orphaned stream emits nothing), so
 * the store watches its own heartbeat instead. Once a live stream has been
 * quiet for `STREAM_STALL_MS` while the plant should be running, it reads the
 * backend's own frame; if that frame proves the stream describes a runtime
 * that no longer exists, it reopens the subscription from seq 0 and forgets
 * the dead projection. The read happens only while quiet, so a healthy stream
 * costs no extra traffic.
 */
const STREAM_STALL_MS = 2000;
const STREAM_RECONCILE_MS = 800;

/**
 * The incident the console should be acting on: the NEWEST one that is not
 * over. `find` would return the oldest, so an incident that never resolved
 * (say, a model that was unavailable) would silently swallow every incident
 * after it and the next fault would never raise its own decision.
 */
function newestUnresolved(list: Incident[]): Incident | null {
  for (let i = list.length - 1; i >= 0; i -= 1) {
    const s = list[i].status;
    if (s !== "resolved" && s !== "escalated") return list[i];
  }
  return null;
}

export function useSimulation(plantId: string | null, adapter: SimAdapter = simAdapter) {
  const [state, setState] = useState<SimUIState>(EMPTY);
  const eventsRef = useRef<SimEvent[]>([]);
  /**
   * Every incident the live stream has announced this session, keyed by id.
   *
   * Incidents are accumulated here rather than re-derived from the event ring
   * buffer: the buffer is capped, so an incident's `incident.created` beat can
   * be evicted while the incident is still open — and two faults in a row must
   * never collapse into one. This keeps each incident (and therefore each
   * incident's decision) addressable for the whole session.
   */
  const incidentsRef = useRef<Map<string, Incident>>(new Map());
  /**
   * Incidents announced since the CURRENT runtime booted.
   *
   * The console resets the plant on every load and a reset replaces the runtime
   * wholesale, so an incident from the previous runtime is not addressable —
   * `GET /incidents/{id}/tasks` answers 404 and the browser logs a failed
   * request on a page that is otherwise healthy. Tracking membership per runtime
   * is what lets the task refetch below ask only for incidents that exist.
   */
  const currentRunIncidentsRef = useRef<Set<string>>(new Set());
  /** The engine's clock, advanced by every `telemetry.batch` on the stream. */
  const engineClockRef = useRef(0);
  /** How many incidents are still open — part of the change signature. */
  const liveIncidentsRef = useRef(0);
  /**
   * A counter that only advances on TASK/PLAN-relevant events.
   *
   * The task/plan refetch below used to key off `events.length`, which grows on
   * *every* event — including `telemetry.batch`, which the engine emits once per
   * simulation tick (1 Hz) whether or not anything incident-related happened.
   * With an incident open that meant a REST `GET .../tasks` roughly once per
   * second for the whole life of the incident, racing the SSE stream that is
   * already delivering the same task records event-by-event.
   *
   * This advances only when something that can actually change the task list or
   * the plan arrives, so the refetch happens when it has a reason to.
   */
  const taskSignalRef = useRef(0);
  /**
   * Monotonic runtime generation. Incremented when a boot is observed, and
   * carried in the change signature so a boot is never swallowed by the
   * "nothing changed" guard.
   */
  const runGenerationRef = useRef(0);
  /** The last published projection signature. */
  const lastSignature = useRef("");
  /** Wall-clock time of the last frame the stream delivered (liveness probe). */
  const lastEventAtRef = useRef(0);
  /**
   * Whether the live runtime is expected to be emitting telemetry. Set by the
   * lifecycle beats themselves, so a genuinely paused plant is never mistaken
   * for a stalled stream.
   */
  const runningRef = useRef(false);
  /**
   * Latest transport status, mirrored outside the state updater so the change
   * signature can include it without an updater side effect.
   */
  const streamRef = useRef<StreamStatus>(EMPTY.stream);
  const rafRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!plantId) return;
    let disposed = false;

    const sync = async () => {
      const eng: SimEngine | undefined =
        adapter.transport === "embedded" ? (adapter as unknown as { engine: (id: string) => SimEngine }).engine(plantId) : undefined;

      /**
       * Forget the projection of a runtime that is over.
       *
       * A reset replaces the runtime wholesale and its event log restarts at
       * seq 1. Two things must be forgotten, or the client keeps describing a
       * plant that no longer exists:
       *
       *  * the incident projection, because an incident from the previous run is
       *    not in the new runtime, so polling `/incidents/{id}/tasks` for it
       *    answers 404 and the browser logs a failed request on a page that is
       *    otherwise perfectly healthy; and
       *  * the dedupe high-water mark (`eventsRef`), because the new log's seq
       *    numbers are lower than the old ones and the guard below would silently
       *    discard every event of the new run.
       */
      const resetProjection = () => {
        eventsRef.current = [];
        incidentsRef.current = new Map();
        currentRunIncidentsRef.current = new Set();
        liveIncidentsRef.current = 0;
        lastSignature.current = "";
        runGenerationRef.current += 1;
      };

      /**
       * Open the one live subscription for this plant.
       *
       * This is re-runnable on purpose: a runtime swap orphans the previous
       * connection (see `reopenStream`), so the store must be able to close it
       * and open a fresh one without re-running the whole effect.
       */
      const connect = () => adapter.subscribe(
        plantId,
        (ev) => {
          if (disposed) return;
          lastEventAtRef.current = Date.now();
          if (ev.type === "simulation.started") {
            resetProjection();
            runningRef.current = true;
          }
          if (ev.type === "simulation.paused") runningRef.current = false;
          // The stream's telemetry batch is the engine's heartbeat: one per
          // simulation tick, carrying the tick's own timestamp.
          if (ev.type === "telemetry.batch") {
            runningRef.current = true;
            const tick = (ev.payload as Record<string, unknown>).t;
            if (typeof tick === "number") engineClockRef.current = tick;
          }
          // Reconnects replay from the last seen seq, so this should never
          // duplicate; the guard makes that a guarantee rather than a hope.
          //
          // A seq that goes BACKWARDS is not a duplicate: it is the signature of
          // a new runtime (its log restarts at 1) whose `simulation.started` beat
          // never arrived — exactly what a reconnect with a stale `after` cursor
          // produces. Treating that as a duplicate discarded every event of the
          // new run; treating it as a new run keeps the incident visible.
          const last = eventsRef.current[eventsRef.current.length - 1];
          if (last) {
            if (ev.seq === last.seq) return;
            if (ev.seq < last.seq) resetProjection();
          }
          eventsRef.current = [...eventsRef.current.slice(-1199), ev];
          // Only these can change the task list or the plan.
          if (ev.type.startsWith("agent.task_") || ev.type === "response.decision" || ev.type === "response.plan") {
            taskSignalRef.current += 1;
          }
          // Operational milestones become organizational memory; the adapter
          // filters out agent.task_* chatter so history cannot be flooded.
          if (ev.type.startsWith("incident.")) {
            const inc = ev.payload as unknown as Incident;
            if (inc?.id) {
              incidentsRef.current.set(inc.id, inc);
              currentRunIncidentsRef.current.add(inc.id);
            }
            liveIncidentsRef.current = [...incidentsRef.current.values()].filter(
              (i) => i.status !== "resolved" && i.status !== "escalated",
            ).length;
          }
          consoleData.history.record(ev);
        },
        (status) => {
          if (disposed) return;
          streamRef.current = status;
          setState((prev) =>
            prev.stream.state === status.state &&
            prev.stream.attempts === status.attempts &&
            prev.stream.detail === status.detail
              ? prev
              : { ...prev, stream: status },
          );
        },
      );

      /**
       * Projection of engine truth into React.
       *
       * This runs at 4 Hz so the UI can never lag the engine by much, but it only
       * **publishes** when something actually changed. It used to return a fresh
       * object every 250 ms unconditionally, which re-rendered every subscriber
       * (and with them the plant drawing and the whole console tree) four times a
       * second even on a plant where nothing was happening — measured at ~77 DOM
       * mutations per second on an idle live page.
       *
       * The signature is cheap on purpose: the engine clock, the incident set,
       * the event count, the task/plan identity and the alarm count. If none of
       * them moved, the projection is identical and React is told so by returning
       * the previous state object.
       */
      const publish = () => {
        if (disposed) return;
        /**
         * The change signature is computed **outside** the state updater.
         *
         * It used to be computed inside, and the updater recorded it and then
         * early-returned `prev` when it matched. React is allowed to invoke an
         * updater more than once (it eagerly computes one, and it replays queued
         * updates during render). On the second call the updater read the
         * signature it had just written and returned the stale `prev` — which
         * overwrote the real projection, while the recorded signature made every
         * later publish skip as well. That is the intermittent freeze where the
         * backend has the incident and the console sits at 0 lanes: an event
         * projection is computed once, discarded, and never published again.
         *
         * An updater must be a pure function of its arguments, so the dedup
         * lives here and the updater below only builds the next state.
         */
        const clock = eng ? eng.t : engineClockRef.current;
        const signature = [
          clock,
          eventsRef.current.length,
          incidentsRef.current.size,
          liveIncidentsRef.current,
          eng ? eng.alarms.size : 0,
          taskSignalRef.current,
          runGenerationRef.current,
          streamRef.current.state,
        ].join("|");
        if (signature === lastSignature.current) return;
        lastSignature.current = signature;
        setState((prev) => {
          if (eng) {
            const incidents = [...eng.incidents.values()];
            const active = newestUnresolved(incidents);
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
              taskSignal: taskSignalRef.current,
              stream: prev.stream,
              runGeneration: runGenerationRef.current,
            };
          }
          // live mode: rebuild projection from the incident map + event log
          const list = [...incidentsRef.current.values()];
          const active = newestUnresolved(list);
          return {
            ...prev,
            // The engine's own clock, from the `telemetry.batch` the stream
            // delivers once per simulation tick.
            //
            // This used to be left at its initial 0 in live mode, so nothing
            // downstream could tell one engine tick from the next: a consumer
            // that wanted "refresh when the plant actually changes" had only the
            // 4 Hz `tick` counter to depend on, and polled four times for every
            // tick — three of those replies identical. `t` now advances at the
            // engine's rate, which is the rate at which anything can change.
            t: engineClockRef.current,
            running: true,
            events: eventsRef.current,
            incidents: list,
            activeIncident: active,
            tick: prev.tick + 1,
            taskSignal: taskSignalRef.current,
            runGeneration: runGenerationRef.current,
          };
        });
      };
      rafRef.current = setInterval(() => {
        if (disposed) return;
        publish();
      }, 250);

      let unsubscribe = connect();

      /**
       * Replace a stream that is no longer the live one.
       *
       * The old connection is closed outright (the adapter's `closed` flag also
       * stops its retry loop), the dead projection is dropped, and a fresh
       * subscription opens with an empty replay cursor so the CURRENT runtime's
       * whole log is delivered from seq 1 — including the `simulation.started`
       * its predecessor never saw.
       */
      const reopenStream = () => {
        if (disposed) return;
        unsubscribe();
        resetProjection();
        engineClockRef.current = 0;
        lastEventAtRef.current = Date.now();
        unsubscribe = connect();
      };

      /**
       * Liveness reconciliation — see `STREAM_STALL_MS`.
       *
       * Only a live transport can be orphaned by a server-side reset, and only a
       * stream that has gone quiet is worth probing: a healthy stream advances
       * `lastEventAtRef` once per tick and never reaches the read.
       */
      let reconciling = false;
      const reconcile = () => {
        if (disposed || reconciling) return;
        if (adapter.transport !== "live") return;
        if (!runningRef.current) return;
        if (Date.now() - lastEventAtRef.current < STREAM_STALL_MS) return;
        reconciling = true;
        adapter
          .frame(plantId)
          .then((res) => {
            if (disposed) return;
            const backendT = typeof res.t === "number" ? res.t : 0;
            // A live incident the stream has not announced for THIS run.
            //
            // Incident ids restart at INC-1001 on every reset, so a stored copy
            // that is already terminal while the backend reports the same id
            // live belongs to a runtime this store has not seen — which is a
            // swap just as surely as a missing id is.
            const unknownLive = (res.incidents ?? []).some((i) => {
              if (!i?.id || i.status === "resolved" || i.status === "escalated") return false;
              const known = incidentsRef.current.get(i.id);
              if (!known) return true;
              return known.status === "resolved" || known.status === "escalated";
            });
            // The backend's clock is behind ours: the runtime was replaced.
            const clockRegressed = backendT + 0.5 < engineClockRef.current;
            // The backend is running and ahead of us: telemetry is not arriving.
            const backendAhead = Boolean(res.running) && backendT > engineClockRef.current + 1.5;
            if (unknownLive || clockRegressed || backendAhead) reopenStream();
          })
          .catch(() => undefined)
          .finally(() => {
            reconciling = false;
          });
      };
      const reconcileTimer = setInterval(reconcile, STREAM_RECONCILE_MS);

      return () => {
        unsubscribe();
        clearInterval(reconcileTimer);
      };
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
      incidentsRef.current = new Map();
    };
  }, [plantId, adapter]);

  // Refresh tasks/plan when the incident changes, or when a task/plan-relevant
  // event actually arrives — NOT on every event. See `taskSignalRef`.
  //
  // The state holds the signal so the effect can depend on a value rather than a
  // ref; it rides along in the change signature so a task event still republishes.
  const activeId = state.activeIncident?.id;
  const taskSignal = state.taskSignal;
  const runGeneration = state.runGeneration;
  useEffect(() => {
    if (!plantId || !activeId) return;
    if (adapter.transport !== "embedded") {
      // Only incidents this runtime announced are addressable. A bundle rebuilt
      // after the server reset answers 404 for the rest, which is noise on an
      // otherwise healthy page.
      if (!currentRunIncidentsRef.current.has(activeId)) return;
      adapter
        .tasks(plantId, activeId)
        .then(({ tasks, plan }) => setState((p) => ({ ...p, tasks, plan })))
        .catch(() => undefined);
    }
  }, [plantId, activeId, taskSignal, adapter, runGeneration]);

  return state;
}
