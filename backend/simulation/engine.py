"""Simulation engine — the physics-lite heart of the digital twin.

Design decisions, each with a reason:

**Deterministic by construction.** One mulberry32-style seeded RNG per plant.
Same seed + same injected faults = byte-identical telemetry. That is what
makes tests meaningful and demos reproducible — no wall-clock randomness.

**Topology-driven, never scripted.** A pump stopping changes the *flow on its
pipe connections*; downstream equipment senses it through the sensors bolted
to *them*. Nothing is hardcoded to a tag — PT-1042A fails the same way any
PT fails, because the rule is in the graph walk, not in an if-statement.

**One tick, batched updates.** All sensors advance on the central tick;
subscribers get a batch per tick (never 200 independent timers).

**Alarms are derived, not stored long-term.** Each tick recomputes envelope
violations from live values; the alarm list is a projection.
"""

from __future__ import annotations

from backend.simulation.models import (
    Alarm,
    AlarmSeverity,
    AssetState,
    ConnectionKind,
    Incident,
    IncidentStatus,
    Measurement,
    Plant,
    Sensor,
    TelemetryPoint,
    TelemetryQuality,
)


class _Rng:
    """Deterministic PRNG (mulberry32). Zero global state."""

    def __init__(self, seed: int) -> None:
        self._s = seed & 0xFFFFFFFF

    def next(self) -> float:
        # mulberry32 with explicit 32-bit truncation (Python ints are unbounded)
        self._s = (self._s + 0x6D2B79F5) & 0xFFFFFFFF
        t = self._s
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        t ^= (t + (((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0

    def uniform(self, lo: float, hi: float) -> float:
        return lo + (hi - lo) * self.next()


class EquipmentRuntime:
    """Mutable per-tick state for one equipment (model stays immutable)."""

    __slots__ = ("capacity", "state", "faults")

    def __init__(self, capacity: float, state: AssetState) -> None:
        self.capacity = capacity
        self.state = state
        self.faults: set[str] = set()


class SensorRuntime:
    __slots__ = ("value", "quality", "failed", "drifting")

    def __init__(self, nominal: float) -> None:
        self.value = nominal
        self.quality = TelemetryQuality.GOOD
        self.failed = False
        self.drifting = False


class SimulationEngine:
    """Ticks one plant. Construct with a validated Plant dataset."""

    def __init__(self, plant: Plant, seed: int = 117, tick_s: float = 1.0) -> None:
        self.plant = plant
        self.tick_s = tick_s
        self.t = 0.0
        self.rng = _Rng(seed)
        self.eq = {e.id: EquipmentRuntime(e.capacity, e.state) for e in plant.equipment}
        self.sensors: dict[str, SensorRuntime] = {}
        self.sensor_model: dict[str, Sensor] = {}
        for e in plant.equipment:
            for s in e.sensors:
                self.sensors[s.id] = SensorRuntime(s.nominal)
                self.sensor_model[s.id] = s
        #: Session-scoped operator mutations. They are RAM-only by design — the
        #: dataset stays pristine, so a reset or a process restart rebuilds the
        #: plant and these sets are discarded with the runtime.
        self._disabled_sensors: set[str] = set()
        self._removed_sensors: set[str] = set()
        self._disabled_equipment: set[str] = set()
        # topology: equipment id -> downstream equipment ids (pipes only)
        self.downstream: dict[str, list[str]] = {}
        self.upstream: dict[str, list[str]] = {}
        self.pipes_out: dict[str, list[str]] = {}
        self.pipe_by_id = {c.id: c for c in plant.connections}
        for c in plant.connections:
            if c.kind == ConnectionKind.PIPE:
                self.downstream.setdefault(c.source, []).append(c.target)
                self.upstream.setdefault(c.target, []).append(c.source)
                self.pipes_out.setdefault(c.source, []).append(c.id)
        self.alarms: dict[str, Alarm] = {}
        self.incidents: dict[str, Incident] = {}
        self._alarm_seq = 0
        self._incident_seq = 0

    # ------------------------------------------------------------------ tick

    def tick(self) -> dict:
        """Advance one tick. Returns the batched update frame for the bus."""
        self.t += self.tick_s
        flow = self._propagate_flow()
        readings = self._read_sensors(flow)
        alarms = self._evaluate_alarms()
        return {
            "t": self.t,
            "readings": readings,
            "alarms": [a.model_dump() for a in alarms],
            "states": {eid: r.state.value for eid, r in self.eq.items() if r.state != AssetState.NORMAL},
        }

    # ------------------------------------------------------------- telemetry

    def _process_factor(self, eq_id: str, measurement: Measurement, flow: dict[str, float]) -> float:
        """How much the process should push this sensor right now.

        Returns a signed offset in units of the sensor's normal span.
        - flow sensors read the actual pipe flow fraction
        - pressure sensors downstream of a stopped/degraded source sag
        - temperatures on exchangers sag when flow is lost
        - vibration rises as capacity climbs (wear signature when faulted)
        """
        span = self.sensor_model_span(eq_id, measurement)
        if span is None:
            return 0.0
        model = self.sensor_model_span_obj(eq_id, measurement)
        if model is None:
            return 0.0
        if model.measurement == Measurement.FLOW:
            # a flow sensor reads its own machine's output, throttled by what
            # upstream actually delivers
            f = self.eq[eq_id].capacity * flow.get(eq_id, 1.0)
            return (f - 1.0) * span * 0.9
        if model.measurement == Measurement.PRESSURE:
            ups = self.upstream.get(eq_id, [])
            worst = min((self.eq[u].capacity for u in ups if u in self.eq), default=1.0)
            return (worst - 1.0) * span * 0.6
        if model.measurement == Measurement.TEMPERATURE:
            ups = self.upstream.get(eq_id, [])
            worst = min((self.eq[u].capacity for u in ups if u in self.eq), default=1.0)
            return (1.0 - worst) * span * 0.35  # loss of flow -> heat-up
        if model.measurement == Measurement.VIBRATION:
            rt = self.eq[eq_id]
            wear = 1.0 if "bearing_wear" in rt.faults or "cavitation" in rt.faults else 0.0
            return wear * span * 0.5 + (rt.capacity - 1.0) * span * 0.1
        if model.measurement == Measurement.LEVEL:
            f = flow.get(eq_id, 1.0)
            return (f - 1.0) * span * 0.7
        if model.measurement in (Measurement.CURRENT, Measurement.POWER, Measurement.RPM):
            return (self.eq[eq_id].capacity - 1.0) * span * 0.8
        if model.measurement in (Measurement.GAS, Measurement.LEAK):
            return 0.0  # detectors are driven by leak events, not process noise
        return 0.0

    def _read_sensors(self, flow: dict[str, float]) -> list[dict]:
        out: list[dict] = []
        for sid, rt in self.sensors.items():
            model = self.sensor_model[sid]
            if rt.failed:
                # failed sensors freeze on their last value; quality says so
                out.append(TelemetryPoint(sensor_id=sid, value=rt.value, quality=TelemetryQuality.BAD, t=self.t).model_dump())
                continue
            span = model.normal_max - model.normal_min or 1.0
            noise = self.rng.uniform(-model.noise, model.noise) * span
            process = self._process_factor(model.equipment_id, model.measurement, flow)
            drift = max(model.drift_rate, span * 0.02) if rt.drifting else 0.0
            if model.is_detector:
                # latched 0/1 detectors hold until a leak event sets them
                rt.value = rt.value  # set by leak machinery
            else:
                revert = (model.nominal - rt.value) * 0.03 if not rt.drifting else 0.0
                rt.value = max(0.0, rt.value + noise + process + drift + revert)
            out.append(TelemetryPoint(sensor_id=sid, value=round(rt.value, 3), quality=rt.quality, t=self.t).model_dump())
        return out

    # ----------------------------------------------------------- propagation

    def _propagate_flow(self) -> dict[str, float]:
        """Compute the flow fraction into each equipment from its pipes.

        A pipe carries `source capacity * pipe capacity` — a stopped pump
        starves everything downstream of it, exactly once per tick.
        """
        flow: dict[str, float] = {}
        for c in self.plant.connections:
            if c.kind != ConnectionKind.PIPE:
                continue
            src = self.eq.get(c.source)
            src_cap = src.capacity if src else 0.0
            pipe_cap = 0.0 if (not c.enabled or c.status == AssetState.DISABLED) else 1.0
            if c.leaking:
                pipe_cap *= 0.55
            c.flow = round(c.capacity * src_cap * pipe_cap, 2)
            # downstream equipment sees the *worst* of its inbound pipes
            prev = flow.get(c.target, 1.0)
            flow[c.target] = min(prev, src_cap * pipe_cap) if c.capacity > 0 else prev
        return flow

    # --------------------------------------------------------------- alarms

    def _evaluate_alarms(self) -> list[Alarm]:
        fresh: list[Alarm] = []
        active_ids: set[str] = set()
        for sid, rt in self.sensors.items():
            m = self.sensor_model[sid]
            if rt.quality == TelemetryQuality.BAD or m.is_detector:
                continue
            v = rt.value
            sev: AlarmSeverity | None = None
            if v <= m.critical_min or v >= m.critical_max:
                sev = AlarmSeverity.CRITICAL
            elif v <= m.warning_min or v >= m.warning_max:
                sev = AlarmSeverity.WARNING
            aid = f"ALM-{sid}"
            if sev:
                if aid not in self.alarms:
                    self._alarm_seq += 1
                    self.alarms[aid] = Alarm(
                        id=f"{aid}-{self._alarm_seq}", sensor_id=sid, tag=m.tag, severity=sev,
                        message=f"{m.tag} {m.measurement.value} {v:.1f} {m.unit} outside envelope", at=self.t,
                    )
                    fresh.append(self.alarms[aid])
                active_ids.add(aid)
        # clear recovered alarms
        for aid in [k for k in self.alarms if k not in active_ids]:
            self.alarms[aid].active = False
            del self.alarms[aid]
        return fresh

    # ------------------------------------------------------------- failures

    def inject_failure(self, equipment_id: str, mode_id: str) -> dict:
        """Apply a failure mode to an equipment. Returns what changed.
        Generic: driven by the FailureMode mechanism, not the tag."""
        eq_model = next((e for e in self.plant.equipment if e.id == equipment_id), None)
        mode = next((m for m in self.plant.failure_modes if m.id == mode_id), None)
        if not eq_model or not mode:
            raise KeyError(f"unknown equipment {equipment_id} or failure mode {mode_id}")
        rt = self.eq[equipment_id]
        changed: dict = {"equipment_id": equipment_id, "mode": mode_id, "mechanism": mode.mechanism}

        if mode.mechanism == "sensor":
            # kill the *first sensor matching* the mode's applies_to measurement
            target = next(
                (s for s in eq_model.sensors if s.measurement.value in mode.applies_to),
                eq_model.sensors[0] if eq_model.sensors else None,
            )
            if target:
                srt = self.sensors[target.id]
                srt.failed = True
                srt.quality = TelemetryQuality.BAD
                changed["sensor_id"] = target.id
                changed["tag"] = target.tag
        elif mode.mechanism == "drift":
            target = next((s for s in eq_model.sensors if s.measurement.value in mode.applies_to), None)
            if target:
                self.sensors[target.id].drifting = True
                changed["sensor_id"] = target.id
        elif mode.mechanism == "stop":
            rt.capacity = 0.0
            rt.state = AssetState.FAILED
        elif mode.mechanism == "degrade":
            rt.capacity = max(0.15, rt.capacity * (1.0 - mode.magnitude))
            rt.state = AssetState.WARNING
        elif mode.mechanism == "leak":
            for pid in self.pipes_out.get(equipment_id, []):
                self.pipe_by_id[pid].leaking = True
            # trip the nearest gas/leak detector in the same area
            det = next(
                (s for s, m in self.sensor_model.items()
                 if m.is_detector and s in self.sensors
                 and self._area_of(m.equipment_id) == eq_model.area_id),
                None,
            )
            if det:
                self.sensors[det].value = 1.0
                changed["detector"] = self.sensor_model[det].tag
        elif mode.mechanism == "surge":
            rt.capacity = min(1.6, rt.capacity * (1.0 + mode.magnitude))
            rt.state = AssetState.WARNING

        rt.faults.add(mode_id)
        return changed

    def disable_equipment(self, equipment_id: str) -> None:
        """Disable = the equipment can no longer perform its function."""
        rt = self.eq[equipment_id]
        rt.capacity = 0.0
        rt.state = AssetState.DISABLED
        self._disabled_equipment.add(equipment_id)

    def remove_equipment(self, equipment_id: str) -> list[str]:
        """Remove from the simulation graph; return broken-path targets."""
        affected = self.downstream.get(equipment_id, [])
        rt = self.eq[equipment_id]
        rt.capacity = 0.0
        rt.state = AssetState.DISABLED
        self._disabled_equipment.add(equipment_id)
        for c in self.plant.connections:
            if c.source == equipment_id or c.target == equipment_id:
                c.enabled = False
        return affected

    # --------------------------------------------------------------- sensors

    def disable_sensor(self, sensor_id: str) -> None:
        """Out of service, not gone: the point stays in the graph so it can be
        restored in place, but its reading must not be trusted."""
        rt = self.sensors[sensor_id]
        rt.failed = True
        rt.quality = TelemetryQuality.BAD
        self._disabled_sensors.add(sensor_id)

    def remove_sensor(self, sensor_id: str) -> None:
        """Remove from the running plant: telemetry, snapshot and every list
        built from the plant lose it. Only a reset brings it back."""
        self.sensors.pop(sensor_id)  # KeyError on unknown id, as equipment does
        model = self.sensor_model[sensor_id]
        for e in self.plant.equipment:
            if e.id == model.equipment_id:
                e.sensors = [s for s in e.sensors if s.id != sensor_id]
                break
        # A removed point cannot carry an active alarm; the next tick would
        # clear it anyway, but snapshot() may be read before that tick.
        self.alarms.pop(f"ALM-{sensor_id}", None)
        self._disabled_sensors.discard(sensor_id)
        self._removed_sensors.add(sensor_id)

    def restore_sensor(self, sensor_id: str) -> None:
        """Undo a disable. A removed sensor is deliberately not resurrected:
        it is absent from the plant definition, so only a reset can rebuild it
        consistently."""
        if sensor_id in self._removed_sensors:
            raise KeyError(
                f"sensor {sensor_id} was removed; it only returns via a plant reset"
            )
        rt = self.sensors[sensor_id]
        self._disabled_sensors.discard(sensor_id)
        rt.failed = False
        rt.quality = TelemetryQuality.GOOD
        rt.value = self.sensor_model[sensor_id].nominal

    def sensor_out_of_service(self, sensor_id: str) -> str | None:
        """``"disabled"`` | ``"removed"`` | ``None`` for the console badge."""
        if sensor_id in self._removed_sensors:
            return "removed"
        if sensor_id in self._disabled_sensors:
            return "disabled"
        return None

    def session_change_counts(self) -> dict[str, int]:
        """RAM-only operator mutations since the runtime was built. This is the
        console's "a reload will discard this" indicator, so it counts what the
        engine actually tracks, not what was requested."""
        return {
            "disabled_sensors": len(self._disabled_sensors),
            "removed_sensors": len(self._removed_sensors),
            "disabled_equipment": len(self._disabled_equipment),
        }

    def repair_sensor(self, sensor_id: str) -> None:
        rt = self.sensors[sensor_id]
        rt.failed = False
        rt.drifting = False
        rt.quality = TelemetryQuality.GOOD
        rt.value = self.sensor_model[sensor_id].nominal

    def restore_equipment(self, equipment_id: str, capacity: float = 1.0) -> None:
        rt = self.eq[equipment_id]
        rt.capacity = capacity
        rt.state = AssetState.NORMAL
        rt.faults.clear()
        self._disabled_equipment.discard(equipment_id)
        for c in self.plant.connections:
            if c.source == equipment_id or c.target == equipment_id:
                c.enabled = True
                c.leaking = False
        # Latched detectors must be reset once the leak path is repaired,
        # otherwise the 0/1 point stays tripped forever and verification can
        # never close the incident (observed on every `leak` failure mode).
        # A removed detector has no runtime left to reset — skip it.
        area = self._area_of(equipment_id)
        for sid, m in self.sensor_model.items():
            if m.is_detector and sid in self.sensors and self._area_of(m.equipment_id) == area:
                self.sensors[sid].value = 0.0
                self.sensors[sid].quality = TelemetryQuality.GOOD

    # ------------------------------------------------------------- topology

    def neighbors(self, equipment_id: str, depth: int = 2) -> dict[str, list[str]]:
        """BFS neighborhood used by the agent pipeline for blast radius."""
        seen = {equipment_id}
        frontier = [equipment_id]
        out: list[str] = []
        for _ in range(depth):
            nxt: list[str] = []
            for cur in frontier:
                for nb in self.downstream.get(cur, []) + self.upstream.get(cur, []):
                    if nb not in seen:
                        seen.add(nb)
                        out.append(nb)
                        nxt.append(nb)
            frontier = nxt
        return {"affected": out}

    def alternate_sensors(self, sensor_id: str) -> list[Sensor]:
        """Redundant/related measurements: same measurement elsewhere on the
        equipment, plus the nearest upstream/downstream same-measurement
        sensors. This is how the agent pipeline 'discovers' PT-1042B."""
        model = self.sensor_model[sensor_id]
        eq = next(e for e in self.plant.equipment if e.id == model.equipment_id)
        alts = [s for s in eq.sensors if s.id != sensor_id and s.measurement == model.measurement]
        for nb_id in self.upstream.get(eq.id, []) + self.downstream.get(eq.id, []):
            nb = next(e for e in self.plant.equipment if e.id == nb_id)
            alts.extend(s for s in nb.sensors if s.measurement == model.measurement)
        # also correlated measurements on the same equipment (flow/vibration)
        if model.measurement == Measurement.PRESSURE:
            alts.extend(
                s for s in eq.sensors
                if s.measurement in (Measurement.FLOW, Measurement.VIBRATION) and s.id != sensor_id
            )
        return alts

    def snapshot(self) -> dict:
        """Full state for late-joining UI (replay then follow the bus)."""
        return {
            "t": self.t,
            "equipment": {
                eid: {"state": r.state.value, "capacity": r.capacity, "faults": sorted(r.faults)}
                for eid, r in self.eq.items()
            },
            "sensors": {
                sid: {"value": rt.value, "quality": rt.quality.value, "failed": rt.failed}
                for sid, rt in self.sensors.items()
            },
            "alarms": [a.model_dump() for a in self.alarms.values()],
            "incidents": [i.model_dump() for i in self.incidents.values()],
        }

    # -------------------------------------------------------------- helpers

    def create_incident(self, title: str, severity: AlarmSeverity, origin_equipment: str,
                        origin_sensor: str | None, failure_mode: str | None) -> Incident:
        self._incident_seq += 1
        hood = self.neighbors(origin_equipment, depth=2)["affected"]
        inc = Incident(
            id=f"INC-{1000 + self._incident_seq}",
            plant_id=self.plant.id,
            title=title,
            severity=severity,
            status=IncidentStatus.DETECTED,
            origin_equipment=origin_equipment,
            origin_sensor=origin_sensor,
            failure_mode=failure_mode,
            affected=hood,
            created_at=self.t,
        )
        self.incidents[inc.id] = inc
        return inc

    def sensor_model_span(self, eq_id: str, measurement: Measurement) -> float | None:
        m = self.sensor_model_span_obj(eq_id, measurement)
        return (m.normal_max - m.normal_min) if m else None

    def sensor_model_span_obj(self, eq_id: str, measurement: Measurement) -> Sensor | None:
        eq = next((e for e in self.plant.equipment if e.id == eq_id), None)
        if not eq:
            return None
        return next((s for s in eq.sensors if s.measurement == measurement), None)

    def _area_of(self, equipment_id: str) -> str:
        eq = next((e for e in self.plant.equipment if e.id == equipment_id), None)
        return eq.area_id if eq else ""
