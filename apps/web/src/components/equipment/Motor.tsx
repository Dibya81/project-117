"use client";

import { assetDefs, basePlate, palette, ports, statusBeacon, tagPlate, type EquipmentAssetProps } from "./shared";

export function Motor({ box, id, name = "Motor", status = "healthy", selected }: EquipmentAssetProps) {
  const uid = `motor-${id ?? name}`.replace(/[^a-zA-Z0-9_-]/g, "");
  const shaftY = box.y + box.h * 0.5;
  return (
    <g data-equipment-asset="motor" data-selected={selected ? "true" : undefined}>
      {assetDefs(uid)}
      {basePlate(box)}
      <rect x={box.x + box.w * 0.18} y={box.y + box.h * 0.34} width={box.w * 0.58} height={box.h * 0.34} rx={box.h * 0.07} fill={`url(#${uid}-steel)`} stroke={palette.stroke} strokeWidth="1.4" />
      <rect x={box.x + box.w * 0.12} y={box.y + box.h * 0.39} width={box.w * 0.08} height={box.h * 0.24} rx={box.h * 0.03} fill="#64748b" stroke={palette.stroke} strokeWidth="1" />
      <rect x={box.x + box.w * 0.76} y={box.y + box.h * 0.43} width={box.w * 0.1} height={box.h * 0.14} rx={box.h * 0.03} fill="#475569" stroke={palette.stroke} strokeWidth="1" />
      <line x1={box.x + box.w * 0.86} y1={shaftY} x2={box.x + box.w * 0.98} y2={shaftY} stroke="#334155" strokeWidth="3" strokeLinecap="round" />
      {[0.28, 0.36, 0.44, 0.52, 0.6, 0.68].map((p) => (
        <line key={p} x1={box.x + box.w * p} y1={box.y + box.h * 0.36} x2={box.x + box.w * p} y2={box.y + box.h * 0.66} stroke="#334155" strokeWidth="0.8" opacity="0.42" />
      ))}
      <path d={`M ${box.x + box.w * 0.25} ${box.y + box.h * 0.31} L ${box.x + box.w * 0.66} ${box.y + box.h * 0.31}`} stroke={palette.highlight} strokeWidth="2" opacity="0.65" />
      {ports(box, [[0.02, 0.5], [0.98, 0.5]])}
      {statusBeacon(box, status)}
      {tagPlate(box, id, name)}
    </g>
  );
}

export function DriveMotorAssembly(props: EquipmentAssetProps) {
  const { box, id, name = "Drive Assembly", status = "healthy", selected } = props;
  const uid = `drive-${id ?? name}`.replace(/[^a-zA-Z0-9_-]/g, "");
  return (
    <g data-equipment-asset="drive-motor-assembly" data-selected={selected ? "true" : undefined}>
      {assetDefs(uid)}
      {basePlate(box)}
      <rect x={box.x + box.w * 0.1} y={box.y + box.h * 0.38} width={box.w * 0.42} height={box.h * 0.3} rx={box.h * 0.06} fill={`url(#${uid}-steel)`} stroke={palette.stroke} strokeWidth="1.3" />
      <rect x={box.x + box.w * 0.54} y={box.y + box.h * 0.42} width={box.w * 0.18} height={box.h * 0.22} rx={box.h * 0.035} fill="#7c8794" stroke={palette.stroke} strokeWidth="1.1" />
      <circle cx={box.x + box.w * 0.83} cy={box.y + box.h * 0.53} r={box.h * 0.15} fill="#8ca0b3" stroke={palette.stroke} strokeWidth="1.4" />
      <path d={`M ${box.x + box.w * 0.72} ${box.y + box.h * 0.53} H ${box.x + box.w * 0.98}`} stroke="#334155" strokeWidth="3" strokeLinecap="round" />
      {[0.18, 0.26, 0.34, 0.42].map((p) => (
        <line key={p} x1={box.x + box.w * p} y1={box.y + box.h * 0.4} x2={box.x + box.w * p} y2={box.y + box.h * 0.66} stroke="#334155" strokeWidth="0.75" opacity="0.36" />
      ))}
      <circle cx={box.x + box.w * 0.83} cy={box.y + box.h * 0.53} r={box.h * 0.055} fill="#e2e8f0" stroke="#475569" strokeWidth="0.9" />
      {ports(box, [[0.02, 0.53], [0.98, 0.53]])}
      {statusBeacon(box, status)}
      {tagPlate(box, id, name)}
    </g>
  );
}
