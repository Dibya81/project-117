import { assetDefs, basePlate, palette, ports, statusBeacon, tagPlate, type EquipmentAssetProps } from "./shared";

export function Compressor({ box: b, id, name, status, selected, variant = "single" }: EquipmentAssetProps) {
  const train = variant === "train";
  return (
    <g data-equipment-asset={train ? "compressor-train" : "compressor"}>
      {assetDefs("eq-compressor")}
      <g filter="url(#eq-compressor-shadow)">
        {basePlate(b, 0.84)}
        <circle cx={b.x + b.w * 0.28} cy={b.y + b.h * 0.5} r={b.h * 0.25} fill="url(#eq-compressor-violet)" stroke={palette.stroke} strokeWidth={1.7} />
        <circle cx={b.x + b.w * 0.28} cy={b.y + b.h * 0.5} r={b.h * 0.11} fill="#c2c8e0" stroke={palette.stroke} strokeWidth={1.1} />
        <rect x={b.x + b.w * 0.5} y={b.y + b.h * 0.32} width={b.w * 0.27} height={b.h * 0.36} rx={3} fill="#d3d8ea" stroke={palette.stroke} strokeWidth={1.5} />
        {train && (
          <>
            <circle cx={b.x + b.w * 0.83} cy={b.y + b.h * 0.5} r={b.h * 0.2} fill="url(#eq-compressor-cool)" stroke={palette.stroke} strokeWidth={1.5} />
            <line x1={b.x + b.w * 0.77} y1={b.y + b.h * 0.5} x2={b.x + b.w * 0.63} y2={b.y + b.h * 0.5} stroke={palette.dark} strokeWidth={2.2} />
          </>
        )}
        <path d={`M ${b.x + b.w * 0.08} ${b.y + b.h * 0.5} H ${b.x + b.w * 0.03} M ${b.x + b.w * 0.95} ${b.y + b.h * 0.5} H ${b.x + b.w * 0.78}`} stroke={palette.stroke} strokeWidth={2} />
      </g>
      {ports(b, [[0.02, 0.5], [0.98, 0.5], [0.5, 0.24]])}
      {tagPlate(b, id, name)}
      {statusBeacon(b, status, selected)}
    </g>
  );
}

export function CompressorTrain(props: EquipmentAssetProps) {
  return <Compressor {...props} variant="train" />;
}

export function PowerGenerator(props: EquipmentAssetProps) {
  const { box: b, id, name, status, selected } = props;
  return (
    <g data-equipment-asset="power-generator">
      {assetDefs("eq-generator")}
      <g filter="url(#eq-generator-shadow)">
        {basePlate(b, 0.84)}
        <rect x={b.x + b.w * 0.08} y={b.y + b.h * 0.28} width={b.w * 0.84} height={b.h * 0.5} rx={b.h * 0.16} fill="url(#eq-generator-steel)" stroke={palette.stroke} strokeWidth={1.7} />
        <g stroke="#64748b" strokeWidth={1}>{Array.from({ length: 7 }, (_, i) => <line key={i} x1={b.x + b.w * (0.18 + i * 0.1)} y1={b.y + b.h * 0.28} x2={b.x + b.w * (0.18 + i * 0.1)} y2={b.y + b.h * 0.78} />)}</g>
        <path d={`M ${b.x + b.w * 0.45} ${b.y + b.h * 0.66} l ${b.w * 0.1} ${-b.h * 0.19} h ${-b.w * 0.08} l ${b.w * 0.1} ${-b.h * 0.18}`} fill="none" stroke={palette.amber} strokeWidth={2.4} strokeLinejoin="round" />
      </g>
      {ports(b, [[0.02, 0.54], [0.98, 0.54]])}
      {tagPlate(b, id, name)}
      {statusBeacon(b, status, selected)}
    </g>
  );
}
