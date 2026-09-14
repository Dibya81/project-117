import { assetDefs, palette, ports, statusBeacon, tagPlate, type EquipmentAssetProps } from "./shared";

export function Instrument({ box: b, id, name, status, selected, variant = "control" }: EquipmentAssetProps) {
  const code = variant === "pressure" ? "PT" : variant === "temperature" ? "TT" : variant === "flow" ? "FT" : variant === "level" ? "LT" : variant === "vibration" ? "VT" : "IC";
  const tone = variant === "vibration" ? palette.violet : variant === "temperature" ? palette.orange : variant === "flow" ? palette.cyan : palette.blue;
  return (
    <g data-equipment-asset={`${variant}-instrument`}>
      {assetDefs("eq-inst")}
      <g filter="url(#eq-inst-shadow)">
        <line x1={b.x + b.w * 0.5} y1={b.y + b.h * 0.12} x2={b.x + b.w * 0.5} y2={b.y + b.h * 0.82} stroke={palette.stroke} strokeWidth={1.2} strokeDasharray={variant === "connection" ? "3 3" : undefined} />
        <circle cx={b.x + b.w * 0.5} cy={b.y + b.h * 0.38} r={Math.min(b.w, b.h) * 0.24} fill="#fff" stroke={tone} strokeWidth={1.8} />
        <text x={b.x + b.w * 0.5} y={b.y + b.h * 0.42} textAnchor="middle" fontFamily="ui-monospace, monospace" fontSize={Math.max(7, b.h * 0.12)} fontWeight={800} fill="#1f2937">{code}</text>
        <rect x={b.x + b.w * 0.37} y={b.y + b.h * 0.7} width={b.w * 0.26} height={b.h * 0.14} rx={2} fill="#e2e8f0" stroke={palette.stroke} strokeWidth={1} />
      </g>
      {ports(b, [[0.5, 0.08], [0.5, 0.86]])}
      {tagPlate(b, id, name)}
      {statusBeacon(b, status, selected)}
    </g>
  );
}
