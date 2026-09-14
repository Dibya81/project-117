import { assetDefs, horizontalVesselShell, ladder, legs, palette, ports, statusBeacon, tagPlate, verticalShell, type EquipmentAssetProps } from "./shared";

export function Vessel({ box: b, id, name, status, selected, variant = "vertical" }: EquipmentAssetProps) {
  const horizontal = variant === "horizontal" || variant === "separator";
  return (
    <g data-equipment-asset={`${variant}-vessel`}>
      {assetDefs("eq-vessel")}
      <g filter="url(#eq-vessel-shadow)">
        {horizontal ? (
          <>
            {horizontalVesselShell(b, `url(#eq-vessel-steel)`)}
            <rect x={b.x + b.w * 0.42} y={b.y + b.h * 0.16} width={b.w * 0.16} height={b.h * 0.16} rx={2} fill="#dce6ef" stroke={palette.stroke} strokeWidth={1.1} />
            <path d={`M ${b.x + b.w * 0.18} ${b.y + b.h * 0.7} V ${b.y + b.h * 0.9} M ${b.x + b.w * 0.82} ${b.y + b.h * 0.7} V ${b.y + b.h * 0.9}`} stroke={palette.stroke} strokeWidth={2} />
          </>
        ) : (
          <>
            {verticalShell(b, `url(#eq-vessel-steel)`, { top: 0.1, bottom: 0.86 })}
            <path d={`M ${b.x + b.w * 0.25} ${b.y + b.h * 0.5} H ${b.x + b.w * 0.75}`} stroke="rgba(51,65,85,0.4)" strokeWidth={1.2} />
            {legs(b, 2)}
            {ladder(b, "right", 0.2, 0.75)}
          </>
        )}
      </g>
      {ports(b, horizontal ? [[0.02, 0.51], [0.98, 0.51], [0.5, 0.16], [0.5, 0.9]] : [[0.5, 0.05], [0.18, 0.5], [0.82, 0.5], [0.5, 0.96]])}
      {tagPlate(b, id, name)}
      {statusBeacon(b, status, selected)}
    </g>
  );
}

export function VerticalVessel(props: EquipmentAssetProps) {
  return <Vessel {...props} variant="vertical" />;
}

export function HorizontalVessel(props: EquipmentAssetProps) {
  return <Vessel {...props} variant="horizontal" />;
}

export function SeparatorVessel(props: EquipmentAssetProps) {
  return <Vessel {...props} variant="separator" />;
}

export function ProcessVessel(props: EquipmentAssetProps) {
  return <Vessel {...props} variant="process" />;
}
