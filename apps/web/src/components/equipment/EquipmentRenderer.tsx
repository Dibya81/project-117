"use client";

import type { ComponentType } from "react";
import type { EquipmentAssetProps, EquipmentBox, EquipmentStatus } from "./shared";
import { AmineUnit } from "./AmineUnit";
import { Boiler, SteamDrum } from "./Boiler";
import { AtmosphericDistillationColumn, Column, FractionationColumn, VacuumDistillationColumn } from "./Column";
import { Compressor, CompressorTrain, PowerGenerator } from "./Compressor";
import { CoolingTower } from "./CoolingTower";
import { Desalter } from "./Desalter";
import { FCC } from "./FCC";
import { Furnace } from "./Furnace";
import { AirCooler, Condenser, HeatExchanger, Reboiler } from "./HeatExchanger";
import { Hydrocracker } from "./Hydrocracker";
import { Hydrotreater } from "./Hydrotreater";
import { Instrument } from "./Instrument";
import { DriveMotorAssembly, Motor } from "./Motor";
import { CentrifugalPump, ChargePump, FeedPump, PositiveDisplacementPump, Pump, TransferPump } from "./Pump";
import { Reactor, ReactorVessel } from "./Reactor";
import { GasTreatmentUnit, HydrogenUnit, SRU } from "./SRU";
import { CrudeStorageTank, ProductStorageTank, Tank, VerticalTank } from "./Tank";
import { CheckValve, ControlValve, IsolationValve, SafetyReliefValve, Valve } from "./Valve";
import { HorizontalVessel, ProcessVessel, SeparatorVessel, Vessel, VerticalVessel } from "./Vessel";

export type RefineryAssetKey =
  | "crude-storage-tank"
  | "product-storage-tank"
  | "vertical-tank"
  | "horizontal-tank"
  | "desalter"
  | "atmospheric-distillation-column"
  | "vacuum-distillation-column"
  | "fractionation-column"
  | "column"
  | "condenser"
  | "reboiler"
  | "heat-exchanger"
  | "air-cooler"
  | "fcc-unit"
  | "hydrocracker-reactor"
  | "hydrotreater"
  | "reactor-vessel"
  | "separator-vessel"
  | "process-vessel"
  | "vertical-vessel"
  | "horizontal-vessel"
  | "amine-treating-unit"
  | "sulfur-recovery-unit"
  | "gas-treatment-unit"
  | "hydrogen-unit"
  | "cooling-tower"
  | "boiler"
  | "furnace"
  | "steam-drum"
  | "power-generator"
  | "compressor"
  | "compressor-train"
  | "centrifugal-pump"
  | "feed-pump"
  | "charge-pump"
  | "transfer-pump"
  | "positive-displacement-pump"
  | "control-valve"
  | "isolation-valve"
  | "check-valve"
  | "safety-relief-valve"
  | "motor"
  | "drive-motor-assembly"
  | "pressure-sensor"
  | "temperature-sensor"
  | "flow-sensor"
  | "level-sensor"
  | "vibration-sensor"
  | "control-instrument"
  | "instrument-connection"
  | "tank"
  | "vessel"
  | "reactor"
  | "pump"
  | "valve"
  | "instrument";

export interface EquipmentRendererProps extends Omit<EquipmentAssetProps, "box"> {
  asset?: string;
  kind?: string;
  type?: string;
  box: EquipmentBox;
  className?: string;
}

export const equipmentAssetCatalog: Array<{ key: RefineryAssetKey; label: string }> = [
  { key: "crude-storage-tank", label: "Crude Storage Tank" },
  { key: "product-storage-tank", label: "Product Storage Tank" },
  { key: "vertical-tank", label: "Vertical Tank" },
  { key: "horizontal-tank", label: "Horizontal Tank" },
  { key: "desalter", label: "Desalter" },
  { key: "atmospheric-distillation-column", label: "Atmospheric Distillation Column" },
  { key: "vacuum-distillation-column", label: "Vacuum Distillation Column" },
  { key: "fractionation-column", label: "Fractionation Column" },
  { key: "condenser", label: "Condenser" },
  { key: "reboiler", label: "Reboiler" },
  { key: "heat-exchanger", label: "Heat Exchanger" },
  { key: "air-cooler", label: "Air Cooler" },
  { key: "fcc-unit", label: "FCC Unit" },
  { key: "hydrocracker-reactor", label: "Hydrocracker Reactor" },
  { key: "hydrotreater", label: "Hydrotreater" },
  { key: "reactor-vessel", label: "Reactor Vessel" },
  { key: "separator-vessel", label: "Separator Vessel" },
  { key: "process-vessel", label: "Process Vessel" },
  { key: "amine-treating-unit", label: "Amine Treating Unit" },
  { key: "sulfur-recovery-unit", label: "Sulfur Recovery Unit" },
  { key: "gas-treatment-unit", label: "Gas Treatment Unit" },
  { key: "hydrogen-unit", label: "Hydrogen Unit" },
  { key: "cooling-tower", label: "Cooling Tower" },
  { key: "boiler", label: "Boiler" },
  { key: "furnace", label: "Furnace" },
  { key: "steam-drum", label: "Steam Drum" },
  { key: "power-generator", label: "Power Generator" },
  { key: "compressor", label: "Compressor" },
  { key: "compressor-train", label: "Compressor Train" },
  { key: "centrifugal-pump", label: "Centrifugal Pump" },
  { key: "feed-pump", label: "Feed Pump" },
  { key: "charge-pump", label: "Charge Pump" },
  { key: "transfer-pump", label: "Transfer Pump" },
  { key: "positive-displacement-pump", label: "Positive Displacement Pump" },
  { key: "control-valve", label: "Control Valve" },
  { key: "isolation-valve", label: "Isolation Valve" },
  { key: "check-valve", label: "Check Valve" },
  { key: "safety-relief-valve", label: "Safety Relief Valve" },
  { key: "motor", label: "Motor" },
  { key: "drive-motor-assembly", label: "Drive/Motor Assembly" },
  { key: "pressure-sensor", label: "Pressure Sensor" },
  { key: "temperature-sensor", label: "Temperature Sensor" },
  { key: "flow-sensor", label: "Flow Sensor" },
  { key: "level-sensor", label: "Level Sensor" },
  { key: "vibration-sensor", label: "Vibration Sensor" },
  { key: "control-instrument", label: "Control Instrument" },
  { key: "instrument-connection", label: "Instrument Connection" },
];

const componentByKey: Record<RefineryAssetKey, ComponentType<EquipmentAssetProps>> = {
  "crude-storage-tank": CrudeStorageTank,
  "product-storage-tank": ProductStorageTank,
  "vertical-tank": VerticalTank,
  "horizontal-tank": HorizontalVessel,
  desalter: Desalter,
  "atmospheric-distillation-column": AtmosphericDistillationColumn,
  "vacuum-distillation-column": VacuumDistillationColumn,
  "fractionation-column": FractionationColumn,
  column: Column,
  condenser: Condenser,
  reboiler: Reboiler,
  "heat-exchanger": HeatExchanger,
  "air-cooler": AirCooler,
  "fcc-unit": FCC,
  "hydrocracker-reactor": Hydrocracker,
  hydrotreater: Hydrotreater,
  "reactor-vessel": ReactorVessel,
  "separator-vessel": SeparatorVessel,
  "process-vessel": ProcessVessel,
  "vertical-vessel": VerticalVessel,
  "horizontal-vessel": HorizontalVessel,
  "amine-treating-unit": AmineUnit,
  "sulfur-recovery-unit": SRU,
  "gas-treatment-unit": GasTreatmentUnit,
  "hydrogen-unit": HydrogenUnit,
  "cooling-tower": CoolingTower,
  boiler: Boiler,
  furnace: Furnace,
  "steam-drum": SteamDrum,
  "power-generator": PowerGenerator,
  compressor: Compressor,
  "compressor-train": CompressorTrain,
  "centrifugal-pump": CentrifugalPump,
  "feed-pump": FeedPump,
  "charge-pump": ChargePump,
  "transfer-pump": TransferPump,
  "positive-displacement-pump": PositiveDisplacementPump,
  "control-valve": ControlValve,
  "isolation-valve": IsolationValve,
  "check-valve": CheckValve,
  "safety-relief-valve": SafetyReliefValve,
  motor: Motor,
  "drive-motor-assembly": DriveMotorAssembly,
  "pressure-sensor": Instrument,
  "temperature-sensor": Instrument,
  "flow-sensor": Instrument,
  "level-sensor": Instrument,
  "vibration-sensor": Instrument,
  "control-instrument": Instrument,
  "instrument-connection": Instrument,
  tank: Tank,
  vessel: Vessel,
  reactor: Reactor,
  pump: Pump,
  valve: Valve,
  instrument: Instrument,
};

export const preferredAssetSize: Record<RefineryAssetKey, { w: number; h: number }> = {
  "crude-storage-tank": { w: 120, h: 86 },
  "product-storage-tank": { w: 112, h: 82 },
  "vertical-tank": { w: 92, h: 118 },
  "horizontal-tank": { w: 118, h: 62 },
  desalter: { w: 128, h: 58 },
  "atmospheric-distillation-column": { w: 82, h: 178 },
  "vacuum-distillation-column": { w: 94, h: 184 },
  "fractionation-column": { w: 76, h: 164 },
  column: { w: 76, h: 160 },
  condenser: { w: 118, h: 58 },
  reboiler: { w: 118, h: 64 },
  "heat-exchanger": { w: 120, h: 56 },
  "air-cooler": { w: 132, h: 70 },
  "fcc-unit": { w: 148, h: 144 },
  "hydrocracker-reactor": { w: 94, h: 136 },
  hydrotreater: { w: 86, h: 126 },
  "reactor-vessel": { w: 88, h: 128 },
  "separator-vessel": { w: 120, h: 64 },
  "process-vessel": { w: 98, h: 112 },
  "vertical-vessel": { w: 86, h: 118 },
  "horizontal-vessel": { w: 118, h: 62 },
  "amine-treating-unit": { w: 120, h: 138 },
  "sulfur-recovery-unit": { w: 138, h: 90 },
  "gas-treatment-unit": { w: 132, h: 118 },
  "hydrogen-unit": { w: 138, h: 104 },
  "cooling-tower": { w: 112, h: 138 },
  boiler: { w: 120, h: 104 },
  furnace: { w: 116, h: 128 },
  "steam-drum": { w: 112, h: 54 },
  "power-generator": { w: 128, h: 70 },
  compressor: { w: 114, h: 70 },
  "compressor-train": { w: 148, h: 76 },
  "centrifugal-pump": { w: 96, h: 56 },
  "feed-pump": { w: 100, h: 58 },
  "charge-pump": { w: 102, h: 58 },
  "transfer-pump": { w: 96, h: 56 },
  "positive-displacement-pump": { w: 108, h: 60 },
  "control-valve": { w: 72, h: 50 },
  "isolation-valve": { w: 68, h: 44 },
  "check-valve": { w: 72, h: 44 },
  "safety-relief-valve": { w: 72, h: 70 },
  motor: { w: 82, h: 48 },
  "drive-motor-assembly": { w: 112, h: 56 },
  "pressure-sensor": { w: 46, h: 46 },
  "temperature-sensor": { w: 46, h: 46 },
  "flow-sensor": { w: 46, h: 46 },
  "level-sensor": { w: 46, h: 46 },
  "vibration-sensor": { w: 46, h: 46 },
  "control-instrument": { w: 50, h: 50 },
  "instrument-connection": { w: 54, h: 42 },
  tank: { w: 112, h: 84 },
  vessel: { w: 96, h: 108 },
  reactor: { w: 88, h: 128 },
  pump: { w: 96, h: 56 },
  valve: { w: 70, h: 44 },
  instrument: { w: 46, h: 46 },
};

function slug(value: string): string {
  return value.toLowerCase().replace(/&/g, "and").replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

export function normalizeEquipmentAsset(...values: Array<string | undefined>): RefineryAssetKey {
  const haystack = values.filter(Boolean).map((value) => slug(value!)).join(" ");
  if (/crude.*storage|storage.*crude/.test(haystack)) return "crude-storage-tank";
  if (/product.*storage|storage.*product/.test(haystack)) return "product-storage-tank";
  if (/vertical.*tank/.test(haystack)) return "vertical-tank";
  if (/horizontal.*tank/.test(haystack)) return "horizontal-tank";
  if (haystack.includes("desalter")) return "desalter";
  if (/atmospheric|crude-column/.test(haystack)) return "atmospheric-distillation-column";
  if (/vacuum/.test(haystack)) return "vacuum-distillation-column";
  if (/fraction/.test(haystack)) return "fractionation-column";
  if (/condenser/.test(haystack)) return "condenser";
  if (/reboiler/.test(haystack)) return "reboiler";
  if (/air.*cooler/.test(haystack)) return "air-cooler";
  if (/heat.*exchanger|exchanger/.test(haystack)) return "heat-exchanger";
  if (/fcc|fluid.*catalytic/.test(haystack)) return "fcc-unit";
  if (/hydrocracker|hydrocrack/.test(haystack)) return "hydrocracker-reactor";
  if (/hydrotreater|hydrotreat/.test(haystack)) return "hydrotreater";
  if (/reactor.*vessel/.test(haystack)) return "reactor-vessel";
  if (/separator/.test(haystack)) return "separator-vessel";
  if (/amine/.test(haystack)) return "amine-treating-unit";
  if (/sulfur|sru|claus/.test(haystack)) return "sulfur-recovery-unit";
  if (/gas.*treatment/.test(haystack)) return "gas-treatment-unit";
  if (/hydrogen/.test(haystack)) return "hydrogen-unit";
  if (/cooling.*tower/.test(haystack)) return "cooling-tower";
  if (/steam.*drum/.test(haystack)) return "steam-drum";
  if (/boiler/.test(haystack)) return "boiler";
  if (/furnace|heater/.test(haystack)) return "furnace";
  if (/power.*generator|generator/.test(haystack)) return "power-generator";
  if (/compressor.*train/.test(haystack)) return "compressor-train";
  if (/compressor/.test(haystack)) return "compressor";
  if (/positive.*displacement/.test(haystack)) return "positive-displacement-pump";
  if (/feed.*pump/.test(haystack)) return "feed-pump";
  if (/charge.*pump/.test(haystack)) return "charge-pump";
  if (/transfer.*pump/.test(haystack)) return "transfer-pump";
  if (/centrifugal.*pump/.test(haystack)) return "centrifugal-pump";
  if (/control.*valve/.test(haystack)) return "control-valve";
  if (/isolation.*valve/.test(haystack)) return "isolation-valve";
  if (/check.*valve/.test(haystack)) return "check-valve";
  if (/safety.*relief|relief.*valve/.test(haystack)) return "safety-relief-valve";
  if (/safety/.test(haystack)) return "safety-relief-valve";
  if (/drive.*motor|motor.*assembly/.test(haystack)) return "drive-motor-assembly";
  if (/motor/.test(haystack)) return "motor";
  if (/pressure.*sensor/.test(haystack)) return "pressure-sensor";
  if (/temperature.*sensor/.test(haystack)) return "temperature-sensor";
  if (/flow.*sensor/.test(haystack)) return "flow-sensor";
  if (/level.*sensor/.test(haystack)) return "level-sensor";
  if (/vibration.*sensor/.test(haystack)) return "vibration-sensor";
  if (/control.*instrument/.test(haystack)) return "control-instrument";
  if (/instrument.*connection/.test(haystack)) return "instrument-connection";
  if (/instrument|sensor/.test(haystack)) return "instrument";
  if (/column/.test(haystack)) return "column";
  if (/tank/.test(haystack)) return "tank";
  if (/reactor/.test(haystack)) return "reactor";
  if (/pump/.test(haystack)) return "pump";
  if (/valve/.test(haystack)) return "valve";
  if (/vessel/.test(haystack)) return "vessel";
  return "process-vessel";
}

function instrumentVariant(key: RefineryAssetKey): EquipmentAssetProps["variant"] {
  if (key === "pressure-sensor") return "pressure";
  if (key === "temperature-sensor") return "temperature";
  if (key === "flow-sensor") return "flow";
  if (key === "level-sensor") return "level";
  if (key === "vibration-sensor") return "vibration";
  if (key === "control-instrument") return "control";
  if (key === "instrument-connection") return "connection";
  return undefined;
}

export function EquipmentRenderer({ asset, kind, type, box, id, name, status = "healthy", selected, variant, className }: EquipmentRendererProps) {
  const key = normalizeEquipmentAsset(asset, type, kind, name);
  const Component = componentByKey[key] ?? ProcessVessel;
  const resolvedVariant = variant ?? instrumentVariant(key);
  return (
    <g className={className} data-equipment-renderer={key} data-status={status}>
      <Component box={box} id={id} name={name} status={status as EquipmentStatus} selected={selected} variant={resolvedVariant} />
    </g>
  );
}
