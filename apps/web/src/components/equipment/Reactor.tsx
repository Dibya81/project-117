import { assetDefs, ladder, legs, palette, platform, ports, statusBeacon, tagPlate, verticalShell, type EquipmentAssetProps } from "./shared";

export function Reactor({ box: b, id, name, status, selected, variant = "reactor" }: EquipmentAssetProps) {
  const fill = variant === "hydrogen" ? `url(#eq-reactor-cool)` : `url(#eq-reactor-violet)`;
  return (
    <g data-equipment-asset={`${variant}-reactor`}>
      {assetDefs("eq-reactor")}
      <g filter="url(#eq-reactor-shadow)">
        {verticalShell(b, fill, { top: 0.09, bottom: 0.86, rx: b.w * 0.18 })}
        <g stroke="#7f8da3" strokeWidth={1.2}>
          <line x1={b.x + b.w * 0.24} y1={b.y + b.h * 0.32} x2={b.x + b.w * 0.76} y2={b.y + b.h * 0.32} />
          <line x1={b.x + b.w * 0.24} y1={b.y + b.h * 0.54} x2={b.x + b.w * 0.76} y2={b.y + b.h * 0.54} />
          <line x1={b.x + b.w * 0.24} y1={b.y + b.h * 0.69} x2={b.x + b.w * 0.76} y2={b.y + b.h * 0.69} />
        </g>
        {platform(b, 0.42)}
        {legs(b, 2)}
      </g>
      {ladder(b, "right", 0.18, 0.78)}
      {ports(b, [[0.5, 0.04], [0.16, 0.5], [0.84, 0.5], [0.5, 0.98]])}
      {tagPlate(b, id, name)}
      {statusBeacon(b, status, selected)}
    </g>
  );
}

export function ReactorVessel(props: EquipmentAssetProps) {
  return <Reactor {...props} variant="reactor" />;
}
