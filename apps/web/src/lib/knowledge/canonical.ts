/**
 * Canonical refinery identity.
 *
 * Project 117 ships two equipment vocabularies, and until they are joined the
 * app shows the same physical machine twice.
 *
 *   REGISTER vocabulary  58 units in the refinery plant definition served by
 *                        GET /api/simulation/plants/refinery/definition
 *                        (local SQLite store; the bundled JSON was removed).
 *                        The live simulation register. Authority for
 *                        instrumentation, process topology and telemetry.
 *
 *   OVERLAY vocabulary   6 units in data/demo/equipment/equipment.json
 *                        The U-200 console dataset that carries the narrative
 *                        already told across the app: C-3, P-1042, V-2210,
 *                        T-118, E-340, P-2051.
 *
 * The mapping below is the same one declared in the refinery dossier
 * (`data/knowledge/refinery/04b-register-overlay-crosswalk.md`, Section 4b).
 * `confidence` is explicit and is never widened for convenience:
 *
 *   exact    same tag string exists in both vocabularies
 *   twin     a distinct register unit carries the same machine signature
 *   partial  the register unit covers only part of the overlay service —
 *            the two must NOT be treated as the same asset
 *
 * Canonical identity rule: for `exact` and `twin` the two records describe one
 * physical machine, so the graph merges them into a single node keyed by the
 * overlay tag (the id the rest of the console already uses), recording the
 * register tag as an alias. For `partial` the records stay separate and are
 * joined by an explicit, provenance-carrying edge instead.
 */

export type MappingConfidence = "exact" | "twin" | "partial";

export interface CrosswalkEntry {
  overlay: string;
  overlayName: string;
  register: string;
  registerName: string;
  confidence: MappingConfidence;
  /** Why this mapping holds, and what it does not claim. */
  basis: string;
}

export const CROSSWALK: CrosswalkEntry[] = [
  {
    overlay: "C-3",
    overlayName: "Recycle Gas Compressor",
    register: "C-1071",
    registerName: "Reformer Recycle Compressor",
    confidence: "twin",
    basis:
      "Register twin carries the same machine signature: VIB-1071 nominal 5.7 mm/s " +
      "(the learned C-3 baseline), RPM-1071 8,840 rpm, TT-1071 79 °C.",
  },
  {
    overlay: "P-1042",
    overlayName: "Feed Charge Pump",
    register: "P-1042",
    registerName: "Crude Charge Pump",
    confidence: "exact",
    basis: "Same tag string in both vocabularies.",
  },
  {
    overlay: "E-340",
    overlayName: "Feed/Effluent Heat Exchanger",
    register: "E-1063",
    registerName: "NHT Effluent Cooler",
    confidence: "twin",
    basis: "Hydrotreater effluent exchanger; register carries inlet/outlet temperature and tube-side flow.",
  },
  {
    overlay: "T-118",
    overlayName: "Intermediate Storage Tank",
    register: "TK-1121",
    registerName: "Naphtha Tank",
    confidence: "twin",
    basis: "Product-storage tank with level and temperature instrumentation.",
  },
  {
    overlay: "V-2210",
    overlayName: "Product Separator Vessel",
    register: "V-1047",
    registerName: "Column Feed Valve",
    confidence: "partial",
    basis:
      "The register asset is a process valve with actuator position feedback; the " +
      "overlay vessel has no register tag number. Related by service position in " +
      "the U-200 train, not by equipment identity.",
  },
  {
    overlay: "P-2051",
    overlayName: "Product Transfer Pump",
    register: "P-1124",
    registerName: "Product Loading Pump",
    confidence: "partial",
    basis:
      "Same duty family only. The overlay pump is recorded under maintenance while the " +
      "register pump is in service, so condition data must not be copied between them.",
  },
];

const BY_OVERLAY = new Map(CROSSWALK.map((c) => [c.overlay, c]));
const BY_REGISTER = new Map(CROSSWALK.map((c) => [c.register, c]));

export function crosswalkForOverlay(tag: string): CrosswalkEntry | undefined {
  return BY_OVERLAY.get(tag);
}
export function crosswalkForRegister(tag: string): CrosswalkEntry | undefined {
  return BY_REGISTER.get(tag);
}

/**
 * True when the two tags name one physical machine and the graph should show a
 * single merged node. `partial` mappings are deliberately excluded.
 */
export function isIdentityMerge(entry: CrosswalkEntry): boolean {
  return entry.confidence === "exact" || entry.confidence === "twin";
}

export const CONFIDENCE_TONE: Record<MappingConfidence, string> = {
  exact: "var(--ok)",
  twin: "var(--cyan)",
  partial: "var(--warn)",
};
