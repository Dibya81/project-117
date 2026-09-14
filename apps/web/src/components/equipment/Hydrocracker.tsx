import { Reactor } from "./Reactor";
import type { EquipmentAssetProps } from "./shared";

export function Hydrocracker(props: EquipmentAssetProps) {
  return <Reactor {...props} variant="hydrocracker" />;
}
