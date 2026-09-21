/**
 * Validation panel.
 *
 * Renders the report from `validateCircuit` — a real BFS/DFS over the canvas,
 * not a checklist. Errors block; warnings inform. Selecting an issue highlights
 * its nodes so a reported problem is findable on a large plant.
 */
import { useSim } from "../store/simStore";

export function ValidationPanel() {
  const validation = useSim((s) => s.validation);
  const runValidation = useSim((s) => s.runValidation);
  const select = useSim((s) => s.select);
  const nodes = useSim((s) => s.nodes);

  const tagOf = (id: string) => {
    const n = nodes.find((x) => x.id === id);
    return (n?.data as { tag?: string; label?: string })?.tag ?? (n?.data as { label?: string })?.label ?? id;
  };

  return (
    <section className="validation" aria-label="Circuit validation">
      <header className="validation__head">
        <h3>Circuit</h3>
        <button className="btn btn--primary" onClick={runValidation}>
          Validate circuit
        </button>
      </header>

      {!validation ? (
        <p className="validation__idle">
          Runs a breadth-first traversal over the canvas and reports orphans, sensors wired to
          sensors, and disconnected groups.
        </p>
      ) : (
        <>
          <div className="validation__stats">
            <span><b>{validation.nodeCount}</b> nodes</span>
            <span><b>{validation.edgeCount}</b> connections</span>
            <span><b>{validation.components.length}</b> groups</span>
            <span className={validation.ok ? "is-ok" : "is-bad"}>
              {validation.ok ? "no blocking errors" : `${validation.issues.filter((i) => i.level === "error").length} errors`}
            </span>
          </div>

          {validation.nodeCount === 0 ? (
            <p className="validation__idle">
              The canvas is empty. Drag units and instruments from the palette, then validate.
            </p>
          ) : validation.issues.length === 0 ? (
            <p className="validation__pass">
              Every node is wired, sensors terminate on equipment, and the plant is one connected
              graph. A fault injected anywhere can propagate.
            </p>
          ) : (
            <ul className="validation__list">
              {validation.issues.map((issue, i) => (
                <li key={`${issue.code}-${i}`} className={`validation__item is-${issue.level}`}>
                  <span className="validation__level">{issue.level === "error" ? "ERROR" : "WARN"}</span>
                  <span className="validation__msg">{issue.message}</span>
                  {issue.nodeIds.length > 0 && (
                    <span className="validation__nodes">
                      {issue.nodeIds.slice(0, 6).map((id) => (
                        <button key={id} onClick={() => select(id)} title="Select this node">
                          {tagOf(id)}
                        </button>
                      ))}
                      {issue.nodeIds.length > 6 && <em>+{issue.nodeIds.length - 6}</em>}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
