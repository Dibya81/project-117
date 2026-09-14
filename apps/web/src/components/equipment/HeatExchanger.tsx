import { assetDefs, horizontalVesselShell, legs, palette, ports, statusBeacon, tagPlate, type EquipmentAssetProps } from "./shared";

export function HeatExchanger({ box: b, id, name, status, selected, variant = "shell-tube" }: EquipmentAssetProps) {
  const air = variant === "air-cooler";
  const condenser = variant === "condenser";
  const fill = condenser ? `url(#eq-hx-cool)` : `url(#eq-hx-green)`;
  return (
    <g data-equipment-asset={`${variant}-heat-exchanger`}>
      {assetDefs("eq-hx")}
      <g filter="url(#eq-hx-shadow)">
        {air ? (
          <>
            <polygon points={`${b.x + b.w * 0.08},${b.y + b.h * 0.78} ${b.x + b.w * 0.92},${b.y + b.h * 0.78} ${b.x + b.w * 0.78},${b.y + b.h * 0.28} ${b.x + b.w * 0.22},${b.y + b.h * 0.28}`} fill="#dbeafe" stroke={palette.stroke} strokeWidth={1.6} />
            {[0.32, 0.5, 0.68].map((x) => <circle key={x} cx={b.x + b.w * x} cy={b.y + b.h * 0.49} r={b.h * 0.13} fill="#f8fafc" stroke={palette.cyan} strokeWidth={1.2} />)}
            <g stroke="#8aa0b7" strokeWidth={1}>{Array.from({ length: 7 }, (_, i) => <line key={i} x1={b.x + b.w * (0.18 + i * 0.1)} y1={b.y + b.h * 0.75} x2={b.x + b.w * (0.28 + i * 0.08)} y2={b.y + b.h * 0.31} />)}</g>
          </>
        ) : (
          <>
            {legs(b, 2)}
            {horizontalVesselShell(b, fill)}
            <g stroke="rgba(51,65,85,0.36)" strokeWidth={1}>
              {Array.from({ length: variant === "reboiler" ? 4 : 7 }, (_, i) => (
                <line key={i} x1={b.x + b.w * 0.13} y1={b.y + b.h * (0.37 + i * 0.045)} x2={b.x + b.w * 0.87} y2={b.y + b.h * (0.37 + i * 0.045)} />
              ))}
            </g>
            {variant === "reboiler" && <path d={`M ${b.x + b.w * 0.28} ${b.y + b.h * 0.68} q ${b.w * 0.22} ${b.h * 0.2} ${b.w * 0.44} 0`} fill="none" stroke={palette.orange} strokeWidth={2.4} />}
          </>
        )}
      </g>
      {ports(b, air ? [[0.12, 0.78], [0.88, 0.78], [0.5, 0.22]] : [[0.02, 0.51], [0.98, 0.51], [0.32, 0.26], [0.68, 0.76]])}
      {tagPlate(b, id, name)}
      {statusBeacon(b, status, selected)}
    </g>
  );
}

export function Condenser(props: EquipmentAssetProps) {
  return <HeatExchanger {...props} variant="condenser" />;
}

export function Reboiler(props: EquipmentAssetProps) {
  return <HeatExchanger {...props} variant="reboiler" />;
}

export function AirCooler(props: EquipmentAssetProps) {
  return <HeatExchanger {...props} variant="air-cooler" />;
}
