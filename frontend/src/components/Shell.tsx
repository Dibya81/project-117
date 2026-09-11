/**
 * App shell: brand, navigation and the connection indicator.
 *
 * The connection chip is the honest status of the orchestrator socket at all
 * times — connected, connecting, or mock — so the state of the bridge is never
 * something you have to open a panel to discover.
 */
import { NavLink } from "react-router-dom";
import { useEffect } from "react";
import { useOrchestrator } from "../ws/orchestrator";
import { DATA_SOURCE, API_BASE } from "../data/service";

export function Shell({
  title,
  subtitle,
  children,
  actions,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
}) {
  const status = useOrchestrator((s) => s.status);
  const attempts = useOrchestrator((s) => s.attempts);
  const connect = useOrchestrator((s) => s.connect);

  // One connection for the whole app, opened on mount.
  useEffect(() => {
    connect();
  }, [connect]);

  const chip =
    status === "open"
      ? { cls: "is-ok", text: "orchestrator live" }
      : status === "connecting"
        ? { cls: "is-warn", text: `connecting… ${attempts}/3` }
        : status === "mock"
          ? { cls: "is-mock", text: "MOCK MODE" }
          : { cls: "is-idle", text: "orchestrator idle" };

  return (
    <div className="app">
      <header className="appbar">
        <div className="appbar__brand">
          <span className="appbar__mark">117</span>
          <span className="appbar__name">Project 117</span>
          <span className="appbar__sub">Simulation Workbench</span>
        </div>

        <nav className="appbar__nav">
          <NavLink to="/simulate" end>
            Hub
          </NavLink>
          <NavLink to="/simulate/build">Builder</NavLink>
          <NavLink to="/simulate/refinery">Refinery</NavLink>
          <NavLink to="/simulate/iron_steel_plant">Steel</NavLink>
        </nav>

        <div className="appbar__right">
          <span className="appbar__source" title={DATA_SOURCE === "backend" ? `${API_BASE}/plants/:id` : "bundled JSON"}>
            data: {DATA_SOURCE}
          </span>
          <span className={`connchip ${chip.cls}`} title={`WebSocket status: ${status}`}>
            <i />
            {chip.text}
          </span>
        </div>
      </header>

      <div className="pagehead">
        <div>
          <h1>{title}</h1>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {actions && <div className="pagehead__actions">{actions}</div>}
      </div>

      {children}
    </div>
  );
}
