"use client";

/**
 * ReactorCoreScene — the Project 117 signature 3D object.
 * A wireframe containment cage around a pulsing energy core, two gyroscope
 * rings and orbital sparkles. Mouse parallax; slow idle rotation.
 * Rendered through ReactorOrb (next/dynamic, ssr:false) — never SSR'd.
 */
import { Canvas, useFrame } from "@react-three/fiber";
import { Float, Sparkles } from "@react-three/drei";
import { useRef } from "react";
import type { Group, Mesh } from "three";

function Core() {
  const group = useRef<Group>(null);
  const core = useRef<Mesh>(null);
  const ringA = useRef<Mesh>(null);
  const ringB = useRef<Mesh>(null);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    const { x, y } = state.pointer;
    if (group.current) {
      group.current.rotation.y = t * 0.16 + x * 0.35;
      group.current.rotation.x = y * -0.22;
    }
    if (core.current) {
      const pulse = 1 + Math.sin(t * 2.1) * 0.07;
      core.current.scale.setScalar(pulse);
      const mats = Array.isArray(core.current.material) ? core.current.material : [core.current.material];
      for (const mat of mats) {
        if (mat && typeof mat === "object" && "emissiveIntensity" in mat) {
          (mat as { emissiveIntensity: number }).emissiveIntensity = 1.6 + Math.sin(t * 2.1) * 0.55;
        }
      }
    }
    if (ringA.current) {
      ringA.current.rotation.z = t * 0.5;
      ringA.current.rotation.x = Math.PI / 2.6 + Math.sin(t * 0.3) * 0.18;
    }
    if (ringB.current) {
      ringB.current.rotation.z = -t * 0.34;
      ringB.current.rotation.x = Math.PI / 1.9 + Math.cos(t * 0.24) * 0.16;
    }
  });

  return (
    <group ref={group}>
      <Float speed={1.6} rotationIntensity={0.35} floatIntensity={0.85}>
        {/* containment cage */}
        <mesh>
          <icosahedronGeometry args={[1.62, 1]} />
          <meshBasicMaterial color="#45d5ff" wireframe transparent opacity={0.32} />
        </mesh>
        <mesh>
          <icosahedronGeometry args={[1.62, 0]} />
          <meshBasicMaterial color="#45d5ff" transparent opacity={0.045} depthWrite={false} />
        </mesh>
        {/* energy core */}
        <mesh ref={core}>
          <sphereGeometry args={[0.62, 48, 48]} />
          <meshStandardMaterial
            color="#0a2438"
            emissive="#45d5ff"
            emissiveIntensity={1.8}
            roughness={0.25}
            metalness={0.1}
          />
        </mesh>
        {/* gyroscope rings */}
        <mesh ref={ringA}>
          <torusGeometry args={[2.05, 0.014, 12, 120]} />
          <meshBasicMaterial color="#45d5ff" transparent opacity={0.55} />
        </mesh>
        <mesh ref={ringB}>
          <torusGeometry args={[2.35, 0.01, 12, 120]} />
          <meshBasicMaterial color="#ff7a3d" transparent opacity={0.4} />
        </mesh>
      </Float>
      <Sparkles count={90} scale={[5.4, 5.4, 5.4]} size={2.4} speed={0.32} color="#7fe3ff" opacity={0.65} />
      <Sparkles count={26} scale={[4.2, 4.2, 4.2]} size={3.4} speed={0.22} color="#ffab7a" opacity={0.5} />
    </group>
  );
}

export default function ReactorCoreScene({ dpr = 1.5 }: { dpr?: number }) {
  return (
    <Canvas
      dpr={[1, dpr]}
      camera={{ position: [0, 0, 5.6], fov: 42 }}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      style={{ background: "transparent" }}
    >
      <ambientLight intensity={0.35} />
      <pointLight position={[4, 3, 4]} intensity={28} color="#45d5ff" />
      <pointLight position={[-4, -3, -2]} intensity={14} color="#ff7a3d" />
      <Core />
    </Canvas>
  );
}
