---
doc_id: refinery-technical-knowledge-base
chunk: 4b
section: Register ↔ Overlay Crosswalk
source: REFINERY-TECHNICAL-KNOWLEDGE-BASE.md
tags: [refinery, equipment, crosswalk]
---
## 4b. Register ↔ Overlay Crosswalk

The console ships two equipment vocabularies and this document uses both. They are declared here so that no tag in the dossier has to be inferred.

* **Register vocabulary** - the 58 tag numbers in `apps/web/public/simulation/refinery/equipment.json`. This is the live simulation register and the authority for Sections 4 and 5.
* **Overlay vocabulary** - the 6 legacy assets in `data/demo/equipment/equipment.json`, the U-200 console/demo dataset: C-3, P-1042, V-2210, T-118, E-340, P-2051. These tags carry the narrative that already exists in the app (compressor C-3, pump P-1042, vessel V-2210, tank T-118, exchanger E-340, pump P-2051) and are used as the primary key in Sections 14 to 17 and wherever the console story is told.

The crosswalk below maps each overlay asset to its register counterpart. `confidence` is deliberately explicit: **exact** means the same tag string exists in the register; **twin** means a distinct register tag carries the same machine signature or duty; **partial** means the register asset covers only part of the overlay service and the mapping must not be read as equivalence.

| Overlay tag | Overlay name | Register tag | Register name | Confidence | Basis and caveat |
|---|---|---|---|---|---|
| C-3 | Recycle Gas Compressor | C-1071 | Reformer Recycle Compressor | twin | Register twin carries the same machine signature: VIB-1071 nominal 5.7 mm/s, RPM-1071 nominal 8,840 rpm, TT-1071 nominal 79 degC. |
| P-1042 | Feed Charge Pump | P-1042 | Crude Charge Pump | exact | Same tag in both vocabularies; register area cdu, criticality class 3. |
| E-340 | Feed/Effluent Heat Exchanger | E-1063 | NHT Effluent Cooler | twin | Hydrotreater effluent exchanger; register carries inlet/outlet temperature and tube-side flow. |
| T-118 | Intermediate Storage Tank | TK-1121 | Naphtha Tank | twin | Product-storage tank with level and temperature instrumentation. |
| V-2210 | Product Separator Vessel | V-1047 | Column Feed Valve | partial | Register asset is the process valve with actuator position feedback; the overlay vessel itself has no register tag number. |
| P-2051 | Product Transfer Pump | P-1124 | Product Loading Pump | partial | Same duty family; overlay pump is under maintenance, register pump is in service. |

### 4b.1 Why C-3 maps to C-1071

The mapping is not a guess. The register twin for C-3 is C-1071, the Reformer Recycle Compressor, and its instrumentation reproduces the console machine signature exactly: VIB-1071 nominal 5.7 mm/s (the learned C-3 baseline), RPM-1071 nominal 8,840 rpm (the console's 8,800 rpm running speed) and TT-1071 nominal 79 degC (the current drive-end bearing temperature). This is the strongest of the six mappings and is treated as an exact twin in this document.

### 4b.2 Partial mappings

V-2210 maps only partially. The overlay asset is a product separator vessel whose live issue is a high level excursion (87% against an 80% setpoint), while the register counterpart V-1047 is a process valve carrying actuator position feedback. The two are related by service position in the U-200 train, not by equipment identity, and V-2210's level excursion is therefore reported against the overlay tag with the register tag named only as a locator. P-2051 maps only partially for the same reason: the register asset P-1124 is in service, while the overlay asset is recorded as under maintenance, so condition data must not be copied between them.

### 4b.3 How to read a tag in this document

If a tag appears in the register vocabulary it is a live register asset and its row in Section 4 is authoritative. If it appears in the overlay vocabulary it is a console asset and its record in `data/demo/equipment/equipment.json` is authoritative; the register counterpart named here is used only to locate the asset in the physical plant. Where both appear together, the convention in this document is `register-tag (overlay-tag)`, for example `C-1071 (C-3)`.
