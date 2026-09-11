/**
 * Central real-time client. One socket, one typed emitter.
 *
 * Components never touch this directly — hooks (`useAgentEvents`,
 * `useTelemetry`, ...) subscribe to topics and write into zustand stores.
 * In mock mode no socket is opened; the mock adapter drives the same emitter
 * with the demo inspection-investigation timeline.
 */
import type { ServerEvent } from "@/types";

type Listener = (event: ServerEvent) => void;

class EventBus {
  private listeners = new Map<string, Set<Listener>>();
  private anyListeners = new Set<Listener>();

  on(topic: string, listener: Listener): () => void {
    if (!this.listeners.has(topic)) this.listeners.set(topic, new Set());
    this.listeners.get(topic)!.add(listener);
    return () => this.listeners.get(topic)?.delete(listener);
  }

  onAny(listener: Listener): () => void {
    this.anyListeners.add(listener);
    return () => this.anyListeners.delete(listener);
  }

  emit(event: ServerEvent): void {
    this.listeners.get(event.type)?.forEach((l) => l(event));
    this.listeners.get("*")?.forEach((l) => l(event));
    this.anyListeners.forEach((l) => l(event));
  }
}

export const bus = new EventBus();

export type ConnectionState = "connecting" | "open" | "closed" | "mock";

let socket: WebSocket | null = null;
let state: ConnectionState = "closed";
let retryMs = 1000;
const stateListeners = new Set<(s: ConnectionState) => void>();

export function connectionState(): ConnectionState {
  return state;
}

export function onConnectionStateChange(listener: (s: ConnectionState) => void): () => void {
  stateListeners.add(listener);
  return () => stateListeners.delete(listener);
}

function setState(next: ConnectionState): void {
  state = next;
  stateListeners.forEach((l) => l(next));
}

export function connect(): void {
  if (process.env.NEXT_PUBLIC_DATA_MODE === "mock") {
    setState("mock");
    return;
  }
  if (socket && socket.readyState <= WebSocket.OPEN) return;
  setState("connecting");
  try {
    socket = new WebSocket(process.env.NEXT_PUBLIC_WS_URL!);
  } catch {
    setState("closed");
    return;
  }
  socket.onopen = () => {
    retryMs = 1000;
    setState("open");
  };
  socket.onmessage = (msg) => {
    try {
      bus.emit(JSON.parse(msg.data) as ServerEvent);
    } catch {
      /* malformed frame — ignore */
    }
  };
  socket.onclose = () => {
    setState("closed");
    // Exponential backoff, capped at 15s. An air-gapped LAN reconnect is fast.
    setTimeout(connect, retryMs);
    retryMs = Math.min(retryMs * 2, 15000);
  };
}

export function disconnect(): void {
  socket?.close();
  socket = null;
  setState("closed");
}
