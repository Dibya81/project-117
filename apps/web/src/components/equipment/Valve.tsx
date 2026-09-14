import { assetDefs, palette, ports, statusBeacon, tagPlate, type EquipmentAssetProps } from "./shared";

export function Valve({ box: b, id, name, status, selected, variant = "control" }: EquipmentAssetProps) {
  const cy = b.y + b.h * 0.58;
  const r = b.h * 0.2;
  const relief = variant === "safety-relief";
  const check = variant === "check";
  return (
    <g data-equipment-asset={`${variant}-valve`}>
      {assetDefs("eq-valve")}
      <g filter="url(#eq-valve-shadow)">
        <line x1={b.x} y1={cy} x2={b.x + b.w} y2={cy} stroke={palette.stroke} strokeWidth={2} />
        <path d={`M ${b.x + b.w * 0.13} ${cy - r} L ${b.x + b.w * 0.13} ${cy + r} L ${b.x + b.w * 0.5} ${cy} Z`} fill="url(#eq-valve-steel)" stroke={palette.stroke} strokeWidth={1.6} />
        <path d={`M ${b.x + b.w * 0.87} ${cy - r} L ${b.x + b.w * 0.87} ${cy + r} L ${b.x + b.w * 0.5} ${cy} Z`} fill="url(#eq-valve-steel)" stroke={palette.stroke} strokeWidth={1.6} />
        {check && <path d={`M ${b.x + b.w * 0.42} ${cy - r * 0.7} L ${b.x + b.w * 0.58} ${cy} L ${b.x + b.w * 0.42} ${cy + r * 0.7}`} fill="none" stroke={palette.cyan} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />}
        {!check && <line x1={b.x + b.w * 0.5} y1={cy - r} x2={b.x + b.w * 0.5} y2={b.y + b.h * 0.18} stroke={palette.stroke} strokeWidth={1.5} />}
        {variant === "control" && <rect x={b.x + b.w * 0.3} y={b.y + b.h * 0.05} width={b.w * 0.4} height={b.h * 0.14} rx={2} fill="#dbeafe" stroke={palette.cyan} strokeWidth={1.3} />}
        {variant === "isolation" && <circle cx={b.x + b.w * 0.5} cy={b.y + b.h * 0.13} r={b.h * 0.09} fill="#e2e8f0" stroke={palette.stroke} strokeWidth={1.2} />}
        {relief && (
          <>
            <path d={`M ${b.x + b.w * 0.5} ${cy - r} V ${b.y + b.h * 0.14} q ${b.w * 0.14} ${b.h * 0.02} ${b.w * 0.16} ${b.h * 0.14}`} fill="none" stroke={palette.red} strokeWidth={2} />
            <circle cx={b.x + b.w * 0.5} cy={b.y + b.h * 0.14} r={b.h * 0.08} fill="#fee2e2" stroke={palette.red} strokeWidth={1.2} />
          </>
        )}
      </g>
      {ports(b, [[0, 0.58], [1, 0.58], [0.5, 0.08]])}
      {tagPlate(b, id, name)}
      {statusBeacon(b, status, selected)}
    </g>
  );
}

export function ControlValve(props: EquipmentAssetProps) {
  return <Valve {...props} variant="control" />;
}

export function IsolationValve(props: EquipmentAssetProps) {
  return <Valve {...props} variant="isolation" />;
}

export function CheckValve(props: EquipmentAssetProps) {
  return <Valve {...props} variant="check" />;
}

export function SafetyReliefValve(props: EquipmentAssetProps) {
  return <Valve {...props} variant="safety-relief" />;
}
