"use client";

/**
 * Network Sentinel — the live allow/block stream, isolated so the page can
 * lazy-load it.
 *
 * Two rules drive the whole component:
 *
 *  1. **The subscription lives exactly as long as the mount.** `EventSource` is
 *     opened in an effect and closed in that effect's cleanup, so navigating
 *     away tears the connection down. Nothing here is started globally: a
 *     security stream that runs on every page is a connection nobody asked for
 *     and a queue leaked per visit.
 *  2. **Every field is the backend's, including the empty ones.** When nothing
 *     has been attempted the panel says so. It does not seed itself with a
 *     sample event, and a null `agent`/`task_id` renders as an explicit "—",
 *     not as a plausible name.
 */
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { NetworkConnectionAttempt } from "@/lib/api";
import { EmptyState, StatusDot, Tag, timeAgo } from "@/components/ui/primitives";

/** How many events to keep in view. Bounded, so a long session cannot grow. */
const MAX_ROWS = 60;

type ConnectionState = "connecting" | "live" | "lost";

export function SentinelStreamPanel() {
  const [events, setEvents] = useState<NetworkConnectionAttempt[]>([]);
  const [state, setState] = useState<ConnectionState>("connecting");
  /** True once the stream has been open at least once: distinguishes
   *  "no attempts yet" from "not connected yet". */
  const [attached, setAttached] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    let alive = true;
    const source = new EventSource(api.network.streamUrl());
    sourceRef.current = source;

    source.onopen = () => {
      if (!alive) return;
      setState("live");
      setAttached(true);
    };

    // Named event, matching the server's `event: network.connection_attempt`.
    source.addEventListener("network.connection_attempt", (raw) => {
      if (!alive) return;
      try {
        const parsed = JSON.parse((raw as MessageEvent).data) as NetworkConnectionAttempt;
        setEvents((prev) => [parsed, ...prev].slice(0, MAX_ROWS));
        setAttached(true);
      } catch {
        // A malformed frame is dropped rather than rendered as a fake event.
      }
    });

    source.onerror = () => {
      if (!alive) return;
      // EventSource reconnects on its own. Say so rather than silently
      // continuing to display a stale list as though it were live.
      setState((prev) => (prev === "live" ? "lost" : "connecting"));
    };

    return () => {
      // The cleanup that makes rule 1 true.
      alive = false;
      source.close();
      sourceRef.current = null;
    };
  }, []);

  const blocked = events.filter((e) => e.action === "BLOCK").length;
  const allowed = events.filter((e) => e.action === "ALLOW").length;

  return (
    <div className="cs-stack" data-testid="network-sentinel">
      <div className="cs-row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <div className="cs-row" style={{ gap: 10 }}>
          <StatusDot state={state === "live" ? "ok" : state === "lost" ? "warning" : "unknown"} />
          <span className="cs-mono" style={{ fontSize: 11, letterSpacing: "0.16em", textTransform: "uppercase" }}>
            {state === "live" ? "subscribed" : state === "lost" ? "reconnecting" : "connecting"}
          </span>
        </div>
        <div className="cs-row" style={{ gap: 8 }}>
          <Tag tone="bad">{blocked} blocked</Tag>
          <Tag tone="ok">{allowed} allowed</Tag>
        </div>
      </div>

      {events.length === 0 ? (
        <EmptyState
          title="No connection attempts observed"
          detail={
            attached
              ? "The stream is subscribed and has seen nothing. Every outbound request passes the egress guard, so an empty list is a real measurement — not a placeholder."
              : "Opening the sentinel stream. If it does not attach, the backend SSE endpoint is unreachable."
          }
        />
      ) : (
        <div style={{ maxHeight: 340, overflowY: "auto", overscrollBehavior: "contain" }}>
          <table className="cs-table">
            <thead>
              <tr>
                <th>When</th>
                <th>Destination</th>
                <th>Port</th>
                <th>Source</th>
                <th>Process</th>
                <th>Agent</th>
                <th>Task</th>
                <th>Decision</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event, index) => (
                <tr key={`${event.timestamp}-${event.destination}-${index}`}>
                  <td className="cs-mono" title={event.timestamp}>{timeAgo(event.timestamp)}</td>
                  <td className="cs-mono">
                    {event.destination ?? "—"}
                    {event.local && <span className="cs-dim"> · loopback</span>}
                  </td>
                  <td className="cs-mono">{event.port ?? "—"}</td>
                  <td className="cs-mono">{event.source ?? "—"}</td>
                  <td className="cs-mono">{event.process ?? "—"}</td>
                  {/* Unknown is unknown: these two are null outside a task
                      context and are shown as such rather than guessed. */}
                  <td className="cs-mono">{event.agent ?? "—"}</td>
                  <td className="cs-mono">{event.task_id ?? "—"}</td>
                  <td>
                    <Tag tone={event.action === "BLOCK" ? "bad" : "ok"}>{event.action}</Tag>
                  </td>
                  <td className="cs-dim">{event.reason ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {state === "lost" && (
        <p className="cs-dim" style={{ margin: 0, fontSize: 12 }}>
          The stream dropped and is reconnecting. Rows below are the last events
          received, not a live view.
        </p>
      )}
    </div>
  );
}
