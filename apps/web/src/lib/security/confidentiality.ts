/**
 * Confidentiality architecture model — `/console/security/confidentiality`.
 *
 * This module holds **no state and no UI**: it maps the payloads the backend
 * already returns onto the nodes of the data-flow diagram, so the diagram
 * cannot show a status the backend did not measure.
 *
 * The governing rule, stated once and applied everywhere below:
 *
 *  * When the backend has a verdict for a capability
 *    (`GET /api/security/sovereignty` returns `VERIFIED / IMPLEMENTED /
 *    PARTIAL / NOT AVAILABLE` per entry), the node shows *that* verdict,
 *    verbatim. The frontend never upgrades one.
 *  * When a node spans several capabilities, its state is the weakest of the
 *    parts it spans, and the detail names both parts and their own verdicts.
 *  * A node is `VERIFIED` only when a probe answered. `IMPLEMENTED` is amber:
 *    the capability exists and is wired but this process has no positive
 *    evidence for it. `UNAVAILABLE` is red. `PLANNED` is grey — not built,
 *    which is different from built-and-broken.
 *
 * Two consequences the brief calls out explicitly, and which are enforced by
 * the data rather than by a comment:
 *
 *  * `SANDBOX` reads `UNAVAILABLE` because OpenSandbox is not running here, so
 *    the node can never render a green "isolated" tick.
 *  * Artifact signing reads `IMPLEMENTED` with `0 signed` while no artifact has
 *    been signed end-to-end on this host — it is not `VERIFIED`.
 */
import type {
  ArtifactSignatures,
  AuditIntegrity,
  CallerIdentity,
  ModelsStatus,
  SecurityEvents,
  SovereigntyEntry,
  SovereigntyState,
  SovereigntyStatus,
} from "@/lib/api";
import type { AgentDescriptor, HealthResponse, HealthState } from "@/types";

/** The status vocabulary the diagram is allowed to print. */
export type NodeStatus =
  | "VERIFIED"
  | "IMPLEMENTED"
  | "PARTIAL"
  | "NOT VERIFIED"
  | "PLANNED"
  | "UNAVAILABLE";

/** Grouping for the five ordered zones inside the security boundary. */
export type ZoneId = "input" | "processing" | "execution" | "verification" | "output";

export interface Zone {
  id: ZoneId;
  index: number;
  title: string;
  caption: string;
}

export const ZONES: Zone[] = [
  {
    id: "input",
    index: 1,
    title: "Confidential Input",
    caption: "Where the plant's own data enters, and the first gate it meets.",
  },
  {
    id: "processing",
    index: 2,
    title: "Local AI Processing",
    caption: "Retrieval, routing and agents — all on this machine.",
  },
  {
    id: "execution",
    index: 3,
    title: "Controlled Execution",
    caption: "The only place code or tools could run, and what actually stops them.",
  },
  {
    id: "verification",
    index: 4,
    title: "Verification",
    caption: "How a result is checked before anyone reads it.",
  },
  {
    id: "output",
    index: 5,
    title: "Output",
    caption: "What leaves the pipeline, signed and audited, or not.",
  },
];

/** One real count, or an explicit absence of one. Never a placeholder zero. */
export interface NodeCount {
  value: number | null;
  label: string;
}

export interface DiagramNode {
  id: string;
  title: string;
  /** One line, always visible: what this node does. */
  blurb: string;
  zone: ZoneId | "external" | "boundary";
  status: NodeStatus;
  /** The backend's own state string when it gave one (e.g. "NOT AVAILABLE"). */
  rawState?: string;
  count: NodeCount | null;
  /** Where the status came from, in the backend's words where possible. */
  detail: string;
  /** Real values for the drawer. */
  evidence: Record<string, unknown>;
  /** True for the node the live sentinel stream can animate. */
  live?: boolean;
}

/** Everything the diagram reads. All of it is fetched; none of it is mocked. */
export interface ConfidentialityFacts {
  sovereignty: SovereigntyStatus | null;
  models: ModelsStatus | null;
  integrity: AuditIntegrity | null;
  signatures: ArtifactSignatures | null;
  health: HealthResponse | null;
  identity: CallerIdentity | null;
  events: SecurityEvents | null;
  agents: AgentDescriptor[] | null;
}

/* ------------------------------------------------------------------ helpers */

function entry(status: SovereigntyStatus | null, key: string): SovereigntyEntry | null {
  return status?.status.find((e) => e.key === key) ?? null;
}

function capability(status: SovereigntyStatus | null, key: string): SovereigntyEntry | null {
  return status?.capabilities.find((e) => e.key === key) ?? null;
}

/**
 * The backend's state vocabulary mapped to the diagram's.
 *
 * `NOT AVAILABLE` becomes `UNAVAILABLE`; everything else is passed through so
 * the node and the Security Console say the same word.
 */
export function fromBackendState(state: SovereigntyState | string | undefined): NodeStatus {
  switch (state) {
    case "VERIFIED":
      return "VERIFIED";
    case "IMPLEMENTED":
      return "IMPLEMENTED";
    case "PARTIAL":
      return "PARTIAL";
    case "NOT AVAILABLE":
    case "UNAVAILABLE":
      return "UNAVAILABLE";
    default:
      return "NOT VERIFIED";
  }
}

/** Status → the shared status-dot tones. Amber is never a pass. */
export const STATUS_TONE: Record<NodeStatus, HealthState> = {
  VERIFIED: "ok",
  IMPLEMENTED: "warning",
  PARTIAL: "warning",
  "NOT VERIFIED": "unknown",
  PLANNED: "unknown",
  UNAVAILABLE: "critical",
};

/** Colour used by the diagram's own glyphs (matches the design tokens). */
export const STATUS_COLOUR: Record<NodeStatus, string> = {
  VERIFIED: "var(--ok, #16a34a)",
  IMPLEMENTED: "var(--warn, #d97706)",
  PARTIAL: "var(--warn, #d97706)",
  "NOT VERIFIED": "var(--ink-3, #64748b)",
  PLANNED: "var(--ink-3, #64748b)",
  UNAVAILABLE: "var(--crit, #dc2626)",
};

/** Weakest-wins, so a node spanning two capabilities cannot round up. */
const SEVERITY: Record<NodeStatus, number> = {
  VERIFIED: 0,
  IMPLEMENTED: 1,
  PARTIAL: 2,
  "NOT VERIFIED": 3,
  PLANNED: 4,
  UNAVAILABLE: 5,
};

function weakest(...states: NodeStatus[]): NodeStatus {
  return states.reduce((a, b) => (SEVERITY[b] > SEVERITY[a] ? b : a), "VERIFIED" as NodeStatus);
}

function modelsAssigned(models: ModelsStatus | null): number | null {
  if (!models) return null;
  return Object.values(models.roles ?? {}).filter((m) => m != null).length;
}

function modelsTotal(models: ModelsStatus | null): number | null {
  if (!models) return null;
  return Object.keys(models.roles ?? {}).length || null;
}

function servedModelCount(models: ModelsStatus | null): number | null {
  if (!models) return null;
  return Object.values(models.models ?? {}).reduce((n, list) => n + (list?.length ?? 0), 0);
}

/* ------------------------------------------------------------------- nodes */

/**
 * Build the diagram from the facts. Pure: same facts in, same nodes out, so
 * `useMemo` can hold object identity and a live event never re-renders a node
 * whose status did not change.
 */
export function buildNodes(facts: ConfidentialityFacts): DiagramNode[] {
  const { sovereignty, models, integrity, signatures, health, identity, events, agents } = facts;

  const localAi = entry(sovereignty, "local_ai");
  const egress = entry(sovereignty, "egress");
  const auditChain = entry(sovereignty, "audit_chain");
  const signing = entry(sovereignty, "signing");
  const rbac = entry(sovereignty, "rbac");
  const clearance = entry(sovereignty, "clearance");
  const sandbox = entry(sovereignty, "sandbox");
  const vision = capability(sovereignty, "local_vision");
  const knowledge = capability(sovereignty, "local_knowledge");
  const vectors = capability(sovereignty, "local_vector_store");
  const tools = capability(sovereignty, "tool_registry");

  const net = health?.network;
  const documentCount = (vectors?.evidence?.documents as number | undefined) ?? null;
  const signedCount = signatures?.totals?.signed ?? (signing?.evidence?.signed as number | undefined) ?? null;

  const nodes: DiagramNode[] = [
    /* ---- zone 1 · Confidential Input ---- */
    {
      id: "data",
      title: "Confidential Industrial Data",
      blurb: "The plant's own drawings, procedures and records, held locally.",
      zone: "input",
      status:
        documentCount == null
          ? "NOT VERIFIED"
          : documentCount > 0
            ? "PARTIAL"
            : "NOT VERIFIED",
      count: { value: documentCount, label: "documents indexed" },
      detail:
        documentCount == null
          ? "The vector store did not report a document count, so the size of the local corpus is unmeasured."
          : `${documentCount} document(s) are recorded in the local store. No document in this deployment carries an explicit clearance label, so every one falls to the deployment default (INTERNAL) rather than to a label someone chose. The corpus is local; that it is *confidential* is not something this host has verified.`,
      evidence: {
        documents: documentCount,
        labelled: 0,
        default_clearance: "INTERNAL",
        store: vectors?.evidence ?? null,
      },
    },
    {
      id: "security_gate",
      title: "Security Gate",
      blurb: "Identity, role and clearance are resolved before anything is read.",
      zone: "input",
      status:
        identity == null
          ? "NOT VERIFIED"
          : identity.authRequired
            ? fromBackendState(rbac?.state)
            : "PARTIAL",
      rawState: rbac?.state,
      count: identity ? { value: identity.permissions.length, label: "permissions granted" } : null,
      detail:
        identity == null
          ? "GET /api/auth/me did not answer, so no caller identity was resolved."
          : identity.authRequired
            ? `Caller '${identity.user}' is authenticated and holds role(s) ${identity.roles.join(", ") || "none"}.`
            : `Caller '${identity.user}' resolves to role(s) ${identity.roles.join(", ") || "none"} and ${identity.permissions.length} permission(s), but this deployment answers anonymous callers (authRequired=false), so identity is asserted by a header and not proven. That is why this node is PARTIAL rather than VERIFIED.`,
      evidence: identity
        ? {
            user: identity.user,
            roles: identity.roles,
            authenticated: identity.authenticated,
            authRequired: identity.authRequired,
            permissions: identity.permissions,
            defaultRole: identity.defaultRole,
            role_clearance: clearance?.evidence?.role_clearance ?? null,
          }
        : { role_clearance: clearance?.evidence?.role_clearance ?? null },
    },
    {
      id: "permission_check",
      title: "Permission Check",
      blurb: "Every gated route and tool consults the fixed role map first.",
      zone: "input",
      status: fromBackendState(rbac?.state),
      rawState: rbac?.state,
      count: rbac ? { value: Object.keys(rbac.evidence?.roles ?? {}).length, label: "roles in the map" } : null,
      detail: rbac?.detail ?? "The RBAC map did not answer, so no permission decision is being reported.",
      evidence: {
        rbac: rbac?.evidence ?? null,
        clearance: clearance?.evidence ?? null,
        clearance_detail: clearance?.detail ?? null,
        caller_permissions: identity?.permissions ?? null,
        caller_roles: identity?.roles ?? null,
        caller_user: identity?.user ?? null,
        caller_authenticated: identity?.authenticated ?? null,
      },
    },
    {
      id: "local_ingestion",
      title: "Local Ingestion",
      blurb: "Parsing and chunking happen on this machine; uploads never leave it.",
      zone: "input",
      status: fromBackendState(vectors?.state),
      rawState: vectors?.state,
      count: { value: documentCount, label: "documents ingested" },
      detail: vectors?.detail ?? "The local vector store did not answer, so ingestion is unverified.",
      evidence: vectors?.evidence ?? {},
    },
    {
      id: "ocr_vision",
      title: "OCR / Vision / Parsing",
      blurb: "Scanned drawings and images would be read here — if a tool existed.",
      zone: "input",
      status: fromBackendState(vision?.state),
      rawState: vision?.state,
      count: null,
      detail: vision?.detail ?? "No vision capability was reported.",
      evidence: vision?.evidence ?? {},
    },

    /* ---- zone 2 · Local AI Processing ---- */
    {
      id: "local_knowledge",
      title: "Local Knowledge",
      blurb: "RAG over the local index, plus industrial memory and the graph.",
      zone: "processing",
      /**
       * PARTIAL, not the weaker of the two: the backend's `local_knowledge`
       * entry measures the *graph* only, and the graph is NOT AVAILABLE while
       * retrieval over the local index is VERIFIED. The node spans both, so it
       * names the half that works and the half that does not instead of
       * collapsing to a single verdict that would misstate one of them.
       */
      status: "PARTIAL",
      rawState: `rag=${vectors?.state ?? "—"} · graph=${knowledge?.state ?? "—"}`,
      count: { value: documentCount, label: "indexed sources" },
      detail: `Retrieval: ${vectors?.state ?? "unreported"} — ${vectors?.detail ?? "no answer"}. Knowledge graph: ${knowledge?.state ?? "unreported"} — ${knowledge?.detail ?? "no answer"}. The node is the weaker of the two, because half of what it names cannot be queried.`,
      evidence: { vector_store: vectors?.evidence ?? null, knowledge_graph: knowledge?.evidence ?? null },
    },
    {
      id: "model_router",
      title: "Model Router",
      blurb: "Which model answers which role — read from the gateway itself.",
      zone: "processing",
      status: fromBackendState(localAi?.state),
      rawState: localAi?.state,
      count: { value: modelsAssigned(models), label: "roles with a model" },
      detail:
        localAi?.detail ??
        "The local model gateway did not answer, so no model is being claimed for any role.",
      evidence: {
        backend: models?.backend ?? null,
        gateway: localAi?.evidence ?? null,
        roles: models?.roles ?? null,
        served_models: servedModelCount(models),
        roles_total: modelsTotal(models),
        models: models?.models ?? null,
      },
    },
    {
      id: "local_agents",
      title: "Local Agents",
      blurb: "Diagnostic, Operations and Safety agents, each with declared tools.",
      zone: "processing",
      status: agents && agents.length > 0 ? "IMPLEMENTED" : agents ? "NOT VERIFIED" : "NOT VERIFIED",
      count: agents ? { value: agents.length, label: "agents registered" } : null,
      detail:
        agents == null
          ? "GET /api/agents did not answer, so no agent roster is being reported."
          : agents.length === 0
            ? "The agent registry answered with no agents, so nothing can run."
            : `${agents.length} agent descriptor(s) are registered with declared tools and RAG requirements. The registry answering is a measurement; it is not evidence that an agent ran, which is why this is IMPLEMENTED and not VERIFIED.`,
      evidence: agents
        ? {
            agents: agents.map((a) => ({
              kind: a.kind,
              name: a.name,
              status: a.status,
              requires_rag: a.requires_rag,
              tools: a.tools.length,
            })),
          }
        : {},
    },

    /* ---- zone 3 · Controlled Execution ---- */
    {
      id: "controlled_tools",
      title: "Controlled Tools",
      blurb: "Every tool is registered, permission-gated and clearance-filtered.",
      zone: "execution",
      status: fromBackendState(tools?.state),
      rawState: tools?.state,
      count: tools ? { value: (tools.evidence?.tools as string[] | undefined)?.length ?? null, label: "tools registered" } : null,
      detail: tools?.detail ?? "The tool registry did not answer, so no tool is being claimed as callable.",
      evidence: tools?.evidence ?? {},
    },
    {
      id: "sandbox",
      title: "Sandbox",
      blurb: "Container isolation for code — not running on this host.",
      zone: "execution",
      status: fromBackendState(sandbox?.state),
      rawState: sandbox?.state,
      count: null,
      // The wording is the backend's, so the page and `sandbox_command` agree.
      detail:
        sandbox?.detail ??
        "OpenSandbox is not running on this host: every sandbox_command returns 'ACTION BLOCKED / SANDBOX UNAVAILABLE'. Container-level network isolation is therefore not enforced here.",
      evidence: sandbox?.evidence ?? {},
    },

    /* ---- zone 4 · Verification ---- */
    {
      id: "verification",
      title: "Verification",
      blurb: "The hash chain is walked and stored artifacts are re-checked.",
      zone: "verification",
      status: weakest(fromBackendState(auditChain?.state), "PARTIAL"),
      rawState: `audit=${auditChain?.state ?? "—"} · signing=${signing?.state ?? "—"}`,
      count: { value: signedCount, label: "outputs signature-verified" },
      detail:
        `${auditChain?.detail ?? "The audit verifier did not answer."} Ed25519 verification is implemented and a key is present, but ${
          signedCount ?? 0
        } artifact(s) have been signed end-to-end on this host, so no produced result has been through the full verify path. PARTIAL is the honest state: the verifier is real, the end-to-end run has not happened.`,
      evidence: {
        integrity: integrity ?? null,
        signatures: signatures ?? null,
      },
    },

    /* ---- zone 5 · Output ---- */
    {
      id: "signed_output",
      title: "Signed / Audited Output",
      blurb: "What leaves the pipeline, signed with Ed25519 and written to the chain.",
      zone: "output",
      status: fromBackendState(signing?.state),
      rawState: signing?.state,
      count: { value: signedCount, label: "signed artifacts" },
      detail:
        signing?.detail ??
        "The signature records could not be read, so nothing is being reported as signed.",
      evidence: {
        algorithm: signatures?.algorithm ?? signing?.evidence?.algorithm ?? null,
        key_id: signatures?.key_id ?? null,
        totals: signatures?.totals ?? null,
        flagged: signatures?.flagged ?? null,
        artifacts: (signatures?.artifacts ?? []).slice(0, 5),
      },
    },
    {
      id: "approval_action",
      title: "Approval / Action",
      blurb: "A human approval is required before an action is taken.",
      zone: "output",
      status: "IMPLEMENTED",
      count: null,
      detail:
        "Approvals and jobs are gated by the permission map (`jobs:approve` for a viewer is refused — exercised by POST /api/security/evaluation), and the Security Console lists the pending queue. The gate is wired; nothing on this page takes an action, so it is not reported VERIFIED here.",
      evidence: { permission: "jobs:approve", rbac: rbac?.evidence ?? null },
    },

    /* ---- outside the boundary ---- */
    {
      id: "external_network",
      title: "External Network",
      blurb: "Everything off this machine. Untrusted by definition.",
      zone: "external",
      status: fromBackendState(egress?.state),
      rawState: egress?.state,
      count: { value: net?.external_allowed ?? null, label: "external hosts reached" },
      detail:
        net == null
          ? "GET /health did not report the network monitor, so external reachability is unmeasured."
          : `${net.external_allowed ?? "—"} non-loopback destination(s) were reached from this process; ${net.external_blocked ?? "—"} external attempt(s) were refused. The policy in force is ${egress?.evidence?.policy ?? "unknown"}.`,
      evidence: {
        policy: egress?.evidence ?? null,
        totals: net?.totals ?? null,
        blocked_hosts: net?.blocked_hosts ?? null,
        allowed_hosts: net?.allowed_hosts ?? null,
      },
    },
    {
      id: "network_sentinel",
      title: "Network Sentinel",
      blurb: "Watches every outbound decision and streams allow/block live.",
      zone: "external",
      status: fromBackendState(egress?.state),
      rawState: egress?.state,
      count: { value: net?.totals?.blocked ?? null, label: "decisions blocked" },
      detail:
        net == null
          ? "The network monitor did not report, so no decision is being claimed."
          : `${net.totals?.blocked ?? "—"} blocked and ${net.totals?.allowed ?? "—"} allowed decision(s) recorded in this process (${net.scope ?? "scope unknown"}). The live stream is subscribed only while this page is mounted — ${net.sentinel_subscribers ?? 0} subscriber(s) attached at the last /health reading.`,
      evidence: {
        subscriber_count_at_health_read: net?.sentinel_subscribers ?? null,
        blocked_hosts: net?.blocked_hosts ?? null,
        allowed_hosts: net?.allowed_hosts ?? null,
        // OS-level enforcement is a separate, absent layer. Stated here so the
        // application-layer guard cannot be read as an air-gap.
        os_egress_enforcement: "PLANNED — nftables/iptables is a Linux facility; this host is macOS",
      },
    },
    {
      id: "allow_block",
      title: "Allow / Block",
      blurb: "The decision the guard actually took, and where it is recorded.",
      zone: "external",
      status: fromBackendState(egress?.state),
      rawState: egress?.state,
      count: { value: net?.totals?.blocked ?? null, label: "blocked · this process" },
      detail:
        egress?.detail ??
        "The egress decision record did not answer, so no decision is being reported.",
      evidence: {
        policy: egress?.evidence ?? null,
        totals: net?.totals ?? null,
        recent: net?.recent ?? null,
      },
      live: true,
    },
    {
      id: "audit",
      title: "Audit",
      blurb: "One tamper-evident chain holds every decision and every action.",
      zone: "external",
      status: fromBackendState(auditChain?.state),
      rawState: auditChain?.state,
      count: { value: integrity?.events ?? null, label: "hash-linked events" },
      detail: integrity
        ? `The verifier reports ${integrity.status}: ${integrity.events} event(s) hash-linked with ${integrity.algorithm}. ${
            integrity.valid
              ? "The chain walks clean to the head."
              : `Broken at seq ${integrity.broken_seq ?? "—"}: ${integrity.reason ?? integrity.error ?? "no reason given"}.`
          }`
        : (auditChain?.detail ?? "The chain verifier did not answer, so the chain is unverified."),
      evidence: {
        integrity: integrity ?? null,
        security_event_namespaces: events?.namespaces ?? null,
      },
    },

    /* ---- the boundary itself ---- */
    {
      id: "security_boundary",
      title: "Security Boundary",
      blurb: "One application-layer guard, no OS firewall, no container isolation.",
      zone: "boundary",
      /**
       * PARTIAL by construction: the application-layer egress guard is the one
       * part of this boundary with a real refusal on record, while container
       * isolation is unavailable and the OS-level layer does not exist. It is
       * deliberately *not* UNAVAILABLE — something does hold — and deliberately
       * not VERIFIED — it is not an air-gap.
       */
      status: "PARTIAL",
      rawState: `app-egress=${egress?.state ?? "—"} · sandbox=${sandbox?.state ?? "—"} · os-firewall=PLANNED`,
      count: null,
      detail:
        "The boundary is enforced in the application: every outbound request passes the egress guard transport (default-deny), and everything else is loopback. It is NOT an air-gap. Container network isolation is unavailable on this host, and OS-level egress filtering (nftables/iptables) is PLANNED and Linux-only while this host is macOS. The boundary is therefore PARTIAL as a whole even where its application layer is VERIFIED.",
      evidence: {
        application_egress_guard: egress?.evidence ?? null,
        container_isolation: sandbox?.evidence ?? null,
        os_egress_enforcement: {
          status: "PLANNED",
          reason: "nftables/iptables is a Linux facility; this host is macOS",
          host_platform: sovereignty?.host?.platform ?? null,
        },
      },
    },
  ];

  return nodes;
}

/* --------------------------------------------------------------- animation */

/**
 * A live sentinel pulse. Built only from a real `network.connection_attempt`
 * frame, and carrying the frame's own fields — nothing is synthesised.
 */
export interface EgressPulse {
  /** Monotonic, so the same destination seen twice animates twice. */
  seq: number;
  action: "ALLOW" | "BLOCK" | "REACHED";
  destination: string | null;
  port: number | null;
  local: boolean;
  reason: string | null;
  at: number;
}

/**
 * Map one real frame to an edge state.
 *
 * A BLOCK stops at the boundary (red, and the edge goes no further). An ALLOW
 * to a loopback destination traverses green to the local model port. An ALLOW
 * to a non-loopback destination is the one case that means the boundary was
 * crossed, and is surfaced as `REACHED` rather than as a success.
 */
export function pulseFromEvent(
  event: { action: "ALLOW" | "BLOCK"; destination: string | null; port: number | null; local: boolean; reason: string | null },
  seq: number,
): EgressPulse {
  const action = event.action === "ALLOW" && !event.local ? "REACHED" : event.action;
  return {
    seq,
    action,
    destination: event.destination,
    port: event.port,
    local: event.local,
    reason: event.reason,
    at: Date.now(),
  };
}

/** The banner line under the diagram, driven by the last real frame. */
export function pulseSentence(pulse: EgressPulse | null): string {
  if (!pulse) return "Idle — no live egress decision has arrived since this page was opened.";
  const where = pulse.destination ? `${pulse.destination}${pulse.port ? `:${pulse.port}` : ""}` : "an unnamed destination";
  switch (pulse.action) {
    case "BLOCK":
      return `BLOCKED — ${where} was refused by the egress guard before a socket was opened.`;
    case "REACHED":
      return `REACHED — ${where} was allowed and is not loopback. This is a boundary crossing.`;
    default:
      return `ALLOWED — ${where} is loopback${pulse.port ? ` (local port ${pulse.port})` : ""}, so the request stayed on this machine.`;
  }
}
