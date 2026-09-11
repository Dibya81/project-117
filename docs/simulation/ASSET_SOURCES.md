# Simulation Asset Sources

Every visual asset in the simulation environment is an **ORIGINAL PROJECT 117
ASSET**, hand-authored as inline SVG in
`apps/web/src/lib/sim/symbols.tsx`. No third-party artwork is bundled.

## Method

ISA-5.1 and P&ID conventions were used as **conceptual references only**
(instrument bubbles with tag letters, bow-tie valve bodies, tray columns,
volute pump casings). No standard artwork or vendor artwork was copied or
traced — the geometry below was written for this project.

## Registry

| Symbol | Type key | Category | Convention reference | License |
|---|---|---|---|---|
| Pressure/Temperature/Flow/Level/Analyzer/Vibration/RPM/Current/Power/Gas/Leak/Position/Speed instruments | `inst_*` | instrumentation | ISA-5.1 bubble + lettering (conceptual) | ORIGINAL PROJECT 117 ASSET |
| Gate / Globe / Ball / Butterfly / Check / Control / Relief / Emergency Shutoff valves | `valve_*` | valves | P&ID bow-tie body (conceptual) | ORIGINAL PROJECT 117 ASSET |
| Centrifugal / Positive-displacement pumps | `pump_*` | pumps | P&ID volute circle (conceptual) | ORIGINAL PROJECT 117 ASSET |
| Motor / Fan / Blower / Compressor / Turbine | `motor`, `fan`, `blower`, `compressor`, `turbine` | machines | P&ID machine conventions (conceptual) | ORIGINAL PROJECT 117 ASSET |
| Tank / Vertical vessel / Horizontal vessel / Separator / Column / Exchanger / Furnace / Reactor / Boiler / Cooling tower / Filter / Scrubber | `tank` … `scrubber` | process | P&ID vessel conventions (conceptual) | ORIGINAL PROJECT 117 ASSET |
| ESD panel / Fire detector / Alarm beacon / E-stop / Flare | `esd_panel` … `flare` | safety | HMI safety conventions (conceptual) | ORIGINAL PROJECT 117 ASSET |
| Junction / Conveyor / Utility package | `junction`, `conveyor`, `utility_pkg` | infrastructure | — | ORIGINAL PROJECT 117 ASSET |

State overlays (status halo, fault cross, verification tick, activity sweep)
are also original and live in the same file.

## External assets used

None.
