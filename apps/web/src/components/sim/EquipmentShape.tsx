"use client";

import { EquipmentRenderer } from "@/components/equipment/EquipmentRenderer";
import type { EquipmentStatus } from "@/components/equipment/shared";

export interface ShapeBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export function EquipmentShape({
  kind,
  box,
  id,
  name,
  status = "healthy",
  selected,
}: {
  kind: string;
  box: ShapeBox;
  id?: string;
  name?: string;
  status?: EquipmentStatus | string;
  selected?: boolean;
  tone?: string;
}) {
  return <EquipmentRenderer kind={kind} name={name} id={id} status={status} selected={selected} box={box} />;
}
