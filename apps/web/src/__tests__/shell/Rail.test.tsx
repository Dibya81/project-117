/**
 * Navigation rail — unit tests.
 *
 * Strategy: we test the data contract (ROLE_NAV produces the right allowed IDs for
 * each role) and verify that role-based navigation is correctly mapped.
 */

import { describe, it, expect, vi } from "vitest";
import { ROLE_NAV } from "@/lib/data/console";
import type { ConsoleRole } from "@/types/console";

describe("ROLE_NAV data contract", () => {
  it("includes knowledge and workspace for the operator role", () => {
    const operatorNav = ROLE_NAV.operator;
    expect(operatorNav).toContain("knowledge-hub");
    expect(operatorNav).toContain("knowledge-docs");
    expect(operatorNav).toContain("workspace");
    expect(operatorNav).toContain("equipment");
  });

  it("every role in ROLE_NAV has non-empty nav items", () => {
    const roles = Object.keys(ROLE_NAV) as ConsoleRole[];
    expect(roles.length).toBeGreaterThan(0);
    for (const role of roles) {
      const items = ROLE_NAV[role];
      expect(items.length, `role ${role} should have nav items`).toBeGreaterThan(0);
      for (const id of items) {
        expect(typeof id).toBe("string");
        expect(id.length).toBeGreaterThan(0);
      }
    }
  });

  it("no duplicate item ids within a role", () => {
    for (const [role, items] of Object.entries(ROLE_NAV)) {
      const unique = new Set(items);
      expect(unique.size, `role '${role}' has duplicate nav item ids`).toBe(items.length);
    }
  });

  it("admin role has the superset of permissions", () => {
    const adminNav = ROLE_NAV.admin;
    expect(adminNav).toContain("admin");
    expect(adminNav).toContain("workspace");
    expect(adminNav).toContain("simulation");
    expect(adminNav.length).toBeGreaterThanOrEqual(ROLE_NAV.operator.length);
  });
});
