"use client";

/**
 * KnowledgeCore3D — the Home page's centre of gravity, as an actual 3D scene.
 *
 * The previous version was a rotated CSS square with HTML cards floating over
 * it. This is geometry: a physical base, three translucent shells turning at
 * different rates, a graph of nodes and edges inside them, and the plant's
 * systems travelling real orbital paths around the whole thing.
 *
 * The orbit is a projection of a genuine coordinate system. Each satellite has
 * a radius, a phase and a plane tilt; position comes from those three numbers
 * every frame, and z decides its scale, its opacity and whether it draws in
 * front of the core. Nothing is animated by CSS or by timers — there is one
 * render loop and the orbital clock is the only thing that advances.
 *
 * Everything outside the scene is real application state: the counts beside
 * each satellite come from the plant, and clicking one routes to the surface it
 * names.
 */

import { useMemo, useRef, useState } from "react";
import { Canvas, useFrame, type ThreeEvent } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import * as THREE from "three";
import { useRouter } from "next/navigation";

export interface Satellite {
  id: string;
  label: string;
  detail: string;
  href: string;
  count: number | null;
  countLabel: string;
  /** Orbital plane: 0 is the inner ring, 1 the outer. */
  ring: 0 | 1;
  /** Phase in radians, so the satellites spread around the ring. */
  phase: number;
  tone: string;
}

const RING_RADIUS = [5.0, 6.9];
const RING_TILT = [0.30, 0.20];
/** Seconds for one full revolution. Slow on purpose: this is not a spinner. */
const RING_PERIOD = [150, 215];

/* --------------------------------------------------------------------- core */

function Core({ reduced, hovered }: { reduced: boolean; hovered: boolean }) {
  const shellA = useRef<THREE.Mesh>(null);
  const shellB = useRef<THREE.Mesh>(null);
  const shellC = useRef<THREE.Mesh>(null);
  const graph = useRef<THREE.Group>(null);

  // The internal graph: a handful of nodes on a sphere with edges between the
  // near neighbours. Fixed seed so the structure is the same every load — a
  // knowledge graph that reshuffles itself is not a knowledge graph.
  const { nodes, edges } = useMemo(() => {
    const pts: THREE.Vector3[] = [];
    const golden = Math.PI * (3 - Math.sqrt(5));
    const N = 26;
    for (let i = 0; i < N; i++) {
      const y = 1 - (i / (N - 1)) * 2;
      const r = Math.sqrt(Math.max(0, 1 - y * y));
      const th = golden * i;
      pts.push(new THREE.Vector3(Math.cos(th) * r, y, Math.sin(th) * r).multiplyScalar(1.16));
    }
    const segs: [THREE.Vector3, THREE.Vector3][] = [];
    for (let i = 0; i < N; i++) {
      for (let j = i + 1; j < N; j++) {
        if (pts[i].distanceTo(pts[j]) < 0.92) segs.push([pts[i], pts[j]]);
      }
    }
    return { nodes: pts, edges: segs };
  }, []);

  useFrame((_, dt) => {
    if (reduced) return;
    const s = dt * (hovered ? 0.5 : 0.22);
    if (shellA.current) shellA.current.rotation.y += s;
    if (shellB.current) shellB.current.rotation.y -= s * 0.7;
    if (shellC.current) shellC.current.rotation.y += s * 0.45;
    if (graph.current) graph.current.rotation.y += s * 0.32;
  });

  const glow = hovered ? 1.5 : 1;

  return (
    <group>
      {/* Physical base: a machined plinth, not a floating shape. */}
      <mesh position={[0, -1.62, 0]} receiveShadow>
        <cylinderGeometry args={[2.05, 2.2, 0.34, 64]} />
        <meshStandardMaterial color="#c9d3e0" metalness={0.65} roughness={0.35} />
      </mesh>
      <mesh position={[0, -1.42, 0]}>
        <cylinderGeometry args={[1.86, 1.86, 0.06, 64]} />
        <meshStandardMaterial color="#8ea6c4" metalness={0.8} roughness={0.24} />
      </mesh>
      {/* A slow emissive ring in the plinth, the one moving light in the scene. */}
      <mesh position={[0, -1.38, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[1.62, 1.78, 64]} />
        <meshBasicMaterial color="#3b82f6" transparent opacity={0.5 * glow} side={THREE.DoubleSide} />
      </mesh>

      {/* The three intelligence layers. Translucent, turning at different rates
          so the depth is legible as depth. */}
      <mesh ref={shellA}>
        <icosahedronGeometry args={[2.0, 1]} />
        <meshPhysicalMaterial
          color="#60a5fa"
          transparent
          opacity={0.34}
          roughness={0.15}
          metalness={0.1}
          transmission={0.35}
          thickness={0.6}
          emissive="#1d4ed8"
          emissiveIntensity={0.5 * glow}
        />
      </mesh>
      <mesh ref={shellB}>
        <icosahedronGeometry args={[1.58, 1]} />
        <meshPhysicalMaterial
          color="#93c5fd"
          transparent
          opacity={0.42}
          roughness={0.1}
          transmission={0.3}
          thickness={0.5}
          emissive="#2563eb"
          emissiveIntensity={0.62 * glow}
        />
      </mesh>
      <mesh ref={shellC}>
        <icosahedronGeometry args={[1.18, 0]} />
        <meshPhysicalMaterial
          color="#bfdbfe"
          transparent
          opacity={0.55}
          roughness={0.05}
          transmission={0.25}
          thickness={0.4}
          emissive="#3b82f6"
          emissiveIntensity={0.9 * glow}
        />
      </mesh>

      {/* Inner graph — what the core actually is. */}
      <group ref={graph}>
        <mesh>
          <sphereGeometry args={[0.5, 24, 24]} />
          <meshStandardMaterial
            color="#dbeafe"
            emissive="#60a5fa"
            emissiveIntensity={1.1 * glow}
            roughness={0.2}
          />
        </mesh>
        {nodes.map((p, i) => (
          <mesh key={i} position={p}>
            <sphereGeometry args={[0.045, 10, 10]} />
            <meshBasicMaterial color="#bfdbfe" transparent opacity={0.85} />
          </mesh>
        ))}
        {edges.map(([a, b], i) => (
          <line key={i}>
            <bufferGeometry
              attach="geometry"
              onUpdate={(g) => g.setFromPoints([a, b])}
            />
            <lineBasicMaterial color="#93c5fd" transparent opacity={0.28} />
          </line>
        ))}
      </group>
    </group>
  );
}

/* --------------------------------------------------------------- satellites */

/**
 * Industrial surround: a low abstract plant for the core to sit above.
 *
 * Deliberately schematic and small — the point is that Project 117 is the
 * intelligence layer over a physical facility, not that this is a refinery
 * drawing. The process map belongs on the Simulation page.
 */
function PlantSurround() {
  const sticks = useMemo(() => {
    // Deterministic layout, so the plant looks the same every load.
    const out: { x: number; z: number; h: number; r: number }[] = [];
    let seed = 117;
    const rnd = () => ((seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);
    for (let i = 0; i < 26; i++) {
      const a = (i / 26) * Math.PI * 2 + rnd() * 0.3;
      const rad = 8.6 + rnd() * 3.4;
      out.push({
        x: Math.cos(a) * rad,
        z: Math.sin(a) * rad,
        h: 0.35 + rnd() * 1.0,
        r: 0.07 + rnd() * 0.12,
      });
    }
    return out;
  }, []);

  return (
    <group position={[0, -1.9, 0]}>
      {/* Engineering grid floor. */}
      <gridHelper args={[40, 40, "#d3dce7", "#e4eaf1"]} position={[0, -0.01, 0]} />
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.02, 0]}>
        <planeGeometry args={[34, 34]} />
        <meshStandardMaterial color="#eef2f7" transparent opacity={0.5} />
      </mesh>
      {sticks.map((s, i) => (
        <group key={i} position={[s.x, 0, s.z]}>
          <mesh position={[0, s.h / 2, 0]}>
            <cylinderGeometry args={[s.r, s.r * 1.1, s.h, 10]} />
            <meshStandardMaterial color="#cdd7e2" metalness={0.35} roughness={0.7} />
          </mesh>
          {i % 5 === 0 && (
            <mesh position={[0, s.h + 0.12, 0]}>
              <sphereGeometry args={[s.r * 1.5, 10, 10]} />
              <meshStandardMaterial color="#d6e0ec" metalness={0.5} roughness={0.5} />
            </mesh>
          )}
        </group>
      ))}
    </group>
  );
}

function SatelliteNode({
  sat,
  reduced,
  onHover,
  active,
}: {
  sat: Satellite;
  reduced: boolean;
  onHover: (id: string | null) => void;
  active: string | null;
}) {
  const router = useRouter();
  const group = useRef<THREE.Group>(null);
  const [hovered, setHovered] = useState(false);
  const radius = RING_RADIUS[sat.ring];
  const tilt = RING_TILT[sat.ring];
  const period = RING_PERIOD[sat.ring];

  useFrame(({ clock }) => {
    if (!group.current) return;
    const t = reduced ? 0 : (clock.getElapsedTime() / period) * Math.PI * 2;
    const a = sat.phase + t;
    const x = Math.cos(a) * radius;
    const z = Math.sin(a) * radius;
    const y = z * tilt;
    group.current.position.set(x, y, z);
    // Depth reads from z: behind the core is quieter and smaller, in front is
    // larger. This is what makes the ring a plane rather than a circle.
    const depth = (z / radius + 1) / 2;
    const near = hovered ? 1 : 0;
    const s = 0.72 + depth * 0.42 + near * 0.22;
    group.current.scale.setScalar(s);
    const op = 0.5 + depth * 0.5;
    group.current.traverse((o) => {
      const m = (o as THREE.Mesh).material as THREE.Material | undefined;
      if (m && "opacity" in m) {
        (m as THREE.MeshBasicMaterial).opacity = active && active !== sat.id ? op * 0.35 : op;
      }
    });
  });

  const dim = active !== null && active !== sat.id;

  return (
    <group ref={group}>
      <mesh
        onPointerOver={(e: ThreeEvent<PointerEvent>) => {
          e.stopPropagation();
          setHovered(true);
          onHover(sat.id);
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={() => {
          setHovered(false);
          onHover(null);
          document.body.style.cursor = "default";
        }}
        onClick={() => router.push(sat.href)}
      >
        <boxGeometry args={[0.62, 0.16, 0.62]} />
        <meshStandardMaterial
          color={hovered ? "#dbeafe" : "#eef2f7"}
          emissive={sat.tone}
          emissiveIntensity={hovered ? 0.9 : 0.35}
          metalness={0.4}
          roughness={0.35}
          transparent
          opacity={dim ? 0.4 : 1}
        />
      </mesh>
      {/* A mast and a beacon so each satellite reads as an object, not a tile. */}
      <mesh position={[0, 0.22, 0]}>
        <cylinderGeometry args={[0.03, 0.03, 0.3, 8]} />
        <meshStandardMaterial color="#94a3b8" transparent opacity={dim ? 0.4 : 1} />
      </mesh>
      <mesh position={[0, 0.4, 0]}>
        <sphereGeometry args={[0.075, 12, 12]} />
        <meshStandardMaterial
          color={sat.tone}
          emissive={sat.tone}
          emissiveIntensity={hovered ? 2.2 : 1.1}
          transparent
          opacity={dim ? 0.4 : 1}
        />
      </mesh>
      <Html center distanceFactor={11} position={[0, -0.42, 0]} zIndexRange={[20, 0]}>
        <div className={`k3-label${hovered ? " is-hot" : ""}${dim ? " is-dim" : ""}`}>
          <b>{sat.label}</b>
          <span>
            {sat.count == null ? sat.countLabel : `${sat.count.toLocaleString()} ${sat.countLabel}`}
          </span>
          {hovered && <em>{sat.detail}</em>}
        </div>
      </Html>
    </group>
  );
}

/** The path from a satellite to the core, with a pulse travelling along it. */
function Link({ sat, reduced }: { sat: Satellite; reduced: boolean }) {
  const dot = useRef<THREE.Mesh>(null);
  const radius = RING_RADIUS[sat.ring];
  const tilt = RING_TILT[sat.ring];
  const period = RING_PERIOD[sat.ring];

  const curve = useMemo(() => {
    const a = Math.cos(sat.phase) * radius;
    const z = Math.sin(sat.phase) * radius;
    const y = z * tilt;
    return new THREE.QuadraticBezierCurve3(
      new THREE.Vector3(0, 0, 0),
      new THREE.Vector3(a * 0.5, y * 0.5 + 1.1, z * 0.5),
      new THREE.Vector3(a, y, z),
    );
  }, [sat.phase, sat.ring, radius, tilt]);

  useFrame(({ clock }) => {
    if (!dot.current) return;
    const t = reduced ? 0.5 : (clock.getElapsedTime() / period) * Math.PI * 2;
    const k = (Math.sin(t + sat.phase) + 1) / 2;
    const p = curve.getPoint(k);
    dot.current.position.copy(p);
    dot.current.visible = k > 0.05 && k < 0.95;
  });

  return (
    <group>
      <primitive
        object={useMemo(() => {
          const pts = curve.getPoints(28);
          const g = new THREE.BufferGeometry().setFromPoints(pts);
          return new THREE.Line(
            g,
            new THREE.LineBasicMaterial({ color: "#93c5fd", transparent: true, opacity: 0.3 }),
          );
        }, [curve])}
      />
      <mesh ref={dot}>
        <sphereGeometry args={[0.055, 10, 10]} />
        <meshBasicMaterial color="#3b82f6" />
      </mesh>
    </group>
  );
}

/* --------------------------------------------------------------------- scene */

export function KnowledgeCore3D({
  satellites,
  reduced = false,
  onOpenCore,
}: {
  satellites: Satellite[];
  reduced?: boolean;
  onOpenCore?: () => void;
}) {
  const [active, setActive] = useState<string | null>(null);
  const [coreHover, setCoreHover] = useState(false);

  return (
    <div className="k3" data-testid="knowledge-core-3d">
      <Canvas
        shadows
        dpr={[1, 1.75]}
        camera={{ position: [0, 3.2, 8.6], fov: 44 }}
        gl={{ antialias: true, alpha: true }}
        frameloop={reduced ? "demand" : "always"}
      >
        <color attach="background" args={["#f4f7fb"]} />
        <fog attach="fog" args={["#eef2f7", 13, 36]} />
        <ambientLight intensity={0.85} />
        <hemisphereLight args={["#ffffff", "#cbd5e1", 0.7]} />
        <directionalLight position={[6, 9, 6]} intensity={1.5} castShadow />
        <directionalLight position={[-7, 4, -5]} intensity={0.5} color="#bfdbfe" />
        <pointLight position={[0, 0.4, 0]} intensity={2.6} color="#60a5fa" distance={9} />

        <PlantSurround />

        <group
          onPointerOver={(e) => {
            e.stopPropagation();
            setCoreHover(true);
            document.body.style.cursor = "pointer";
          }}
          onPointerOut={() => {
            setCoreHover(false);
            document.body.style.cursor = "default";
          }}
          onClick={() => onOpenCore?.()}
        >
          <Core reduced={reduced} hovered={coreHover} />
        </group>

        {satellites.map((s) => (
          <Link key={`l-${s.id}`} sat={s} reduced={reduced} />
        ))}
        {satellites.map((s) => (
          <SatelliteNode key={s.id} sat={s} reduced={reduced} active={active} onHover={setActive} />
        ))}
      </Canvas>

      <div className="k3__badge" aria-hidden="true">
        <b>Knowledge Core</b>
        <span>documents · procedures · history · engineering data · AI agents</span>
      </div>
    </div>
  );
}
