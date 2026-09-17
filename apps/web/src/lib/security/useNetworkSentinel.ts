"use client";

/**
 * The Network Sentinel subscription, owned by the page that needs it.
 *
 * This is deliberately the same pattern `SentinelStreamPanel` already uses, and
 * deliberately not a global: `EventSource` is opened in an effect and closed in
 * that effect's cleanup, so navigating away tears the connection down. A
 * security stream that runs on every page is a connection nobody asked for, a
 * backend subscriber queue leaked per visit, and — worse — a page that could
 * imply live observation when nothing is being observed.
 *
 * The hook returns the frames it actually received. It never invents one, never
 * seeds a sample, and reports `attached` separately from `events` so "the stream
 * is open and has seen nothing" stays distinguishable from "not connected yet".
 */
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { NetworkConnectionAttempt } from "@/lib/api";

/** Bounded, so a long session cannot grow the panel without limit. */
const MAX_ROWS = 60;

export type SentinelState = "connecting" | "live" | "lost";

export interface NetworkSentinel {
  state: SentinelState;
  /** True once the stream has opened at least once. */
  attached: boolean;
  /** Newest first, bounded. */
  events: NetworkConnectionAttempt[];
  /** The newest frame, or null when nothing has arrived. */
  lastEvent: NetworkConnectionAttempt | null;
  /** Increments on every frame, so a repeat of the same destination re-fires. */
  lastSeq: number;
}

export function useNetworkSentinel(): NetworkSentinel {
  const [events, setEvents] = useState<NetworkConnectionAttempt[]>([]);
  const [state, setState] = useState<SentinelState>("connecting");
  const [attached, setAttached] = useState(false);
  const [lastEvent, setLastEvent] = useState<NetworkConnectionAttempt | null>(null);
  const [lastSeq, setLastSeq] = useState(0);
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

    source.addEventListener("network.connection_attempt", (raw) => {
      if (!alive) return;
      try {
        const parsed = JSON.parse((raw as MessageEvent).data) as NetworkConnectionAttempt;
        setEvents((prev) => [parsed, ...prev].slice(0, MAX_ROWS));
        setLastEvent(parsed);
        setLastSeq((n) => n + 1);
        setAttached(true);
      } catch {
        // A malformed frame is dropped rather than rendered as a fake event.
      }
    });

    source.onerror = () => {
      if (!alive) return;
      // EventSource reconnects on its own; say so rather than showing a stale
      // list as though it were live.
      setState((prev) => (prev === "live" ? "lost" : "connecting"));
    };

    return () => {
      alive = false;
      source.close();
      sourceRef.current = null;
    };
  }, []);

  return { state, attached, events, lastEvent, lastSeq };
}
