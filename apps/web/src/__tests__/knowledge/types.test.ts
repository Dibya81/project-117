/**
 * Knowledge type-guards — unit tests.
 *
 * Verifies the structural contracts of the KGraph / Namespace types used by
 * the Knowledge Hub and Graph views. These types are the source of truth for
 * what the frontend sends to the API and what it renders; a silent structural
 * regression here would break both.
 */

import { describe, it, expect } from "vitest";
import type { KGraph, Namespace } from "@/lib/knowledge/types";

// ── Helpers ────────────────────────────────────────────────────────────────

function makeNamespace(overrides: Partial<Namespace> = {}): Namespace {
  return {
    id: "company",
    label: "Company Docs",
    icon: "building",
    color: "#7c3aed",
    ...overrides,
  };
}

function makeKGraph(overrides: Partial<KGraph> = {}): KGraph {
  return {
    id: "graph-1",
    namespace: "company",
    nodes: [],
    edges: [],
    ...overrides,
  };
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe("Namespace type contract", () => {
  it("requires id, label, icon and color", () => {
    const ns = makeNamespace();
    expect(ns.id).toBeTruthy();
    expect(ns.label).toBeTruthy();
    expect(ns.icon).toBeTruthy();
    expect(ns.color).toMatch(/^#[0-9a-fA-F]{6}$/);
  });

  it("accepts optional description", () => {
    const ns = makeNamespace({ description: "Uploaded company documents" });
    expect(ns.description).toBe("Uploaded company documents");
  });
});

describe("KGraph type contract", () => {
  it("requires id, namespace, nodes and edges", () => {
    const g = makeKGraph();
    expect(g.id).toBeTruthy();
    expect(g.namespace).toBeTruthy();
    expect(Array.isArray(g.nodes)).toBe(true);
    expect(Array.isArray(g.edges)).toBe(true);
  });

  it("namespace links back to a valid namespace id", () => {
    const ns = makeNamespace({ id: "simulation" });
    const g = makeKGraph({ namespace: ns.id });
    expect(g.namespace).toBe(ns.id);
  });

  it("node shapes follow the expected contract", () => {
    const node = { id: "n1", label: "P-101", type: "equipment" };
    const g = makeKGraph({ nodes: [node] });
    expect(g.nodes[0].id).toBe("n1");
    expect(g.nodes[0].label).toBe("P-101");
  });
});
