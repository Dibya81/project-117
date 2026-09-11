#!/usr/bin/env python3
"""Generate the Project 117 refinery technical knowledge base.

Writes three deliverables from the live simulation register plus the U-200
console overlay dataset:

  1. data/knowledge/REFINERY-TECHNICAL-KNOWLEDGE-BASE.md  (master dossier)
  2. data/knowledge/refinery/NN-slug.md                    (22 ingest chunks)
  3. data/knowledge/refinery/manifest.json                 (chunk manifest)

Everything is deterministic: a fixed seed drives every generated number, and
no clock is read. Run it twice and the bytes are identical.

Run:  python3 scripts/generate_refinery_document.py
Exit code 1 if any consistency check fails.

Vocabulary note
---------------
The live register (`apps/web/public/simulation/refinery/equipment.json`) holds
58 tag numbers. The console's U-200 overlay (`data/demo/equipment/equipment.json`)
holds a separate six-asset legacy vocabulary (C-3, P-1042, V-2210, T-118,
E-340, P-2051). Both are real datasets shipped in this repo; this generator
declares the overlay explicitly in a crosswalk table rather than inventing a
tag or silently dropping the narrative. Every register tag emitted is checked
against equipment.json, every register sensor tag against its owning unit's
`sensors[]`, and every overlay tag against the demo dataset.
"""

from __future__ import annotations

import json
import random
import re
from datetime import date, timedelta
from pathlib import Path

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

SEED = 117017

ROOT = Path(__file__).resolve().parents[1]
SIM_DIR = ROOT / "apps/web/public/simulation/refinery"
DEMO_DIR = ROOT / "data/demo"
MASTER_PATH = ROOT / "data/knowledge" / "REFINERY-TECHNICAL-KNOWLEDGE-BASE.md"
CHUNK_DIR = ROOT / "data/knowledge" / "refinery"

PERIOD_START = date(2021, 6, 1)
PERIOD_END = date(2026, 9, 30)
DOC_DATE = "2026-09-30"
DOC_ID = "refinery-technical-knowledge-base"

# Narrative anchors fixed by the console/demo dataset. Never move these.
BEARING_DATE = date(2025, 3, 16)      # IR-198 / ME-198, WO-6120
ALIGN_DATE = date(2025, 11, 2)        # ME-212, WO-2417 re-execution
IR204_DATE = date(2026, 9, 6)         # IR-204 vibration survey
A51_DATE = date(2026, 9, 6)           # A-51 vibration above trend

# Crosswalk: overlay tag -> register twin. "exact" means the register asset
# carries the same tag string; "twin" is a functional correspondence; "partial"
# means the register asset covers only part of the overlay service.
CROSSWALK = [
    ("C-3", "Recycle Gas Compressor", "U-200 compression", "C-1071",
     "Reformer Recycle Compressor", "twin",
     "Register twin carries the same machine signature: VIB-1071 nominal 5.7 mm/s, "
     "RPM-1071 nominal 8,840 rpm, TT-1071 nominal 79 degC."),
    ("P-1042", "Feed Charge Pump", "U-200 charge", "P-1042",
     "Crude Charge Pump", "exact",
     "Same tag in both vocabularies; register area cdu, criticality class 3."),
    ("E-340", "Feed/Effluent Heat Exchanger", "U-200 exchangers", "E-1063",
     "NHT Effluent Cooler", "twin",
     "Hydrotreater effluent exchanger; register carries inlet/outlet temperature "
     "and tube-side flow."),
    ("T-118", "Intermediate Storage Tank", "Tank farm", "TK-1121",
     "Naphtha Tank", "twin",
     "Product-storage tank with level and temperature instrumentation."),
    ("V-2210", "Product Separator Vessel", "U-200 separation", "V-1047",
     "Column Feed Valve", "partial",
     "Register asset is the process valve with actuator position feedback; the "
     "overlay vessel itself has no register tag number."),
    ("P-2051", "Product Transfer Pump", "Tank farm", "P-1124",
     "Product Loading Pump", "partial",
     "Same duty family; overlay pump is under maintenance, register pump is in service."),
]

# Overlay unit designations (not equipment tags) used in prose.
UNIT_DESIGNATIONS = ["U-200", "Unit 200", "Unit 300", "U-300"]

# --------------------------------------------------------------------------
# Model catalogue
# --------------------------------------------------------------------------
# `equipment.json` `model` values are a generation artefact: every one is the
# unit's own tag with the final digit masked to X (P-1001 -> "P-101X",
# TK-1101 -> "TK-121X"). They are not model numbers, so this dossier records a
# real commercial designation per unit instead. Each designation is chosen to
# match the unit's kind and service role. Three pairs are genuinely the same
# model and are declared as such; every other string is unique.
MODEL_BY_TAG = {
    # pumps - API 610 / ISO 2858 process pump families
    "P-1001": "Flowserve HPX 6x8-15",
    "P-1002": "Flowserve HPX 6x8-15",
    "P-1042": "Sulzer MSD 8x10x15",
    "P-1051": "Sulzer MSD 6x8x14",
    "P-1061": "Goulds 3196 MTX 4x6-10",
    "P-1084": "Ruhrpumpen API 610 OH2 6x8-15",
    "P-1091": "Durco Mark 3 4x6-10",
    "P-1124": "KSB Etanorm 080-200",
    "P-1127": "Dickow NMM 100/250",
    "P-1131": "KSB Etanorm 250-400",
    "P-1132": "KSB Etanorm 250-400",
    "P-1142": "Grundfos NK 125-400",
    "P-1171": "Ebara 150x125 FS4JA",
    "P-1202": "Wilo CronoLine IL 100/160",
    # compressors and blowers - frame / rotor designations
    "C-1053": "Kobelco 3M7-6",
    "C-1071": "Elliott 29M9-6",
    "C-1082": "MAN RG 45/25",
    "C-1112": "Dresser-Rand DATUM D-8",
    "C-1125": "Siemens STC-SV 080",
    "C-1152": "Atlas Copco GA 315 VSD",
    # shell-and-tube heat exchangers - TEMA size designations
    "E-1004": "TEMA BEM 1100-450-25-2",
    "E-1045": "API Basco 500-300-2",
    "E-1054": "Sondex S7-1200-25",
    "E-1063": "Alfa Laval ST-340",
    "E-1083": "Thermal Engineering 900 BEM",
    "E-1093": "GEA Ecoflex NT 250S",
    # storage tanks - floating-roof tank designations
    "TK-1101": "CB&I FRT-5000",
    "TK-1102": "CB&I FRT-5000",
    "TK-1121": "BHEL FRT-118",
    "TK-1122": "PECOFacet EFRT-3200",
    "TK-1123": "Chicago Bridge EFRT-2000",
    # control and block valves - trim / body designations
    "V-1003": "Fisher ED-667",
    "V-1047": "Valtek Mark One 6x4",
    "V-1064": "Masoneilan 21000-6",
    "V-1103": "Samson 241-1",
    "V-1203": "Copes-Vulcan D-100-3",
    # pressure vessels, reactors and drums
    "VS-1046": "Chart VPS-1800",
    "VS-1062": "L&T PV-4500",
    "VS-1073": "Godrej PV-2400",
    "VS-1081": "CB&I PV-6200",
    "VS-1092": "Larsen & Toubro PV-4000",
    "VS-1113": "Kobe Steel PV-1800",
    "VS-1126": "ISGEC PV-2800",
    "VS-1162": "Bharat Heavy PV-1600",
    "VS-1172": "Tata Projects PV-3400",
    "VS-1201": "Babcock & Wilcox PV-2100",
    # columns - internals designations
    "COL-1044": "Koch-Glitsch FRI-2400",
    "COL-1052": "Sulzer Mellapak 250Y-2600",
    # fired heaters and boilers
    "F-1043": "Foster Wheeler H-1201",
    "F-1072": "Selas D-1050",
    "F-1111": "UOP F-4500",
    "F-1141": "Born Heaters B-2200",
    # electric drive
    "M-1143": "Siemens 1LA8 450",
    # utility packages
    "UT-1133": "SPX Marley NC-8412",
    "UT-1151": "Ingersoll Rand SSR-200",
    "UT-1161": "John Zink Z-500",
    # safety instrumented system elements
    "ESD-1181": "Honeywell FSC-500",
    "ESD-1182": "Fisher 657-ED",
}

# Model strings legitimately shared by more than one unit (genuine same-model
# pairs). Any other duplicate model string is a defect.
MODEL_SHARED_OK = {"Flowserve HPX 6x8-15", "KSB Etanorm 250-400", "CB&I FRT-5000"}

# Masked-tag artefact strings quoted in Section 4 only to explain why the
# register's `model` field is not reproduced. They are documented artefacts,
# not model values, and CHECK 8 confirms no Model cell contains one.
DOCUMENTED_ARTIFACTS = {"P-101X", "TK-121X"}

# --------------------------------------------------------------------------
# Commissioning window
# --------------------------------------------------------------------------
# The phase brief is a refinery that has been operating for approximately five
# years at the 2026-09 dossier cutoff, i.e. first production mid-2021. The
# register's `installed` field is a fabrication/legacy date spanning 2015-2023
# and is NOT used as the commissioning date here. Every unit is given a
# normalized commissioning date inside the declared window below, staged by
# area in the order the plant was brought up.
COMMISSIONING_WINDOW_START = date(2021, 6, 1)
COMMISSIONING_WINDOW_END = date(2026, 9, 30)
FIRST_PRODUCTION = date(2021, 6, 1)
COMMISSIONING_PHASES = [
    ("Phase 1 - crude train and utilities", date(2021, 6, 1), date(2021, 9, 30),
     ["crude-receiving", "crude-storage", "utilities", "steam", "cooling", "flare",
      "wastewater", "safety", "desalter"]),
    ("Phase 2 - distillation and reforming", date(2021, 7, 1), date(2022, 1, 31),
     ["cdu", "vdu", "nht", "reformer", "hydrogen", "product-storage"]),
    ("Phase 3 - conversion and treating", date(2021, 11, 1), date(2022, 5, 31),
     ["fcc", "dht", "sulfur"]),
]
AREA_PHASE = {}
for _label, _s, _e, _areas in COMMISSIONING_PHASES:
    for _a in _areas:
        AREA_PHASE[_a] = (_s, _e)
COMMISSIONING_PIN = {"C-1071": date(2021, 6, 14)}

CLASS_LABEL = {
    1: "Class 1 - highest consequence",
    2: "Class 2 - high",
    3: "Class 3 - standard",
}
MAINT_INTERVAL_DAYS = {1: 120, 2: 180, 3: 365}
HEALTH_BASE = {1: 88, 2: 91, 3: 94}
HEALTH_OVERRIDE = {"C-1071": 82, "P-1042": 84}
STATUS_OVERRIDE = {"C-1071": "WARNING", "P-1042": "WARNING"}

KIND_ROLE = {
    "pump": "centrifugal process pump",
    "compressor": "rotating compressor",
    "exchanger": "shell-and-tube heat exchanger",
    "tank": "atmospheric storage tank",
    "valve": "control or block valve",
    "vessel": "pressure vessel",
    "column": "fractionation column",
    "furnace": "fired heater",
    "motor": "electric drive motor",
    "utility": "utility package",
    "safety": "safety instrumented system element",
}

# Per-kind maintenance scope vocabulary. Deterministic selection only.
ACTIVITIES = {
    "pump": [
        "mechanical seal inspection", "bearing lubrication and vibration survey",
        "impeller wear check", "coupling alignment check",
        "motor current signature test", "suction strainer cleaning",
    ],
    "compressor": [
        "bearing temperature survey", "lube-oil sampling and analysis",
        "surge margin check", "rotor alignment check",
        "dry gas seal inspection", "anti-surge valve stroke test",
    ],
    "exchanger": [
        "delta-P trend review and cleaning assessment", "tube bundle eddy-current survey",
        "gasket and flange inspection", "shell-side flow verification",
    ],
    "tank": [
        "external visual inspection", "level transmitter calibration",
        "roof seal inspection", "internal floating roof check",
        "secondary containment inspection",
    ],
    "valve": [
        "stroke test and position feedback calibration", "packing replacement",
        "actuator overhaul", "seat leakage check",
    ],
    "vessel": [
        "wall-thickness survey", "relief valve recertification",
        "level instrument calibration", "internals inspection",
    ],
    "column": [
        "tray efficiency assessment", "pressure envelope survey",
        "reflux system inspection", "level and temperature loop verification",
    ],
    "furnace": [
        "tube skin-temperature survey", "burner management check",
        "draft and excess-oxygen survey", "refractory inspection",
    ],
    "motor": [
        "winding insulation resistance test", "vibration and current survey",
        "cooling air path inspection", "bearing greasing",
    ],
    "utility": [
        "performance test", "structural inspection", "control loop verification",
    ],
    "safety": [
        "proof test", "detector calibration", "logic solver verification",
        "final element stroke test",
    ],
}

INCIDENT_TEMPLATES = {
    "pressure": [
        ("pressure excursion above operating limit", "process", "controlled rate reduction"),
        ("transmitter reading outside critical envelope", "instrument", "transmitter isolated and replaced"),
        ("relief path demand during upset", "process", "relief path verified, no release"),
    ],
    "temperature": [
        ("bearing temperature alarm", "mechanical", "load reduced, bearing inspected"),
        ("outlet temperature drift", "instrument", "calibration work order raised"),
        ("furnace pass temperature excursion", "process", "firing rate reduced"),
    ],
    "vibration": [
        ("overall vibration alarm above alert threshold", "mechanical", "daily monitoring, work order raised"),
        ("vibration step change on bearing housing", "mechanical", "machine stopped on controlled ramp"),
    ],
    "flow": [
        ("charge flow sag below normal band", "process", "upstream valve stroked, flow restored"),
        ("flow restriction across blocked path", "mechanical", "strainer cleaned"),
    ],
    "level": [
        ("high level alarm in separator", "process", "level loop moved to manual and drained"),
        ("low level trip on storage tank", "process", "transfer rate reduced, alarm cleared"),
    ],
    "gas": [
        ("area gas detector trip", "leak", "exclusion zone set, release isolated"),
        ("leak detector latched in pump area", "leak", "seal replaced, detector reset"),
    ],
    "current": [
        ("motor overload trip", "electrical", "drive inspected before restart"),
        ("current draw above rated envelope", "electrical", "load rebalanced"),
    ],
    "position": [
        ("valve position feedback mismatch", "instrument", "loop moved to manual, actuator overhauled"),
        ("control valve stuck mid-travel", "mechanical", "valve isolated and stroked"),
    ],
    "rpm": [
        ("compressor speed excursion outside band", "process", "speed governor returned to setpoint"),
    ],
    "power": [
        ("power draw above expected duty", "mechanical", "impeller wear assessed"),
    ],
}

SEVERITIES = [
    ("Low", "no process impact; corrected at next opportunity"),
    ("Medium", "localised process deviation; unit stayed on line"),
    ("High", "rate reduction or partial unit outage required"),
    ("Critical", "safety-relevant deviation; escalated to the shift manager"),
]

# --------------------------------------------------------------------------
# Deterministic helpers
# --------------------------------------------------------------------------


def rng_for(key: str) -> random.Random:
    """A fresh, reproducible generator for one logical entity."""
    return random.Random(f"{SEED}:{key}")


def pick(rng: random.Random, seq):
    return seq[rng.randrange(len(seq))]


def d(value: str) -> date:
    return date.fromisoformat(value)


def iso(dt: date) -> str:
    return dt.isoformat()


def num(value) -> str:
    """Compact number rendering: drop pointless trailing zeros."""
    if isinstance(value, float):
        if value == int(value):
            return str(int(value))
        return ("%.3f" % value).rstrip("0").rstrip(".")
    return str(value)


def rng_str(lo, hi, nd=2) -> str:
    return f"{num(round(lo, nd))} .. {num(round(hi, nd))}"


def table(headers, rows) -> str:
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        cells = [str(c).replace("|", "\\|").replace("\n", " ") for c in row]
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def para(*lines) -> str:
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Load the authoritative datasets
# --------------------------------------------------------------------------

def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


PLANT = load_json(SIM_DIR / "plant.json")
AREAS = load_json(SIM_DIR / "areas.json")
UNITS = load_json(SIM_DIR / "equipment.json")
CONNECTIONS = load_json(SIM_DIR / "connections.json")
FAILURE_MODES = load_json(SIM_DIR / "failure_modes.json")
SCENARIOS = load_json(SIM_DIR / "scenarios.json")
DEMO_UNITS = load_json(DEMO_DIR / "equipment" / "equipment.json")
DEMO_WORK_ORDERS = load_json(DEMO_DIR / "work-orders.json")
DEMO_APPROVALS = load_json(DEMO_DIR / "approvals.json")
DEMO_HISTORY = load_json(DEMO_DIR / "history.json")

AREA_BY_ID = {a["id"]: a for a in AREAS}
UNIT_BY_TAG = {u["tag"]: u for u in UNITS}
UNIT_BY_ID = {u["id"]: u for u in UNITS}
REGISTER_TAGS = [u["tag"] for u in UNITS]
REGISTER_TAG_SET = set(REGISTER_TAGS)
SENSORS_BY_TAG = {u["tag"]: u["sensors"] for u in UNITS}
ALL_SENSOR_TAGS = {s["tag"] for u in UNITS for s in u["sensors"]}
ALL_SENSOR_TAGS_BY_UNIT = {u["tag"]: {s["tag"] for s in u["sensors"]} for u in UNITS}
DEMO_TAGS = [u["id"] for u in DEMO_UNITS]
DEMO_TAG_SET = set(DEMO_TAGS)
DEMO_BY_TAG = {u["id"]: u for u in DEMO_UNITS}
FAILURE_MODE_BY_ID = {m["id"]: m for m in FAILURE_MODES}


def area_name(area_id: str) -> str:
    return AREA_BY_ID[area_id]["name"]


def units_in_area(area_id: str):
    return [u for u in UNITS if u["area_id"] == area_id]


def medium_counts_for(area_id: str):
    """Inbound/outbound line media for prose."""
    ids = {u["id"] for u in units_in_area(area_id)}
    inbound, outbound = [], []
    for c in CONNECTIONS:
        if c["target"] in ids and c["source"] not in ids:
            inbound.append(c["medium"])
        if c["source"] in ids and c["target"] not in ids:
            outbound.append(c["medium"])
    return sorted(set(inbound)), sorted(set(outbound))


# --------------------------------------------------------------------------
# Derived register attributes (equipment.json has no health/lifecycle fields)
# --------------------------------------------------------------------------

def unit_health(u) -> int:
    if u["tag"] in HEALTH_OVERRIDE:
        return HEALTH_OVERRIDE[u["tag"]]
    r = rng_for("health:" + u["tag"])
    return HEALTH_BASE[u["criticality"]] - r.randrange(0, 7)


def unit_status(u) -> str:
    return STATUS_OVERRIDE.get(u["tag"], "NORMAL")


def unit_commissioned(u) -> str:
    """Normalized commissioning date inside the declared operating window.

    Staged by area phase; within a phase the units of that area are spread
    evenly so no two units share a date. The C-3 twin is pinned to the
    compression-train recommissioning date used through Section 14.
    """
    if u["tag"] in COMMISSIONING_PIN:
        return iso(COMMISSIONING_PIN[u["tag"]])
    start, end = AREA_PHASE[u["area_id"]]
    peers = [x for x in UNITS if x["area_id"] == u["area_id"]]
    i = peers.index(u)
    span = (end - start).days
    return iso(start + timedelta(days=(span * i) // max(len(peers), 1)))


def unit_last_maint(u) -> str:
    return u["last_inspection"]


def unit_next_maint(u) -> date:
    return d(u["last_inspection"]) + timedelta(days=MAINT_INTERVAL_DAYS[u["criticality"]])


def unit_model(u) -> str:
    return MODEL_BY_TAG[u["tag"]]


def unit_reliability(u):
    """(failures, mtbf_h, mttr_h, availability_pct) over the review period."""
    r = rng_for("rel:" + u["tag"])
    start = max(d(unit_commissioned(u)), PERIOD_START)
    hours = max((PERIOD_END - start).days, 30) * 24
    fails = r.randrange(1, 7)
    mttr = round(4.0 + r.random() * 20.0, 1)
    mtbf = round(hours / fails, 1)
    availability = round(100.0 * mtbf / (mtbf + mttr), 3)
    return fails, mtbf, mttr, availability


def sensor_rows(u):
    for s in u["sensors"]:
        yield s


# --------------------------------------------------------------------------
# Maintenance events, work orders, inspections, anomalies, incidents
# --------------------------------------------------------------------------

def _weekly(start: date, end: date, step: int = 7):
    out = []
    dt = start
    while dt <= end:
        out.append(dt)
        dt = dt + timedelta(days=step)
    return out


def build_me_records():
    """Return a chronological list of maintenance-event dicts.

    ME ids are assigned by chronological position so ME-198 lands exactly on
    the IR-198 drive-end bearing replacement.
    """
    # Explicit pinned events keyed by date where the console narrative fixes them.
    pinned = {
        date(2022, 6, 14): ("C-3", "preventive",
                            "coupling alignment inspection raised (legacy CMMS number)",
                            "WO-2417"),
        BEARING_DATE: ("C-3", "corrective",
                       "drive-end bearing replacement, OEM spare fitted, post-repair hot alignment",
                       "WO-6120"),
        ALIGN_DATE: ("C-3", "preventive",
                     "hot alignment check, coupling offset 0.06 mm against 0.10 mm tolerance",
                     "WO-2417"),
        date(2026, 8, 18): ("T-118", "preventive",
                            "six-monthly external visual inspection, no findings", "WO-8802"),
        date(2026, 8, 26): ("E-340", "preventive",
                            "quarterly delta-P trend review, no action expected", "WO-8810"),
        date(2026, 9, 3): ("V-2210", "corrective",
                           "high level alarm response, level loop verified and drained", "WO-8837"),
        date(2026, 9, 4): ("P-1042", "corrective",
                           "discharge pressure investigation, relief path and impeller check", "WO-8841"),
        date(2026, 9, 7): ("C-3", "corrective",
                           "drive-end bearing inspection raised from IR-204; pending approval", "WO-8852"),
    }

    raw = _weekly(PERIOD_START, PERIOD_END) + list(pinned.keys())
    dates = sorted(set(raw))
    before = [x for x in dates if x < BEARING_DATE]
    after = [x for x in dates if x > BEARING_DATE]
    # ME-198 must be the bearing replacement: exactly 197 events before it.
    if len(before) > 197:
        before = before[:197]
    while len(before) < 197:
        gaps = [(before[i + 1] - before[i], i) for i in range(len(before) - 1)]
        gaps.sort(reverse=True)
        _, i = gaps[0]
        before.insert(i + 1, before[i] + (before[i + 1] - before[i]) // 2)
    dates = before + [BEARING_DATE] + after
    assert dates[197] == BEARING_DATE, "ME-198 anchor drift"

    # Reserved work-order numbers fixed by the console narrative.
    reserved = {"WO-2417", "WO-6120", "WO-8802", "WO-8810", "WO-8837", "WO-8841", "WO-8852"}
    wo_base = {2021: 4100, 2022: 4700, 2023: 5200, 2024: 5700, 2025: 6100, 2026: 8600}
    wo_counter = {y: 0 for y in wo_base}
    used_wo = set(reserved)

    def next_wo(dt: date) -> str:
        y = dt.year if dt.year in wo_base else 2026
        while True:
            cand = "WO-%d" % (wo_base[y] + wo_counter[y])
            wo_counter[y] += 1
            if cand not in used_wo:
                used_wo.add(cand)
                return cand

    overlay_for_register = {
        "C-1071": "C-3", "P-1042": "P-1042", "E-1063": "E-340",
        "TK-1121": "T-118", "V-1047": "V-2210",
    }
    register_for_overlay = {v: k for k, v in overlay_for_register.items()}

    records = []
    for idx, dt in enumerate(dates):
        me = "ME-%03d" % (idx + 1)
        if dt in pinned:
            overlay_tag, mtype, scope, wo = pinned[dt]
            unit = UNIT_BY_TAG[register_for_overlay[overlay_tag]]
        else:
            r = rng_for("me:" + me)
            unit = UNITS[r.randrange(len(UNITS))]
            mtype = "preventive" if r.random() < 0.62 else "corrective"
            scope = pick(r, ACTIVITIES.get(unit["kind"], ACTIVITIES["utility"]))
            wo = next_wo(dt)
            overlay_tag = overlay_for_register.get(unit["tag"])
        records.append({
            "me": me, "date": dt, "unit": unit["tag"], "kind": unit["kind"],
            "area": unit["area_id"], "type": mtype, "scope": scope, "wo": wo,
            "overlay": overlay_tag,
        })
    return records


def build_ir_records():
    """28 inspection records, IR-177..IR-204, chronological.

    IR-198 is the drive-end bearing replacement and IR-204 the 2026 vibration
    survey; both ids fall out of chronological position by construction.
    """
    early = []
    span = (BEARING_DATE - timedelta(days=1) - date(2021, 8, 10)).days
    for i in range(21):
        early.append(date(2021, 8, 10) + timedelta(days=(span * i) // 20))
    mid = []
    mspan = (IR204_DATE - timedelta(days=1) - date(2025, 5, 20)).days
    for i in range(5):
        mid.append(date(2025, 5, 20) + timedelta(days=(mspan * i) // 4))
    dates = early + [BEARING_DATE] + mid + [IR204_DATE]
    dates = sorted(set(dates))
    while len(dates) < 28:
        gaps = [(dates[i + 1] - dates[i], i) for i in range(len(dates) - 1)]
        gaps.sort(reverse=True)
        _, i = gaps[0]
        dates.insert(i + 1, dates[i] + (dates[i + 1] - dates[i]) // 2)
    dates = dates[:28]
    assert dates[21] == BEARING_DATE and dates[27] == IR204_DATE, "IR anchor drift"

    def findings_for(tag, dt, ir):
        r = rng_for("ir:" + ir)
        u = UNIT_BY_TAG.get(tag)
        kind = u["kind"] if u else "vessel"
        if ir == "IR-198":
            return ("Drive-end bearing removed and replaced with OEM spare following rising 1x "
                    "vibration and bearing-housing temperature. Bearing outer-race spalling on two "
                    "rolling elements; lube-oil varnish present on the cage. Post-repair overall "
                    "vibration 5.4 mm/s against a 5.7 mm/s baseline; machine re-baselined at 5.69 mm/s.",
                    "Bearing replaced, alignment re-checked and accepted; returned to service.")
        if ir == "IR-204":
            return ("Overall vibration on the drive-end bearing housing 6.8 mm/s RMS against a "
                    "90-day rolling baseline of 5.8 mm/s (an increase of 18%). Energy concentrated "
                    "at 1x running speed (4.9 mm/s) with a stable 2x component and a slightly "
                    "elevated bearing defect band. DE bearing-housing temperature 79 degC against "
                    "a 68 degC baseline. Pattern consistent with progressive bearing wear or a "
                    "developing alignment shift.",
                    "Daily monitoring imposed, corrective work order WO-8852 raised, hot alignment "
                    "check required before re-baselining.")
        pool = {
            "pump": [
                ("Mechanical seal face wear within replacement tolerance; no process leak. "
                 "Suction strainer 20% blinded.", "Seal faces dressed, strainer cleaned."),
                ("Bearing housing vibration 0.4 mm/s above the rolling baseline with stable "
                 "temperature.", "Lubrication corrected, re-survey scheduled."),
                ("Coupling insert degradation and 0.03 mm soft-foot on the drive-end foot.",
                 "Insert replaced, soft-foot shimmed, alignment verified."),
            ],
            "compressor": [
                ("Rotor alignment within tolerance; lube-oil particle count ISO 18/16/13.",
                 "Oil charge replaced, no mechanical action."),
                ("Anti-surge valve stroke 4% slow at the closed end.",
                 "Actuator overhauled, stroke re-profiled."),
            ],
            "exchanger": [
                ("Shell-side delta-P 0.42 bar against a clean 0.28 bar reference; fouling "
                 "factor estimated at 0.00021 m2K/W.", "Cleaning deferred to the next window; "
                 "trend review quarterly."),
                ("No tube-wall loss on the eddy-current sample; two baffle-tip clearances "
                 "slightly enlarged.", "Bundle returned to service, next survey at 48 months."),
            ],
            "tank": [
                ("External coating intact; secondary containment dry; level transmitter within "
                 "0.4% of the gauging tape.", "No action."),
                ("Roof seal abrasion over a 2 m run; no product wetted surface exposed.",
                 "Seal section scheduled for replacement."),
            ],
            "valve": [
                ("Position feedback tracking commanded position within 1.1%; packing weep "
                 "recorded on two studs.", "Packing re-torqued, feedback re-zeroed."),
                ("Actuator diaphragm perished at the stem guide.", "Diaphragm replaced."),
            ],
            "vessel": [
                ("Wall thickness at the design minimum plus 1.4 mm; no blistering or cracking.",
                 "Fitness-for-service interval retained."),
                ("Relief valve set pressure 2% low on the bench.", "Valve re-set and certified."),
            ],
            "column": [
                ("Tray pressure drop within design; two valve trays show slight weep.",
                 "No action, next internal survey in 24 months."),
            ],
            "furnace": [
                ("Tube skin temperature 38 degC below the design limit; burner flame pattern even.",
                 "No action."),
                ("Refractory spalling over a 0.6 m2 patch on the radiant floor.",
                 "Cold-face patch scheduled."),
            ],
            "motor": [
                ("Insulation resistance 480 MOhm; winding thermography even.",
                 "No action."),
            ],
            "utility": [
                ("Performance within 3% of the commissioned curve.", "No action."),
            ],
            "safety": [
                ("Proof test passed at 96% sensor coverage; one detector at the 2% drift limit.",
                 "Detector recalibrated and re-tested."),
            ],
        }
        return pick(r, pool.get(kind, pool["vessel"]))

    records = []
    for i, dt in enumerate(dates):
        ir = "IR-%d" % (177 + i)
        r = rng_for("ir-unit:" + ir)
        if ir == "IR-198":
            tag = "C-1071"
        elif ir == "IR-204":
            tag = "C-1071"
        else:
            tag = UNITS[r.randrange(len(UNITS))]["tag"]
        finding, disposition = findings_for(tag, dt, ir)
        u = UNIT_BY_TAG[tag]
        records.append({
            "ir": ir, "date": dt, "unit": tag, "kind": u["kind"], "area": u["area_id"],
            "finding": finding, "disposition": disposition,
            "inspector": pick(rng_for("ir-insp:" + ir),
                              ["Reliability Engineering", "Inspection Services",
                               "Maintenance Execution", "Third-party NDT (vendor)", "Operations Shift"]),
        })
    return records


def build_anomalies():
    """48 anomalies A-04..A-51, chronological, A-51 pinned to the C-3 trend."""
    r = rng_for("anom-dates")
    dates = []
    start = date(2021, 7, 6)
    end = date(2026, 8, 28)
    total = 48
    span = (end - start).days
    step = span / (total - 1)
    for i in range(total - 1):
        dates.append(start + timedelta(days=int(step * i) + r.randrange(0, 4)))
    dates.append(A51_DATE)
    dates = sorted(set(dates))[:total]
    while len(dates) < total:
        gaps = [(dates[i + 1] - dates[i], i) for i in range(len(dates) - 1)]
        gaps.sort(reverse=True)
        _, i = gaps[0]
        dates.insert(i + 1, dates[i] + (dates[i + 1] - dates[i]) // 2)
    # A-51 sits on the C-3 survey date; A-04..A-51 are assigned in date order.
    dates[-1] = A51_DATE
    assert len(dates) == total

    pool = {
        "vibration": ("mm/s", "overall vibration", 4.6, 7.4,
                      "daily monitoring, corrective work order raised"),
        "temperature": ("degC", "bearing or outlet temperature", 60.0, 96.0,
                        "loop checked, calibration or lubrication corrected"),
        "pressure": ("bar", "discharge or header pressure", 6.0, 46.0,
                     "control valve stroked, relief path verified"),
        "flow": ("m3/h", "process flow", 60.0, 240.0,
                 "strainer cleaned, upstream path restored"),
        "level": ("%", "vessel or tank level", 42.0, 92.0,
                  "level loop moved to manual, drain or fill path corrected"),
        "position": ("%", "valve position feedback", 30.0, 90.0,
                     "actuator overhauled, position loop recalibrated"),
        "current": ("A", "motor current", 40.0, 180.0,
                    "load rebalanced, driven equipment inspected"),
        "power": ("kW", "shaft power", 40.0, 620.0,
                  "impeller wear assessed, duty re-rated"),
        "rpm": ("rpm", "machine speed", 3200.0, 9600.0,
                "speed governor returned to setpoint"),
        "gas": ("%LEL", "area gas concentration", 0.0, 45.0,
                "exclusion zone set, release isolated and detector reset"),
        "leak": ("0/1", "latched leak detector", 0.0, 1.0,
                 "seal replaced, detector reset and held at zero"),
    }
    meas_keys = list(pool.keys())

    records = []
    for i in range(total):
        aid = "A-%02d" % (4 + i)
        dt = dates[i]
        if aid == "A-51":
            tag = "C-1071"
            meas = "vibration"
            magnitude = "6.8 mm/s against a 5.7 mm/s learned baseline and a 5.8 mm/s 90-day rolling baseline (+18%)"
            resolution = ("IR-204 survey, daily monitoring, WO-8852 raised pending APR-231 outage approval")
            notes = ("Energy concentrated at 1x running speed on the drive-end bearing housing with "
                     "bearing-housing temperature at 79 degC against a 68 degC baseline.")
        else:
            rr = rng_for("anom:" + aid)
            tag = UNITS[rr.randrange(len(UNITS))]["tag"]
            meas = pick(rr, meas_keys)
            unit, label, lo, hi, resolution = pool[meas]
            base = round(lo + (hi - lo) * rr.random(), 2)
            magn = round(base * (1.0 + (0.10 + rr.random() * 0.35)), 2)
            magnitude = "%s %s against a %s %s baseline (+%d%%)" % (
                num(magn), unit, num(base), unit, int(100 * (magn - base) / base))
            notes = "Detected by %s; no critical alarm active at detection." % label
        records.append({
            "id": aid, "date": dt, "unit": tag, "kind": UNIT_BY_TAG[tag]["kind"],
            "area": UNIT_BY_TAG[tag]["area_id"], "measurement": meas,
            "magnitude": magnitude, "resolution": resolution, "notes": notes,
        })
    return records


def build_incidents():
    """36 dated incident/event rows, INC-401..INC-430 and EV-101..EV-106."""
    r = rng_for("inc-dates")
    total = 36
    start = date(2021, 7, 20)
    end = date(2026, 9, 9)
    span = (end - start).days
    dates = sorted(start + timedelta(days=int(span * i / (total - 1)) + r.randrange(0, 3))
                   for i in range(total))
    pinned = {
        date(2026, 9, 3): ("V-2210", "level", "Critical"),
        date(2026, 9, 4): ("P-1042", "pressure", "High"),
        date(2026, 9, 6): ("C-3", "vibration", "High"),
    }
    # Force the three current events onto the tail of the chronological list.
    dates = [x for x in dates if x < date(2026, 9, 1)]
    dates += [date(2026, 9, 3), date(2026, 9, 4), date(2026, 9, 6)]
    dates = sorted(dates)[:total]

    records = []
    for i in range(total):
        dt = dates[i]
        iid = ("INC-%d" % (401 + i)) if i < 30 else ("EV-%d" % (101 + i - 30))
        r2 = rng_for("inc:" + iid)
        meas = pick(r2, ["pressure", "temperature", "vibration", "flow", "level",
                         "current", "position", "gas"])
        if dt in pinned:
            overlay, meas, sev = pinned[dt]
            register = {"C-3": "C-1071", "P-1042": "P-1042", "V-2210": "V-1047"}[overlay]
        else:
            register = UNITS[r2.randrange(len(UNITS))]["tag"]
            sev = pick(r2, ["Low", "Medium", "Medium", "High", "Critical"])
        title, cause_class, outcome = pick(r2, INCIDENT_TEMPLATES[meas])
        if dt == date(2026, 9, 3):
            title = "high level alarm 87% against an 80% setpoint"
            cause_class = "process"
            outcome = "level loop drained and verified; WO-8837 raised; APR-218 approved priority escalation"
        elif dt == date(2026, 9, 4):
            title = "discharge pressure 18.5 bar above the 17.0 bar operating limit"
            cause_class = "process"
            outcome = "relief path and impeller wear check opened under WO-8841"
        elif dt == date(2026, 9, 6):
            title = "overall vibration 18% above baseline with 1x dominance"
            cause_class = "mechanical"
            outcome = "IR-204 survey, daily monitoring, WO-8852 raised pending approval"
        detail = pick(r2, [
            "Operator confirmed the reading against a redundant transmitter before acting.",
            "Alarm annunciated at the console and was acknowledged within the shift.",
            "Detector or transmitter was cross-checked against a correlated measurement.",
            "Unit remained on line; the deviation was contained locally.",
        ])
        records.append({
            "id": iid, "date": dt, "unit": register, "kind": UNIT_BY_TAG[register]["kind"],
            "area": UNIT_BY_TAG[register]["area_id"], "measurement": meas,
            "title": title, "severity": sev, "cause_class": cause_class,
            "outcome": outcome, "detail": detail,
        })
    return records


ME_RECORDS = build_me_records()
IR_RECORDS = build_ir_records()
ANOMALIES = build_anomalies()
INCIDENTS = build_incidents()


# --------------------------------------------------------------------------
# Small formatting helpers shared by the section builders
# --------------------------------------------------------------------------

def sensor_band(s, key):
    return rng_str(s[key + "_min"], s[key + "_max"], 2)


def sensor_line(s):
    return "%s | %s | %s | %s" % (s["tag"], s["measurement"], s["unit"], num(s["nominal"]))


def area_unit_rows(area_id):
    return [u for u in UNITS if u["area_id"] == area_id]


def all_area_ids():
    return [a["id"] for a in AREAS]


def overlay_rows():
    rows = []
    for u in DEMO_UNITS:
        for sig in u["keySignals"]:
            rows.append({
                "asset": u["id"], "signal": sig["signal"], "value": sig["value"],
                "unit": sig["unit"], "baseline": sig["baseline"], "limit": sig["limit"],
                "delta": sig["deltaPercent"], "state": sig["state"],
                "name": u["name"],
            })
    return rows


OVERLAY_ROWS = overlay_rows()


def area_summary_lines(area_id):
    """Deterministic condition commentary for one area, built from real records."""
    us = area_unit_rows(area_id)
    corr = [r for r in ME_RECORDS if r["area"] == area_id and r["type"] == "corrective"]
    prev = [r for r in ME_RECORDS if r["area"] == area_id and r["type"] == "preventive"]
    sensors = sum(len(u["sensors"]) for u in us)
    fails = sum(unit_reliability(u)[0] for u in us)
    high = max(us, key=lambda u: unit_health(u))
    low = min(us, key=lambda u: unit_health(u))
    last = max((r["date"] for r in ME_RECORDS if r["area"] == area_id), default=None)
    return (
        "**%s.** %d units, %d instruments, carrying %s. The review period recorded %d "
        "corrective and %d preventive events here, with %d modelled failures. "
        "Best-condition asset is %s (%s, %d/100); lowest-condition asset is %s (%s, "
        "%d/100). Most recent maintenance event: %s."
        % (area_name(area_id), len(us), sensors,
           ", ".join(sorted({u["kind"] for u in us})), len(corr), len(prev), fails,
           high["tag"], high["name"], unit_health(high),
           low["tag"], low["name"], unit_health(low), iso(last) if last else "-"))


# --------------------------------------------------------------------------
# Section 1 - Executive Summary
# --------------------------------------------------------------------------

def sec_01():
    total_sensors = sum(len(u["sensors"]) for u in UNITS)
    warnings = [u for u in UNITS if unit_status(u) != "NORMAL"]
    rows = []
    for u in UNITS:
        if unit_status(u) != "NORMAL":
            rows.append([u["tag"], u["name"], area_name(u["area_id"]),
                         CLASS_LABEL[u["criticality"]].split(" - ")[0],
                         "%d/100" % unit_health(u), unit_status(u)])
    table_ = table(["Tag", "Name", "Area", "Criticality", "Health", "Status"], rows)
    return para(
        "This dossier is the consolidated technical knowledge base for the "
        "%s, a %s complex of %d process areas, %d registered equipment items and "
        "%d field instruments. It covers the five-year reliability record from "
        "2021-06 through 2026-09 and is written to be ingested as a retrieval corpus "
        "as well as read by an engineer." % (PLANT["name"], PLANT["industry"], len(AREAS),
                                             len(UNITS), total_sensors),
        "",
        "The plant is a synthetic-but-complete refinery model: crude receiving and "
        "storage, desalting, crude and vacuum distillation, naphtha hydrotreating, "
        "catalytic reforming, fluid catalytic cracking, diesel hydrotreating, sulphur "
        "recovery, hydrogen, product storage, and the utility block (steam, cooling "
        "water, instrument air, flare, wastewater and safety systems). Every tag in "
        "this document resolves to a record in `equipment.json`; every instrument tag "
        "resolves to an entry in its owning unit's `sensors[]`.",
        "",
        "## 1.1 State of the plant at %s" % DOC_DATE,
        "",
        "All %d registered units are running and reporting process data. No unit is in "
        "a tripped or shutdown state at the review date. Two registered assets carry a "
        "degraded condition that is being managed under an open work order:" % len(UNITS),
        "",
        table_,
        "",
        "## 1.2 The two live engineering problems",
        "",
        "**Compressor C-3 (register twin C-1071, Recycle Gas Compressor).** Overall "
        "vibration on the drive-end bearing housing has risen to 6.8 mm/s RMS against "
        "a 5.7 mm/s learned baseline and a 5.8 mm/s 90-day rolling baseline, an increase "
        "of 18%. Energy is concentrated at 1x running speed with a stable 2x component, "
        "and the drive-end bearing housing temperature has risen from 68 degC to 79 degC. "
        "Inspection IR-204 records the survey and its spectral evidence; anomaly A-51 "
        "tracks the trend. The machine is inside its 7.1 mm/s alarm limit but outside the "
        "10% deviation band that triggers daily monitoring, so vibration monitoring has "
        "been increased to once per shift and work order WO-8852 (drive-end bearing "
        "inspection) has been raised, gated by outage approval APR-231. The drive-end "
        "bearing was last replaced on 2025-03-16 under IR-198 and ME-198.",
        "",
        "**Crude charge pump P-1042 (area cdu, criticality class 3).** Discharge pressure "
        "is running at 18.5 bar against a 17.0 bar operating alert threshold and a 16.2 bar "
        "baseline, a deviation of +14%. The transmitter envelope for PT-1042A is much wider "
        "(normal band 17.76 to 19.24 bar), so the excursion is an operating-limit breach "
        "rather than an instrument-envelope breach. Scenario `sc-sensor-failure` exercises "
        "the loss of PT-1042A itself, which is why the learned rule pins the process alert "
        "threshold at 17 bar rather than at the transmitter's own limits. Work order WO-8841 "
        "is open under SOP-14.2.",
        "",
        "## 1.3 Where the reliability risk sits",
        "",
        "The period generated 270 recorded maintenance events, 28 formal inspections, "
        "48 tracked anomalies and 36 incident or event records. Rotating equipment "
        "(pumps, compressors and the one drive motor) accounts for the majority of "
        "unplanned corrective work; exchangers account for the largest single recurring "
        "degradation mechanism because fouling is progressive and tolerated by design "
        "until the duty loss is material.",
        "",
        "## 1.4 What this document contains",
        "",
        "Sections 2 and 3 describe the plant and its process units. Section 4 is the "
        "equipment register for all 58 units and states the health and next-maintenance "
        "derivation formula. Section 4b declares the register/overlay tag crosswalk. "
        "Section 5 instruments every unit. Sections 6 to 13 carry the operating "
        "envelope, the five-year maintenance history, inspection records, failure "
        "modes, safety and operating procedures, incident history and the reliability "
        "analysis. Sections 14 to 17 are the deep asset histories for C-3, P-1042, "
        "E-340 and T-118. Sections 18 to 22 carry the anomaly register, the "
        "intervention register, current status, lessons learned and recommended actions.",
    )


# --------------------------------------------------------------------------
# Section 2 - Plant Overview
# --------------------------------------------------------------------------

def sec_02():
    rows = []
    for a in AREAS:
        us = area_unit_rows(a["id"])
        sensors = sum(len(u["sensors"]) for u in us)
        rows.append([a["id"], a["name"], len(us), sensors,
                     ", ".join(sorted({u["kind"] for u in us}))])
    area_table = table(["Area id", "Area name", "Units", "Instruments", "Equipment kinds"], rows)

    flow_rows = []
    for c in CONNECTIONS:
        flow_rows.append([c["id"], c["source"], c["target"], c["medium"],
                          "%s" % num(c["capacity"]), c["kind"]])
    flow_table = table(["Line", "Source", "Target", "Medium", "Capacity", "Kind"],
                       flow_rows[:20])

    phase_rows = []
    for label, start, end, areas_ in COMMISSIONING_PHASES:
        us = [u for u in UNITS if u["area_id"] in areas_]
        phase_rows.append([label, iso(start) + " .. " + iso(end), len(areas_),
                           len(us), "%d" % sum(len(u["sensors"]) for u in us)])
    phase_table = table(["Build phase", "Commissioning window", "Areas", "Units",
                         "Instruments"], phase_rows)

    return para(
        "## 2.1 Identity",
        "",
        "The plant is modelled as **%s** (id `%s`, industry `%s`). The model is a "
        "full-conversion refinery: it takes crude in at the receiving header, desalts "
        "and distils it, upgrades the naphtha and diesel fractions with hydrogen, "
        "reforms naphtha for octane, cracks vacuum gasoil in the FCC, recovers sulphur "
        "from acid gas, and ships naphtha, diesel and jet to product storage. The "
        "utility block supplies steam, cooling water, instrument air and plant air, and "
        "the safety block provides fire and gas detection and emergency shutdown."
        % (PLANT["name"], PLANT["id"], PLANT["industry"]),
        "",
        "## 2.2 Process areas",
        "",
        area_table,
        "",
        "## 2.3 Process connectivity",
        "",
        "The register carries %d process lines between %d units. Media in service are: "
        "%s. The excerpt below is the first block of the connectivity list; the full "
        "list is reproduced in the simulation dataset and is used by the plant graph."
        % (len(CONNECTIONS), len(UNITS),
           ", ".join(sorted({c["medium"] for c in CONNECTIONS}))),
        "",
        flow_table,
        "",
        "## 2.4 Operating basis",
        "",
        "The plant runs continuously with a nominal two-shift operations roster and a "
        "day-shift maintenance crew. Turnaround work is planned by area and sequenced "
        "so that no more than one distillation train is out of service at a time. "
        "Crude and vacuum distillation cannot be left unattended with a lost column "
        "temperature or level measurement (OPS-03.2 rev4). Rotating equipment of "
        "criticality class 2 and above is governed by SOP-07.3 rev4 for vibration "
        "response.",
        "",
        "## 2.5 Commissioning and operating age",
        "",
        "The plant has been in production for approximately five years. "
        "**Commissioning window: %s to %s.** First production was %s, so the refinery "
        "is 5.3 years old at the %s cutoff. Every one of the %d registered units was "
        "commissioned inside that window, and no unit predates the plant. Commissioning "
        "was staged in three build phases so that the crude train and its utilities came "
        "up first, distillation and reforming followed, and the conversion and treating "
        "units were the last to start."
        % (iso(COMMISSIONING_WINDOW_START), iso(COMMISSIONING_WINDOW_END),
           iso(FIRST_PRODUCTION), DOC_DATE, len(UNITS)),
        "",
        phase_table,
        "",
        "## 2.6 Instrumentation density",
        "",
        "The %d units carry %d field instruments, an average of %.1f per unit. The "
        "density is highest on the compressor trains and the seven-instrument pump "
        "blocks (pressure, flow, temperature, vibration, current and power), and "
        "lowest on utility packages and safety elements, which report a single status "
        "or detector channel." % (len(UNITS), sum(len(u["sensors"]) for u in UNITS),
                                  sum(len(u["sensors"]) for u in UNITS) / len(UNITS)),
    )


# --------------------------------------------------------------------------
# Section 3 - Refinery Units
# --------------------------------------------------------------------------

def sec_03():
    out = [
        "The %d process areas are described below in process order. Each subsection "
        "gives the area duty, the media crossing its boundary, and the registered "
        "equipment that carries it." % len(AREAS),
        "",
    ]
    for a in AREAS:
        us = area_unit_rows(a["id"])
        inbound, outbound = medium_counts_for(a["id"])
        rows = [[u["tag"], u["name"], KIND_ROLE.get(u["kind"], u["kind"]),
                 CLASS_LABEL[u["criticality"]].split(" - ")[0]] for u in us]
        out.append("### 3.%d %s" % (AREAS.index(a) + 1, a["name"]))
        out.append("")
        out.append(
            "Duty: %s. Inbound media: %s. Outbound media: %s. The area holds %d "
            "registered units and %d field instruments."
            % (_area_duty(a["id"]), ", ".join(inbound) or "none (utility boundary)",
               ", ".join(outbound) or "none (utility boundary)", len(us),
               sum(len(u["sensors"]) for u in us)))
        out.append("")
        out.append(table(["Tag", "Name", "Role", "Criticality class"], rows))
        out.append("")
        out.append(area_summary_lines(a["id"]))
        out.append("")
    return "\n".join(out)


AREA_DUTY = {
    "crude-receiving": "receive tanker and pipeline crude and pump it to storage",
    "crude-storage": "hold crude inventory and feed the desalter at a controlled rate",
    "desalter": "remove salts and water from crude ahead of distillation",
    "cdu": "split desalted crude into naphtha, kerosene, diesel and atmospheric residue",
    "vdu": "recover vacuum gasoil from atmospheric residue under vacuum",
    "nht": "hydrotreat naphtha to remove sulphur and nitrogen ahead of reforming",
    "reformer": "raise naphtha octane and produce reformate and hydrogen-rich gas",
    "fcc": "crack vacuum gasoil to gasoline-range products and light gases",
    "dht": "hydrodesulphurise diesel to product specification",
    "sulfur": "recover elemental sulphur from amine acid gas",
    "hydrogen": "generate and purify hydrogen for the hydrotreaters",
    "product-storage": "hold finished naphtha, diesel and jet and load out product",
    "utilities": "supply instrument air and plant air to the whole site",
    "steam": "raise and distribute steam and return boiler feed water",
    "cooling": "reject process heat to atmosphere and circulate cooling water",
    "flare": "safely dispose of relief and upset hydrocarbon vapour",
    "wastewater": "separate oil from process water before discharge",
    "safety": "detect fire and gas and execute emergency shutdown",
}


def _area_duty(area_id):
    return AREA_DUTY.get(area_id, "process duty as registered")


# --------------------------------------------------------------------------
# Section 4 - Equipment Register
# --------------------------------------------------------------------------

def _register_rows():
    rows = []
    for u in UNITS:
        rows.append([
            u["tag"], u["name"], u["kind"], area_name(u["area_id"]),
            CLASS_LABEL[u["criticality"]],
            unit_commissioned(u), u["manufacturer"], unit_model(u),
            unit_last_maint(u), iso(unit_next_maint(u)), "%d/100" % unit_health(u),
        ])
    return rows


def sec_04():
    rows = _register_rows()
    by_area = []
    for a in AREAS:
        us = area_unit_rows(a["id"])
        by_area.append([a["name"], len(us),
                        sum(1 for u in us if u["criticality"] == 1),
                        sum(1 for u in us if u["criticality"] == 2),
                        sum(1 for u in us if u["criticality"] == 3)])
    area_notes = "\n\n".join(
        "### 4.4.%d %s\n\n%s" % (i + 1, a["name"], area_summary_lines(a["id"]))
        for i, a in enumerate(AREAS))
    comm_sorted = sorted(UNITS, key=lambda u: unit_commissioned(u))
    oldest = ", ".join("%s (%s)" % (u["tag"], unit_commissioned(u)) for u in comm_sorted[:2])
    newest = ", ".join("%s (%s)" % (u["tag"], unit_commissioned(u)) for u in comm_sorted[-2:])
    return para(
        "The register below is the authoritative equipment list for the plant model. "
        "It contains one row for every registered unit: **%d units**, covering %s. "
        "The `tag` column is the tag number used everywhere else in this document and "
        "in the simulation engine; it is the primary key." % (len(UNITS), PLANT["name"]),
        "",
        "**Column set (11 columns, in this order):** `Tag`, `Name`, `Kind`, `Area`, "
        "`Criticality`, `Commissioned`, `Manufacturer`, `Model`, `Last maint.`, "
        "`Next maint.`, `Health`. This is the register schema referenced by the "
        "manifest and by Section 5, which joins to it on `Tag` through its own "
        "`Equipment` column.",
        "",
        "Derivation footnote. Four of the eleven columns are read verbatim from "
        "`equipment.json` and seven require a stated rule; all rules are deterministic "
        "and reproducible from the fixed seed, and none of them reads the clock.",
        "",
        "* **Commissioned** - *normalized, not the register's `installed` value.* The "
        "register's `installed` field is a fabrication/legacy date that predates first "
        "production, which would contradict the plant's five-year operating age. "
        "This dossier therefore records a commissioning date normalized into the "
        "declared operating window (%s to %s), staged by the three build phases in "
        "Section 2.5. Within a phase, units of an area are spread evenly across the "
        "phase window so no two units share a date; C-1071 is pinned to %s, the "
        "compression-train recommissioning date used throughout Section 14."
        % (iso(COMMISSIONING_WINDOW_START), iso(COMMISSIONING_WINDOW_END),
           iso(COMMISSIONING_PIN["C-1071"])),
        "* **Manufacturer** - read verbatim from `equipment.json`'s `manufacturer` "
        "field. The register assigns each unit to one of six vendors: Atlas Pumps, "
        "SynthWorks, Flowdyne, Rotodyne, Helix Process and Vulcan Industrial. This "
        "document does not reassign vendors; the vendor split is the dataset's own.",
        "* **Model** - *curated, not the register's `model` value.* Every `model` "
        "string in `equipment.json` is a masked-tag artefact - the unit's own tag with "
        "the final digit replaced by X (P-1001 -> `P-101X`, TK-1101 -> `TK-121X`) - so "
        "it is not a model number and is not reproduced here. Each unit instead carries "
        "a commercial designation matched to its kind and service role: API 610 / ISO "
        "2858 pump families, compressor frame designations, TEMA exchanger sizes, "
        "floating-roof tank designations, valve trim designations, vessel and reactor "
        "tags, column internals, heater designations, a motor frame, utility packages "
        "and safety element designations. Only three strings are shared, and only "
        "because the units are genuinely the same model: `Flowserve HPX 6x8-15` "
        "(P-1001/P-1002), `KSB Etanorm 250-400` (P-1131/P-1132) and `CB&I FRT-5000` "
        "(TK-1101/TK-1102). All other 52 designations are unique.",
        "* **Last maint.** - read verbatim from the register's `last_inspection` date.",
        "* **Next maint.** - derived as `last_inspection + interval`, where the "
        "interval is 120 days for criticality class 1, 180 days for class 2 and 365 "
        "days for class 3. Next-maint dates are forecasts and may fall after the "
        "dossier cutoff.",
        "* **Health** - derived as `base[class] - jitter`, where base is 88 (class 1), "
        "91 (class 2) and 94 (class 3), and jitter is a seeded integer in 0..6 derived "
        "from `SHA-512(SEED:health:<tag>)`. Two assets carry a fixed override taken "
        "from the live console narrative rather than the formula: C-1071 = 82/100 (the "
        "C-3 twin) and P-1042 = 84/100.",
        "* **Criticality** - read verbatim from the register's `criticality` field, "
        "presented as class 1 (highest consequence) to class 3 (standard).",
        "",
        "### 4.1 Register",
        "",
        table(["Tag", "Name", "Kind", "Area", "Criticality", "Commissioned",
               "Manufacturer", "Model", "Last maint.", "Next maint.", "Health"], rows),
        "",
        "## 4.2 Distribution by area",
        "",
        table(["Area", "Units", "Class 1", "Class 2", "Class 3"], by_area),
        "",
        "## 4.3 Register notes",
        "",
        "* Commissioned dates span %s to %s. The oldest registered assets are %s; the "
        "newest are %s. The spread is the staged build described in Section 2.5, not "
        "piecemeal replacement."
        % (min(unit_commissioned(u) for u in UNITS), max(unit_commissioned(u) for u in UNITS),
           oldest, newest),
        "* Manufacturer spread is narrow by design: Atlas Pumps, SynthWorks, Flowdyne, "
        "Rotodyne, Helix Process and Vulcan Industrial between them supply every unit. "
        "Spares strategy follows the manufacturer, not the area. Vendors are the "
        "register's own assignment and are reproduced without change.",
        "* Criticality class 1 units (%d of %d) are the distillation columns' fired "
        "heaters, the FCC air blower, the SMR furnace and the emergency shutdown "
        "elements. They drive the turnaround sequence."
        % (sum(1 for u in UNITS if u["criticality"] == 1), len(UNITS)),
        "* Health is a condition score, not an availability figure; availability is in "
        "Section 13.",
        "",
        "## 4.4 Area commentary",
        "",
        "The same %d units read by area, with the maintenance and condition record for "
        "each area summarised from the registers in Sections 7 and 13." % len(AREAS),
        "",
        area_notes,
    )


# --------------------------------------------------------------------------
# Section 4b - Register / Overlay Crosswalk
# --------------------------------------------------------------------------

def sec_04b():
    rows = []
    for overlay, oname, ounit, reg, rname, conf, note in CROSSWALK:
        rows.append([overlay, oname, reg, rname, conf, note])
    return para(
        "The console ships two equipment vocabularies and this document uses both. "
        "They are declared here so that no tag in the dossier has to be inferred.",
        "",
        "* **Register vocabulary** - the %d tag numbers in "
        "`apps/web/public/simulation/refinery/equipment.json`. This is the live "
        "simulation register and the authority for Sections 4 and 5."
        % len(REGISTER_TAGS),
        "* **Overlay vocabulary** - the %d legacy assets in "
        "`data/demo/equipment/equipment.json`, the U-200 console/demo dataset: %s. "
        "These tags carry the narrative that already exists in the app (compressor C-3, "
        "pump P-1042, vessel V-2210, tank T-118, exchanger E-340, pump P-2051) and are "
        "used as the primary key in Sections 14 to 17 and wherever the console story "
        "is told." % (len(DEMO_TAGS), ", ".join(DEMO_TAGS)),
        "",
        "The crosswalk below maps each overlay asset to its register counterpart. "
        "`confidence` is deliberately explicit: **exact** means the same tag string "
        "exists in the register; **twin** means a distinct register tag carries the same "
        "machine signature or duty; **partial** means the register asset covers only "
        "part of the overlay service and the mapping must not be read as equivalence.",
        "",
        table(["Overlay tag", "Overlay name", "Register tag", "Register name",
               "Confidence", "Basis and caveat"], rows),
        "",
        "## 4b.1 Why C-3 maps to C-1071",
        "",
        "The mapping is not a guess. The register twin for C-3 is C-1071, the Reformer "
        "Recycle Compressor, and its instrumentation reproduces the console machine "
        "signature exactly: VIB-1071 nominal 5.7 mm/s (the learned C-3 baseline), "
        "RPM-1071 nominal 8,840 rpm (the console's 8,800 rpm running speed) and TT-1071 "
        "nominal 79 degC (the current drive-end bearing temperature). This is the "
        "strongest of the six mappings and is treated as an exact twin in this document.",
        "",
        "## 4b.2 Partial mappings",
        "",
        "V-2210 maps only partially. The overlay asset is a product separator vessel "
        "whose live issue is a high level excursion (87% against an 80% setpoint), while "
        "the register counterpart V-1047 is a process valve carrying actuator position "
        "feedback. The two are related by service position in the U-200 train, not by "
        "equipment identity, and V-2210's level excursion is therefore reported against "
        "the overlay tag with the register tag named only as a locator. P-2051 maps only "
        "partially for the same reason: the register asset P-1124 is in service, while "
        "the overlay asset is recorded as under maintenance, so condition data must not "
        "be copied between them.",
        "",
        "## 4b.3 How to read a tag in this document",
        "",
        "If a tag appears in the register vocabulary it is a live register asset and its "
        "row in Section 4 is authoritative. If it appears in the overlay vocabulary it is "
        "a console asset and its record in `data/demo/equipment/equipment.json` is "
        "authoritative; the register counterpart named here is used only to locate the "
        "asset in the physical plant. Where both appear together, the convention in this "
        "document is `register-tag (overlay-tag)`, for example `C-1071 (C-3)`.",
    )


# --------------------------------------------------------------------------
# Section 5 - Instrumentation
# --------------------------------------------------------------------------

def sec_05():
    all_sensors = [(u, s) for u in UNITS for s in u["sensors"]]
    rows = []
    for u, s in sorted(all_sensors, key=lambda pair: (pair[0]["tag"], pair[1]["tag"])):
        rows.append([s["tag"], u["tag"], s["measurement"], s["unit"], num(s["nominal"]),
                     sensor_band(s, "normal"), sensor_band(s, "warning"),
                     sensor_band(s, "critical")])
    overlay = []
    for r in OVERLAY_ROWS:
        overlay.append([r["asset"], r["name"], r["signal"], num(r["value"]), r["unit"],
                        num(r["baseline"]), num(r["limit"]),
                        "%+d%%" % r["delta"], r["state"]])
    detectors = [(u, s) for u, s in all_sensors if s.get("is_detector")
                 or s["measurement"] in ("gas", "leak", "flame")]
    detector_rows = []
    for u, s in sorted(detectors, key=lambda p: p[1]["tag"]):
        detector_rows.append([s["tag"], u["tag"], s["measurement"], s["unit"],
                              num(s["nominal"]), sensor_band(s, "critical")])
    by_meas = {}
    for _, s in all_sensors:
        by_meas[s["measurement"]] = by_meas.get(s["measurement"], 0) + 1
    meas_rows = [[k, v] for k, v in sorted(by_meas.items(), key=lambda kv: -kv[1])]

    cal_interval = {"pressure": 365, "temperature": 365, "flow": 365, "level": 180,
                    "vibration": 180, "current": 730, "power": 730, "position": 365,
                    "gas": 90, "leak": 90, "rpm": 365}
    cal_tol = {"pressure": "0.5% of span", "temperature": "1.0 degC", "flow": "1.0% of rate",
               "level": "0.5% of range", "vibration": "2.0% of reading",
               "current": "1.0% of range", "power": "1.5% of range",
               "position": "1.0% of travel", "gas": "2.0% LEL", "leak": "pass / fail",
               "rpm": "0.5% of reading"}
    cal_rows = []
    for u, s in sorted(all_sensors, key=lambda p: (p[0]["tag"], p[1]["tag"])):
        interval = cal_interval.get(s["measurement"], 365)
        r = rng_for("cal:" + s["tag"])
        offset = r.randrange(5, max(6, interval - 5))
        last = PERIOD_END - timedelta(days=offset)
        nxt = last + timedelta(days=interval)
        cal_rows.append([s["tag"], u["tag"], area_name(u["area_id"]), s["measurement"],
                         "%d d" % interval, iso(last), iso(nxt),
                         cal_tol.get(s["measurement"], "1.0% of span")])
    cal_table = table(["Sensor tag", "Equipment", "Area", "Measurement", "Interval",
                       "Last calibration", "Next due", "Tolerance"], cal_rows)

    return para(
        "The register carries **%d field instruments** across %d units, every one "
        "listed below. A sensor's `normal` band is the register's "
        "`normal_min..normal_max`; `warning` is `warning_min..warning_max` and "
        "`critical` is `critical_min..critical_max`. By construction each band "
        "strictly contains the previous one, so a warning range always sits outside "
        "the normal range and a critical range always outside the warning range. "
        "Latched detector channels (gas, leak) are one-sided by design: their lower "
        "thresholds collapse onto zero because a healthy detector reads zero."
        % (len(all_sensors), len(UNITS)),
        "",
        "**Column set (8 columns, in this order):** `Sensor tag`, `Equipment`, "
        "`Measurement`, `Unit`, `Nominal`, `Normal range`, `Warning range`, "
        "`Critical range`. This instrumentation schema joins to the 11-column "
        "equipment register in Section 4 on `Equipment` -> `Tag`; the `Tag` values "
        "here are exactly the register tags, so the two tables agree unit for unit.",
        "",
        "Instrumentation by measurement type:",
        "",
        table(["Measurement", "Instruments"], meas_rows),
        "",
        "### 5.1 Field instrument register",
        "",
        table(["Sensor tag", "Equipment", "Measurement", "Unit", "Nominal",
               "Normal range", "Warning range", "Critical range"], rows),
        "",
        "## 5.2 Latched detectors",
        "",
        "%d channels are latched point detectors. Healthy state is zero and a trip "
        "latches at full scale until the release is cleared and the device is reset. "
        "A detector reading zero is healthy, not failed, and must never be treated as "
        "an envelope violation (SOP-41.2 rev8)." % len(detector_rows),
        "",
        table(["Sensor tag", "Equipment", "Measurement", "Unit", "Nominal",
               "Critical band"], detector_rows),
        "",
        "### 5.3 Legacy overlay instrumentation (U-200 console dataset)",
        "",
        "The overlay assets report named signals rather than register sensor tags. "
        "They are reproduced verbatim from `data/demo/equipment/equipment.json` so "
        "the C-3, P-1042, E-340, T-118 and V-2210 narrative can be read against its "
        "own instrumentation. These signal names are not sensor tags and must not be "
        "searched as if they were.",
        "",
        table(["Asset", "Name", "Signal", "Value", "Unit", "Baseline", "Limit",
               "Deviation", "State"], overlay),
        "",
        "## 5.4 Loop calibration register",
        "",
        "Calibration intervals are set by measurement type: latched detectors every "
        "90 days, level and vibration every 180 days, pressure, temperature, flow, "
        "position and speed annually, and electrical measurements on a 730-day cycle. "
        "`last calibration` and `next due` are derived deterministically from the "
        "cutoff date and the interval; `next due` is a forecast and may fall after the "
        "dossier cutoff. Tolerance is the acceptance band applied after calibration, "
        "and a loop is not returned to automatic until the instrument agrees with its "
        "reference across the normal range for ten consecutive scans.",
        "",
        cal_table,
        "",
        "## 5.5 Instrumentation notes",
        "",
        "* Coverage of the compressor trains is the densest in the plant: the six "
        "registered compressors carry suction and discharge pressure, one or two "
        "temperature points, overall vibration and, on C-1071, a speed channel. "
        "This is deliberate - surge and bearing degradation are the two credible "
        "failure paths and both are observable.",
        "* The seven-instrument pump blocks (P-1001, P-1202, P-1042, P-1051, P-1061, "
        "P-1084, P-1091, P-1124, P-1127, P-1131, P-1132, P-1142, P-1171) carry "
        "redundant pressure (A/B), flow, temperature, vibration, current and power. "
        "The A/B pressure pair is what allows SOP-14.2 to be executed without "
        "stopping the pump when one transmitter fails.",
        "* Vibration channels use a rolling baseline rather than a fixed limit; the "
        "band shown in the table is the alarm envelope, and the learned baseline is "
        "evaluated separately (SOP-07.3 rev4).",
        "* Position feedback is instrumented on the five registered valves; the "
        "position loop is the first place an actuator fault becomes visible.",
    )


# --------------------------------------------------------------------------
# Section 6 - Operating Parameters
# --------------------------------------------------------------------------

def sec_06():
    out = [
        "This section states the operating envelope area by area. The `normal` band is "
        "the control target range; the plant is expected to run inside it. The `warning` "
        "band is the first deviation state and triggers increased monitoring. The "
        "`critical` band is the trip or immediate-action envelope. All figures are read "
        "from the register's own sensor definitions.",
        "",
    ]
    for a in AREAS:
        us = area_unit_rows(a["id"])
        rows = []
        for u in us:
            for s in u["sensors"]:
                rows.append([u["tag"], "%s (%s)" % (s["measurement"], s["tag"]),
                             "%s %s" % (num(s["nominal"]), s["unit"]),
                             sensor_band(s, "normal"), sensor_band(s, "warning"),
                             sensor_band(s, "critical")])
        out.append("### 6.%d %s" % (AREAS.index(a) + 1, a["name"]))
        out.append("")
        out.append("Controlling parameters for %d units / %d instruments. %s"
                   % (len(us), len(rows), _area_duty(a["id"]).capitalize() + "."))
        out.append("")
        out.append(table(["Asset", "Parameter", "Nominal", "Normal band",
                          "Warning band", "Critical band"], rows))
        out.append("")
        out.append("Envelope note. The controlling measurement in this area is %s on %s; "
                   "the widest envelope is %s on %s and the tightest is %s on %s. %s"
                   % (_area_primary(a["id"])[0], _area_primary(a["id"])[1],
                      _area_widest(a["id"])[0], _area_widest(a["id"])[1],
                      _area_tightest(a["id"])[0], _area_tightest(a["id"])[1],
                      area_summary_lines(a["id"])))
        out.append("")
    return "\n".join(out)


def _area_primary(area_id):
    us = area_unit_rows(area_id)
    u = max(us, key=lambda x: x["criticality"] * 100 + len(x["sensors"]))
    s = u["sensors"][0]
    return (s["measurement"], s["tag"])


def _area_widest(area_id):
    best = None
    for u in area_unit_rows(area_id):
        for s in u["sensors"]:
            width = (s["normal_max"] - s["normal_min"]) / max(abs(s["nominal"]), 1e-9)
            if best is None or width > best[0]:
                best = (width, s)
    return (best[1]["measurement"], best[1]["tag"]) if best else ("-", "-")


def _area_tightest(area_id):
    best = None
    for u in area_unit_rows(area_id):
        for s in u["sensors"]:
            width = (s["normal_max"] - s["normal_min"]) / max(abs(s["nominal"]), 1e-9)
            if best is None or width < best[0]:
                best = (width, s)
    return (best[1]["measurement"], best[1]["tag"]) if best else ("-", "-")


# --------------------------------------------------------------------------
# Section 7 - Maintenance History
# --------------------------------------------------------------------------

CAMPAIGN_YEARS = [
    ("Year 1", "Commissioning and baselining", date(2021, 6, 1), date(2022, 9, 30)),
    ("Year 2", "First minor vibration event", date(2022, 10, 1), date(2024, 2, 28)),
    ("Year 3", "Drive-end bearing replacement", date(2024, 3, 1), date(2025, 8, 31)),
    ("Year 4", "Rising vibration trend", date(2025, 9, 1), date(2026, 5, 31)),
    ("Year 5", "Current anomaly", date(2026, 6, 1), date(2026, 9, 30)),
]

YEAR_TEXT = {
    "Year 1": (
        "The review period opens with the compression train recommissioned after the "
        "rotor re-installation campaign. Baseline vibration on the drive-end bearing "
        "housing was established at **5.7 mm/s at 8,800 rpm** on 2021-06-14 and entered "
        "the condition-monitoring system as the learned baseline for the machine. That "
        "number is still the reference every later deviation is measured against. The "
        "same window delivered the current revision of the vibration response standard, "
        "SOP-07.3 rev4, and the first full instrument loop check across the "
        "seven-instrument pump blocks. Work in this year was overwhelmingly preventive: "
        "commissioning checks, loop verification, lubrication changes and baseline "
        "surveys."),
    "Year 2": (
        "The first minor vibration event appeared on 2022-11-18, when overall vibration "
        "briefly reached 6.1 mm/s on the drive-end housing during a lube-oil temperature "
        "excursion. The event cleared without mechanical intervention after a lube-oil "
        "flush and a filter change, but it established two things that shaped the rest "
        "of the record: the machine responds to oil condition before it responds to load, "
        "and the 1x component is the earliest indicator. The same year raised WO-2417, "
        "the coupling alignment inspection that would be re-executed three years later."),
    "Year 3": (
        "The drive-end bearing replacement of 2025-03-16 is the single most significant "
        "intervention in the record. Inspection IR-198 documents outer-race spalling on "
        "two rolling elements and lube-oil varnish on the cage; maintenance event ME-198 "
        "fitted an OEM spare and re-checked alignment before return to service. "
        "Post-repair overall vibration fell to 5.4 mm/s and the machine was re-baselined "
        "at 5.69 mm/s. The year also carried the first exchanger fouling review on E-340 "
        "and the tank integrity inspections on T-118."),
    "Year 4": (
        "Vibration began climbing again, slowly and monotonically. The 90-day rolling "
        "mean moved 5.69 -> 5.74 -> 5.80 mm/s across the year, and a hot alignment check "
        "on 2025-11-02 (ME-212, re-executing WO-2417) measured a coupling offset of "
        "0.06 mm against a 0.10 mm tolerance - inside tolerance, so no correction was "
        "made. Because alignment was eliminated as the driver, the residual trend was "
        "attributed to bearing degradation and placed under quarterly review."),
    "Year 5": (
        "The current anomaly crystallised on 2026-09-06. The IR-204 vibration survey "
        "measured 6.8 mm/s on the drive-end bearing housing against the 5.8 mm/s 90-day "
        "rolling baseline, an 18% increase developed progressively over eight days rather "
        "than as a step change, with drive-end bearing temperature at 79 degC against a "
        "68 degC baseline. Anomaly A-51 tracks it. Daily monitoring was imposed under "
        "SOP-07.3 rev4 section 4.2, WO-8852 was raised for drive-end bearing inspection "
        "and is pending outage approval APR-231. The machine remains on line inside its "
        "7.1 mm/s alarm limit."),
}


def sec_07():
    out = [
        "This section is the five-year maintenance history from 2021-06 through "
        "2026-09. It is presented as five campaign years. The campaign years are "
        "deliberately not calendar years: they are the phases the reliability programme "
        "actually ran in, and they are bounded so that each required milestone falls in "
        "the right phase. The full event register follows the narrative.",
        "",
        "| Campaign phase | Window | Theme |",
        "|---|---|---|",
    ]
    for label, theme, start, end in CAMPAIGN_YEARS:
        out.append("| %s | %s .. %s | %s |" % (label, iso(start), iso(end), theme))
    out.append("")
    for label, theme, start, end in CAMPAIGN_YEARS:
        events = [r for r in ME_RECORDS if start <= r["date"] <= end]
        corr = sum(1 for r in events if r["type"] == "corrective")
        out.append("### 7.%d %s - %s" % (CAMPAIGN_YEARS.index((label, theme, start, end)) + 1,
                                         label, theme))
        out.append("")
        out.append(YEAR_TEXT[label])
        out.append("")
        out.append("Recorded in this phase: %d maintenance events, of which %d were "
                   "corrective and %d preventive." % (len(events), corr, len(events) - corr))
        out.append("")

    out.append("## 7.6 Maintenance event register")
    out.append("")
    out.append("Every recorded event carries a maintenance event id (`ME-\\d+`) and, "
               "where a work order was raised, a work order number (`WO-\\d+`). The "
               "register is in strict date order. %d events are recorded in the period."
               % len(ME_RECORDS))
    out.append("")
    rows = []
    for r in ME_RECORDS:
        outcome = _me_outcome(r)
        rows.append([iso(r["date"]), r["me"], r["wo"], r["unit"], area_name(r["area"]),
                     r["type"], r["scope"], outcome])
    out.append(table(["Date", "ME id", "WO", "Equipment", "Area", "Type", "Scope",
                      "Outcome"], rows))
    out.append("")
    out.append("## 7.7 Work-order numbering")
    out.append("")
    out.append("Work order numbers are sequential within a calendar year and the "
               "series ascends across the period: 2021 uses 41xx, 2022 uses 47xx, 2023 "
               "uses 52xx, 2024 uses 57xx, 2025 uses 61xx and 2026 uses 86xx after the "
               "CMMS migration. Three numbers are fixed by the console narrative and "
               "appear out of series by design: **WO-2417** (C-3 coupling alignment, "
               "raised 2022 and re-executed 2025-11-02), **WO-6120** (C-3 drive-end "
               "bearing replacement, 2025-03-16) and the 2026 series **WO-8802**, "
               "**WO-8810**, **WO-8837**, **WO-8841** and **WO-8852**.")
    out.append("")
    out.append("## 7.8 Maintenance by area")
    out.append("")
    rows = []
    for a in AREAS:
        ev = [r for r in ME_RECORDS if r["area"] == a["id"]]
        corr = sum(1 for r in ev if r["type"] == "corrective")
        last = max((r["date"] for r in ev), default=None)
        rows.append([a["name"], len(ev), len(ev) - corr, corr,
                     iso(last) if last else "-"])
    out.append(table(["Area", "Events", "Preventive", "Corrective", "Last event"], rows))
    out.append("")
    out.append("Corrective share is the useful column: areas whose corrective share "
               "exceeds half are running reactively, and areas below a third are running "
               "on their preventive plan. The rotating-equipment areas sit at the top of "
               "the corrective share, which is consistent with the failure-mode frequency "
               "table in Section 13.4.")
    out.append("")
    for i, a in enumerate(AREAS):
        out.append("### 7.8.%d %s" % (i + 1, a["name"]))
        out.append("")
        out.append(area_summary_lines(a["id"]))
        out.append("")
    return "\n".join(out)


def _me_outcome(r):
    if r["me"] == "ME-198":
        return "Bearing replaced with OEM spare, alignment verified, re-baselined at 5.69 mm/s"
    if r["wo"] == "WO-2417" and r["date"] == ALIGN_DATE:
        return "Coupling offset 0.06 mm within 0.10 mm tolerance; no correction"
    if r["wo"] == "WO-8852":
        return "Open, pending approval APR-231"
    r2 = rng_for("me-out:" + r["me"])
    if r["type"] == "corrective":
        return pick(r2, [
            "Fault corrected, equipment returned to service inside the normal band",
            "Temporary repair applied, follow-up work order raised",
            "Component replaced, post-work survey inside the normal band",
            "Deviation cleared after adjustment, trend review scheduled",
        ])
    return pick(r2, [
        "No findings, next inspection interval retained",
        "Minor wear noted, no immediate action",
        "Consumable renewed, condition confirmed normal",
        "Check completed inside tolerance, next interval retained",
    ])


# --------------------------------------------------------------------------
# Section 8 - Inspection Records
# --------------------------------------------------------------------------

def sec_08():
    out = [
        "This section carries the %d formal inspection records raised in the period, "
        "`IR-177` through `IR-204`, in date order. Each record states the equipment, the "
        "finding and the disposition. **IR-198** is the drive-end bearing replacement and "
        "**IR-204** is the 2026 C-3 vibration survey; both are anchor documents for the "
        "C-3 history in Section 14." % len(IR_RECORDS),
        "",
        "| Inspection | Date | Equipment | Area | Inspector | Disposition |",
        "|---|---|---|---|---|---|",
    ]
    for r in IR_RECORDS:
        out.append("| %s | %s | %s | %s | %s | %s |"
                   % (r["ir"], iso(r["date"]), r["unit"], area_name(r["area"]),
                      r["inspector"], r["disposition"]))
    out.append("")
    for i, r in enumerate(IR_RECORDS):
        out.append("### 8.%d %s - %s" % (i + 1, r["ir"], r["unit"]))
        out.append("")
        out.append("**Date:** %s. **Equipment:** %s (%s), area %s. **Inspector:** %s."
                   % (iso(r["date"]), r["unit"], r["kind"], area_name(r["area"]), r["inspector"]))
        out.append("")
        out.append("**Findings.** %s" % r["finding"])
        out.append("")
        out.append("**Disposition.** %s" % r["disposition"])
        out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------------
# Section 9 - Failure Modes
# --------------------------------------------------------------------------

FM_RESPONSE = {
    "sensor_failure": "Mark the transmitter unavailable, validate an alternate, cross-check "
                      "against a correlated measurement, and move the unit to attended "
                      "operation if no consistent alternate exists (SOP-14.2 rev6).",
    "instrument_drift": "Freeze automatic action on the drifting point, raise a calibration "
                        "work order, and replace the element if drift recurs within one month "
                        "(SOP-14.7 rev3).",
    "bearing_wear": "Increase monitoring frequency, raise a corrective work order, and "
                    "inspect the bearing when overall vibration exceeds baseline by 15% with "
                    "1x dominance (SOP-07.3 rev4 section 4.3).",
    "cavitation": "Reduce speed or throttle discharge, restore upstream inventory, and stop "
                  "the pump if suction conditions cannot be restored promptly (SOP-22.4 rev2).",
    "bearing_overheat": "Reduce load, check lubrication and cooling, and stop on a controlled "
                        "ramp if vibration leaves the critical envelope (SOP-22.1 rev5).",
    "valve_stuck": "Place the loop in manual, hold the last safe position, and establish "
                   "whether the process can be controlled from an alternate path "
                   "(SOP-52.4 rev2).",
    "seal_leak": "Treat as a real release, isolate and depressurise, establish the exclusion "
                 "zone, and reset the detector only after the release is cleared "
                 "(SOP-31.5 rev7, SOP-41.2 rev8).",
    "pressure_surge": "Confirm against a second transmitter, reduce inlet flow, verify the "
                      "relief path to flare, and check for a downstream restriction "
                      "(SOP-27.9 rev3).",
    "trip": "Do not reset without establishing the cause, start the spare where one exists, "
            "and inspect the coupling and driven shaft before restart (SOP-18.3 rev4).",
    "fouling": "Trend shell-side delta-P against the clean reference, clean at the next "
               "available window, and re-rate the duty until then.",
    "overload": "Do not reset and restart a tripped drive; check the driven equipment's "
                "discharge conditions before assuming a motor fault (SOP-18.3 rev4).",
    "esd": "Execute the area shutdown per the unit procedure and reset only after the "
           "initiating condition is cleared and the area is confirmed safe.",
}


def fm_counts():
    counts = {}
    for m in FAILURE_MODES:
        c = 0
        for u in UNITS:
            if u["kind"] in m["applies_to"]:
                r = rng_for("fm:" + m["id"] + ":" + u["tag"])
                c += r.randrange(0, 3)
        counts[m["id"]] = max(1, c)
    return counts


FAILURE_MODE_COUNTS = fm_counts()


def sec_09():
    out = [
        "The simulation defines %d failure modes. Each mode names the equipment kinds it "
        "applies to, the physical mechanism it models, and the magnitude of its effect on "
        "the affected measurements. The table below is the failure-mode register; the "
        "subsections give detection and response." % len(FAILURE_MODES),
        "",
    ]
    rows = []
    for m in FAILURE_MODES:
        exposed = sum(1 for u in UNITS if u["kind"] in m["applies_to"])
        rows.append([m["id"], m["name"], ", ".join(m["applies_to"]), m["mechanism"],
                     num(m["magnitude"]), exposed, FAILURE_MODE_COUNTS[m["id"]]])
    out.append(table(["Mode id", "Name", "Applies to", "Mechanism", "Magnitude",
                      "Exposed units", "Recorded occurrences"], rows))
    out.append("")
    for i, m in enumerate(FAILURE_MODES):
        exposed = [u["tag"] for u in UNITS if u["kind"] in m["applies_to"]]
        out.append("### 9.%d %s" % (i + 1, m["name"]))
        out.append("")
        out.append("**Mode id:** `%s`. **Mechanism:** %s. **Magnitude:** %s. "
                   "**Applies to:** %s." % (m["id"], m["mechanism"], num(m["magnitude"]),
                                            ", ".join(m["applies_to"])))
        out.append("")
        out.append(m["description"])
        out.append("")
        out.append("Exposed register units (%d): %s." % (len(exposed), ", ".join(exposed)))
        out.append("")
        out.append("**Response.** %s" % FM_RESPONSE.get(m["id"], "Follow the applicable SOP."))
        out.append("")
        out.append("Recorded occurrences in the review period: %d." % FAILURE_MODE_COUNTS[m["id"]])
        out.append("")
    mode_detect = {
        "sensor_failure": ("pressure", "redundant pressure pair (A/B) on the same block",
                           "SOP-14.2 rev6"),
        "instrument_drift": ("temperature / pressure / flow",
                             "correlated measurement on the same service", "SOP-14.7 rev3"),
        "bearing_wear": ("vibration", "overall vibration against the learned baseline",
                         "SOP-07.3 rev4 s.4.3"),
        "cavitation": ("flow / pressure", "suction pressure and upstream level", "SOP-22.4 rev2"),
        "bearing_overheat": ("temperature", "bearing-housing thermocouple or RTD",
                             "SOP-22.1 rev5"),
        "valve_stuck": ("position", "commanded vs actual position feedback", "SOP-52.4 rev2"),
        "seal_leak": ("leak / gas", "latched area detector", "SOP-31.5 rev7"),
        "pressure_surge": ("pressure", "second independent transmitter", "SOP-27.9 rev3"),
        "trip": ("current", "current signature and drive status", "SOP-18.3 rev4"),
        "fouling": ("temperature / flow", "delta-T and delta-P at constant flow",
                    "fouling trend review"),
        "overload": ("current", "current draw against the rated envelope", "SOP-18.3 rev4"),
        "esd": ("gas / leak", "fire and gas panel matrix", "SOP-41.2 rev8"),
    }
    out.append("## 9.13 Detection summary")
    out.append("")
    out.append("Each failure mode has a primary measurement and a corroborating channel. "
               "The corroborating channel is what prevents a single failed transmitter from "
               "being mistaken for a process event, and it is the reason the pump blocks "
               "carry a redundant pressure pair.")
    out.append("")
    d_rows = []
    for m in FAILURE_MODES:
        meas, corr, sop = mode_detect.get(m["id"], ("-", "-", "-"))
        d_rows.append([m["id"], m["name"], meas, corr, sop])
    out.append(table(["Mode id", "Name", "Primary measurement", "Corroborating channel",
                      "Reference"], d_rows))
    out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------------
# Section 10 - Safety Procedures
# --------------------------------------------------------------------------

def sec_10():
    detectors = [(u, s) for u in UNITS for s in u["sensors"]
                 if s.get("is_detector") or s["measurement"] in ("gas", "leak", "flame")]
    det_rows = [[s["tag"], u["tag"], area_name(u["area_id"]), s["measurement"], s["unit"]]
                for u, s in detectors]
    safety_units = [u for u in UNITS if u["area_id"] == "safety"]
    return para(
        "## 10.1 Safety basis",
        "",
        "The plant's protective layer has three tiers: process control and operator "
        "response, alarm and operator action at the warning band, and the safety "
        "instrumented system at the critical band. This section states the standing "
        "rules; the procedures themselves are registered in Section 11.",
        "",
        "## 10.2 Lockout / tagout",
        "",
        "SOP-11.2 rev2 governs isolation of rotating equipment: obtain a work permit "
        "referencing the work order number, isolate the electrical supply at the "
        "designated disconnect and apply a personal lock, isolate process suction and "
        "discharge and bleed to atmospheric pressure, verify zero energy state, attach "
        "tags recording permit number, time and responsible person, and remove locks "
        "only by the person who applied them or under a documented two-signature "
        "supervisor override.",
        "",
        "## 10.3 Gas and leak detection",
        "",
        "The register carries %d latched detector channels. A detector reads zero when "
        "healthy and latches at full scale on a trip. A trip is treated as a real release "
        "until proven otherwise: the detector is never silenced or bypassed, the exclusion "
        "zone is set for the reported area, the release is isolated, and the detector is "
        "reset only after the release is confirmed cleared and it reads and holds zero. An "
        "incident may not be closed while any detector in the affected area remains "
        "latched (SOP-41.2 rev8)." % len(detectors),
        "",
        table(["Detector tag", "Equipment", "Area", "Measurement", "Unit"], det_rows),
        "",
        "## 10.4 Emergency shutdown",
        "",
        "The safety area holds %s. ESD-1181 is the fire and gas panel; ESD-1182 is the "
        "emergency shutdown valve. Scenario `sc-esd` exercises a controlled area shutdown "
        "initiated from ESD-1182. The shutdown philosophy is to isolate and depressurise "
        "to the flare rather than to hold inventory in a potentially leaking section, and "
        "the flare block (UT-1161 flare stack, VS-1162 flare knock-out drum) is the "
        "designated relief destination."
        % ", ".join("%s (%s)" % (u["tag"], u["name"]) for u in safety_units),
        "",
        "## 10.5 Process safety rules that recur in the record",
        "",
        "* Never isolate a relief device to stop a surge, and never raise an alarm limit "
        "to silence an alarm (SOP-27.9 rev3).",
        "* Crude and vacuum distillation may not run unattended with a lost column "
        "temperature or level measurement (OPS-03.2 rev4).",
        "* A unit may continue to run with a failed instrument only when a validated "
        "alternate covers the same control objective, the operator is notified, and the "
        "condition is reviewed at the next shift handover.",
        "* Escalate to a controlled rate reduction when two or more measurements on the "
        "same service are unavailable, when a detector is latched in the affected area, "
        "or when a downstream unit loses its only flow path.",
        "* A second trip on the same fault damages the winding; a tripped drive is not "
        "reset until the cause is established (SOP-18.3 rev4).",
        "",
        "## 10.6 Permit-to-work matrix",
        "",
        "The permit type is set by the work, not by the work order priority. A high-priority "
        "work order on a non-hydrocarbon utility still takes the lighter permit; a routine "
        "work order on a hydrocarbon line still takes the full isolation permit.",
        "",
        table(["Permit type", "Applies to", "Isolation required", "Gas test",
               "Fire watch", "Authority"], [
            ["Cold work", "Utilities, cooling water, instrument air, non-hydrocarbon "
             "externals", "None or local isolation", "Not required", "No", "Shift supervisor"],
            ["Hot work", "Any work introducing an ignition source in a process area",
             "Full process isolation", "Required before and during", "Yes",
             "Shift supervisor plus safety"],
            ["Confined space", "Tanks, vessels, columns, knock-out drums",
             "Full isolation and purge", "Required, continuous", "Standby man required",
             "Safety officer"],
            ["Electrical isolation", "Motors, drives, panels, instrument loops",
             "Electrical lockout at the disconnect", "Not required", "No",
             "Authorised electrical person"],
            ["Line break", "Hydrocarbon, acid gas, amine, steam lines",
             "Full isolation, drain and purge", "Required at the break point", "Yes",
             "Shift supervisor"],
            ["Rotating equipment", "Pumps, compressors, motors, fans",
             "Electrical plus process isolation (SOP-11.2)", "Required for hydrocarbon "
             "service", "As area dictates", "Shift supervisor"],
            ["Tank entry", "TK-1101, TK-1102, TK-1121, TK-1122, TK-1123",
             "Full isolation, drain, purge and inert where required", "Required, continuous",
             "Yes", "Safety officer"],
            ["Excavation", "Underground services and drainage",
             "Service drawings checked and services isolated", "As required", "No",
             "Shift supervisor"],
            ["Working at height", "Columns, stacks, flare, tanks", "Not applicable",
             "Not required", "No", "Shift supervisor"],
            ["Radiography", "Weld and wall-thickness surveys", "Area barricaded",
             "Not required", "No", "Safety officer"],
        ]),
    )


# --------------------------------------------------------------------------
# Section 11 - Standard Operating Procedures
# --------------------------------------------------------------------------

DEMO_SOPS = [
    ("SOP-07.3", "Rotating Equipment Vibration Response", "rev4", "vibration",
     "Maintenance Standards", "2026-05-22",
     "Defines the baseline deviation bands (0-10% routine, 10-25% daily monitoring plus a "
     "corrective work order within 72 h, above alarm limit reduce load and notify, above "
     "trip limit controlled shutdown), the daily monitoring requirement at section 4.2, "
     "the 15% / 1x bearing inspection trigger at section 4.3, and the manager approval "
     "gate for outages on criticality-high equipment at section 5."),
    ("SOP-11.2", "Lockout / Tagout for Rotating Equipment", "rev2", "lockout",
     "Safety", "2026-01-30",
     "Six-step isolation and tagout sequence for rotating equipment maintenance."),
]


def _read_frontmatter(path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    fm = {}
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip()
    return fm, text


def sop_corpus():
    docs = []
    for p in sorted((ROOT / "data" / "knowledge").glob("*.md")):
        if p.name.upper().startswith("REFINERY-TECHNICAL"):
            continue
        fm, text = _read_frontmatter(p)
        if not fm.get("id"):
            continue
        if "steel" in text[:2500].lower() or "blast furnace" in text[:2500].lower():
            continue
        docs.append({
            "id": fm.get("id", p.stem), "title": fm.get("title", p.stem),
            "revision": fm.get("revision", "-"), "kind": fm.get("kind", "-"),
            "mechanism": fm.get("mechanism", "-"), "owner": "Operations Standards",
            "effective": "-", "scope": _sop_scope(text),
        })
    for sid, title, rev, kind, owner, eff, scope in DEMO_SOPS:
        docs.append({"id": sid, "title": title, "revision": rev, "kind": kind,
                     "mechanism": "vibration" if kind == "vibration" else "lockout",
                     "owner": owner, "effective": eff, "scope": scope})
    return docs


def _sop_scope(text):
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("## scope"):
            body = []
            for nxt in lines[i + 1:]:
                if nxt.startswith("##"):
                    break
                if nxt.strip():
                    body.append(nxt.strip())
            return " ".join(body)
    return "Scope as stated in the controlled document."


def sec_11():
    docs = sop_corpus()
    rows = [[x["id"], x["title"], x["revision"], x["kind"], x["mechanism"],
             x["owner"], x["effective"]] for x in docs]
    out = [
        "This section registers the controlled operating procedures that govern the "
        "plant. %d procedures are in force in the review period. Each is scoped to a "
        "specific equipment kind and failure mechanism, which is what makes different "
        "incidents retrieve different evidence instead of one universal procedure."
        % len(docs),
        "",
        table(["Id", "Title", "Revision", "Kind", "Mechanism", "Owner", "Effective"], rows),
        "",
        "## 11.1 Procedure scope statements",
        "",
    ]
    for i, x in enumerate(docs):
        out.append("**%s %s (%s).** %s" % (x["id"], x["title"], x["revision"],
                                           x["scope"]))
        out.append("")
    out.append("## 11.2 Revision history in the period")
    out.append("")
    out.append("SOP-07.3 rev4 took effect on 2026-05-22 and is the revision in force "
               "during the C-3 anomaly; its section 4.3 bearing inspection trigger and "
               "section 5 outage-approval gate are the two clauses that produced WO-8852 "
               "and APR-231. SOP-11.2 rev2 took effect on 2026-01-30. The instrument "
               "procedures (SOP-14.2 rev6, SOP-14.7 rev3) were re-issued as the pump and "
               "compressor instrument base was completed. SOP-41.2 rev8 is the most "
               "revised safety procedure in the corpus, reflecting the detector-heavy "
               "protective layer.")
    out.append("")
    out.append("## 11.3 Procedure-to-failure-mode matrix")
    out.append("")
    out.append("Retrieval quality depends on this matrix: an incident on a pump bearing "
               "must retrieve SOP-22.1, not the column procedure, and a transmitter failure "
               "must retrieve SOP-14.2 regardless of which unit it sits on.")
    out.append("")
    proc_for = {
        "sensor_failure": ("SOP-14.2", "instrument"), "instrument_drift": ("SOP-14.7",
                                                                          "instrument"),
        "bearing_wear": ("SOP-07.3", "rotating"), "cavitation": ("SOP-22.4", "pump"),
        "bearing_overheat": ("SOP-22.1", "rotating"), "valve_stuck": ("SOP-52.4", "valve"),
        "seal_leak": ("SOP-31.5", "pump / vessel"), "pressure_surge": ("SOP-27.9", "static"),
        "trip": ("SOP-18.3", "motor / drive"), "fouling": ("fouling trend review", "exchanger"),
        "overload": ("SOP-18.3", "motor / drive"), "esd": ("SOP-41.2", "safety"),
    }
    p_rows = []
    for m in FAILURE_MODES:
        pid, kind = proc_for.get(m["id"], ("-", "-"))
        p_rows.append([m["id"], m["name"], pid,
                       ", ".join(m["applies_to"]), kind,
                       "%d" % FAILURE_MODE_COUNTS[m["id"]]])
    out.append(table(["Mode id", "Mode", "Governing procedure", "Equipment kinds",
                      "Family", "Occurrences"], p_rows))
    out.append("")
    out.append("Two procedures are cross-cutting rather than mode-specific: SOP-11.2 "
               "(lockout / tagout) applies to every intervention on a rotating machine, and "
               "OPS-03.2 (unit continuity) applies to every decision to keep a unit running "
               "with a degraded instrument.")
    return "\n".join(out)


# --------------------------------------------------------------------------
# Section 12 - Incident History
# --------------------------------------------------------------------------

def sec_12():
    out = [
        "This section is the incident and event register for the review period: %d "
        "dated rows, `INC-401` through `INC-430` and `EV-101` through `EV-106`. "
        "Severity is classified Low (no process impact, corrected at next opportunity), "
        "Medium (localised deviation, unit stayed on line), High (rate reduction or "
        "partial unit outage) or Critical (safety-relevant deviation, escalated)."
        % len(INCIDENTS),
        "",
        "| Id | Date | Equipment | Area | Measurement | Event | Severity | Cause class | Outcome |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in INCIDENTS:
        out.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s |"
                   % (r["id"], iso(r["date"]), r["unit"], area_name(r["area"]),
                      r["measurement"], r["title"], r["severity"], r["cause_class"],
                      r["outcome"]))
    out.append("")
    out.append("## 12.1 Severity distribution")
    out.append("")
    dist = {}
    for r in INCIDENTS:
        dist[r["severity"]] = dist.get(r["severity"], 0) + 1
    rows = [[k, v] for k, v in sorted(dist.items(), key=lambda kv: -kv[1])]
    out.append(table(["Severity", "Events"], rows))
    out.append("")
    out.append("## 12.2 Selected event narratives")
    out.append("")
    selected = [r for r in INCIDENTS if iso(r["date"]) in
                ("2026-09-03", "2026-09-04", "2026-09-06")] + INCIDENTS[:5]
    seen_ids = {r["id"] for r in selected}
    for r in INCIDENTS[6::4]:
        if len(selected) >= 15:
            break
        if r["id"] not in seen_ids:
            selected.append(r)
            seen_ids.add(r["id"])
    selected.sort(key=lambda r: r["date"])
    for i, r in enumerate(selected):
        out.append("### 12.2.%d %s - %s (%s)" % (i + 1, r["id"], r["unit"], iso(r["date"])))
        out.append("")
        out.append("%s on %s in area %s. %s %s"
                   % (r["title"].capitalize(), r["unit"], area_name(r["area"]),
                      r["detail"], r["outcome"].capitalize() + "."))
        out.append("")
    out.append("## 12.3 Cause classes")
    out.append("")
    out.append("Events split across mechanical degradation (bearing, valve, impeller), "
               "process deviation (level, pressure, flow), instrument fault (transmitter "
               "failure and drift), electrical (overload and trip) and leak (seal failure "
               "and detector trip). Instrument-caused events are the most common single "
               "class, which is why SOP-14.2 and SOP-14.7 are the two most used "
               "procedures in the corpus and why every seven-instrument pump block carries "
               "a redundant pressure pair.")
    return "\n".join(out)


# --------------------------------------------------------------------------
# Section 13 - Reliability Analysis
# --------------------------------------------------------------------------

def _last_failure_unit(tag):
    dates = [r["date"] for r in ME_RECORDS if r["unit"] == tag and r["type"] == "corrective"]
    return max(dates) if dates else None


def sec_13():
    unit_rows = []
    rel = {}
    for u in UNITS:
        fails, mtbf, mttr, avail = unit_reliability(u)
        rel[u["tag"]] = (fails, mtbf, mttr, avail)
        lf = _last_failure_unit(u["tag"])
        unit_rows.append([u["tag"], u["name"], area_name(u["area_id"]), fails,
                          "%.0f" % mtbf, "%.1f" % mttr, "%.3f" % avail,
                          iso(lf) if lf else "-"])
    total_fails = sum(v[0] for v in rel.values())
    area_rows = []
    for a in AREAS:
        us = area_unit_rows(a["id"])
        f = sum(rel[u["tag"]][0] for u in us)
        mtbf = sum(rel[u["tag"]][1] for u in us) / len(us)
        mttr = sum(rel[u["tag"]][2] for u in us) / len(us)
        avail = sum(rel[u["tag"]][3] for u in us) / len(us)
        area_rows.append([a["name"], len(us), f, "%.0f" % mtbf, "%.1f" % mttr,
                          "%.3f" % avail])
    fm_rows = []
    for m in FAILURE_MODES:
        c = FAILURE_MODE_COUNTS[m["id"]]
        fm_rows.append([m["id"], m["name"], c, "%.1f%%" % (100.0 * c / total_fails)])
    worst = sorted(UNITS, key=lambda u: rel[u["tag"]][3])[:10]
    worst_rows = [[u["tag"], u["name"], area_name(u["area_id"]), rel[u["tag"]][0],
                   "%.0f" % rel[u["tag"]][1], "%.1f" % rel[u["tag"]][2],
                   "%.3f" % rel[u["tag"]][3]] for u in worst]

    out = [
        "Reliability is computed over the review window 2021-06-01 to 2026-09-30. "
        "Operating hours are counted from the later of the unit's commissioned date and "
        "the window start, at 24 hours per day. Failure counts are the seeded corrective "
        "event counts for each unit; MTBF is operating hours divided by failures, MTTR is "
        "the mean corrective duration in hours, and availability is "
        "`MTBF / (MTBF + MTTR)`.",
        "",
        "## 13.1 Method and caveats",
        "",
        "These are model-derived figures, not meter readings. They are internally "
        "consistent with the maintenance register and are reproducible from the fixed "
        "seed. The absolute values matter less than the ordering: rotating equipment "
        "dominates unplanned work, and the two assets under open corrective work (C-1071 "
        "and P-1042) sit at the bottom of the availability table, which is why they are "
        "the subjects of Sections 14 and 15.",
        "",
        "## 13.2 Availability by unit",
        "",
        table(["Tag", "Name", "Area", "Failures", "MTBF (h)", "MTTR (h)",
               "Availability %", "Last failure"], unit_rows),
        "",
        "## 13.3 Availability by area",
        "",
        table(["Area", "Units", "Failures", "Mean MTBF (h)", "Mean MTTR (h)",
               "Mean availability %"], area_rows),
        "",
        "## 13.4 Failure-mode frequency",
        "",
        table(["Mode id", "Name", "Occurrences", "Share of failures"], fm_rows),
        "",
        "## 13.5 Lowest-availability assets",
        "",
        table(["Tag", "Name", "Area", "Failures", "MTBF (h)", "MTTR (h)",
               "Availability %"], worst_rows),
        "",
        "## 13.6 Reading",
        "",
        "Across %d units the record shows %d corrective failures, a plant mean MTBF of "
        "%.0f hours and a mean MTTR of %.1f hours. The spread between the best and worst "
        "unit is roughly an order of magnitude, which is normal for a plant where "
        "rotating machines, fired heaters and safety elements are counted the same way. "
        "The compressor train is not the least reliable block in the plant, but it is the "
        "block whose degradation is most observable: a 1x-dominant vibration trend gives "
        "weeks of warning, which is exactly why the C-3 anomaly was caught before the "
        "alarm limit rather than after it."
        % (len(UNITS), total_fails,
           sum(v[1] for v in rel.values()) / len(rel),
           sum(v[2] for v in rel.values()) / len(rel)),
        "",
        "## 13.7 Area reliability commentary",
        "",
        "The commentary below pairs each area's availability figures with its condition "
        "and maintenance record so that a high availability with a low health score (a "
        "degraded asset still running) can be told apart from a genuinely reliable area.",
        "",
    ]
    for i, a in enumerate(AREAS):
        out.append("### 13.7.%d %s" % (i + 1, a["name"]))
        out.append("")
        out.append(area_summary_lines(a["id"]))
        out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------------
# Sections 14-17 - deep asset histories
# --------------------------------------------------------------------------

def _unit_event_rows(tag):
    rows = []
    for r in ME_RECORDS:
        if r["unit"] == tag:
            rows.append([iso(r["date"]), r["me"], r["wo"], r["type"], r["scope"]])
    for r in IR_RECORDS:
        if r["unit"] == tag:
            rows.append([iso(r["date"]), r["ir"], "-", "inspection", r["disposition"]])
    rows.sort(key=lambda x: x[0])
    return rows


def sec_14():
    u = UNIT_BY_TAG["C-1071"]
    sensors = [[s["tag"], s["measurement"], s["unit"], num(s["nominal"]),
                sensor_band(s, "normal"), sensor_band(s, "warning"),
                sensor_band(s, "critical")] for s in u["sensors"]]
    overlay = [[r["signal"], num(r["value"]), r["unit"], num(r["baseline"]),
                num(r["limit"]), "%+d%%" % r["delta"], r["state"]]
               for r in OVERLAY_ROWS if r["asset"] == "C-3"]
    events = _unit_event_rows("C-1071")
    chronology = [
        ["2021-06-14", "Commissioning", "Compression train recommissioned after the rotor "
         "re-installation campaign; baseline set at 5.7 mm/s at 8,800 rpm."],
        ["2022-11-18", "A-19 / ME-067", "First minor vibration event: 6.1 mm/s transient "
         "during a lube-oil temperature excursion, cleared by oil flush and filter change."],
        ["2022-06-14", "WO-2417", "Coupling alignment inspection raised (legacy CMMS number)."],
        ["2025-03-16", "IR-198 / ME-198 / WO-6120", "Drive-end bearing replaced. Outer-race "
         "spalling on two rolling elements, lube-oil varnish on the cage. Post-repair "
         "vibration 5.4 mm/s, re-baselined at 5.69 mm/s."],
        ["2025-11-02", "ME-212 / WO-2417", "Hot alignment check. Coupling offset 0.06 mm "
         "against 0.10 mm tolerance; no correction required."],
        ["2026-03-16", "Baseline", "90-day rolling mean 5.74 mm/s; trend classified as "
         "slow bearing degradation, quarterly review."],
        ["2026-09-06", "IR-204 / A-51", "Survey measures 6.8 mm/s against a 5.8 mm/s rolling "
         "baseline (+18%), 1x dominant, DE bearing housing 79 degC against 68 degC."],
        ["2026-09-07", "WO-8852 / APR-231", "Drive-end bearing inspection work order raised "
         "under SOP-07.3 rev4 section 4.3; outage approval pending."],
    ]
    spectral = [
        ["1x running speed (49.6 Hz)", "4.9", "dominant; rising"],
        ["2x running speed", "1.1", "stable"],
        ["Bearing defect band (BPFO)", "0.6", "slightly elevated"],
    ]
    return para(
        "## 14.1 Identity",
        "",
        "**C-3 (register twin C-1071), Recycle Gas Compressor.** Overlay asset from the "
        "U-200 console dataset; register counterpart C-1071, Reformer Recycle Compressor, "
        "area %s, criticality %s, manufacturer %s, model %s, commissioned %s. "
        "Register health 82/100, status WARNING. The mapping is exact in machine "
        "signature - see Section 4b.1." % (area_name(u["area_id"]),
                                           CLASS_LABEL[u["criticality"]],
                                           u["manufacturer"], unit_model(u), unit_commissioned(u)),
        "",
        "## 14.2 Machine data",
        "",
        table(["Attribute", "Value"],
              [["Service", "Recycle gas compression, U-200 hydrotreater train"],
               ["Register tag", "C-1071"],
               ["Overlay tag", "C-3"],
               ["Kind", "compressor"],
               ["Running speed", "8,800 rpm (register nominal RPM-1071 = 8,840 rpm)"],
               ["Vibration baseline", "5.7 mm/s at 8,800 rpm (learned, 2021-06-14)"],
               ["90-day rolling baseline", "5.80 mm/s (established 2026-09-07)"],
               ["Alert threshold", "5.8 mm/s; alarm 7.1 mm/s (manual Table 7-2)"],
               ["Latest survey", "6.8 mm/s RMS, 2026-09-06 (IR-204)"],
               ["DE bearing temperature", "79 degC against a 68 degC baseline"],
               ["Open work", "WO-8852 (pending APR-231); WO-2417 alignment follow-up"]]),
        "",
        "## 14.3 Instrumentation",
        "",
        "Register instruments on C-1071:",
        "",
        table(["Sensor", "Measurement", "Unit", "Nominal", "Normal", "Warning", "Critical"],
              sensors),
        "",
        "Overlay signals on C-3:",
        "",
        table(["Signal", "Value", "Unit", "Baseline", "Limit", "Deviation", "State"],
              overlay),
        "",
        "## 14.4 Five-year chronology",
        "",
        table(["Date", "Reference", "Event"], chronology),
        "",
        "## 14.5 IR-204 spectral evidence",
        "",
        table(["Frequency", "Amplitude (mm/s)", "Interpretation"], spectral),
        "",
        "Energy is concentrated at 1x running speed with a stable 2x component. Combined "
        "with the drive-end bearing temperature rise, this pattern is consistent with "
        "progressive drive-end bearing wear or a developing alignment shift, not with "
        "looseness or blade-pass excitation. On 2025-11-02 the coupling offset was 0.06 mm "
        "against a 0.10 mm tolerance, so alignment was eliminated as the primary driver at "
        "that time; the residual trend is therefore attributed to the bearing.",
        "",
        "## 14.6 Register event history",
        "",
        table(["Date", "Reference", "Work order", "Type", "Scope"],
              events if events else [["-", "-", "-", "-", "No register events recorded"]]),
        "",
        "## 14.7 Learned rules and standing controls",
        "",
        "* **C-3 vibration baseline: 5.7 mm/s at 8,800 rpm.** This is the reference every "
        "deviation in the record is measured against.",
        "* SOP-07.3 rev4 section 4.2: above 10% deviation, monitoring rises to once per "
        "shift and a corrective work order is raised within 72 hours.",
        "* SOP-07.3 rev4 section 4.3: a drive-end bearing inspection is required when "
        "overall vibration exceeds baseline by 15% or more with 1x dominance, or when "
        "bearing housing temperature rises more than 10 degC above baseline. IR-204 "
        "satisfies both triggers.",
        "* SOP-07.3 rev4 section 5: an outage on criticality-high equipment requires "
        "Maintenance Manager approval - this is APR-231.",
        "",
        "## 14.8 Assessment",
        "",
        "The machine is inside its alarm limit but outside the 10% deviation band and "
        "above the 15% bearing inspection trigger. The trend is progressive, not a step "
        "change. The correct posture is to keep the machine on line under once-per-shift "
        "monitoring while the outage window is approved, and to inspect the drive-end "
        "bearing at the first available opportunity rather than to wait for the alarm "
        "limit. If vibration reaches 7.1 mm/s, or bearing temperature reaches 85 degC, "
        "SOP-07.3 requires a load reduction and shift-supervisor notification.",
    )


def sec_15():
    u = UNIT_BY_TAG["P-1042"]
    sensors = [[s["tag"], s["measurement"], s["unit"], num(s["nominal"]),
                sensor_band(s, "normal"), sensor_band(s, "warning"),
                sensor_band(s, "critical")] for s in u["sensors"]]
    overlay = [[r["signal"], num(r["value"]), r["unit"], num(r["baseline"]),
                num(r["limit"]), "%+d%%" % r["delta"], r["state"]]
               for r in OVERLAY_ROWS if r["asset"] == "P-1042"]
    events = _unit_event_rows("P-1042")
    scen = [[s["id"], s["name"], ", ".join(
        "%s -> %s (%s)" % (st["action"], st["target"], st.get("mode", "-")) for st in s["steps"])]
        for s in SCENARIOS if any(st["target"] in ("e-P-1042",) or "P-1042" in s["name"]
                                  for st in s["steps"])]
    return para(
        "## 15.1 Identity",
        "",
        "**P-1042 (register and overlay), Crude Charge Pump.** The only asset whose tag "
        "string exists in both vocabularies - an **exact** mapping. Register area %s, "
        "criticality %s, manufacturer %s, model %s, commissioned %s, register "
        "health 84/100, status WARNING. The overlay names the same machine the Feed "
        "Charge Pump." % (area_name(u["area_id"]), CLASS_LABEL[u["criticality"]],
                          u["manufacturer"], unit_model(u), unit_commissioned(u)),
        "",
        "## 15.2 Current condition",
        "",
        "Discharge pressure is running at 18.5 bar against a 17.0 bar operating alert "
        "threshold and a 16.2 bar baseline, a deviation of +14%. The transmitter envelope "
        "for PT-1042A is wider than the operating limit: its normal band is 17.76 to 19.24 "
        "bar, its warning band 16.65 to 19.98 bar and its critical band 15.17 to 21.46 bar. "
        "The excursion is therefore an operating-limit breach, not an instrument-envelope "
        "breach, and the process limit is the number that governs the response.",
        "",
        "## 15.3 Instrumentation",
        "",
        table(["Sensor", "Measurement", "Unit", "Nominal", "Normal", "Warning", "Critical"],
              sensors),
        "",
        "Overlay signal:",
        "",
        table(["Signal", "Value", "Unit", "Baseline", "Limit", "Deviation", "State"],
              overlay),
        "",
        "The seven-instrument block carries a redundant pressure pair, PT-1042A and "
        "PT-1042B. That redundancy is what makes scenario `sc-sensor-failure` survivable: "
        "if PT-1042A fails, PT-1042B carries the process and SOP-14.2 governs the response "
        "without stopping the pump.",
        "",
        "## 15.4 Exercises that target this pump",
        "",
        table(["Scenario", "Name", "Steps"], scen),
        "",
        "## 15.5 Learned rules and standing controls",
        "",
        "* **P-1042 discharge pressure alert threshold: 17 bar.** This is an operating "
        "limit, held separately from the PT-1042A transmitter envelope, because the "
        "transmitter is deliberately ranged wider than the process limit.",
        "* SOP-14.2 rev6 governs field instrument failure: mark the transmitter "
        "unavailable, validate the alternate, cross-check against a correlated "
        "measurement (flow against pump discharge pressure), and move to attended "
        "operation if no consistent alternate exists.",
        "* WO-8841 (raised 2026-09-04) is the open corrective work order: check the relief "
        "path and impeller wear.",
        "",
        "## 15.6 Register event history",
        "",
        table(["Date", "Reference", "Work order", "Type", "Scope"],
              events if events else [["-", "-", "-", "-", "No register events recorded"]]),
        "",
        "## 15.7 Assessment",
        "",
        "Two credible causes fit a +14% discharge pressure excursion with stable flow: "
        "impeller wear raising the head required for the same duty, or a downstream "
        "restriction raising the back pressure. The correct next step is to trend "
        "FT-1042 against PT-1042A and PT-1042B together - if flow is falling while "
        "pressure rises, the restriction is downstream; if flow and pressure rise "
        "together, the pump is being asked for more head. Suction conditions should be "
        "confirmed against the desalter and crude storage levels before any mechanical "
        "work is scheduled, because cavitation (scenario `sc-cavitation`) produces the "
        "same pressure signature.",
    )


def sec_16():
    u = UNIT_BY_TAG["E-1063"]
    sensors = [[s["tag"], s["measurement"], s["unit"], num(s["nominal"]),
                sensor_band(s, "normal"), sensor_band(s, "warning"),
                sensor_band(s, "critical")] for s in u["sensors"]]
    overlay = [[r["signal"], num(r["value"]), r["unit"], num(r["baseline"]),
                num(r["limit"]), "%+d%%" % r["delta"], r["state"]]
               for r in OVERLAY_ROWS if r["asset"] == "E-340"]
    trend = []
    clean = 0.28
    for i, q in enumerate(["2025-Q3", "2025-Q4", "2026-Q1", "2026-Q2", "2026-Q3"]):
        val = round(0.28 + 0.035 * i, 3)
        trend.append([q, "%.3f" % val, "%.3f" % clean,
                      "%.1f%%" % (100.0 * (val - clean) / clean)])
    events = _unit_event_rows("E-1063")
    return para(
        "## 16.1 Identity",
        "",
        "**E-340 (register twin E-1063), Feed/Effluent Heat Exchanger.** Shell-and-tube "
        "exchanger on the U-200 hydrotreater train; register counterpart E-1063, NHT "
        "Effluent Cooler, area %s, criticality %s, manufacturer %s, model %s, "
        "commissioned %s. Register health %d/100, status NORMAL." 
        % (area_name(u["area_id"]), CLASS_LABEL[u["criticality"]],
           u["manufacturer"], unit_model(u), unit_commissioned(u), unit_health(u)),
        "",
        "## 16.2 Service and instrumentation",
        "",
        "The exchanger recovers heat from the hydrotreater effluent to the reactor feed. "
        "Its condition is read almost entirely from three points: inlet temperature "
        "TT-1063I (nominal 210 degC), outlet temperature TT-1063O (nominal 188 degC) and "
        "tube-side flow FT-1063 (nominal 88 m3/h). Duty is inferred from the temperature "
        "drop across the unit; fouling shows up first as a shrinking delta-T at constant "
        "flow, then as a rising shell-side delta-P.",
        "",
        table(["Sensor", "Measurement", "Unit", "Nominal", "Normal", "Warning", "Critical"],
              sensors),
        "",
        "Overlay signal:",
        "",
        table(["Signal", "Value", "Unit", "Baseline", "Limit", "Deviation", "State"],
              overlay),
        "",
        "## 16.3 Fouling analysis",
        "",
        "The overlay delta-P is 0.42 bar against a 0.40 bar baseline and a 0.75 bar "
        "limit, a deviation of +5% - inside the normal band, which is why the quarterly "
        "review (WO-8810) expects no action. The register-side trend over five quarters:",
        "",
        table(["Quarter", "Shell-side delta-P (bar)", "Clean reference (bar)",
               "Deviation from clean"], trend),
        "",
        "Fouling is progressive and slow. The mechanism models as `fouling` with "
        "magnitude 0.3: fouling factor rises and duty and outlet temperature sag. The "
        "engineering response is to trend, not to clean early: cleaning has a cost and a "
        "window, and cleaning a bundle at 5% over the clean reference recovers almost no "
        "duty.",
        "",
        "## 16.4 Learned rules and standing controls",
        "",
        "* WO-8810 (raised 2026-08-26) is the quarterly delta-P trend review; its expected "
        "outcome is no action, and the work order exists to make the absence of action an "
        "explicit, recorded decision.",
        "* A cleaning decision requires the delta-P to approach the 0.75 bar limit or the "
        "outlet temperature to fall outside the normal band at constant inlet conditions.",
        "* The exchanger is not a rotating machine and carries no vibration channel; "
        "fouling is its only credible degradation path, together with `pressure_surge` on "
        "the shell side (scenario `sc-pressure-surge` targets the atmospheric column, but "
        "the same mechanism applies to any shell-side inventory).",
        "",
        "## 16.5 Register event history",
        "",
        table(["Date", "Reference", "Work order", "Type", "Scope"],
              events if events else [["-", "-", "-", "-", "No register events recorded"]]),
        "",
        "## 16.6 Assessment",
        "",
        "The exchanger is healthy. Delta-P is 5% above the clean reference and the outlet "
        "temperature is inside the normal band. The correct posture is to keep the "
        "quarterly trend review, watch for the point at which the outlet temperature "
        "starts to sag at constant flow (that is the real duty-loss signal, earlier and "
        "more useful than delta-P), and hold the bundle for the next planned window rather "
        "than an unscheduled clean.",
    )


def sec_17():
    u = UNIT_BY_TAG["TK-1121"]
    sensors = [[s["tag"], s["measurement"], s["unit"], num(s["nominal"]),
                sensor_band(s, "normal"), sensor_band(s, "warning"),
                sensor_band(s, "critical")] for s in u["sensors"]]
    overlay = [[r["signal"], num(r["value"]), r["unit"], num(r["baseline"]),
                num(r["limit"]), "%+d%%" % r["delta"], r["state"]]
               for r in OVERLAY_ROWS if r["asset"] == "T-118"]
    events = _unit_event_rows("TK-1121")
    return para(
        "## 17.1 Identity",
        "",
        "**T-118 (register twin TK-1121), Intermediate Storage Tank.** Atmospheric "
        "storage tank in the tank farm; register counterpart TK-1121, Naphtha Tank, area "
        "%s, criticality %s, manufacturer %s, model %s, commissioned %s. Register "
        "health %d/100, status NORMAL." 
        % (area_name(u["area_id"]), CLASS_LABEL[u["criticality"]],
           u["manufacturer"], unit_model(u), unit_commissioned(u), unit_health(u)),
        "",
        "## 17.2 Service and instrumentation",
        "",
        "T-118 buffers intermediate product between the process units and the finished "
        "product tanks. It is instrumented for level (LT-1121, nominal 62%) and "
        "temperature (TT-1121, nominal 41 degC). The overlay reports level at 54% against "
        "a 55% baseline and a 90% limit, i.e. normal, and the asset is recorded healthy.",
        "",
        table(["Sensor", "Measurement", "Unit", "Nominal", "Normal", "Warning", "Critical"],
              sensors),
        "",
        "Overlay signal:",
        "",
        table(["Signal", "Value", "Unit", "Baseline", "Limit", "Deviation", "State"],
              overlay),
        "",
        "## 17.3 Integrity and inspection regime",
        "",
        "The tank is on a six-monthly external visual inspection cycle; the most recent "
        "was completed on 2026-08-18 under WO-8802 with no findings. The register twin's "
        "commissioned date is %s and its last recorded inspection was %s. Tank integrity "
        "is a static problem: there is no vibration, no rotating degradation and no "
        "fouling mechanism in the failure-mode set that applies to it. The credible "
        "issues are level instrument error, roof seal wear, secondary containment breach "
        "and, at the extreme, overfill."
        % (unit_commissioned(u), u["last_inspection"]),
        "",
        "## 17.4 Learned rules and standing controls",
        "",
        "* WO-8802 (2026-08-18) is the six-monthly external visual inspection; completed "
        "with no findings.",
        "* Level is the safety-critical measurement: high level is a containment risk and "
        "low level is a transfer risk. LT-1121 is calibrated at every second inspection.",
        "* A tank with an uncalibrated level transmitter must not be used to close an "
        "inventory balance; the level is cross-checked against the gauging tape at each "
        "external inspection.",
        "",
        "## 17.5 Register event history",
        "",
        table(["Date", "Reference", "Work order", "Type", "Scope"],
              events if events else [["-", "-", "-", "-", "No register events recorded"]]),
        "",
        "## 17.6 Assessment",
        "",
        "No action. The tank is inside every band, the level is below its baseline rather "
        "than above it, and the last two external inspections produced no findings. The "
        "only standing requirement is the six-monthly cycle, which is next due on the "
        "register interval computed in Section 4.",
    )


# --------------------------------------------------------------------------
# Section 18 - Historical Anomalies
# --------------------------------------------------------------------------

def sec_18():
    out = [
        "The anomaly register carries %d tracked deviations, `A-04` through `A-51`, in "
        "date order. An anomaly is a measurement outside its learned trend that did not "
        "necessarily breach an alarm limit - the point of the register is to catch "
        "deviations before they become incidents. `A-51` is the current C-3 vibration "
        "anomaly." % len(ANOMALIES),
        "",
        "| Anomaly | Date | Equipment | Area | Measurement | Magnitude vs baseline | Resolution |",
        "|---|---|---|---|---|---|---|",
    ]
    for a in ANOMALIES:
        out.append("| %s | %s | %s | %s | %s | %s | %s |"
                   % (a["id"], iso(a["date"]), a["unit"], area_name(a["area"]),
                      a["measurement"], a["magnitude"], a["resolution"]))
    out.append("")
    out.append("## 18.1 Notable anomalies")
    out.append("")
    for a in ANOMALIES[-14:]:
        out.append("**%s - %s, %s (%s).** %s Resolution: %s"
                   % (a["id"], a["unit"], iso(a["date"]), a["measurement"],
                      a["notes"], a["resolution"]))
        out.append("")
    out.append("## 18.2 Anomalies by measurement")
    out.append("")
    dist = {}
    for a in ANOMALIES:
        dist[a["measurement"]] = dist.get(a["measurement"], 0) + 1
    out.append(table(["Measurement", "Anomalies"],
                     [[k, v] for k, v in sorted(dist.items(), key=lambda kv: -kv[1])]))
    out.append("")
    out.append("## 18.3 Anomalies by area")
    out.append("")
    adist = {}
    for a in ANOMALIES:
        adist[area_name(a["area"])] = adist.get(area_name(a["area"]), 0) + 1
    out.append(table(["Area", "Anomalies"],
                     [[k, v] for k, v in sorted(adist.items(), key=lambda kv: -kv[1])]))
    return "\n".join(out)


# --------------------------------------------------------------------------
# Section 19 - Maintenance Interventions
# --------------------------------------------------------------------------

def sec_19():
    major = [r for r in ME_RECORDS if r["type"] == "corrective" or r["overlay"]]
    major = sorted(major, key=lambda r: r["date"])
    rows = []
    for r in major:
        rr = rng_for("intv:" + r["me"])
        dur = round(3.0 + rr.random() * 29.0, 1)
        impact = pick(rr, ["none - duty covered by spare", "brief rate reduction",
                           "localised unit slowdown", "none - line isolated",
                           "short controlled stop"])
        rows.append([r["me"], iso(r["date"]), r["unit"], r["wo"], r["kind"],
                     "%.1f" % dur, impact, _me_outcome(r)])
    out = [
        "This section is the intervention register: the corrective events and the pinned "
        "console-narrative events, with duration and production impact. Preventive work "
        "is registered in Section 7 and is not repeated here. **%d interventions** are "
        "recorded." % len(rows),
        "",
        table(["ME id", "Date", "Equipment", "WO", "Kind", "Duration (h)",
               "Production impact", "Outcome"], rows),
        "",
        "## 19.1 Intervention classes",
        "",
        "Interventions fall into four classes: **instrument** (transmitter replacement, "
        "calibration and loop repair), **mechanical rotating** (bearing, seal, coupling "
        "and impeller work), **static** (valve actuator, exchanger bundle, vessel "
        "internals) and **electrical** (motor and drive). Mechanical rotating work "
        "consumes the most downtime per event; instrument work is the most frequent but "
        "the shortest. That asymmetry is the reason the plant carries redundant pressure "
        "on every seven-instrument pump block: it converts the most frequent failure class "
        "into a no-stop event.",
        "",
        "## 19.2 The three anchor interventions",
        "",
        "* **ME-198 (2025-03-16, C-3 / C-1071, WO-6120).** Drive-end bearing replacement. "
        "Outer-race spalling on two rolling elements and lube-oil varnish on the cage. "
        "Post-repair vibration 5.4 mm/s; re-baselined at 5.69 mm/s.",
        "* **ME-212 (2025-11-02, C-3 / C-1071, WO-2417).** Hot alignment check after six "
        "hours of steady operation. Coupling offset 0.06 mm against a 0.10 mm tolerance, "
        "angular 0.02 mm/100 mm against 0.05. Soft-foot check passed. No correction.",
        "* **WO-8852 (2026-09-07, C-3 / C-1071).** Drive-end bearing inspection raised "
        "from IR-204, pending outage approval APR-231.",
    ]
    return "\n".join(out)


# --------------------------------------------------------------------------
# Section 20 - Current Operational Status
# --------------------------------------------------------------------------

ACTIVE_WORK_ORDERS = [
    ["WO-8852", "C-1071 (C-3)", "C-3 drive-end bearing inspection", "high", "open",
     "2026-09-18", "pending approval APR-231"],
    ["WO-8841", "P-1042", "P-1042 discharge pressure investigation", "medium",
     "in_progress", "2026-09-12", "relief path and impeller wear check"],
    ["WO-8837", "V-1047 (V-2210)", "V-2210 high level alarm response", "critical",
     "in_progress", "2026-09-10", "level loop verified and drained"],
    ["WO-8810", "E-1063 (E-340)", "E-340 fouling trend review", "low", "open",
     "2026-09-30", "quarterly delta-P review; no action expected"],
    ["WO-8802", "TK-1121 (T-118)", "T-118 external visual inspection", "low",
     "completed", "2026-08-30", "no findings"],
    ["WO-2417", "C-1071 (C-3)", "C-3 coupling alignment re-execution", "medium",
     "completed", "-", "offset 0.06 mm within tolerance"],
]


def sec_20():
    unit_rows = []
    for u in UNITS:
        unit_rows.append([u["tag"], u["name"], area_name(u["area_id"]),
                          unit_status(u), "%d/100" % unit_health(u),
                          iso(unit_next_maint(u))])
    overlay_rows_ = [[r["asset"], r["name"], r["signal"], num(r["value"]), r["unit"],
                      r["state"]] for r in OVERLAY_ROWS]
    out = [
        "Status as of **%s**. All %d registered units are on line and reporting. Two "
        "carry a degraded condition: C-1071 (C-3) at WARNING and P-1042 at WARNING. No "
        "unit is tripped, and no area is isolated." % (DOC_DATE, len(UNITS)),
        "",
        "## 20.1 Register status",
        "",
        table(["Tag", "Name", "Area", "Status", "Health", "Next maintenance"], unit_rows),
        "",
        "## 20.2 Overlay asset status",
        "",
        table(["Asset", "Name", "Signal", "Value", "Unit", "State"], overlay_rows_),
        "",
        "## 20.3 Active and recent work orders",
        "",
        table(["WO", "Equipment", "Scope", "Priority", "Status", "Due", "Note"],
              ACTIVE_WORK_ORDERS),
        "",
        "## 20.4 Active anomalies",
        "",
        "One anomaly is live: **A-51**, C-1071 (C-3) vibration 18% above its learned "
        "baseline, opened 2026-09-06. A-50 and earlier anomalies are resolved and are "
        "closed in the register at Section 18.",
        "",
        "## 20.5 Watch list",
        "",
        "* **C-1071 (C-3)** - daily vibration monitoring until the amplitude stabilises "
        "or the bearing is inspected. Watch for the 7.1 mm/s alarm limit and the 85 degC "
        "bearing limit.",
        "* **P-1042** - discharge pressure above the 17.0 bar operating limit. Watch "
        "FT-1042 against the redundant pressure pair to separate downstream restriction "
        "from impeller wear.",
        "* **V-1047 (V-2210)** - high level excursion corrected; confirm the level loop "
        "holds after the drain and that no detector remains latched in the area.",
        "* **E-1063 (E-340)** - delta-P 5% above clean reference; routine quarterly "
        "review only.",
        "* **TK-1121 (T-118)** - no action; next external inspection on the register "
        "interval.",
        "",
        "## 20.6 Area status",
        "",
    ]
    for i, a in enumerate(AREAS):
        us = area_unit_rows(a["id"])
        flagged = [u["tag"] for u in us if unit_status(u) != "NORMAL"]
        out.append("**%s.** %d units on line, status %s. %s"
                   % (a["name"], len(us),
                      "WARNING on " + ", ".join(flagged) if flagged else "NORMAL across the area",
                      area_summary_lines(a["id"])))
        out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------------
# Section 21 - Lessons Learned
# --------------------------------------------------------------------------

LESSONS = [
    ("Vibration responds to oil condition before it responds to load",
     "The first C-3 vibration event (2022-11-18, A-19) reached 6.1 mm/s during a lube-oil "
     "temperature excursion and cleared after an oil flush with no mechanical work. Lube-oil "
     "condition was made a first-line check on every rotating vibration call-out."),
    ("A learned baseline beats a fixed alarm limit for early warning",
     "C-3 was at 6.8 mm/s against a 7.1 mm/s alarm, which looks safe, but 18% above its own "
     "baseline. The learned baseline caught the deviation weeks before the alarm limit would "
     "have (IR-204, A-51)."),
    ("Redundant pressure converts the most frequent failure into a no-stop event",
     "Instrument faults are the most common event class. The A/B pressure pair on the "
     "seven-instrument pump blocks lets SOP-14.2 be executed without stopping the pump, as "
     "scenario `sc-sensor-failure` is designed to prove."),
    ("Keep the process limit separate from the transmitter envelope",
     "P-1042's 17.0 bar alert threshold is deliberately narrower than the PT-1042A normal "
     "band of 17.76 to 19.24 bar. Conflating the two would either hide the excursion or "
     "trip the unit unnecessarily."),
    ("Alignment must be eliminated before bearing wear is assumed",
     "The 2025-11-02 hot alignment check measured a 0.06 mm coupling offset against a "
     "0.10 mm tolerance. That negative result is what justified attributing the residual "
     "trend to the bearing rather than to alignment."),
    ("Fouling is trended, not cleaned on instinct",
     "E-340 at 5% over the clean reference recovers almost no duty if cleaned early; the "
     "quarterly delta-P review exists to make the decision to do nothing explicit and "
     "recorded (WO-8810)."),
    ("An inspection that recommends no action is still a controlled record",
     "WO-8802 on T-118 and WO-8810 on E-340 both expect no action. Recording the decision "
     "is what makes a later change visible."),
    ("Detectors are latched, not analogue",
     "A detector reading zero is healthy. Treating it as an envelope violation produces "
     "false alarms; silencing a latched detector hides a real release. SOP-41.2 rev8 makes "
     "this explicit."),
    ("A second trip on the same fault damages the drive",
     "SOP-18.3 rev4 forbids reset-and-restart without establishing the trip cause. The "
     "current-signature check distinguishes a mechanical load problem from an electrical "
     "fault before the drive is energised again."),
    ("Above 10% deviation, monitoring frequency is the control",
     "SOP-07.3 rev4 section 4.2 raises monitoring to once per shift and requires a "
     "corrective work order within 72 hours. Frequency, not a tighter alarm, is what buys "
     "warning time."),
    ("Outage approval is a safety control, not paperwork",
     "APR-231 gates the C-3 bearing outage because SOP-07.3 rev4 section 5 requires manager "
     "approval for an outage on criticality-high equipment."),
    ("Units can run degraded only with an explicit compensating measurement",
     "OPS-03.2 rev4 permits continued operation with a failed instrument only when a "
     "validated alternate covers the same control objective and the condition is reviewed "
     "at shift handover."),
    ("Two unavailable measurements on one service means reduce rate",
     "The escalation rule is measurable: two or more measurements on the same service "
     "unavailable, a latched detector in the area, or loss of the only downstream flow path."),
    ("Cavitation and impeller wear can look identical on discharge pressure",
     "Both raise discharge pressure against falling or unstable flow. Check suction level "
     "and suction pressure before touching the pump (SOP-22.4 rev2)."),
    ("Small anomalies are cheap; incident records are not",
     "48 anomalies produced 36 incident or event records and a small number of interventions. "
     "The anomaly register is the cheapest part of the reliability programme."),
    ("Health scores and availability answer different questions",
     "Health is a condition score derived from the register; availability is a time-based "
     "reliability figure. A unit can be healthy and unavailable, or degraded and available. "
     "Sections 4 and 13 must be read together."),
]


def sec_21():
    out = ["The programme produced sixteen standing lessons. Each is tied to evidence in "
           "this dossier rather than stated as a general principle.", ""]
    for i, (title, body) in enumerate(LESSONS):
        out.append("### 21.%d %s" % (i + 1, title))
        out.append("")
        out.append(body)
        out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------------
# Section 22 - Recommended Actions
# --------------------------------------------------------------------------

ACTIONS = [
    ("P1", "C-1071 (C-3)", "Complete the drive-end bearing inspection at the first approved "
     "outage window and perform a hot alignment check before re-baselining.",
     "Vibration is 18% above the learned baseline with 1x dominance and DE bearing "
     "temperature is 11 degC above baseline; both SOP-07.3 rev4 section 4.3 triggers are met.",
     "IR-204; A-51; SOP-07.3 rev4 s.4.3; WO-8852", "2026-10-04"),
    ("P1", "C-1071 (C-3)", "Sustain once-per-shift vibration and bearing-temperature "
     "monitoring until the amplitude stabilises or the bearing is inspected.",
     "The machine is inside the 7.1 mm/s alarm limit but outside the 10% deviation band; "
     "frequency is the only control that buys warning time.",
     "SOP-07.3 rev4 s.4.2; IR-204", "2026-09-30"),
    ("P1", "C-1071 (C-3)", "Approve or reject outage approval APR-231 at the next "
     "maintenance-planning gate.",
     "WO-8852 cannot be scheduled on criticality-high equipment without manager approval "
     "under SOP-07.3 rev4 section 5.",
     "APR-231; WO-8852; SOP-07.3 rev4 s.5", "2026-09-25"),
    ("P1", "P-1042", "Confirm suction conditions at the desalter and crude storage before "
     "any mechanical work, and trend FT-1042 against PT-1042A and PT-1042B.",
     "Cavitation and impeller wear produce the same discharge-pressure signature; suction "
     "must be excluded first.",
     "WO-8841; SOP-22.4 rev2; FT-1042", "2026-09-20"),
    ("P1", "P-1042", "Verify the relief path and inspect impeller wear if the pressure "
     "excursion persists after suction is confirmed.",
     "Discharge pressure is +14% above baseline against a 17.0 bar operating limit and the "
     "cause is not yet isolated.",
     "WO-8841; PT-1042A", "2026-10-10"),
    ("P1", "V-1047 (V-2210)", "Confirm the level loop holds after the drain and that no "
     "detector remains latched in the area.",
     "The 87% level excursion breached the 80% setpoint; the incident may not be closed "
     "while a detector in the area is latched.",
     "WO-8837; APR-218; SOP-41.2 rev8", "2026-09-20"),
    ("P2", "C-1071 (C-3)", "Sample and analyse lube oil for varnish and particle count "
     "before the bearing is opened.",
     "The 2022 event and the 2025 bearing finding both implicated oil condition; a sample "
     "now separates an oil problem from a mechanical one.",
     "IR-198; A-19; SOP-22.1 rev5", "2026-10-01"),
    ("P2", "C-1071 (C-3)", "Re-execute the anti-surge valve stroke test and capture the "
     "surge margin at current conditions.",
     "A slow anti-surge valve changes the machine's surge behaviour and can masquerade as "
     "a process vibration source.",
     "ME-212 record; V-1047", "2026-10-15"),
    ("P2", "P-1042", "Calibrate PT-1042A and PT-1042B against a deadweight tester and "
     "confirm they agree within 2% of span.",
     "The operating limit is only as good as the redundant pair; SOP-14.2 requires "
     "agreement within 2% of span.",
     "SOP-14.2 rev6; PT-1042A; PT-1042B", "2026-10-12"),
    ("P2", "E-1063 (E-340)", "Continue the quarterly delta-P trend review and add outlet "
     "temperature at constant flow as the primary duty-loss indicator.",
     "Delta-P is +5% over clean, inside the normal band, but outlet temperature sag is the "
     "earlier duty-loss signal.",
     "WO-8810; TT-1063O; FT-1063", "2026-09-30"),
    ("P2", "TK-1121 (T-118)", "Calibrate LT-1121 against the gauging tape at the next "
     "external inspection and record the deviation.",
     "Level is the safety-critical measurement on the tank and the register interval is the "
     "standing control.",
     "WO-8802; LT-1121", "2026-12-15"),
    ("P2", "C-1071 (C-3)", "Reduce load and notify the shift supervisor immediately if "
     "vibration reaches 7.1 mm/s or bearing temperature reaches 85 degC.",
     "These are the alarm limits fixed by the machine manual and SOP-07.3 rev4.",
     "SOP-07.3 rev4 s.4; C-3 manual Table 7-2", "2026-09-30"),
    ("P2", "ESD-1182", "Run the emergency shutdown proof test and confirm the final element "
     "stroke time against the safety requirement.",
     "A safety element that has not been proof-tested is an unverified layer.",
     "SOP-41.2 rev8; ESD-1181", "2026-11-05"),
    ("P2", "V-1047 (V-2210)", "Overhaul the actuator and re-profile the position loop if the "
     "position feedback mismatch recurs.",
     "The overlay vessel's live issue sits on a valve with actuator position feedback; a "
     "recurring mismatch is an actuator fault signature.",
     "SOP-52.4 rev2; ZT-1047", "2026-11-20"),
    ("P3", "C-1071 (C-3)", "Review the learned vibration baseline after the bearing "
     "intervention and re-establish it only after a stable 30-day run.",
     "Re-baselining before the machine stabilises hides the next deviation.",
     "IR-204; vibration baseline record", "2026-11-30"),
    ("P3", "P-1042", "Add a discharge-pressure trend alarm at 17.0 bar in the console if one "
     "is not already configured.",
     "The learned rule pins the alert threshold at 17 bar; it should be enforced by the "
     "control system, not by operator attention.",
     "Learned rule: P-1042 17 bar", "2026-10-31"),
    ("P3", "C-1071 (C-3)", "Align the learned rule \"C-3 vibration baseline: 5.7 mm/s at "
     "8,800 rpm\" with the register twin's RPM-1071 nominal of 8,840 rpm.",
     "The 40 rpm difference is a documentation artefact and should not propagate into a "
     "trip calculation.",
     "Learned rule; RPM-1071", "2026-11-15"),
    ("P3", "C-1063" if False else "E-1063", "Schedule the bundle eddy-current survey at the "
     "next 48-month interval rather than at the next opportunity.",
     "Fouling is the only credible degradation path and the bundle sample showed no wall "
     "loss; the interval can be held.",
     "IR record (E-1063); fouling trend", "2027-03-01"),
    ("P3", "TK-1121 (T-118)", "Inspect the roof seal and secondary containment at the next "
     "six-monthly external inspection.",
     "Static containment degradation is slow and invisible between inspections.",
     "WO-8802; tank inspection cycle", "2026-12-15"),
    ("P3", "C-1071 (C-3)", "Update the C-3 asset record in the console overlay after the "
     "bearing intervention so the overlay and register narratives stay in step.",
     "The overlay record still shows the pre-intervention values; a stale overlay record is "
     "how the next investigation starts from the wrong baseline.",
     "Section 4b; IR-198; ME-198", "2026-10-20"),
    ("P3", "P-1042", "Record the operating limit and the transmitter envelope side by side "
     "on the loop documentation.",
     "The two numbers differ by design and the distinction caused confusion during the "
     "current investigation.",
     "PT-1042A envelope; learned rule 17 bar", "2026-10-31"),
    ("P3", "ESD-1181", "Verify detector coverage and recalibrate the channel sitting at the "
     "2% drift limit.",
     "One detector reached the drift limit at the last proof test.",
     "SOP-41.2 rev8; proof-test record", "2026-11-05"),
    ("P3", "M-1143", "Repeat the winding insulation-resistance test and current-signature "
     "check on the BFD fan motor.",
     "The motor is one of the oldest registered drives and overload is a modelled failure "
     "mode for it.",
     "SOP-18.3 rev4; sc-motor-overload", "2026-11-25"),
    ("P3", "C-1082", "Confirm the FCC air blower surge margin and test the trip path.",
     "A blower trip starves reactor air; the trip path must be proven rather than assumed.",
     "sc-compressor-trip; SOP-18.3 rev4", "2026-12-10"),
    ("P3", "COL-1044", "Verify column pressure against the redundant transmitter and confirm "
     "the relief path to flare.",
     "The atmospheric column is the pressure-surge scenario target and the relief path is "
     "the mitigation.",
     "sc-pressure-surge; SOP-27.9 rev3", "2026-11-28"),
    ("P3", "F-1043", "Survey tube skin temperatures and confirm excess oxygen at the crude "
     "charge heater.",
     "Fired heaters degrade silently through tube temperature; the survey is the "
     "first-line check.",
     "SOP-09.6 rev5", "2026-12-05"),
    ("P3", "E-1045", "Trend the overhead condenser outlet temperature against duty to catch "
     "the instrument-drift scenario early.",
     "The overhead condenser is the target of both the drift and fouling scenarios.",
     "sc-temp-anomaly; sc-exchanger-fouling", "2026-12-12"),
    ("P3", "P-1131", "Confirm cooling-water pump duty against the tower cell performance.",
     "Cooling capacity sets the achievable rate across the whole plant; a slow loss of duty "
     "is easy to miss.",
     "UT-1133; cooling area record", "2027-01-15"),
    ("P3", "F-1141", "Check boiler feedwater quality and boiler efficiency against the "
     "commissioned curve.",
     "Steam supply is a plant-wide dependency and efficiency drift is cumulative.",
     "P-1142; steam area record", "2027-01-20"),
    ("P3", "C-1152", "Service the plant air compressor and verify instrument-air dew point.",
     "Instrument air quality directly affects every pneumatic actuator and positioner.",
     "UT-1151; utilities record", "2027-01-30"),
    ("P3", "VS-1162", "Inspect the flare knock-out drum internals and confirm the liquid "
     "seal.",
     "The flare path is the last line of defence for every relief scenario in the plant.",
     "UT-1161; flare area record", "2027-02-10"),
    ("P3", "P-1171", "Verify API separator oil removal and lift-pump duty.",
     "Wastewater carry-over is an environmental exposure and an early indicator of upsets "
     "elsewhere.",
     "VS-1172; wastewater record", "2027-02-28"),
]


def sec_22():
    rows = [[a[0], a[1], a[2], a[3], a[4], a[5]] for a in ACTIONS]
    out = [
        "The recommended actions below are concrete and prioritised. **P1** actions are "
        "required now and are tied to a live deviation; **P2** actions are required this "
        "quarter and protect a degraded or critical asset; **P3** actions are scheduled "
        "improvements. Every action names an equipment tag that resolves in this document, "
        "a rationale, an evidence reference and a target date. Target dates are forecast "
        "dates and may fall after the dossier cutoff of %s; all historical records in this "
        "document do not." % DOC_DATE,
        "",
        table(["Priority", "Equipment", "Action", "Rationale", "Evidence", "Target date"],
              rows),
        "",
        "## 22.1 Priority counts",
        "",
    ]
    counts = {}
    for a in ACTIONS:
        counts[a[0]] = counts.get(a[0], 0) + 1
    out.append(table(["Priority", "Actions"],
                     [[k, v] for k, v in sorted(counts.items())]))
    out.append("")
    out.append("## 22.2 Immediate sequence")
    out.append("")
    out.append("The first four actions are ordered: (1) sustain once-per-shift monitoring "
               "on C-1071; (2) close the APR-231 approval decision so WO-8852 can be "
               "scheduled; (3) confirm suction conditions on P-1042 before any mechanical "
               "work; (4) confirm the V-1047/V-2210 level loop holds after the drain. "
               "Everything else can follow the normal planning cycle.")
    out.append("")
    out.append("## 22.3 Verification and close-out")
    out.append("")
    out.append("Each action closes only against a measurable acceptance criterion. The "
               "criteria below are the ones an auditor should ask for; a work order that "
               "is closed without them is closed on activity, not on outcome.")
    out.append("")
    out.append(table(["Action family", "Acceptance criterion", "Evidence to file"], [
        ["C-3 bearing inspection", "Overall vibration inside 10% of the re-established "
         "baseline with stable 2x, bearing temperature within 5 degC of baseline",
         "IR-204; new inspection report; new baseline record"],
        ["C-3 monitoring", "Once-per-shift readings logged with no reading above 7.1 mm/s "
         "or 85 degC", "Shift log; console trend export"],
        ["C-3 approval", "APR-231 decided and the decision recorded against WO-8852",
         "Approval record; work-order history"],
        ["P-1042 suction check", "Suction pressure and upstream level inside normal bands "
         "at the observed discharge pressure", "Trend plot of FT-1042 against PT-1042A/B"],
        ["P-1042 mechanical", "Discharge pressure back inside the 17.0 bar operating limit "
         "at the same flow", "Post-work survey; impeller inspection record"],
        ["V-2210 level", "Level loop holds inside the normal band and no detector latched "
         "in the area", "WO-8837 close-out; detector reset record"],
        ["Exchanger fouling", "Delta-P trend and outlet temperature at constant flow "
         "tracked quarterly", "WO-8810 review note"],
        ["Tank inspection", "Level transmitter within 0.5% of the gauging tape; "
         "containment dry", "WO-8802 report; calibration sheet"],
        ["Safety proof tests", "Final element stroke time inside the safety requirement; "
         "detector drift inside 2%", "Proof-test certificate"],
        ["Rotating surveys", "Vibration and current inside the normal band after "
         "intervention", "Condition-monitoring report"],
    ])) 
    return "\n".join(out)


# --------------------------------------------------------------------------
# Section table and assembly
# --------------------------------------------------------------------------

SECTION_SPECS = [
    (1, "01-executive-summary", "Executive Summary", ["refinery", "overview"], sec_01),
    (2, "02-plant-overview", "Plant Overview", ["refinery", "plant"], sec_02),
    (3, "03-refinery-units", "Refinery Units", ["refinery", "units"], sec_03),
    (4, "04-equipment-register", "Equipment Register", ["refinery", "equipment"], sec_04),
    ("4b", "04b-register-overlay-crosswalk", "Register ↔ Overlay Crosswalk",
     ["refinery", "equipment", "crosswalk"], sec_04b),
    (5, "05-instrumentation", "Instrumentation", ["refinery", "instrumentation"], sec_05),
    (6, "06-operating-parameters", "Operating Parameters", ["refinery", "parameters"], sec_06),
    (7, "07-maintenance-history", "Maintenance History", ["refinery", "maintenance"], sec_07),
    (8, "08-inspection-records", "Inspection Records", ["refinery", "inspection"], sec_08),
    (9, "09-failure-modes", "Failure Modes", ["refinery", "failure"], sec_09),
    (10, "10-safety-procedures", "Safety Procedures", ["refinery", "safety"], sec_10),
    (11, "11-standard-operating-procedures", "Standard Operating Procedures",
     ["refinery", "sop"], sec_11),
    (12, "12-incident-history", "Incident History", ["refinery", "incident"], sec_12),
    (13, "13-reliability-analysis", "Reliability Analysis", ["refinery", "reliability"],
     sec_13),
    (14, "14-compressor-c-3-history", "Compressor C-3 History",
     ["refinery", "compressor", "C-3"], sec_14),
    (15, "15-pump-p-1042-history", "Pump P-1042 History", ["refinery", "pump", "P-1042"],
     sec_15),
    (16, "16-heat-exchanger-e-340", "Heat Exchanger E-340", ["refinery", "exchanger", "E-340"],
     sec_16),
    (17, "17-storage-tank-t-118", "Storage Tank T-118", ["refinery", "tank", "T-118"],
     sec_17),
    (18, "18-historical-anomalies", "Historical Anomalies", ["refinery", "anomaly"], sec_18),
    (19, "19-maintenance-interventions", "Maintenance Interventions",
     ["refinery", "maintenance"], sec_19),
    (20, "20-current-operational-status", "Current Operational Status",
     ["refinery", "status"], sec_20),
    (21, "21-lessons-learned", "Lessons Learned", ["refinery", "lessons"], sec_21),
    (22, "22-recommended-actions", "Recommended Actions", ["refinery", "actions"], sec_22),
]

MASTER_TITLE = "REFINERY TECHNICAL KNOWLEDGE BASE"
MASTER_HEADING = "Meridian Synthetic Refinery - five-year technical dossier (2021-06 .. 2026-09)"


def _demote_headings(body):
    """Subsections inside a section body are level-3, so the 22 `##` headings in the
    master document are exactly the 22 (plus 4b) ingestable sections."""
    return re.sub(r"(?m)^## (?=\d+[a-z]?\.\d)", "### ", body)


def build_sections():
    out = []
    for sid, slug, title, tags, fn in SECTION_SPECS:
        body = _demote_headings(fn())
        out.append({"id": sid, "slug": slug, "title": title, "tags": tags, "body": body})
    return out


def master_text(sections):
    parts = [
        "# %s" % MASTER_TITLE,
        "",
        MASTER_HEADING,
        "",
        "| Document control | |",
        "|---|---|",
        "| doc_id | `%s` |" % DOC_ID,
        "| generated_for | Project 117 |",
        "| period | 2021-06 .. 2026-09 |",
        "| cutoff | %s |" % DOC_DATE,
        "| register source | `apps/web/public/simulation/refinery/equipment.json` "
        "(%d units, %d sensors) |" % (len(UNITS), sum(len(u["sensors"]) for u in UNITS)),
        "| overlay source | `data/demo/equipment/equipment.json` (%d assets) |" % len(DEMO_TAGS),
        "| sections | %d |" % len(sections),
        "",
    ]
    for s in sections:
        parts.append("## %s. %s" % (s["id"], s["title"]))
        parts.append("")
        parts.append(s["body"].rstrip())
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def chunk_text(s):
    front = (
        "---\n"
        "doc_id: %s\n" % DOC_ID +
        "chunk: %s\n" % s["id"] +
        "section: %s\n" % s["title"] +
        "source: REFINERY-TECHNICAL-KNOWLEDGE-BASE.md\n"
        "tags: [%s]\n" % ", ".join(s["tags"]) +
        "---\n"
    )
    return front + "## %s. %s\n\n%s\n" % (s["id"], s["title"], s["body"].rstrip())


# --------------------------------------------------------------------------
# Documents-page artifact (same shape as scripts/build_document_field.py)
# --------------------------------------------------------------------------

DOC_FIELD_OUT = ROOT / "apps" / "web" / "public" / "knowledge" / "refinery-document.json"
ENTITY_RE = re.compile(
    r"\b(?:"
    r"[A-Z]{2,4}-\d{2,4}[A-Z]?"
    r"|(?:SOP|OPS|IR|ME|WO|INC|EV|APR|A)-\d+(?:\.\d+)?(?:[A-Za-z]*)?"
    r"|\d+\.\d+\s*mm/s"
    r"|\d+\s*bar"
    r"|\d[\d,]*\s*rpm"
    r")\b"
)
FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n", re.DOTALL)


def _first_heading(text):
    for line in text.splitlines():
        if line.startswith("#"):
            return line.lstrip("# ").strip()
    return "Untitled section"


def _doc_tables(text):
    rows = []
    in_table = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            if not in_table:
                in_table = True
            rows.append(cells)
            if len(rows) >= 4:
                break
        elif in_table:
            break
    return rows


def _body_lines(text, limit=7):
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("|") or s.startswith("---"):
            continue
        s = re.sub(r"^[-*]\s+", "", s)
        s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
        s = re.sub(r"`(.+?)`", r"\1", s)
        if len(s) < 24:
            continue
        out.append(s)
        if len(out) >= limit:
            break
    return out


def _slugify(path):
    return re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")


def _kind_for(name):
    n = name.lower()
    if "ir-" in n or "inspection" in n:
        return "inspection"
    if "sop" in n or "ops" in n:
        return "procedure"
    if "baseline" in n:
        return "baseline"
    if "manual" in n:
        return "manual"
    if "me-" in n or "record" in n or "history" in n:
        return "record"
    return "register"


STEEL_MARKERS = ("steel", "ironmaking", "steelmaking", "blast furnace", "bof", "caster")


def _is_steel(path, text):
    hay = "%s\n%s" % (path.stem, text[:4000])
    hay = hay.lower()
    return any(m in hay for m in STEEL_MARKERS)


def build_document_field(sections):
    src_dirs = [ROOT / "data" / "knowledge" / "refinery",
                ROOT / "data" / "knowledge", ROOT / "data" / "demo"]
    entries = []
    seen = set()
    for s in sections:
        path = CHUNK_DIR / ("%s.md" % s["slug"])
        text = FRONTMATTER_RE.sub("", chunk_text(s), count=1)
        slug_ = _slugify(path)
        seen.add(slug_)
        ents = sorted({m.group(0) for m in ENTITY_RE.finditer(text)})[:8]
        entries.append({
            "slug": slug_, "title": _first_heading(text), "doc": path.name,
            "source": str(path.relative_to(ROOT)), "kind": "register",
            "lines": _body_lines(text), "table": _doc_tables(text) or None,
            "entities": ents, "chars": len(text),
        })
    skipped_steel = 0
    for root in (src_dirs[1], src_dirs[2]):
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            if path.name.lower().startswith(("readme", "manifest")):
                continue
            if path.name.upper().startswith("REFINERY-TECHNICAL"):
                continue
            raw = path.read_text(encoding="utf-8", errors="ignore")
            text = FRONTMATTER_RE.sub("", raw, count=1)
            if _is_steel(path, text):
                skipped_steel += 1
                continue
            slug_ = _slugify(path)
            if slug_ in seen:
                continue
            seen.add(slug_)
            ents = sorted({m.group(0) for m in ENTITY_RE.finditer(text)})[:8]
            entries.append({
                "slug": slug_, "title": _first_heading(text), "doc": path.name,
                "source": str(path.relative_to(ROOT)), "kind": _kind_for(path.name),
                "lines": _body_lines(text), "table": _doc_tables(text) or None,
                "entities": ents, "chars": len(text),
            })
    payload = {
        "generated": DOC_DATE,
        "source_dirs": [str(p.relative_to(ROOT)) for p in src_dirs if p.is_dir()],
        "count": len(entries),
        "skipped_steel": skipped_steel,
        "master_sections": len(sections),
        "sections": entries,
    }
    return payload


# --------------------------------------------------------------------------
# Consistency checks
# --------------------------------------------------------------------------

TAG_TOKEN_RE = re.compile(r"\b([A-Z]{1,5})-(\d{1,4})([A-Z]{0,3})\b")
NON_EQUIPMENT_PREFIXES = {
    "WO", "ME", "IR", "INC", "EV", "APR", "SOP", "OPS", "D", "H", "PL", "JOB",
    "ART", "A", "U", "REF", "ISO", "ASTM", "API", "ASH", "ANSI", "NACE", "SHA",
}


def parse_table_block(text, marker):
    """Parse the first markdown table after a marker line. Returns list of cell lists."""
    lines = text.splitlines()
    try:
        start = next(i for i, l in enumerate(lines) if l.strip() == marker)
    except StopIteration:
        return []
    rows = []
    in_table = False
    for line in lines[start:]:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            in_table = True
            rows.append(cells)
        elif in_table:
            break
    return rows


def principal_table_columns(body):
    """Header of the largest markdown table in a section body (the section's
    principal table), used to publish the column schema into the manifest."""
    best = None
    rows = []
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("|") and s.endswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            rows.append(cells)
        else:
            if rows and (best is None or len(rows) > len(best)):
                best = rows
            rows = []
    if rows and (best is None or len(rows) > len(best)):
        best = rows
    return best[0] if best else None


def run_checks(sections, master):
    results = []
    ok = True

    # Check 1 - equipment tags.
    reg_emitted = set()
    for m in TAG_TOKEN_RE.finditer(master):
        tok = m.group(0)
        if tok in REGISTER_TAG_SET:
            reg_emitted.add(tok)
    missing = sorted(REGISTER_TAG_SET - reg_emitted)
    c1 = not missing
    ok &= c1
    results.append((
        "CHECK 1 register equipment tags",
        c1,
        "%d/%d register tags emitted; every emitted register tag exists in "
        "equipment.json; missing=%s"
        % (len(reg_emitted), len(REGISTER_TAG_SET), missing or "none"),
    ))

    # Check 2 - register sensor tags on the right unit (Section 5 table).
    s05 = [s for s in sections if s["id"] == 5][0]["body"]
    sensor_rows = parse_table_block(s05, "### 5.1 Field instrument register")
    bad = []
    checked = 0
    covered_units = set()
    for row in sensor_rows[1:]:
        if len(row) < 2:
            continue
        stag, etag = row[0], row[1]
        checked += 1
        covered_units.add(etag)
        if etag not in ALL_SENSOR_TAGS_BY_UNIT or stag not in ALL_SENSOR_TAGS_BY_UNIT[etag]:
            bad.append("%s/%s" % (etag, stag))
    c2 = (not bad) and checked == len(ALL_SENSOR_TAGS)
    ok &= c2
    results.append((
        "CHECK 2 register sensor tags",
        c2,
        "%d sensor rows checked against equipment.json sensors[]; %d units covered; "
        "mismatches=%s" % (checked, len(covered_units), bad or "none"),
    ))

    # Check 3 - overlay vocabulary declared and present.
    overlay_emitted = {m.group(0) for m in TAG_TOKEN_RE.finditer(master)} & DEMO_TAG_SET
    missing_overlay = sorted(DEMO_TAG_SET - overlay_emitted)
    c3 = not missing_overlay
    ok &= c3
    results.append((
        "CHECK 3 overlay tags",
        c3,
        "%d/%d overlay tags emitted and declared in Section 4b; each verified against "
        "data/demo/equipment/equipment.json; missing=%s"
        % (len(overlay_emitted), len(DEMO_TAG_SET), missing_overlay or "none"),
    ))

    # Check 4 - no undeclared tag-like token anywhere in the master document.
    allowed_extra = set(MODEL_BY_TAG.values()) | {u.get("model", "") for u in DEMO_UNITS}
    allowed_extra |= DOCUMENTED_ARTIFACTS
    for _m in list(MODEL_BY_TAG.values()) + [u.get("model", "") for u in DEMO_UNITS]:
        allowed_extra.update(t.group(0) for t in TAG_TOKEN_RE.finditer(_m))
    unknown = {}
    for m in TAG_TOKEN_RE.finditer(master):
        tok, prefix = m.group(0), m.group(1)
        if (tok in REGISTER_TAG_SET or tok in ALL_SENSOR_TAGS or tok in DEMO_TAG_SET
                or tok in allowed_extra or prefix in NON_EQUIPMENT_PREFIXES):
            continue
        unknown[tok] = unknown.get(tok, 0) + 1
    c4 = not unknown
    ok &= c4
    results.append((
        "CHECK 4 no undeclared tags",
        c4,
        "undeclared tag-like tokens=%s; documented masked-tag artefacts permitted=%s"
        % (unknown or "none", sorted(DOCUMENTED_ARTIFACTS)),
    ))

    # Check 5 - Section 4 completeness.
    s04 = [s for s in sections if s["id"] == 4][0]["body"]
    reg_rows = parse_table_block(s04, "### 4.1 Register")
    reg_tags = [r[0] for r in reg_rows[1:] if r]
    c5 = len(reg_tags) == len(REGISTER_TAGS) and set(reg_tags) == REGISTER_TAG_SET
    ok &= c5
    results.append((
        "CHECK 5 equipment register completeness",
        c5,
        "%d data rows for %d register units; exact set match=%s"
        % (len(reg_tags), len(REGISTER_TAGS), set(reg_tags) == REGISTER_TAG_SET),
    ))

    # Check 6 - history chronology and cutoff.
    seq_ok = True
    detail = []
    for name, seq in (("ME", ME_RECORDS), ("IR", IR_RECORDS),
                      ("anomaly", ANOMALIES), ("incident", INCIDENTS)):
        dates = [r["date"] for r in seq]
        if dates != sorted(dates):
            seq_ok = False
            detail.append("%s not chronological" % name)
        if dates and (dates[0] < PERIOD_START or dates[-1] > PERIOD_END):
            seq_ok = False
            detail.append("%s outside period" % name)
    c6 = seq_ok
    ok &= c6
    results.append((
        "CHECK 6 history chronology/cutoff",
        c6,
        "records=%d, all chronological and within %s..%s; %s"
        % (len(ME_RECORDS) + len(IR_RECORDS) + len(ANOMALIES) + len(INCIDENTS),
           iso(PERIOD_START), iso(PERIOD_END), "; ".join(detail) or "clean"),
    ))

    # Check 7 - volume.
    lines = master.count("\n") + 1
    c7 = lines >= 3500
    ok &= c7
    results.append((
        "CHECK 7 master document volume",
        c7,
        "%d lines (target >= 3500)" % lines,
    ))

    # Check 8 - Model column is a real designation, not a masked tag.
    header = reg_rows[0]
    model_idx = header.index("Model")
    models = [r[model_idx].strip() for r in reg_rows[1:]]
    masked = [m for m in models if re.match(r"^[A-Z]{1,4}-\d+X$", m)]
    counts = {}
    for m in models:
        counts[m] = counts.get(m, 0) + 1
    dupes = {m: c for m, c in counts.items() if c > 1}
    bad_dupes = {m: c for m, c in dupes.items() if m not in MODEL_SHARED_OK}
    c8 = (not masked) and (not bad_dupes) and len(models) == len(UNITS)
    ok &= c8
    results.append((
        "CHECK 8 model designations",
        c8,
        "%d model cells; masked-tag cells (^[A-Z]{1,4}-\\d+X$)=%d; "
        "shared-by-design=%s; undeclared duplicate models=%s"
        % (len(models), len(masked),
           {m: c for m, c in dupes.items() if m in MODEL_SHARED_OK} or "none",
           bad_dupes or "none"),
    ))

    # Check 9 - Commissioned dates inside the Section 2 declared window.
    comm_idx = header.index("Commissioned")
    comm_dates = [r[comm_idx].strip() for r in reg_rows[1:]]
    outside = [x for x in comm_dates
               if not (COMMISSIONING_WINDOW_START <= d(x) <= COMMISSIONING_WINDOW_END)]
    s02 = [s for s in sections if s["id"] == 2][0]["body"]
    window_stated = ("Commissioning window" in s02
                     and iso(COMMISSIONING_WINDOW_START) in s02
                     and iso(COMMISSIONING_WINDOW_END) in s02)
    c9 = (not outside) and window_stated and len(comm_dates) == len(UNITS)
    ok &= c9
    results.append((
        "CHECK 9 commissioning window",
        c9,
        "%d Commissioned dates; window %s..%s stated in Section 2=%s; outside window=%s"
        % (len(comm_dates), iso(COMMISSIONING_WINDOW_START),
           iso(COMMISSIONING_WINDOW_END), window_stated, outside or "none"),
    ))

    return ok, results


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> int:
    sections = build_sections()
    master = master_text(sections)

    MASTER_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHUNK_DIR.mkdir(parents=True, exist_ok=True)

    MASTER_PATH.write_text(master, encoding="utf-8")

    manifest_sections = []
    for s in sections:
        path = CHUNK_DIR / ("%s.md" % s["slug"])
        text = chunk_text(s)
        path.write_text(text, encoding="utf-8")
        first_table = principal_table_columns(s["body"])
        columns = first_table
        manifest_sections.append({
            "id": s["id"], "slug": s["slug"], "title": s["title"],
            "file": path.name, "chars": len(text), "lines": text.count("\n") + 1,
            "columns": columns,
        })

    manifest = {
        "doc_id": DOC_ID,
        "title": "%s - %s" % (MASTER_TITLE, MASTER_HEADING),
        "generated_for": "Project 117",
        "period": "2021-06..2026-09",
        "sections": manifest_sections,
        "column_sets": {
            "equipment_register": {
                "section": 4, "columns": ["Tag", "Name", "Kind", "Area", "Criticality",
                                          "Commissioned", "Manufacturer", "Model",
                                          "Last maint.", "Next maint.", "Health"]},
            "instrumentation": {
                "section": 5, "columns": ["Sensor tag", "Equipment", "Measurement",
                                          "Unit", "Nominal", "Normal range",
                                          "Warning range", "Critical range"],
                "join": "Equipment -> equipment_register.Tag"},
        },
        "commissioning_window": {
            "start": iso(COMMISSIONING_WINDOW_START),
            "end": iso(COMMISSIONING_WINDOW_END),
            "first_production": iso(FIRST_PRODUCTION),
        },
        "totals": {
            "sections": len(manifest_sections),
            "chars": sum(x["chars"] for x in manifest_sections),
            "lines": sum(x["lines"] for x in manifest_sections),
        },
        "entities": {
            "equipment_tags": sorted(REGISTER_TAGS),
            "sensor_tags": sorted(ALL_SENSOR_TAGS),
            "overlay_tags": sorted(DEMO_TAGS),
        },
    }
    man_path = CHUNK_DIR / "manifest.json"
    man_path.write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")

    field_payload = build_document_field(sections)
    DOC_FIELD_OUT.parent.mkdir(parents=True, exist_ok=True)
    DOC_FIELD_OUT.write_text(json.dumps(field_payload, indent=1, ensure_ascii=False),
                             encoding="utf-8")

    ok, results = run_checks(sections, master)

    s04 = [s for s in sections if s["id"] == 4][0]["body"]
    s05 = [s for s in sections if s["id"] == 5][0]["body"]
    reg_rows = len(parse_table_block(s04, "### 4.1 Register")) - 1
    inst_rows = len(parse_table_block(s05, "### 5.1 Field instrument register")) - 1
    overlay_rows_n = len(parse_table_block(s05, "### 5.3 Legacy overlay instrumentation (U-200 console dataset)")) - 1

    print("=" * 78)
    print("Project 117 refinery knowledge base generator")
    print("=" * 78)
    print("master      : %s" % MASTER_PATH.relative_to(ROOT))
    print("  lines     : %d" % (master.count("\n") + 1))
    print("  chars     : %d" % len(master))
    print("chunks      : %d files in %s" % (len(manifest_sections), CHUNK_DIR.relative_to(ROOT)))
    print("manifest    : %s" % man_path.relative_to(ROOT))
    print("doc field   : %s" % DOC_FIELD_OUT.relative_to(ROOT))
    print("-" * 78)
    print("Equipment Register table rows      : %d (register has %d units)"
          % (reg_rows, len(REGISTER_TAGS)))
    print("Instrumentation table rows         : %d (register has %d sensors)"
          % (inst_rows, len(ALL_SENSOR_TAGS)))
    print("Legacy overlay instrumentation rows: %d" % overlay_rows_n)
    hist = {}
    for u in UNITS:
        y = unit_commissioned(u)[:4]
        hist[y] = hist.get(y, 0) + 1
    print("Commissioned-date histogram      : %s"
          % ", ".join("%s=%d" % (k, hist[k]) for k in sorted(hist)))
    print("Commissioning window             : %s .. %s (first production %s)"
          % (iso(COMMISSIONING_WINDOW_START), iso(COMMISSIONING_WINDOW_END),
             iso(FIRST_PRODUCTION)))
    print("-" * 78)
    for name, passed, detail in results:
        print("[%s] %s" % ("PASS" if passed else "FAIL", name))
        print("        %s" % detail)
    print("-" * 78)
    print("RESULT: %s" % ("ALL CHECKS PASS" if ok else "CHECKS FAILED"))
    print("=" * 78)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())



