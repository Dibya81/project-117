import { assetDefs, basePlate, palette, ports, statusBeacon, tagPlate, type EquipmentAssetProps } from "./shared";

export function Pump({ box: b, id, name, status, selected, variant = "centrifugal" }: EquipmentAssetProps) {
  const positive = variant === "positive-displacement";
  const hot = variant === "charge" || variant === "feed";
  return (
    <g data-equipment-asset={`${variant}-pump`}>
      {assetDefs("eq-pump")}
      <g filter="url(#eq-pump-shadow)">
        {basePlate(b, 0.86)}
        <circle cx={b.x + b.w * 0.32} cy={b.y + b.h * 0.55} r={b.h * 0.25} fill={hot ? "url(#eq-pump-warm)" : "url(#eq-pump-steel)"} stroke={palette.stroke} strokeWidth={1.7} />
        {positive ? (
          <rect x={b.x + b.w * 0.16} y={b.y + b.h * 0.37} width={b.w * 0.34} height={b.h * 0.34} rx={3} fill="#dbe5f0" stroke={palette.stroke} strokeWidth={1.5} />
        ) : (
          <path d={`M ${b.x + b.w * 0.28} ${b.y + b.h * 0.55} q ${b.w * 0.13} ${-b.h * 0.13} ${b.w * 0.22} 0 q ${-b.w * 0.08} ${b.h * 0.15} ${-b.w * 0.22} 0`} fill="none" stroke={palette.cyan} strokeWidth={2} />
        )}
        <circle cx={b.x + b.w * 0.32} cy={b.y + b.h * 0.55} r={b.h * 0.08} fill="#b6c7da" stroke={palette.stroke} strokeWidth={1.1} />
        <path d={`M ${b.x + b.w * 0.32} ${b.y + b.h * 0.3} V ${b.y + b.h * 0.13}`} stroke={palette.stroke} strokeWidth={1.8} />
        <rect x={b.x + b.w * 0.53} y={b.y + b.h * 0.36} width={b.w * 0.41} height={b.h * 0.34} rx={3} fill="#cfd9e6" stroke={palette.stroke} strokeWidth={1.6} />
        <g stroke="rgba(51,65,85,0.34)" strokeWidth={1}>{Array.from({ length: 4 }, (_, i) => <line key={i} x1={b.x + b.w * (0.59 + i * 0.08)} y1={b.y + b.h * 0.36} x2={b.x + b.w * (0.59 + i * 0.08)} y2={b.y + b.h * 0.7} />)}</g>
      </g>
      {ports(b, [[0.02, 0.55], [0.98, 0.55], [0.32, 0.12]])}
      {tagPlate(b, id, name)}
      {statusBeacon(b, status, selected)}
    </g>
  );
}

export function CentrifugalPump(props: EquipmentAssetProps) {
  return <Pump {...props} variant="centrifugal" />;
}

export function FeedPump(props: EquipmentAssetProps) {
  return <Pump {...props} variant="feed" />;
}

export function ChargePump(props: EquipmentAssetProps) {
  return <Pump {...props} variant="charge" />;
}

export function TransferPump(props: EquipmentAssetProps) {
  return <Pump {...props} variant="transfer" />;
}

export function PositiveDisplacementPump(props: EquipmentAssetProps) {
  return <Pump {...props} variant="positive-displacement" />;
}
