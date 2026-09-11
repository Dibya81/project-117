/**
 * Edge component.
 *
 * Two kinds, distinguished structurally rather than by colour alone:
 *
 *   pipe  process flow — solid, thick, square-ish routing
 *   wire  signal       — thin, dashed at rest, and labelled with the signal
 *
 * When a flow is active the dashes animate and a small travelling marker runs
 * the path, so "animated dash when flow is active" is visible rather than
 * implied. An edge incident to a traced unit gets the active treatment.
 */
import { EdgeLabelRenderer, getBezierPath, type EdgeProps } from "reactflow";

export interface FlowEdgeData {
  kind: "pipe" | "wire";
  /** Set from the store while an agent event references either endpoint. */
  active?: boolean;
}

export function FlowEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  selected,
}: EdgeProps<FlowEdgeData>) {
  const kind = data?.kind ?? "pipe";
  const active = Boolean(data?.active);

  const [path, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    curvature: kind === "wire" ? 0.22 : 0.4,
  });

  const classes = [
    "rf-edge",
    `rf-edge--${kind}`,
    active ? "is-active" : "",
    selected ? "is-selected" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <>
      {/* Drawn directly rather than through BaseEdge so the state classes
          (dashed wire, animated flow, selection) can be pure CSS. */}
      <path id={id} d={path} className={classes} fill="none" />
      {active && (
        <circle r={kind === "wire" ? 2.6 : 3.4} className={`rf-edge__pulse rf-edge__pulse--${kind}`}>
          <animateMotion dur={kind === "wire" ? "1.1s" : "1.6s"} repeatCount="indefinite" path={path} />
        </circle>
      )}
      {kind === "wire" && labelX > 0 && (
        <EdgeLabelRenderer>
          <span
            className={`rf-edge__label${active ? " is-active" : ""}`}
            style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
          >
            signal
          </span>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
