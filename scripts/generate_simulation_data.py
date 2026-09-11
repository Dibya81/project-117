#!/usr/bin/env python3
"""Generate the synthetic demonstration plants (refinery + steel).

Deterministic by construction: same code = same dataset, always. Tags follow
an industrial convention (documented in docs/simulation/SIMULATION_INTEGRATION.md):

    P- pumps · V- valves · TK- tanks · VS- vessels · COL- columns
    E- exchangers · F- furnaces · C- compressors · M- motors · CV- conveyors
    PT/TT/FT/LT/AT transmitters (A/B suffix = redundant pair)
    VIB-/RPM-/A-/KW- machinery instruments · GD-/LK- detectors · XV-/ESD- safety

The refinery's crude charge pump is tagged P-1042 with a redundant pressure
pair PT-1042A/B — a deliberately *named asset* in a real plant, not a
hardcoded rule. The engine has no tag-specific logic.

Usage: python3 scripts/generate_simulation_data.py
"""

from __future__ import annotations

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "data" / "simulation"

R = random.Random(117)

MEAS = {
    "pressure": "bar", "temperature": "°C", "flow": "m³/h", "level": "%",
    "vibration": "mm/s", "rpm": "rpm", "current": "A", "power": "kW",
    "gas": "ppm", "leak": "0/1", "position": "%", "speed": "m/s",
}

TAG_PREFIX = {
    "pump": "P", "valve": "V", "tank": "TK", "vessel": "VS", "column": "COL",
    "exchanger": "E", "furnace": "F", "compressor": "C", "motor": "M",
    "conveyor": "CV", "safety": "ESD", "utility": "UT",
}

MEAS_PREFIX = {
    "pressure": "PT", "temperature": "TT", "flow": "FT", "level": "LT",
    "vibration": "VIB", "rpm": "RPM", "current": "A", "power": "KW",
    "gas": "GD", "leak": "LK", "position": "ZT", "speed": "ST",
}

MAKERS = ["SynthWorks", "Flowdyne", "Rotodyne", "Helix Process", "Vulcan Industrial", "Atlas Pumps"]


def rngs(nominal: float, spread: float = 0.08) -> dict:
    return {
        "nominal": round(nominal, 2),
        "normal_min": round(nominal * 0.96, 2),
        "normal_max": round(nominal * 1.04, 2),
        "warning_min": round(nominal * 0.9, 2),
        "warning_max": round(nominal * 1.08, 2),
        "critical_min": round(nominal * 0.82, 2),
        "critical_max": round(nominal * 1.16, 2),
    }


def sensor(tag: str, eq_id: str, measurement: str, nominal: float, *, detector=False, drift=0.0) -> dict:
    base = rngs(nominal)
    if detector:
        base = {"nominal": 0, "normal_min": 0, "normal_max": 0.2, "warning_min": 0.2, "warning_max": 0.5, "critical_min": 0.5, "critical_max": 1.0}
    return {
        "id": f"s-{tag}", "tag": tag, "equipment_id": eq_id, "measurement": measurement,
        "unit": MEAS[measurement], "sampling_ms": 1000,
        "noise": 0.010, "drift_rate": drift, "is_detector": detector, **base,
    }


def sensors_for(kind: str, eq_id: str, num: str, duty: float) -> list[dict]:
    s: list[dict] = []
    p = MEAS_PREFIX
    if kind == "pump":
        s += [
            sensor(f"{p['pressure']}-{num}A", eq_id, "pressure", 18.5 * duty),
            sensor(f"{p['pressure']}-{num}B", eq_id, "pressure", 18.5 * duty),
            sensor(f"{p['flow']}-{num}", eq_id, "flow", 96 * duty),
            sensor(f"{p['temperature']}-{num}", eq_id, "temperature", 73),
            sensor(f"{p['vibration']}-{num}", eq_id, "vibration", 5.7, drift=0.02),
            sensor(f"{p['current']}-{num}", eq_id, "current", 84 * duty),
            sensor(f"{p['power']}-{num}", eq_id, "power", 410 * duty),
        ]
    elif kind == "valve":
        s += [sensor(f"{p['position']}-{num}", eq_id, "position", 62)]
        if R.random() < 0.5:
            s.append(sensor(f"{p['pressure']}-{num}", eq_id, "pressure", 14.5 * duty))
    elif kind == "tank":
        s += [
            sensor(f"{p['level']}-{num}", eq_id, "level", 62),
            sensor(f"{p['temperature']}-{num}", eq_id, "temperature", 41),
        ]
    elif kind in ("vessel", "column"):
        s += [
            sensor(f"{p['pressure']}-{num}", eq_id, "pressure", 9.5 * duty),
            sensor(f"{p['temperature']}-{num}", eq_id, "temperature", 188 * duty),
            sensor(f"{p['level']}-{num}", eq_id, "level", 55),
        ]
    elif kind == "exchanger":
        s += [
            sensor(f"{p['temperature']}-{num}I", eq_id, "temperature", 210 * duty),
            sensor(f"{p['temperature']}-{num}O", eq_id, "temperature", 188 * duty),
            sensor(f"{p['flow']}-{num}", eq_id, "flow", 88 * duty),
        ]
    elif kind == "furnace":
        s += [
            sensor(f"{p['temperature']}-{num}", eq_id, "temperature", 620 * duty),
            sensor(f"{p['pressure']}-{num}", eq_id, "pressure", 3.4 * duty),
            sensor(f"{p['gas']}-{num}", eq_id, "gas", 12, detector=True),
        ]
    elif kind == "compressor":
        s += [
            sensor(f"{p['pressure']}-{num}S", eq_id, "pressure", 6.8 * duty),
            sensor(f"{p['pressure']}-{num}D", eq_id, "pressure", 19.5 * duty),
            sensor(f"{p['vibration']}-{num}", eq_id, "vibration", 5.7, drift=0.02),
            sensor(f"{p['rpm']}-{num}", eq_id, "rpm", 8840),
            sensor(f"{p['temperature']}-{num}", eq_id, "temperature", 79),
        ]
    elif kind == "motor":
        s += [
            sensor(f"{p['current']}-{num}", eq_id, "current", 96 * duty),
            sensor(f"{p['power']}-{num}", eq_id, "power", 460 * duty),
            sensor(f"{p['rpm']}-{num}", eq_id, "rpm", 1480),
        ]
    elif kind == "conveyor":
        s += [
            sensor(f"{p['speed']}-{num}", eq_id, "speed", 2.2),
            sensor(f"{p['current']}-{num}", eq_id, "current", 64),
        ]
    elif kind == "safety":
        s += [
            sensor(f"{p['gas']}-{num}", eq_id, "gas", 0, detector=True),
            sensor(f"{p['leak']}-{num}", eq_id, "leak", 0, detector=True),
        ]
    elif kind == "utility":
        s += [sensor(f"{p['flow']}-{num}", eq_id, "flow", 120 * duty)]
    return s


FAILURE_MODES = [
    {"id": "sensor_failure", "name": "Sensor failure", "applies_to": ["pressure"], "mechanism": "sensor", "magnitude": 1.0, "description": "Primary measurement element fails; quality goes BAD."},
    {"id": "instrument_drift", "name": "Instrument drift", "applies_to": ["temperature", "pressure", "flow"], "mechanism": "drift", "magnitude": 1.0, "description": "Transmitter reading drifts away from true value."},
    {"id": "bearing_wear", "name": "Bearing wear", "applies_to": ["pump", "compressor", "motor"], "mechanism": "degrade", "magnitude": 0.25, "description": "Vibration signature rises; capacity degrades."},
    {"id": "cavitation", "name": "Pump cavitation", "applies_to": ["pump"], "mechanism": "degrade", "magnitude": 0.4, "description": "Net positive suction head lost; flow and pressure become unstable."},
    {"id": "bearing_overheat", "name": "Bearing overheating", "applies_to": ["pump", "motor", "compressor"], "mechanism": "drift", "magnitude": 1.0, "description": "Bearing temperature climbs toward trip."},
    {"id": "valve_stuck", "name": "Valve failure (stuck)", "applies_to": ["valve"], "mechanism": "degrade", "magnitude": 0.6, "description": "Valve stops responding; flow restricted."},
    {"id": "seal_leak", "name": "Seal failure / oil leak", "applies_to": ["pump", "vessel"], "mechanism": "leak", "magnitude": 0.45, "description": "Mechanical seal failure; medium escapes, detectors trip."},
    {"id": "pressure_surge", "name": "Pressure surge", "applies_to": ["vessel", "column", "exchanger"], "mechanism": "surge", "magnitude": 0.35, "description": "Upstream excursion drives pressures over envelope."},
    {"id": "trip", "name": "Equipment trip", "applies_to": ["compressor", "pump", "motor"], "mechanism": "stop", "magnitude": 1.0, "description": "Machine trips offline; dependent flow collapses."},
    {"id": "fouling", "name": "Heat exchanger fouling", "applies_to": ["exchanger"], "mechanism": "degrade", "magnitude": 0.3, "description": "Fouling factor rises; duty and outlet temperature sag."},
    {"id": "overload", "name": "Motor overload", "applies_to": ["motor", "conveyor"], "mechanism": "degrade", "magnitude": 0.5, "description": "Current draw exceeds rated; thermal protection near."},
    {"id": "esd", "name": "Emergency shutdown", "applies_to": ["safety"], "mechanism": "stop", "magnitude": 1.0, "description": "Safety system initiates a controlled area shutdown."},
]

FM_BY_KIND = {
    "pump": ["sensor_failure", "instrument_drift", "bearing_wear", "cavitation", "bearing_overheat", "seal_leak", "trip"],
    "valve": ["valve_stuck", "instrument_drift"],
    "tank": ["instrument_drift"],
    "vessel": ["pressure_surge", "seal_leak", "instrument_drift"],
    "column": ["pressure_surge", "instrument_drift"],
    "exchanger": ["fouling", "pressure_surge", "instrument_drift"],
    "furnace": ["pressure_surge", "instrument_drift"],
    "compressor": ["bearing_wear", "bearing_overheat", "trip", "sensor_failure"],
    "motor": ["overload", "bearing_overheat", "trip"],
    "conveyor": ["overload", "trip"],
    "safety": ["esd"],
    "utility": ["instrument_drift"],
}


def meta(num: int, kind: str) -> dict:
    return {
        "manufacturer": MAKERS[num % len(MAKERS)],
        "model": f"{TAG_PREFIX[kind]}-{100 + (num % 40)}X",
        "installed": f"{2015 + (num % 9)}-{(num % 12) + 1:02d}-{(num % 27) + 1:02d}",
        "last_inspection": f"2026-{(num % 8) + 1:02d}-{(num % 27) + 1:02d}",
    }


class PlantBuilder:
    def __init__(self, pid: str, name: str, industry: str) -> None:
        self.plant = {"id": pid, "name": name, "industry": industry}
        self.areas: list[dict] = []
        self.equipment: list[dict] = []
        self.connections: list[dict] = []
        self._conn = 0
        self._by_tag: dict[str, str] = {}

    def area(self, aid: str, name: str, col: int, row: int) -> None:
        self.areas.append({"id": aid, "name": name, "x": 40 + col * 300, "y": 40 + row * 210, "w": 280, "h": 180})

    def equip(self, tag: str, name: str, kind: str, area: str, idx: int, duty: float = 1.0) -> str:
        num = "".join(ch for ch in tag if ch.isdigit()) or "0"
        eid = f"e-{tag}"
        self._by_tag[tag] = eid
        area_info = next(a for a in self.areas if a["id"] == area)
        x = area_info["x"] + 34 + (idx % 4) * 62
        y = area_info["y"] + 44 + (idx // 4) * 62
        self.equipment.append({
            "id": eid, "tag": tag, "name": name, "kind": kind, "area_id": area,
            "x": x, "y": y, "criticality": 1 + (int(num[-1]) if num and num[-1].isdigit() else 1) % 3,
            "capacity": 1.0, "state": "normal",
            "sensors": sensors_for(kind, eid, num, duty),
            "failure_modes": FM_BY_KIND.get(kind, ["instrument_drift"]),
            **meta(int(num) if num.isdigit() else 42, kind),
        })
        return eid

    def pipe(self, src_tag: str, dst_tag: str, medium: str = "process", capacity: float = 100.0) -> None:
        self._conn += 1
        self.connections.append({
            "id": f"pl-{self._conn:03d}", "kind": "pipe",
            "source": self._by_tag[src_tag], "target": self._by_tag[dst_tag],
            "medium": medium, "capacity": capacity, "flow": 0.0, "status": "normal", "leaking": False, "enabled": True,
        })

    def dump(self, outdir: Path, scenarios: list[dict]) -> dict:
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "plant.json").write_text(json.dumps(self.plant, indent=2))
        (outdir / "areas.json").write_text(json.dumps(self.areas, indent=2))
        (outdir / "equipment.json").write_text(json.dumps(self.equipment, indent=2))
        (outdir / "connections.json").write_text(json.dumps(self.connections, indent=2))
        (outdir / "failure_modes.json").write_text(json.dumps(FAILURE_MODES, indent=2))
        (outdir / "scenarios.json").write_text(json.dumps(scenarios, indent=2))
        sensors = sum(len(e["sensors"]) for e in self.equipment)
        return {"equipment": len(self.equipment), "sensors": sensors, "connections": len(self.connections), "areas": len(self.areas)}


# ===================================================================
#  OIL REFINERY — 18 areas, ~60 equipment, ~110 instruments
# ===================================================================

def build_refinery() -> dict:
    b = PlantBuilder("refinery", "Meridian Synthetic Refinery", "refining")

    A = [
        ("crude-receiving", "Crude Receiving", 0, 0), ("crude-storage", "Crude Storage", 1, 0),
        ("desalter", "Desalter", 2, 0), ("cdu", "Crude Distillation", 3, 0),
        ("vdu", "Vacuum Distillation", 4, 0), ("nht", "Naphtha Hydrotreater", 5, 0),
        ("reformer", "Catalytic Reforming", 0, 1), ("fcc", "FCC", 1, 1),
        ("dht", "Diesel Hydrotreater", 2, 1), ("sulfur", "Sulfur Recovery", 3, 1),
        ("hydrogen", "Hydrogen", 4, 1), ("product-storage", "Product Storage", 5, 1),
        ("utilities", "Utilities", 0, 2), ("steam", "Steam", 1, 2),
        ("cooling", "Cooling Water", 2, 2), ("flare", "Flare", 3, 2),
        ("wastewater", "Wastewater", 4, 2), ("safety", "Safety Systems", 5, 2),
    ]
    for aid, name, c, r in A:
        b.area(aid, name, c, r)

    # --- Crude receiving ---------------------------------------------------
    b.equip("P-1001", "Offloading Pump A", "pump", "crude-receiving", 0, 1.1)
    b.equip("P-1002", "Offloading Pump B", "pump", "crude-receiving", 1, 1.1)
    b.equip("V-1003", "Receiving Header Valve", "valve", "crude-receiving", 2)
    b.equip("E-1004", "Crude Preheater", "exchanger", "crude-receiving", 3)

    # --- Crude storage ------------------------------------------------------
    b.equip("TK-1101", "Crude Tank 1", "tank", "crude-storage", 0)
    b.equip("TK-1102", "Crude Tank 2", "tank", "crude-storage", 1)
    b.equip("V-1103", "Tank Outlet Valve", "valve", "crude-storage", 2)

    # --- Desalter -----------------------------------------------------------
    b.equip("VS-1201", "Desalter Vessel", "vessel", "desalter", 0)
    b.equip("P-1202", "Desalter Water Pump", "pump", "desalter", 1, 0.6)
    b.equip("V-1203", "Brine Outlet Valve", "valve", "desalter", 2)

    # --- CDU (the named charge pump lives here) -----------------------------
    b.equip("P-1042", "Crude Charge Pump", "pump", "cdu", 0, 1.0)   # PT-1042A/B, FT-1042, VIB-1042
    b.equip("F-1043", "Crude Charge Heater", "furnace", "cdu", 1)
    b.equip("COL-1044", "Atmospheric Column", "column", "cdu", 2)
    b.equip("E-1045", "Overhead Condenser", "exchanger", "cdu", 3)
    b.equip("VS-1046", "Reflux Drum", "vessel", "cdu", 4, 0.8)
    b.equip("V-1047", "Column Feed Valve", "valve", "cdu", 5)

    # --- VDU ----------------------------------------------------------------
    b.equip("P-1051", "VDU Feed Pump", "pump", "vdu", 0, 0.9)
    b.equip("COL-1052", "Vacuum Column", "column", "vdu", 1)
    b.equip("C-1053", "Vacuum Ejector Compressor", "compressor", "vdu", 2, 0.7)
    b.equip("E-1054", "Vacuum Resid Cooler", "exchanger", "vdu", 3)

    # --- Naphtha hydrotreater ------------------------------------------------
    b.equip("P-1061", "NHT Feed Pump", "pump", "nht", 0, 0.8)
    b.equip("VS-1062", "NHT Reactor", "vessel", "nht", 1, 1.2)
    b.equip("E-1063", "NHT Effluent Cooler", "exchanger", "nht", 2)
    b.equip("V-1064", "Stripper Level Valve", "valve", "nht", 3)

    # --- Reformer ------------------------------------------------------------
    b.equip("C-1071", "Reformer Recycle Compressor", "compressor", "reformer", 0, 1.0)
    b.equip("F-1072", "Reformer Charge Heater", "furnace", "reformer", 1, 0.9)
    b.equip("VS-1073", "Reformer Separator", "vessel", "reformer", 2, 0.8)

    # --- FCC ----------------------------------------------------------------
    b.equip("VS-1081", "FCC Reactor", "vessel", "fcc", 0, 1.4)
    b.equip("C-1082", "Main Air Blower", "compressor", "fcc", 1, 1.3)
    b.equip("E-1083", "FCC Slurry Cooler", "exchanger", "fcc", 2)
    b.equip("P-1084", "FCC Feed Pump", "pump", "fcc", 3, 1.2)

    # --- Diesel hydrotreater -------------------------------------------------
    b.equip("P-1091", "DHT Feed Pump", "pump", "dht", 0, 0.9)
    b.equip("VS-1092", "DHT Reactor", "vessel", "dht", 1, 1.1)
    b.equip("E-1093", "DHT Product Cooler", "exchanger", "dht", 2)

    # --- Sulfur recovery -----------------------------------------------------
    b.equip("C-1125", "Sour Gas Compressor", "compressor", "sulfur", 0, 0.7)
    b.equip("VS-1126", "Amine Contactor", "vessel", "sulfur", 1, 0.8)
    b.equip("P-1127", "Lean Amine Pump", "pump", "sulfur", 2, 0.6)

    # --- Hydrogen ------------------------------------------------------------
    b.equip("F-1111", "SMR Furnace", "furnace", "hydrogen", 0, 1.1)
    b.equip("C-1112", "Hydrogen Compressor", "compressor", "hydrogen", 1, 0.9)
    b.equip("VS-1113", "PSA Vessel", "vessel", "hydrogen", 2, 0.7)

    # --- Product storage -----------------------------------------------------
    b.equip("TK-1121", "Naphtha Tank", "tank", "product-storage", 0)
    b.equip("TK-1122", "Diesel Tank", "tank", "product-storage", 1)
    b.equip("TK-1123", "Jet Tank", "tank", "product-storage", 2)
    b.equip("P-1124", "Product Loading Pump", "pump", "product-storage", 3, 0.8)

    # --- Utilities ------------------------------------------------------------
    b.equip("P-1131", "Cooling Water Pump A", "pump", "cooling", 0, 1.3)
    b.equip("P-1132", "Cooling Water Pump B", "pump", "cooling", 1, 1.3)
    b.equip("UT-1133", "Cooling Tower Cell", "utility", "cooling", 2, 1.2)
    b.equip("F-1141", "Steam Boiler", "furnace", "steam", 0, 1.0)
    b.equip("P-1142", "Boiler Feed Pump", "pump", "steam", 1, 0.9)
    b.equip("M-1143", "BFD Fan Motor", "motor", "steam", 2, 0.8)
    b.equip("UT-1151", "Instrument Air Package", "utility", "utilities", 0, 0.8)
    b.equip("C-1152", "Plant Air Compressor", "compressor", "utilities", 1, 0.7)
    b.equip("UT-1161", "Flare Stack", "utility", "flare", 0, 0.4)
    b.equip("VS-1162", "Flare KO Drum", "vessel", "flare", 1, 0.5)
    b.equip("P-1171", "Wastewater Lift Pump", "pump", "wastewater", 0, 0.5)
    b.equip("VS-1172", "API Separator", "vessel", "wastewater", 1, 0.6)
    b.equip("ESD-1181", "Fire & Gas Panel", "safety", "safety", 0)
    b.equip("ESD-1182", "Emergency Shutdown Valve", "safety", "safety", 1)

    # --- process piping (the causal graph) -----------------------------------
    b.pipe("P-1001", "TK-1101", "crude", 140)
    b.pipe("P-1002", "TK-1102", "crude", 140)
    b.pipe("TK-1101", "V-1103", "crude", 120)
    b.pipe("V-1103", "P-1042", "crude", 120)
    b.pipe("P-1042", "E-1004", "crude", 115)
    b.pipe("E-1004", "VS-1201", "crude", 110)
    b.pipe("VS-1201", "F-1043", "crude", 105)
    b.pipe("F-1043", "V-1047", "crude", 100)
    b.pipe("V-1047", "COL-1044", "crude", 100)
    b.pipe("COL-1044", "E-1045", "vapor", 60)
    b.pipe("E-1045", "VS-1046", "naphtha", 45)
    b.pipe("COL-1044", "P-1051", "atm-resid", 55)
    b.pipe("P-1051", "COL-1052", "atm-resid", 55)
    b.pipe("COL-1052", "C-1053", "vacuum-gas", 30)
    b.pipe("COL-1052", "E-1054", "vac-resid", 40)
    b.pipe("VS-1046", "P-1061", "naphtha", 40)
    b.pipe("P-1061", "VS-1062", "naphtha", 40)
    b.pipe("VS-1062", "E-1063", "naphtha", 38)
    b.pipe("E-1063", "TK-1121", "naphtha", 38)
    b.pipe("COL-1044", "P-1084", "vgo", 60)
    b.pipe("P-1084", "VS-1081", "vgo", 60)
    b.pipe("VS-1081", "E-1083", "slurry", 45)
    b.pipe("C-1082", "VS-1081", "air", 80)
    b.pipe("COL-1044", "P-1091", "diesel", 45)
    b.pipe("P-1091", "VS-1092", "diesel", 45)
    b.pipe("VS-1092", "E-1093", "diesel", 42)
    b.pipe("E-1093", "TK-1122", "diesel", 42)
    b.pipe("C-1125", "VS-1126", "sour-gas", 25)
    b.pipe("P-1127", "VS-1126", "amine", 20)
    b.pipe("F-1111", "C-1112", "hydrogen", 30)
    b.pipe("C-1112", "VS-1113", "hydrogen", 28)
    b.pipe("VS-1113", "VS-1062", "hydrogen", 10)
    b.pipe("VS-1113", "VS-1092", "hydrogen", 10)
    b.pipe("P-1131", "E-1045", "water", 200)
    b.pipe("P-1132", "E-1054", "water", 180)
    b.pipe("UT-1133", "P-1131", "water", 400)
    b.pipe("F-1141", "COL-1044", "steam", 25)
    b.pipe("P-1142", "F-1141", "water", 30)
    b.pipe("M-1143", "F-1141", "air", 60)
    b.pipe("C-1152", "UT-1151", "air", 50)
    b.pipe("VS-1162", "UT-1161", "gas", 15)
    b.pipe("P-1171", "VS-1172", "wastewater", 35)
    b.pipe("E-1004", "P-1171", "wastewater", 10)
    b.pipe("VS-1201", "P-1171", "brine", 12)
    b.pipe("P-1202", "VS-1201", "water", 15)
    b.pipe("VS-1201", "V-1203", "brine", 12)
    b.pipe("P-1002", "V-1003", "crude", 60)
    b.pipe("V-1003", "TK-1102", "crude", 60)
    b.pipe("E-1063", "F-1072", "naphtha", 30)
    b.pipe("F-1072", "VS-1073", "reformate", 30)
    b.pipe("VS-1073", "C-1071", "gas", 20)
    b.pipe("C-1071", "F-1072", "recycle-gas", 20)
    b.pipe("VS-1073", "TK-1121", "reformate", 25)
    b.pipe("COL-1044", "TK-1123", "jet", 30)
    b.pipe("TK-1121", "P-1124", "naphtha", 35)
    b.pipe("TK-1122", "P-1124", "diesel", 35)
    b.pipe("VS-1062", "V-1064", "naphtha", 30)
    b.pipe("V-1064", "E-1063", "naphtha", 30)
    b.pipe("ESD-1181", "ESD-1182", "control", 0)
    b.pipe("ESD-1182", "V-1047", "control", 0)

    scenarios = refinery_scenarios()
    return b.dump(ROOT / "refinery", scenarios)


def refinery_scenarios() -> list[dict]:
    def step(at_s: float, mode: str, tag: str) -> dict:
        return {"at_s": at_s, "action": "inject_failure", "target": f"e-{tag}", "mode": mode}

    return [
        {"id": "sc-sensor-failure", "name": "PT-1042A sensor failure", "description": "Primary charge-pump pressure transmitter fails; redundant instrumentation must carry the process.", "steps": [step(5, "sensor_failure", "P-1042")]},
        {"id": "sc-cavitation", "name": "P-1042 pump cavitation", "description": "Suction starvation drives flow/pressure instability at the charge pump.", "steps": [step(5, "cavitation", "P-1042")]},
        {"id": "sc-bearing-overheat", "name": "C-1053 bearing overheating", "description": "Vacuum ejector compressor bearing temperature climbs toward trip.", "steps": [step(5, "bearing_overheat", "C-1053")]},
        {"id": "sc-valve-stuck", "name": "V-1047 feed valve stuck", "description": "Column feed valve stops responding mid-travel.", "steps": [step(5, "valve_stuck", "V-1047")]},
        {"id": "sc-oil-leak", "name": "P-1042 seal failure — oil leak", "description": "Mechanical seal fails; leak detector trips; safety response engages.", "steps": [step(5, "seal_leak", "P-1042")]},
        {"id": "sc-pressure-surge", "name": "COL-1044 pressure surge", "description": "Atmospheric column overpressure excursion.", "steps": [step(5, "pressure_surge", "COL-1044")]},
        {"id": "sc-temp-anomaly", "name": "E-1045 outlet temperature drift", "description": "Overhead condenser outlet transmitter drifts high.", "steps": [step(5, "instrument_drift", "E-1045")]},
        {"id": "sc-flow-restriction", "name": "V-1103 flow restriction", "description": "Tank outlet valve plugs; charge flow sags.", "steps": [step(5, "valve_stuck", "V-1103")]},
        {"id": "sc-compressor-trip", "name": "C-1082 main air blower trip", "description": "FCC air blower trips offline; reactor air starves.", "steps": [step(5, "trip", "C-1082")]},
        {"id": "sc-exchanger-fouling", "name": "E-1045 fouling", "description": "Overhead condenser fouls; duty declines.", "steps": [step(5, "fouling", "E-1045")]},
        {"id": "sc-motor-overload", "name": "M-1143 motor overload", "description": "BFD fan motor current over rated.", "steps": [step(5, "overload", "M-1143")]},
        {"id": "sc-esd", "name": "Emergency shutdown", "description": "F&G panel initiates controlled shutdown of the CDU feed path.", "steps": [step(5, "esd", "ESD-1182")]},
        {"id": "sc-cascade", "name": "Cascading failure — charge pump trip", "description": "P-1042 trips; downstream heater, column and product chain respond.", "steps": [step(5, "trip", "P-1042")]},
        {"id": "sc-drift", "name": "PT-1042A instrument drift", "description": "Charge pump pressure transmitter drifts away from its redundant twin.", "steps": [step(5, "instrument_drift", "P-1042")]},
    ]


# ===================================================================
#  IRON & STEEL — 17 areas, integrated plant
# ===================================================================

def build_steel() -> dict:
    b = PlantBuilder("steel", "Kalinga Synthetic Steelworks", "steel")

    A = [
        ("raw-material", "Raw Material Handling", 0, 0), ("sinter", "Sinter Plant", 1, 0),
        ("coke", "Coke Handling", 2, 0), ("blast-furnace", "Blast Furnace", 3, 0),
        ("hot-blast", "Hot Blast System", 4, 0), ("gas-cleaning", "Gas Cleaning", 5, 0),
        ("bof", "BOF Shop", 0, 1), ("ladle", "Secondary Metallurgy", 1, 1),
        ("casting", "Continuous Casting", 2, 1), ("reheat", "Reheating", 3, 1),
        ("rolling", "Hot Rolling", 4, 1), ("cooling", "Cooling", 5, 1),
        ("finishing", "Finishing", 0, 2), ("utilities", "Utilities", 1, 2),
        ("water", "Water Treatment", 2, 2), ("dust", "Dust Collection", 3, 2),
        ("safety", "Safety Systems", 4, 2),
    ]
    for aid, name, c, r in A:
        b.area(aid, name, c, r)

    # --- Raw material handling ------------------------------------------------
    b.equip("CV-2001", "Iron Ore Conveyor A", "conveyor", "raw-material", 0, 1.2)
    b.equip("CV-2002", "Iron Ore Conveyor B", "conveyor", "raw-material", 1, 1.2)
    b.equip("CV-2003", "Limestone Conveyor", "conveyor", "raw-material", 2, 0.8)
    b.equip("VS-2004", "Ore Crusher", "vessel", "raw-material", 3, 1.3)
    b.equip("VS-2005", "Vibrating Screen", "vessel", "raw-material", 4, 1.0)
    b.equip("TK-2006", "Ore Surge Bin", "tank", "raw-material", 5)

    # --- Sinter plant ----------------------------------------------------------
    b.equip("CV-2011", "Sinter Feed Conveyor", "conveyor", "sinter", 0, 1.0)
    b.equip("F-2012", "Sinter Strand Furnace", "furnace", "sinter", 1, 1.2)
    b.equip("M-2013", "Sinter Fan Motor", "motor", "sinter", 2, 1.1)
    b.equip("E-2014", "Sinter Cooler", "exchanger", "sinter", 3, 1.1)

    # --- Coke handling ---------------------------------------------------------
    b.equip("CV-2021", "Coke Conveyor", "conveyor", "coke", 0, 0.9)
    b.equip("TK-2022", "Coke Bin", "tank", "coke", 1)
    b.equip("V-2023", "Coke Charging Valve", "valve", "coke", 2)

    # --- Blast furnace ----------------------------------------------------------
    b.equip("F-2031", "Blast Furnace", "furnace", "blast-furnace", 0, 1.5)
    b.equip("C-2032", "Hot Blast Stove Compressor", "compressor", "blast-furnace", 1, 1.2)
    b.equip("P-2033", "Cast House Pump", "pump", "blast-furnace", 2, 0.7)
    b.equip("VS-2034", "Torpid Ladle Transfer", "vessel", "blast-furnace", 3, 1.0)

    # --- Hot blast ---------------------------------------------------------------
    b.equip("F-2041", "Hot Blast Stove A", "furnace", "hot-blast", 0, 1.3)
    b.equip("F-2042", "Hot Blast Stove B", "furnace", "hot-blast", 1, 1.3)
    b.equip("C-2043", "Cold Blast Blower", "compressor", "hot-blast", 2, 1.1)

    # --- Gas cleaning -------------------------------------------------------------
    b.equip("VS-2051", "Dustcatcher", "vessel", "gas-cleaning", 0, 0.9)
    b.equip("VS-2052", "Venturi Scrubber", "vessel", "gas-cleaning", 1, 0.9)
    b.equip("P-2053", "Scrubber Water Pump", "pump", "gas-cleaning", 2, 0.8)
    b.equip("V-2054", "Gas Bleeder Valve", "valve", "gas-cleaning", 3)

    # --- BOF shop ------------------------------------------------------------------
    b.equip("F-2061", "BOF Converter", "furnace", "bof", 0, 1.4)
    b.equip("C-2062", "Oxygen Lance Compressor", "compressor", "bof", 1, 1.0)
    b.equip("VS-2063", "BOF Charging Vessel", "vessel", "bof", 2, 1.1)
    b.equip("P-2064", "BOF Cooling Pump", "pump", "bof", 3, 0.9)

    # --- Secondary metallurgy ---------------------------------------------------------
    b.equip("VS-2071", "Ladle Furnace", "vessel", "ladle", 0, 1.0)
    b.equip("P-2072", "Argon Stirring Pump", "pump", "ladle", 1, 0.5)
    b.equip("VS-2073", "Vacuum Degasser", "vessel", "ladle", 2, 0.9)

    # --- Continuous casting ------------------------------------------------------------
    b.equip("VS-2081", "Tundish", "vessel", "casting", 0, 0.9)
    b.equip("P-2082", "Mold Cooling Pump", "pump", "casting", 1, 1.0)
    b.equip("E-2083", "Caster Spray Cooler", "exchanger", "casting", 2, 0.9)
    b.equip("M-2084", "Withdrawal Roll Motor", "motor", "casting", 3, 0.7)

    # --- Reheating ------------------------------------------------------------------------
    b.equip("F-2091", "Reheat Furnace", "furnace", "reheat", 0, 1.2)
    b.equip("P-2092", "Scale Wash Pump", "pump", "reheat", 1, 0.6)

    # --- Hot rolling ------------------------------------------------------------------------
    b.equip("M-2101", "Roughing Mill Motor", "motor", "rolling", 0, 1.3)
    b.equip("M-2102", "Finishing Mill Motor", "motor", "rolling", 1, 1.4)
    b.equip("P-2103", "Roll Cooling Pump", "pump", "rolling", 2, 0.9)
    b.equip("E-2104", "Lube Oil Cooler", "exchanger", "rolling", 3, 0.5)

    # --- Cooling ----------------------------------------------------------------------------
    b.equip("P-2111", "Cooling Tower Pump A", "pump", "cooling", 0, 1.2)
    b.equip("P-2112", "Cooling Tower Pump B", "pump", "cooling", 1, 1.2)
    b.equip("UT-2113", "Cooling Tower Cell", "utility", "cooling", 2, 1.1)

    # --- Finishing -----------------------------------------------------------------------------
    b.equip("M-2121", "Coiler Motor", "motor", "finishing", 0, 0.9)
    b.equip("V-2122", "Coil Transfer Valve", "valve", "finishing", 1)
    b.equip("TK-2123", "Finished Coil Bay", "tank", "finishing", 2)

    # --- Utilities / water / dust / safety ------------------------------------------------------
    b.equip("C-2131", "Plant Air Compressor", "compressor", "utilities", 0, 0.8)
    b.equip("UT-2132", "Oxygen Plant", "utility", "utilities", 1, 1.0)
    b.equip("P-2141", "Water Intake Pump", "pump", "water", 0, 1.0)
    b.equip("VS-2142", "Clarifier", "vessel", "water", 1, 0.7)
    b.equip("M-2151", "Baghouse Fan Motor", "motor", "dust", 0, 0.9)
    b.equip("VS-2152", "Baghouse", "vessel", "dust", 1, 0.8)
    b.equip("ESD-2161", "Fire & Gas Panel", "safety", "safety", 0)
    b.equip("ESD-2162", "BOF Emergency Lance Hoist", "safety", "safety", 1)

    # --- process chain ---------------------------------------------------------------------------
    b.pipe("CV-2001", "VS-2004", "ore", 220)
    b.pipe("CV-2002", "VS-2004", "ore", 220)
    b.pipe("VS-2004", "VS-2005", "ore", 200)
    b.pipe("VS-2005", "TK-2006", "ore", 190)
    b.pipe("TK-2006", "CV-2011", "ore", 180)
    b.pipe("CV-2003", "CV-2011", "flux", 60)
    b.pipe("CV-2011", "F-2012", "mix", 240)
    b.pipe("F-2012", "E-2014", "sinter", 200)
    b.pipe("M-2013", "F-2012", "air", 120)
    b.pipe("E-2014", "CV-2021", "sinter", 190)
    b.pipe("CV-2021", "TK-2022", "coke+sinter", 150)
    b.pipe("TK-2022", "V-2023", "charge", 140)
    b.pipe("V-2023", "F-2031", "charge", 140)
    b.pipe("C-2043", "F-2041", "air", 160)
    b.pipe("C-2043", "F-2042", "air", 160)
    b.pipe("F-2041", "F-2031", "hot-blast", 150)
    b.pipe("F-2042", "F-2031", "hot-blast", 150)
    b.pipe("F-2031", "VS-2051", "top-gas", 90)
    b.pipe("VS-2051", "VS-2052", "gas", 85)
    b.pipe("P-2053", "VS-2052", "water", 60)
    b.pipe("VS-2052", "V-2054", "gas", 80)
    b.pipe("F-2031", "VS-2034", "hot-metal", 120)
    b.pipe("VS-2034", "VS-2063", "hot-metal", 110)
    b.pipe("C-2062", "F-2061", "oxygen", 70)
    b.pipe("VS-2063", "F-2061", "charge", 110)
    b.pipe("P-2064", "F-2061", "water", 50)
    b.pipe("F-2061", "VS-2071", "steel", 100)
    b.pipe("P-2072", "VS-2071", "argon", 8)
    b.pipe("VS-2071", "VS-2073", "steel", 95)
    b.pipe("VS-2073", "VS-2081", "steel", 90)
    b.pipe("VS-2081", "E-2083", "steel", 85)
    b.pipe("P-2082", "E-2083", "water", 70)
    b.pipe("E-2083", "M-2084", "slab", 80)
    b.pipe("M-2084", "F-2091", "slab", 80)
    b.pipe("P-2092", "F-2091", "water", 40)
    b.pipe("F-2091", "M-2101", "slab", 85)
    b.pipe("M-2101", "M-2102", "strip", 80)
    b.pipe("P-2103", "M-2102", "water", 45)
    b.pipe("E-2104", "M-2102", "oil", 20)
    b.pipe("M-2102", "M-2121", "strip", 75)
    b.pipe("M-2121", "TK-2123", "coil", 70)
    b.pipe("P-2141", "VS-2142", "water", 300)
    b.pipe("VS-2142", "P-2111", "water", 250)
    b.pipe("P-2111", "UT-2113", "water", 240)
    b.pipe("P-2112", "UT-2113", "water", 240)
    b.pipe("UT-2113", "P-2082", "water", 120)
    b.pipe("UT-2113", "P-2103", "water", 90)
    b.pipe("UT-2132", "C-2062", "oxygen", 65)
    b.pipe("C-2131", "ESD-2161", "air", 30)
    b.pipe("M-2151", "VS-2152", "dust-air", 100)
    b.pipe("VS-2052", "M-2151", "dust-air", 60)
    b.pipe("C-2032", "F-2041", "air", 60)
    b.pipe("UT-2113", "P-2033", "water", 40)
    b.pipe("P-2033", "F-2031", "water", 40)
    b.pipe("M-2121", "V-2122", "coil", 70)
    b.pipe("V-2122", "TK-2123", "coil", 70)
    b.pipe("ESD-2161", "ESD-2162", "control", 0)
    b.pipe("ESD-2162", "F-2061", "control", 0)

    scenarios = steel_scenarios()
    return b.dump(ROOT / "steel", scenarios)


def steel_scenarios() -> list[dict]:
    def step(at_s: float, mode: str, tag: str) -> dict:
        return {"at_s": at_s, "action": "inject_failure", "target": f"e-{tag}", "mode": mode}

    return [
        {"id": "sc-sensor-failure", "name": "PT-2033A cast house pressure failure", "description": "Cast house pump pressure transmitter fails; alternates carry the reading.", "steps": [step(5, "sensor_failure", "P-2033")]},
        {"id": "sc-cavitation", "name": "P-2082 mold cooling cavitation", "description": "Caster mold cooling pump cavitates; strand cooling at risk.", "steps": [step(5, "cavitation", "P-2082")]},
        {"id": "sc-bearing-overheat", "name": "M-2102 finishing mill bearing overheat", "description": "Finishing mill motor bearing temperature climbs.", "steps": [step(5, "bearing_overheat", "M-2102")]},
        {"id": "sc-valve-stuck", "name": "V-2054 gas bleeder stuck", "description": "Gas cleaning bleeder valve fails to travel.", "steps": [step(5, "valve_stuck", "V-2054")]},
        {"id": "sc-oil-leak", "name": "P-2103 seal failure — oil leak", "description": "Roll cooling pump seal leaks near the mill.", "steps": [step(5, "seal_leak", "P-2103")]},
        {"id": "sc-pressure-surge", "name": "VS-2073 degasser pressure surge", "description": "Vacuum degasser pressure excursion.", "steps": [step(5, "pressure_surge", "VS-2073")]},
        {"id": "sc-temp-anomaly", "name": "F-2091 reheat temperature drift", "description": "Reheat furnace temperature transmitter drifts.", "steps": [step(5, "instrument_drift", "F-2091")]},
        {"id": "sc-flow-restriction", "name": "V-2023 charging valve restriction", "description": "Coke charging valve plugs.", "steps": [step(5, "valve_stuck", "V-2023")]},
        {"id": "sc-compressor-trip", "name": "C-2043 cold blast blower trip", "description": "Cold blast blower trips; stoves starve the furnace.", "steps": [step(5, "trip", "C-2043")]},
        {"id": "sc-exchanger-fouling", "name": "E-2104 lube oil cooler fouling", "description": "Lube oil cooler fouls; mill bearing temperatures rise.", "steps": [step(5, "fouling", "E-2104")]},
        {"id": "sc-motor-overload", "name": "M-2101 roughing mill overload", "description": "Roughing mill motor over current.", "steps": [step(5, "overload", "M-2101")]},
        {"id": "sc-esd", "name": "BOF emergency lance hoist", "description": "Safety system hoists the oxygen lance and isolates the converter.", "steps": [step(5, "esd", "ESD-2162")]},
        {"id": "sc-cascade", "name": "Cascading failure — mold cooling trip", "description": "P-2082 trips; caster thermal chain responds.", "steps": [step(5, "trip", "P-2082")]},
        {"id": "sc-drift", "name": "PT-2033A instrument drift", "description": "Cast house pressure transmitter drifts from its twin.", "steps": [step(5, "instrument_drift", "P-2033")]},
    ]


def main() -> None:
    for fn in (build_refinery, build_steel):
        stats = fn()
        print(f"{fn.__name__}: {stats['equipment']} equipment · {stats['sensors']} sensors · {stats['connections']} connections · {stats['areas']} areas · assets={stats['equipment'] + stats['sensors']}")


if __name__ == "__main__":
    main()
