import { Reactor } from "./Reactor";
import type { EquipmentAssetProps } from "./shared";

export function Hydrotreater(props: EquipmentAssetProps) {
  return <Reactor {...props} variant="hydrotreater" />;
}
