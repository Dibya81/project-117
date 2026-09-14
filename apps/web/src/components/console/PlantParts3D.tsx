"use client";

/**
 * Miniature 3D industrial equipment, built from primitives into recognisable
 * objects.
 *
 * The first pass at the Home scene was cylinders and spheres standing in for
 * plant, which read as random primitives because that is what they were. A
 * column is a tall shell on a skirt with trays and a dished head; a tank is a
 * squat cylinder with a domed roof; a pump is a volute with a motor block on a
 * baseplate. These are the same silhouettes EquipmentShape draws in 2D for the
 * process map, so the Home scene and the plant agree about what the equipment
 * looks like.
 *
 * Everything is proportioned from a single `s` (scale) argument, so the same
 * part works as a satellite icon at 0.2 and as scenery at 1.0.
 */

import { useMemo } from "react";
import * as THREE from "three";

const STEEL = "#b9c5d4";
const STEEL_DARK = "#8fa0b5";
const SHELL = "#d3dce7";

export type PartKind = "column" | "tank" | "pump" | "exchanger" | "compressor" | "cabinet" | "vessel";

/** A distillation column: skirt, trayed shell, dished head, draw nozzles. */
function Column({ s = 1 }: { s?: number }) {
  const trays = useMemo(() => [0.2, 0.34, 0.48, 0.62, 0.76], []);
  return (
    <group scale={s}>
      <mesh position={[0, 0.14, 0]}>
        <cylinderGeometry args={[0.2, 0.24, 0.28, 16]} />
        <meshStandardMaterial color={STEEL_DARK} metalness={0.7} roughness={0.4} />
      </mesh>
      <mesh position={[0, 0.98, 0]} castShadow>
        <cylinderGeometry args={[0.2, 0.2, 1.4, 20]} />
        <meshStandardMaterial color={SHELL} metalness={0.55} roughness={0.35} />
      </mesh>
      <mesh position={[0, 1.7, 0]}>
        <sphereGeometry args={[0.2, 18, 12, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <meshStandardMaterial color={SHELL} metalness={0.55} roughness={0.35} />
      </mesh>
      {trays.map((t, i) => (
        <mesh key={i} position={[0, 0.32 + t * 1.3, 0]}>
          <cylinderGeometry args={[0.21, 0.21, 0.02, 18]} />
          <meshStandardMaterial color={STEEL_DARK} metalness={0.6} roughness={0.5} />
        </mesh>
      ))}
      <mesh position={[0.28, 0.9, 0]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[0.035, 0.035, 0.24, 8]} />
        <meshStandardMaterial color={STEEL_DARK} metalness={0.6} roughness={0.4} />
      </mesh>
    </group>
  );
}

/** A storage tank: squat shell, domed roof, ring foundation, stairway rail. */
function Tank({ s = 1 }: { s?: number }) {
  return (
    <group scale={s}>
      <mesh position={[0, 0.05, 0]}>
        <cylinderGeometry args={[0.46, 0.48, 0.1, 24]} />
        <meshStandardMaterial color={STEEL_DARK} metalness={0.5} roughness={0.6} />
      </mesh>
      <mesh position={[0, 0.42, 0]} castShadow>
        <cylinderGeometry args={[0.42, 0.42, 0.66, 24]} />
        <meshStandardMaterial color={SHELL} metalness={0.5} roughness={0.35} />
      </mesh>
      <mesh position={[0, 0.75, 0]}>
        <sphereGeometry args={[0.42, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <meshStandardMaterial color={SHELL} metalness={0.5} roughness={0.35} />
      </mesh>
      {/* Level gauge: the one detail that makes a disc read as a tank. */}
      <mesh position={[0.44, 0.44, 0]}>
        <boxGeometry args={[0.03, 0.3, 0.05]} />
        <meshStandardMaterial color="#3b82f6" emissive="#3b82f6" emissiveIntensity={0.5} />
      </mesh>
    </group>
  );
}

/** A centrifugal pump: volute, discharge nozzle, finned motor on a baseplate. */
function Pump({ s = 1 }: { s?: number }) {
  return (
    <group scale={s}>
      <mesh position={[0, 0.04, 0]}>
        <boxGeometry args={[0.78, 0.08, 0.36]} />
        <meshStandardMaterial color={STEEL_DARK} metalness={0.5} roughness={0.6} />
      </mesh>
      <mesh position={[-0.16, 0.24, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.19, 0.19, 0.2, 20]} />
        <meshStandardMaterial color={SHELL} metalness={0.6} roughness={0.3} />
      </mesh>
      <mesh position={[-0.16, 0.44, 0]}>
        <cylinderGeometry args={[0.05, 0.05, 0.16, 10]} />
        <meshStandardMaterial color={STEEL_DARK} metalness={0.6} roughness={0.4} />
      </mesh>
      <mesh position={[0.2, 0.26, 0]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[0.15, 0.15, 0.42, 16]} />
        <meshStandardMaterial color="#aab6c6" metalness={0.55} roughness={0.45} />
      </mesh>
    </group>
  );
}

/** A shell-and-tube exchanger: long shell, channel ends, saddle supports. */
function Exchanger({ s = 1 }: { s?: number }) {
  return (
    <group scale={s}>
      <mesh position={[0, 0.12, 0]}>
        <boxGeometry args={[0.5, 0.1, 0.28]} />
        <meshStandardMaterial color={STEEL_DARK} metalness={0.5} roughness={0.6} />
      </mesh>
      <mesh position={[0, 0.32, 0]} rotation={[0, 0, Math.PI / 2]} castShadow>
        <cylinderGeometry args={[0.18, 0.18, 1.15, 20]} />
        <meshStandardMaterial color="#ced9e2" metalness={0.55} roughness={0.32} />
      </mesh>
      {[-0.62, 0.62].map((x, i) => (
        <mesh key={i} position={[x, 0.32, 0]} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.21, 0.21, 0.1, 20]} />
          <meshStandardMaterial color={STEEL} metalness={0.6} roughness={0.3} />
        </mesh>
      ))}
    </group>
  );
}

/** A compressor: casing with impeller housing and a drive. */
function Compressor({ s = 1 }: { s?: number }) {
  return (
    <group scale={s}>
      <mesh position={[0, 0.05, 0]}>
        <boxGeometry args={[0.8, 0.1, 0.4]} />
        <meshStandardMaterial color={STEEL_DARK} metalness={0.5} roughness={0.6} />
      </mesh>
      <mesh position={[-0.16, 0.34, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.26, 0.26, 0.24, 22]} />
        <meshStandardMaterial color="#c6cfdd" metalness={0.6} roughness={0.32} />
      </mesh>
      <mesh position={[0.26, 0.32, 0]}>
        <boxGeometry args={[0.4, 0.34, 0.34]} />
        <meshStandardMaterial color={SHELL} metalness={0.55} roughness={0.4} />
      </mesh>
    </group>
  );
}

/** An instrument/control cabinet — the small vertical boxes on a real plot. */
function Cabinet({ s = 1 }: { s?: number }) {
  return (
    <group scale={s}>
      <mesh position={[0, 0.28, 0]} castShadow>
        <boxGeometry args={[0.34, 0.56, 0.26]} />
        <meshStandardMaterial color="#dfe6ee" metalness={0.35} roughness={0.5} />
      </mesh>
      <mesh position={[0, 0.42, 0.14]}>
        <boxGeometry args={[0.22, 0.16, 0.02]} />
        <meshStandardMaterial color="#3b82f6" emissive="#3b82f6" emissiveIntensity={0.35} />
      </mesh>
      <mesh position={[0, 0.04, 0]}>
        <boxGeometry args={[0.4, 0.08, 0.32]} />
        <meshStandardMaterial color={STEEL_DARK} metalness={0.4} roughness={0.7} />
      </mesh>
    </group>
  );
}

/** A vertical pressure vessel on legs. */
function Vessel({ s = 1 }: { s?: number }) {
  return (
    <group scale={s}>
      {[-0.14, 0.14].map((x, i) => (
        <mesh key={i} position={[x, 0.14, 0]}>
          <cylinderGeometry args={[0.025, 0.025, 0.28, 8]} />
          <meshStandardMaterial color={STEEL_DARK} metalness={0.6} roughness={0.4} />
        </mesh>
      ))}
      <mesh position={[0, 0.72, 0]} castShadow>
        <cylinderGeometry args={[0.3, 0.3, 0.86, 20]} />
        <meshStandardMaterial color={SHELL} metalness={0.55} roughness={0.35} />
      </mesh>
      <mesh position={[0, 1.16, 0]}>
        <sphereGeometry args={[0.3, 20, 12, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <meshStandardMaterial color={SHELL} metalness={0.55} roughness={0.35} />
      </mesh>
    </group>
  );
}

const PARTS: Record<PartKind, (p: { s?: number }) => React.JSX.Element> = {
  column: Column,
  tank: Tank,
  pump: Pump,
  exchanger: Exchanger,
  compressor: Compressor,
  cabinet: Cabinet,
  vessel: Vessel,
};

export function PlantPart({ kind, s = 1 }: { kind: PartKind; s?: number }) {
  const Part = PARTS[kind];
  return <Part s={s} />;
}

/**
 * A connected pipe run between two points, drawn as a tube so it reads as a
 * pipe rather than a line.
 */
export function Pipe({
  from,
  to,
  colour = STEEL_DARK,
  radius = 0.035,
}: {
  from: [number, number, number];
  to: [number, number, number];
  colour?: string;
  radius?: number;
}) {
  const { pos, quat, len } = useMemo(() => {
    const a = new THREE.Vector3(...from);
    const b = new THREE.Vector3(...to);
    const d = new THREE.Vector3().subVectors(b, a);
    const len = d.length();
    const quat = new THREE.Quaternion().setFromUnitVectors(
      new THREE.Vector3(0, 1, 0),
      d.clone().normalize(),
    );
    return { pos: a.clone().add(d.multiplyScalar(0.5)), quat, len };
  }, [from, to]);

  return (
    <mesh position={pos} quaternion={quat}>
      <cylinderGeometry args={[radius, radius, len, 8]} />
      <meshStandardMaterial color={colour} metalness={0.7} roughness={0.4} />
    </mesh>
  );
}
