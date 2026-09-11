"use client";

/**
 * Console role context — demo role switcher for the SIH build.
 * On a shared deployment this resolves from the authenticated session;
 * the shape stays identical.
 */
import { createContext, useContext, useState, type ReactNode } from "react";
import type { ConsoleRole } from "@/types/console";

interface RoleState {
  role: ConsoleRole;
  user: string;
  setRole: (r: ConsoleRole) => void;
}

const RoleContext = createContext<RoleState>({
  role: "engineer",
  user: "r.kapoor",
  setRole: () => undefined,
});

const ROLE_USER: Record<ConsoleRole, string> = {
  operator: "t.nguyen",
  engineer: "r.kapoor",
  maintenance: "s.mehta",
  safety: "m.farouk",
  manager: "a.iyer",
  admin: "d.bhusal",
};

export function RoleProvider({ children }: { children: ReactNode }) {
  const [role, setRole] = useState<ConsoleRole>("engineer");
  return (
    <RoleContext.Provider value={{ role, user: ROLE_USER[role], setRole }}>
      {children}
    </RoleContext.Provider>
  );
}

export function useRole() {
  return useContext(RoleContext);
}
