/**
 * Local identity for the on-prem deployment model.
 *
 * The backend treats an unauthenticated request as `operator` (the machine is
 * the trust boundary) and accepts role claims via `X-P117-Roles`. This module
 * holds the current role selection in session storage so the API client can
 * attach it. A shared deployment would set P117_AUTH_REQUIRED=true and replace
 * this with a real login flow — the header contract stays identical.
 */
import type { Role } from "@/types";

const KEY = "p117.roles";

export function currentRoles(): Role[] {
  if (typeof window === "undefined") return ["operator"];
  const raw = window.sessionStorage.getItem(KEY);
  if (!raw) return ["operator"];
  return raw.split(",").filter(Boolean) as Role[];
}

export function setRoles(roles: Role[]): void {
  window.sessionStorage.setItem(KEY, roles.join(","));
}

export function currentUser(): string {
  return "local"; // matches backend ANONYMOUS_USER for on-prem installs
}
