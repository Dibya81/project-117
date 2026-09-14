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

import { useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import * as THREE from "three";
import { useRouter } from "next/navigation";
import { Icon, type IconName } from "@/components/ui/Icon";

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
  /** Icon shown on the tile, as the reference shows for each system. */
  icon: IconName;
  /** The one-line descriptor shown on hover, as the reference labels it. */
  descriptor: string;
}

const RING_RADIUS = [5.2, 7.0];
const RING_TILT = [0.34, 0.24];
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
      <mesh ref={shellA} castShadow>
        <icosahedronGeometry args={[2.0, 1]} />
        <meshStandardMaterial
          color="#2f6fe0"
          transparent
          opacity={0.34}
          roughness={0.12}
          metalness={0.25}
          emissive="#1d4ed8"
          emissiveIntensity={0.55 * glow}
          flatShading
        />
      </mesh>
      <mesh ref={shellB}>
        <icosahedronGeometry args={[1.58, 1]} />
        <meshStandardMaterial
          color="#5b9bf0"
          transparent
          opacity={0.5}
          roughness={0.08}
          metalness={0.2}
          emissive="#2563eb"
          emissiveIntensity={0.8 * glow}
          flatShading
        />
      </mesh>
      <mesh ref={shellC}>
        <icosahedronGeometry args={[1.18, 0]} />
        <meshStandardMaterial
          color="#9cc6f8"
          transparent
          opacity={0.72}
          roughness={0.06}
          metalness={0.15}
          emissive="#3b82f6"
          emissiveIntensity={1.2 * glow}
          flatShading
        />
      </mesh>

      {/* Inner graph — what the core actually is. */}
      <group ref={graph}>
        <mesh>
          <sphereGeometry args={[0.62, 28, 28]} />
          <meshStandardMaterial
            color="#dbeafe"
            emissive="#60a5fa"
            emissiveIntensity={2.8 * glow}
            roughness={0.2}
          />
        </mesh>
        {nodes.map((p, i) => (
          <mesh key={i} position={p}>
            <sphereGeometry args={[0.07, 12, 12]} />
            <meshBasicMaterial color="#e0f2fe" transparent opacity={1} />
          </mesh>
        ))}
        {edges.map(([a, b], i) => (
          <line key={i}>
            <bufferGeometry
              attach="geometry"
              onUpdate={(g) => g.setFromPoints([a, b])}
            />
            <lineBasicMaterial color="#bfdbfe" transparent opacity={0.9} />
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
/**
 * The eight systems as a balanced ring of cards around the 3D core.
 *
 * Positions come from an ellipse, not from projecting a tilted orbit through
 * the camera. That projection clustered the cards and clipped some at the frame
 * edge; a DOM ring is symmetric by construction and every card stays in frame.
 * The orbit still reads as an orbit — the ring slowly rotates, a card at the
 * back is dimmer and smaller, one at the front is larger and on top — but the
 * geometry is legible.
 */
function SatelliteRing({
  satellites,
  reduced,
}: {
  satellites: Satellite[];
  reduced?: boolean;
}) {
  const router = useRouter();
  const wrap = useRef<HTMLDivElement>(null);
  const [hot, setHot] = useState<string | null>(null);

  /**
   * Eight logos, evenly spaced on one ellipse, travelling around the core.
   *
   * The spacing is what keeps it composed: a constant 45° apart, so the ring
   * stays symmetric at every moment of the rotation. The earlier version put
   * two rings at uneven phases, which is why it looked scattered rather than
   * orbiting — the arrangement changed shape as it turned.
   */
  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    let raf = 0;
    let t = 0;
    let last = performance.now();
    const place = (offset: number) => {
      const w = el.clientWidth;
      const h = el.clientHeight;
      const rx = w * 0.40;
      const ry = h * 0.335;
      satellites.forEach((sat, i) => {
        // Constant angular step: one logo per equal slice of the revolution, so
        // the ring turns at a steady rate like an orbit rather than speeding up
        // and slowing down as it crosses the ellipse.
        const a = -Math.PI / 2 + (i / satellites.length) * Math.PI * 2 + offset;
        const node = el.querySelector<HTMLElement>(`[data-satellite="${sat.id}"]`);
        if (!node) return;
        node.style.setProperty("--sx", `${(Math.cos(a) * rx).toFixed(1)}px`);
        node.style.setProperty("--sy", `${(Math.sin(a) * ry).toFixed(1)}px`);
      });
    };
    const tick = (now: number) => {
      // A slow drift: a full circuit takes about two minutes, so it reads as a
      // mechanism running rather than a loading spinner.
      if (!reduced) t += (now - last) * 0.00005;
      last = now;
      place(t);
      raf = requestAnimationFrame(tick);
    };
    place(0);
    const ro = new ResizeObserver(() => place(t));
    ro.observe(el);
    if (!reduced) raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [satellites, reduced]);

  return (
    <div className="k3-ring" ref={wrap}>
      {satellites.map((s) => {
        const dim = hot !== null && hot !== s.id;
        return (
          <button
            key={s.id}
            type="button"
            className={`k3-card${dim ? " is-dim" : ""}${hot === s.id ? " is-hot" : ""}`}
            data-satellite={s.id}
            onMouseEnter={() => setHot(s.id)}
            onMouseLeave={() => setHot(null)}
            onClick={() => router.push(s.href)}
            aria-label={`${s.label} — ${s.descriptor}`}
          >
            <span className="k3-card__tile" style={{ background: s.tone }}>
              <Icon name={s.icon} size={21} strokeWidth={1.5} />
            </span>
            <span className="k3-card__body">
              <b>{s.label}</b>
              <span>{s.descriptor}</span>
            </span>
          </button>
        );
      })}
    </div>
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
        camera={{ position: [4.4, 4.0, 8.6], fov: 46 }}
        gl={{ antialias: true, alpha: true }}
        frameloop={reduced ? "demand" : "always"}
        onCreated={({ camera }) => {
          // Elevated three-quarter view, locked on the core. One fixed frame —
          // the camera is not a prop, it is the composition.
          camera.lookAt(0, 0.05, 0);
        }}
      >
        <color attach="background" args={["#f4f7fb"]} />
        <fog attach="fog" args={["#eef2f7", 13, 36]} />
        <ambientLight intensity={0.85} />
        <hemisphereLight args={["#ffffff", "#cbd5e1", 0.7]} />
        <directionalLight position={[6, 9, 6]} intensity={1.5} castShadow />
        <directionalLight position={[-7, 4, -5]} intensity={0.5} color="#bfdbfe" />
        <pointLight position={[0, 0.4, 0]} intensity={2.6} color="#60a5fa" distance={9} />

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

        {/* The nameplate sits on the front of the plinth, inside the scene, so
            it belongs to the object instead of floating beneath it. */}
        <Html center position={[0, -0.92, 0]} zIndexRange={[10, 0]}>
          <div className="k3-plate" aria-hidden="true">
            <b>Knowledge Core</b>
            <span>documents · procedures · history · engineering data</span>
          </div>
        </Html>
      </Canvas>

      {/* The systems are laid out as a balanced ring of DOM cards around the
          core, not as 3D objects projected through a tilted camera (which
          clustered them and clipped some). One rAF loop drives the orbit; the
          positions are computed from a clean ellipse so the composition is
          symmetric and nothing leaves the frame. */}
      <SatelliteRing satellites={satellites} reduced={reduced} />

    </div>
  );
}
