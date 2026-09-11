"""
Project 117 — simulation data generator.

Single source of truth for both prebuilt plant scenes. Produces:
  - database/schema.sql
  - database/seed_oil_refinery.sql
  - database/seed_iron_steel_plant.sql
  - public/data/oil_refinery.json
  - public/data/iron_steel_plant.json

Run: python3 generate_seed.py
"""
import json
import random
import hashlib
from datetime import date, timedelta
from pathlib import Path

random.seed(117)

ROOT = Path(__file__).resolve().parent.parent
DB_DIR = ROOT / "database"
DATA_DIR = ROOT / "public" / "data"

TODAY = date(2026, 9, 10)

FAILURE_MODES = {
    "pump": ["seal wear", "cavitation", "bearing failure", "impeller erosion"],
    "valve": ["actuator failure", "seat leakage", "stem seizure", "positioner drift"],
    "tank": ["corrosion", "level sensor drift", "roof seal degradation"],
    "heat_exchanger": ["tube fouling", "tube leak", "shell corrosion"],
    "compressor": ["surge", "bearing wear", "valve plate fracture"],
    "column": ["tray fouling", "flooding", "corrosion at feed nozzle"],
    "reactor": ["catalyst deactivation", "refractory wear", "thermocouple drift"],
    "furnace": ["refractory wear", "burner failure", "tuyere blockage"],
    "conveyor": ["belt slip", "motor overheat", "idler bearing failure"],
    "motor": ["winding overheat", "bearing wear", "shaft misalignment"],
    "compressor_blower": ["bearing wear", "impeller imbalance"],
    "caster": ["mould wear", "roll misalignment", "spray nozzle blockage"],
    "mill_stand": ["roll wear", "bearing failure", "hydraulic leak"],
}

SENSOR_TYPES = {
    "PT": ("pressure", "bar", 2, 22),
    "TT": ("temperature", "C", 40, 480),
    "FT": ("flow", "m3/h", 10, 600),
    "LT": ("level", "%", 10, 95),
    "VT": ("vibration", "mm/s", 0.5, 7.0),
}

TAG_PREFIX = {
    "pump": "P", "valve": "V", "tank": "TK", "heat_exchanger": "E",
    "compressor": "C", "column": "CL", "reactor": "R", "furnace": "F",
    "conveyor": "CV", "motor": "M", "compressor_blower": "B", "caster": "CST",
    "mill_stand": "MS",
}


def make_equipment(counter, zone_id, etype, plant):
    tag_no = counter[etype]
    counter[etype] += 1
    tag = f"{TAG_PREFIX[etype]}-{plant['tag_base']}{tag_no:02d}"
    install = TODAY - timedelta(days=random.randint(365 * 2, 365 * 22))
    lifespan = random.choice([10, 12, 15, 18, 20, 25])
    age_years = (TODAY - install).days / 365.0
    ratio = age_years / lifespan
    status = "normal"
    if ratio > 0.95:
        status = "warning"
    if ratio > 1.05:
        status = "critical"
    last_inspection = TODAY - timedelta(days=random.randint(5, 220))
    eq_id = f"{plant['id']}-{tag}"
    return {
        "id": eq_id,
        "tag": tag,
        "type": etype,
        "zone_id": zone_id,
        "install_date": install.isoformat(),
        "expected_lifespan_years": lifespan,
        "age_years": round(age_years, 1),
        "last_inspection": last_inspection.isoformat(),
        "status": status,
        "failure_modes": FAILURE_MODES[etype],
    }


def make_sensor(eq, idx):
    stype = random.choice(list(SENSOR_TYPES.keys()))
    label, unit, lo, hi = SENSOR_TYPES[stype]
    current = round(random.uniform(lo, hi), 1)
    return {
        "id": f"{eq['id']}-SEN{idx}",
        "equipment_id": eq["id"],
        "tag": f"{stype}-{eq['tag']}{idx}",
        "type": stype,
        "label": label,
        "unit": unit,
        "normal_min": lo,
        "normal_max": hi,
        "current_value": current,
    }


def build_plant(plant):
    counter = {k: 1 for k in TAG_PREFIX}
    equipment = []
    sensors = []
    zones_out = []
    for zi, zone in enumerate(plant["zones"]):
        zones_out.append({"id": f"{plant['id']}-zone{zi}", "name": zone["name"], "sequence": zi})
        zone_id = zones_out[-1]["id"]
        for etype, count in zone["equipment"].items():
            for _ in range(count):
                eq = make_equipment(counter, zone_id, etype, plant)
                equipment.append(eq)
                n_sensors = 1 if etype in ("valve", "conveyor", "motor") else random.choice([1, 2])
                for si in range(1, n_sensors + 1):
                    sensors.append(make_sensor(eq, si))

    # connections: chain equipment within a zone in creation order, then bridge
    # the last equipment of each zone to the first of the next zone.
    connections = []
    by_zone = {}
    for eq in equipment:
        by_zone.setdefault(eq["zone_id"], []).append(eq)
    zone_ids = [z["id"] for z in zones_out]
    for zid in zone_ids:
        items = by_zone.get(zid, [])
        for a, b in zip(items, items[1:]):
            connections.append({
                "id": f"conn-{a['id']}-{b['id']}",
                "source": a["id"], "target": b["id"], "kind": "pipe",
            })
    for za, zb in zip(zone_ids, zone_ids[1:]):
        items_a, items_b = by_zone.get(za, []), by_zone.get(zb, [])
        if items_a and items_b:
            connections.append({
                "id": f"conn-{items_a[-1]['id']}-{items_b[0]['id']}",
                "source": items_a[-1]["id"], "target": items_b[0]["id"], "kind": "pipe",
            })
    # sensor wires (signal, not process pipe)
    for s in sensors:
        connections.append({
            "id": f"wire-{s['id']}",
            "source": s["id"], "target": s["equipment_id"], "kind": "wire",
        })

    return {
        "plant_id": plant["id"],
        "plant_name": plant["name"],
        "zones": zones_out,
        "equipment": equipment,
        "sensors": sensors,
        "connections": connections,
    }


PLANTS = [
    {
        "id": "refinery",
        "name": "Oil refinery",
        "tag_base": "1",
        "zones": [
            {"name": "Crude distillation unit", "equipment": {
                "column": 2, "heat_exchanger": 6, "pump": 6, "valve": 8}},
            {"name": "Vacuum distillation unit", "equipment": {
                "column": 1, "heat_exchanger": 4, "pump": 4, "valve": 6}},
            {"name": "Fluid catalytic cracker", "equipment": {
                "reactor": 2, "compressor": 3, "pump": 4, "valve": 6}},
            {"name": "Hydrotreater", "equipment": {
                "reactor": 2, "compressor": 2, "pump": 3, "valve": 5}},
            {"name": "Storage and tank farm", "equipment": {
                "tank": 10, "pump": 4, "valve": 6}},
            {"name": "Utilities and pipeline network", "equipment": {
                "compressor_blower": 3, "pump": 4, "valve": 6, "motor": 4}},
        ],
    },
    {
        "id": "iron_steel",
        "name": "Iron and steel plant",
        "tag_base": "2",
        "zones": [
            {"name": "Raw material handling", "equipment": {
                "conveyor": 10, "motor": 8, "valve": 3}},
            {"name": "Sinter plant", "equipment": {
                "furnace": 2, "conveyor": 6, "motor": 6, "valve": 4}},
            {"name": "Blast furnace", "equipment": {
                "furnace": 2, "compressor_blower": 4, "pump": 5, "valve": 7}},
            {"name": "Basic oxygen furnace", "equipment": {
                "furnace": 2, "compressor": 3, "valve": 5}},
            {"name": "Continuous casting", "equipment": {
                "caster": 4, "pump": 5, "motor": 5}},
            {"name": "Hot and cold rolling mill", "equipment": {
                "mill_stand": 8, "motor": 10, "pump": 5}},
        ],
    },
]


def to_sql_value(v):
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        v = ",".join(v)
    return "'" + str(v).replace("'", "''") + "'"


def write_sql(plant_data, path):
    lines = [f"-- Seed data for {plant_data['plant_name']} (generated, seed=117)\n"]
    for z in plant_data["zones"]:
        lines.append(
            "INSERT INTO zones (id, plant_id, name, sequence) VALUES "
            f"({to_sql_value(z['id'])}, {to_sql_value(plant_data['plant_id'])}, "
            f"{to_sql_value(z['name'])}, {z['sequence']});"
        )
    for e in plant_data["equipment"]:
        lines.append(
            "INSERT INTO equipment (id, plant_id, zone_id, tag, type, install_date, "
            "expected_lifespan_years, last_inspection, status, failure_modes) VALUES "
            f"({to_sql_value(e['id'])}, {to_sql_value(plant_data['plant_id'])}, "
            f"{to_sql_value(e['zone_id'])}, {to_sql_value(e['tag'])}, {to_sql_value(e['type'])}, "
            f"{to_sql_value(e['install_date'])}, {e['expected_lifespan_years']}, "
            f"{to_sql_value(e['last_inspection'])}, {to_sql_value(e['status'])}, "
            f"{to_sql_value(e['failure_modes'])});"
        )
    for s in plant_data["sensors"]:
        lines.append(
            "INSERT INTO sensors (id, equipment_id, tag, type, label, unit, normal_min, "
            "normal_max, current_value) VALUES "
            f"({to_sql_value(s['id'])}, {to_sql_value(s['equipment_id'])}, {to_sql_value(s['tag'])}, "
            f"{to_sql_value(s['type'])}, {to_sql_value(s['label'])}, {to_sql_value(s['unit'])}, "
            f"{s['normal_min']}, {s['normal_max']}, {s['current_value']});"
        )
    for c in plant_data["connections"]:
        lines.append(
            "INSERT INTO connections (id, plant_id, source_id, target_id, kind) VALUES "
            f"({to_sql_value(c['id'])}, {to_sql_value(plant_data['plant_id'])}, "
            f"{to_sql_value(c['source'])}, {to_sql_value(c['target'])}, {to_sql_value(c['kind'])});"
        )
    path.write_text("\n".join(lines) + "\n")


def main():
    DB_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    summary = []
    for plant in PLANTS:
        data = build_plant(plant)
        json_path = DATA_DIR / f"{plant['id'] if plant['id'] != 'iron_steel' else 'iron_steel_plant'}.json"
        json_path = DATA_DIR / ("oil_refinery.json" if plant["id"] == "refinery" else "iron_steel_plant.json")
        json_path.write_text(json.dumps(data, indent=2))
        sql_path = DB_DIR / (
            "seed_oil_refinery.sql" if plant["id"] == "refinery" else "seed_iron_steel_plant.sql"
        )
        write_sql(data, sql_path)
        summary.append((plant["name"], len(data["equipment"]), len(data["sensors"]), len(data["connections"])))
    print("Generated:")
    for name, eq, se, co in summary:
        print(f"  {name}: {eq} equipment, {se} sensors, {co} connections")


if __name__ == "__main__":
    main()
