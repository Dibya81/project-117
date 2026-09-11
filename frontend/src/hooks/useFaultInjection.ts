/**
 * Fault injection.
 *
 * One place that joins the two halves of a fault: the local state change and
 * the orchestrator notification. The order matters — the store is mutated
 * first so the `sensor_snapshot` we send is the post-fault state, which is what
 * the orchestrator needs to reason about.
 */
import { useCallback } from "react";
import { useSim } from "../store/simStore";
import { useOrchestrator } from "../ws/orchestrator";
import type { FaultType } from "../types";

export function useFaultInjection() {
  const applyLocal = useSim((s) => s.injectFault);
  const notify = useOrchestrator((s) => s.injectFault);

  return useCallback(
    (nodeId: string, faultType: FaultType) => {
      const { plantId, sensors } = applyLocal(nodeId, faultType);
      notify({ plantId, equipmentId: nodeId, faultType, sensorSnapshot: sensors });
    },
    [applyLocal, notify],
  );
}
