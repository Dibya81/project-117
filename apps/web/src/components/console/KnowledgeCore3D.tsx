"use client";

/**
 * KnowledgeCore3D — the Home page's centre of gravity, as an actual 3D scene.
 *
 * Three things make the core read as an object rather than a picture:
 *
 *  1. **A transmissive glass shell.** `MeshTransmissionMaterial` bends what is
 *     behind it (the particle cloud and the plinth ring), with chromatic
 *     aberration on the silhouette and a thin-film iridescence so the highlights
 *     shift colour as it turns. The old version was three opaque
 *     `meshStandardMaterial` icosahedra — nothing was ever seen *through* it.
 *
 *  2. **An inner particle cloud.** 1,600 points on a Fibonacci shell, turning
 *     against the glass. This is what the refraction has to bend, which is why
 *     the material choice and the cloud only make sense together.
 *
 *  3. **A Fresnel rim.** A custom shader on a shell just outside the glass that
 *     is transparent face-on and bright at grazing angles — what gives a glass
 *     sphere its edge. Without it the orb dissolves into the background.
 *
 * The satellite nodes are `drei` `<Html>` elements anchored to real 3D positions
 * and wrapped in `<Float>`, so they bob with the scene rather than being a DOM
 * ring painted over it.
 *
 * Every figure shown is real application state. Nothing here invents a number.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Float, Html, MeshTransmissionMaterial } from "@react-three/drei";
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";
import * as THREE from "three";
import { useRouter } from "next/navigation";
import { Lucide } from "@/components/ui/LucideIcon";
import { SPRING, SPRING_OPTIONS } from "@/lib/ui/motion";
import type { IconName } from "@/components/ui/Icon";

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

/** The fixed composition. The camera is not a prop — it is the frame. */
const CAMERA_POS: [number, number, number] = [4.4, 4.0, 8.6];
const ORB_RADIUS = 1.5;
/** Seconds for one full revolution of the node ring. Slow: this is not a spinner. */
const RING_PERIOD = 210;
const RING_RADIUS = [3.15, 3.95];
const RING_DEPTH = [0.9, 1.5];

/* --------------------------------------------------------------- fresnel rim */

const RIM_VERT = /* glsl */ `
  varying vec3 vNormalW;
  varying vec3 vViewDir;
  void main() {
    vec4 world = modelMatrix * vec4(position, 1.0);
    vNormalW = normalize(mat3(modelMatrix) * normal);
    vViewDir = normalize(cameraPosition - world.xyz);
    gl_Position = projectionMatrix * viewMatrix * world;
  }
`;

/**
 * Grazing-angle falloff. `pow(1 - |N·V|, power)` is 0 facing the camera and 1 at
 * the silhouette, which is exactly where glass catches light.
 */
const RIM_FRAG = /* glsl */ `
  uniform vec3 uColorCool;
  uniform vec3 uColorWarm;
  uniform float uPower;
  uniform float uIntensity;
  uniform float uTime;
  varying vec3 vNormalW;
  varying vec3 vViewDir;
  void main() {
    float fres = pow(1.0 - abs(dot(normalize(vNormalW), normalize(vViewDir))), uPower);
    // A slow hue drift so the rim reads as living light rather than a decal.
    float mixv = 0.5 + 0.5 * sin(uTime * 0.35 + vNormalW.y * 3.14159);
    vec3 col = mix(uColorCool, uColorWarm, mixv);
    gl_FragColor = vec4(col, fres * uIntensity);
  }
`;

/* ------------------------------------------------------------ particle cloud */

/**
 * A Fibonacci-distributed shell of points.
 *
 * Even coverage with no clumping and no seams — a random shell reads as noise,
 * and a lat/long grid leaves visible poles as it rotates.
 */
function useParticleShell(count: number, inner: number, outer: number) {
  return useMemo(() => {
    const positions = new Float32Array(count * 3);
    const sizes = new Float32Array(count);
    const golden = Math.PI * (3 - Math.sqrt(5));
    for (let i = 0; i < count; i++) {
      const y = 1 - (i / (count - 1)) * 2;
      const r = Math.sqrt(Math.max(0, 1 - y * y));
      const th = golden * i;
      // Two shells, so some points read as nearer the glass than others.
      const radius = i % 3 === 0 ? outer : inner + (i % 7) * ((outer - inner) / 7);
      positions[i * 3] = Math.cos(th) * r * radius;
      positions[i * 3 + 1] = y * radius;
      positions[i * 3 + 2] = Math.sin(th) * r * radius;
      sizes[i] = 0.6 + (i % 5) * 0.22;
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geo.setAttribute("aSize", new THREE.BufferAttribute(sizes, 1));
    return geo;
  }, [count, inner, outer]);
}

const CLOUD_VERT = /* glsl */ `
  attribute float aSize;
  varying float vFade;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vFade = clamp(1.0 - (-mv.z - 1.0) / 3.0, 0.15, 1.0);
    gl_PointSize = aSize * (150.0 / -mv.z);
    gl_Position = projectionMatrix * mv;
  }
`;

/**
 * Normal alpha blending, deliberately.
 *
 * Additive blending is the reflex for a glowing cloud, but it only brightens —
 * against this light stage it renders as nothing at all. Saturated points with
 * real alpha read as suspended matter inside the glass, which is what the orb
 * needs to look like it contains something.
 */
const CLOUD_FRAG = /* glsl */ `
  uniform vec3 uColor;
  varying float vFade;
  void main() {
    // Round, soft-edged points: a square sprite betrays the technique.
    vec2 d = gl_PointCoord - vec2(0.5);
    float a = smoothstep(0.5, 0.08, length(d));
    if (a < 0.02) discard;
    gl_FragColor = vec4(uColor, a * vFade * 0.46);
  }
`;

function ParticleCloud({ reduced }: { reduced: boolean }) {
  const group = useRef<THREE.Points>(null);
  const geo = useParticleShell(1100, 0.55, 1.28);
  const uniforms = useMemo(() => ({ uColor: { value: new THREE.Color("#0369a1") } }), []);

  useFrame((_, dt) => {
    if (reduced || !group.current) return;
    group.current.rotation.y += dt * 0.16;
    group.current.rotation.x = Math.sin(performance.now() * 0.00008) * 0.24;
  });

  return (
    <points ref={group} geometry={geo}>
      <shaderMaterial
        uniforms={uniforms}
        vertexShader={CLOUD_VERT}
        fragmentShader={CLOUD_FRAG}
        transparent
        depthWrite={false}
      />
    </points>
  );
}

/* ------------------------------------------------------------------- the orb */

function GlassOrb({ reduced, hovered }: { reduced: boolean; hovered: boolean }) {
  const rim = useRef<THREE.Mesh>(null);
  const kernel = useRef<THREE.Mesh>(null);

  const rimUniforms = useMemo(
    () => ({
      uColorCool: { value: new THREE.Color("#22d3ee") },
      uColorWarm: { value: new THREE.Color("#818cf8") },
      uPower: { value: 2.4 },
      uIntensity: { value: 0.95 },
      uTime: { value: 0 },
    }),
    [],
  );

  useFrame((state, dt) => {
    if (reduced) return;
    rimUniforms.uTime.value = state.clock.elapsedTime;
    if (kernel.current) kernel.current.rotation.y += dt * (hovered ? 0.5 : 0.22);
    if (rim.current) {
      const s = 1 + Math.sin(state.clock.elapsedTime * 0.6) * 0.012;
      rim.current.scale.setScalar(hovered ? s * 1.03 : s);
    }
  });

  /**
   * A cheap two-tone environment. Without one, a transmissive material has
   * almost nothing to refract when the page behind it is flat, and the orb goes
   * milky. Ice above, deep blue below.
   */
  const envTexture = useMemo(() => {
    const c = document.createElement("canvas");
    c.width = 4;
    c.height = 64;
    const ctx = c.getContext("2d");
    if (!ctx) return null;
    const g = ctx.createLinearGradient(0, 0, 0, 64);
    g.addColorStop(0, "#f8fbff");
    g.addColorStop(0.45, "#bfdbfe");
    g.addColorStop(1, "#1e3a8a");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 4, 64);
    const t = new THREE.CanvasTexture(c);
    t.mapping = THREE.EquirectangularReflectionMapping;
    t.colorSpace = THREE.SRGBColorSpace;
    return t;
  }, []);

  return (
    <group>
      {/* Machined plinth — the one moving light in the scene. */}
      <mesh position={[0, -1.98, 0]} receiveShadow>
        <cylinderGeometry args={[2.02, 2.18, 0.32, 64]} />
        <meshStandardMaterial
          color="#e8eef7"
          metalness={0.35}
          roughness={0.38}
          envMap={envTexture ?? undefined}
          envMapIntensity={1.4}
        />
      </mesh>
      <mesh position={[0, -1.8, 0]}>
        <cylinderGeometry args={[1.84, 1.84, 0.05, 64]} />
        <meshStandardMaterial
          color="#b6c6dc"
          metalness={0.55}
          roughness={0.24}
          envMap={envTexture ?? undefined}
          envMapIntensity={1.6}
        />
      </mesh>
      <mesh position={[0, -1.76, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[1.58, 1.74, 64]} />
        <meshBasicMaterial
          color="#22d3ee"
          transparent
          opacity={hovered ? 0.75 : 0.45}
          side={THREE.DoubleSide}
        />
      </mesh>

      <Float
        speed={reduced ? 0 : 1.1}
        rotationIntensity={reduced ? 0 : 0.22}
        floatIntensity={reduced ? 0 : 0.5}
        floatingRange={[-0.06, 0.06]}
      >
        <group position={[0, 0.12, 0]}>
          {/* Inner cloud — the thing the glass is seen through. */}
          <ParticleCloud reduced={reduced} />

          {/* Transmissive shell. */}
          <mesh castShadow>
            {/* 96×96 on a sphere this smooth was ~9k vertices carrying no
                silhouette detail; 64×64 is the same edge for a third of them. */}
            <sphereGeometry args={[ORB_RADIUS, 64, 64]} />
            <MeshTransmissionMaterial
              transmission={1}
              // Thickness drives how much the attenuation colour tints the
              // interior. At 1.55 the orb read as a solid blue marble; this is
              // thin enough to stay glass while still tinting the edges.
              thickness={0.82}
              roughness={0.045}
              ior={1.44}
              chromaticAberration={0.5}
              anisotropy={0.28}
              distortion={0.22}
              distortionScale={0.35}
              temporalDistortion={reduced ? 0 : 0.08}
              iridescence={1}
              iridescenceIOR={1.9}
              iridescenceThicknessRange={[120, 520]}
              clearcoat={1}
              clearcoatRoughness={0.06}
              attenuationDistance={6.5}
              attenuationColor="#f0f9ff"
              color="#f2f9ff"
              // No `background`: that prop REPLACES what is refracted with a flat
              // colour, which is what made the interior milky and hid the
              // particle cloud. Without it the material samples the real scene,
              // so the cloud and the plinth ring are what shows through.
              envMap={envTexture ?? undefined}
              envMapIntensity={1.1}
              // Left at 6 deliberately. Lowering it to 2 measured no improvement
              // in frame cost (the main-thread block on this route is the chunk's
              // own parse, not the transmissive passes), and at this roughness the
              // multi-sample blur is part of how the glass reads. A visual change
              // that buys nothing measurable is not worth making.
              samples={6}
              // 512² made the transmissive pass the most expensive thing on the
              // page and the driver logged "GPU stall due to ReadPixels"; 256² is
              // visually indistinguishable under this much refraction.
              resolution={256}
            />
          </mesh>

          {/* Fresnel rim — what gives the sphere its edge. */}
          <mesh ref={rim}>
            <sphereGeometry args={[ORB_RADIUS * 1.035, 64, 64]} />
            <shaderMaterial
              uniforms={rimUniforms}
              vertexShader={RIM_VERT}
              fragmentShader={RIM_FRAG}
              transparent
              depthWrite={false}
              blending={THREE.AdditiveBlending}
            />
          </mesh>

          {/* The kernel: one solid thing inside, so the eye has a centre. */}
          <mesh ref={kernel}>
            <icosahedronGeometry args={[0.3, 1]} />
            <meshBasicMaterial color="#e0f2fe" />
          </mesh>
        </group>
      </Float>

      {/* Nameplate on the plinth, inside the scene so it belongs to the object.
          Positioned on the world Y axis with NO z offset, deliberately: the
          camera looks in from (4.4, 4.0, 8.6), so its right vector is
          normalise(-8.6, 0, 4.4) — a zero y-component, which means every point
          on the Y axis projects to the same screen column. Pushing the plate
          toward the camera (z = 1.15, as it was) therefore slid it sideways off
          the orb's centre line. With z = 0 it sits exactly under the orb, and
          y = -1.94 puts it on the plinth's front band rather than floating over
          the top disc. */}
      <Html center position={[0, -1.94, 0]} zIndexRange={[10, 0]}>
        <div className="k3-plate" aria-hidden="true">
          <b>Knowledge Core</b>
          <span>documents · procedures · history · engineering data</span>
        </div>
      </Html>
    </group>
  );
}

/* ------------------------------------------------------------------ the ring */

/**
 * One orbiting system card.
 *
 * `Html` projects a real 3D position into the DOM, so the card sits where its
 * point in space is. Wrapped in `Float` it drifts, and the depth offset along the
 * view axis drives its scale, opacity and stacking — which is what turns a flat
 * circle of cards into nodes passing in front of and behind the core.
 */
function NodeCard({
  sat,
  position,
  depth,
  dim,
  hot,
  onEnter,
  onLeave,
  onClick,
}: {
  sat: Satellite;
  position: [number, number, number];
  depth: number;
  dim: boolean;
  /** This card is the one under the pointer — its label is revealed. */
  hot: boolean;
  onEnter: () => void;
  onLeave: () => void;
  onClick: () => void;
}) {
  // Spring tilt: the pointer's offset from the card centre drives rotateX/Y.
  const mx = useMotionValue(0);
  const my = useMotionValue(0);
  const rx = useSpring(useTransform(my, [-0.5, 0.5], [9, -9]), SPRING_OPTIONS.micro);
  const ry = useSpring(useTransform(mx, [-0.5, 0.5], [-11, 11]), SPRING_OPTIONS.micro);
  const scale = 0.9 + depth * 0.14;
  /**
   * Depth is a cue, not a fade-out. At 0.62 the far cards read as disabled
   * rather than as further away, and the dim factor used to multiply on top of
   * that (0.42 × 0.34) leaving the un-hovered cards almost invisible. Opacity is
   * computed in exactly one place now, and its floor stays legible.
   */
  const opacity = dim ? 0.5 : 0.84 + depth * 0.16;

  return (
    <Float speed={1.35} rotationIntensity={0.12} floatIntensity={0.42} floatingRange={[-0.05, 0.05]}>
      <Html position={position} center zIndexRange={[30, 10]}>
        <motion.button
          type="button"
          className={`k3-card${dim ? " is-dim" : ""}${hot ? " is-hot" : ""}`}
          data-satellite={sat.id}
          style={{
            rotateX: rx,
            rotateY: ry,
            scale,
            // Without perspective the rotateX/Y read as a flat skew.
            transformPerspective: 700,
            opacity,
            // Stacking across cards is `Html`'s zIndexRange above, which is
            // derived from the same 3D distance — setting it here too would
            // fight it inside a different stacking context.
            transformStyle: "preserve-3d",
          }}
          onMouseMove={(e) => {
            const r = e.currentTarget.getBoundingClientRect();
            mx.set((e.clientX - r.left) / r.width - 0.5);
            my.set((e.clientY - r.top) / r.height - 0.5);
          }}
          onMouseEnter={onEnter}
          onMouseLeave={() => {
            mx.set(0);
            my.set(0);
            onLeave();
          }}
          onClick={onClick}
          aria-label={`${sat.label} — ${sat.descriptor}`}
          whileHover={{ scale: scale * 1.04 }}
          transition={SPRING.micro}
        >
          <span className="k3-card__tile" style={{ background: sat.tone }}>
            <Lucide name={sat.icon} size={20} strokeWidth={1.6} />
          </span>
          {/* The label is the thing the operator came for, so it is never
              truncated: one line, full text, with the descriptor and the live
              figure beneath it. The reveal is a max-width slide, so the body is
              always exactly as wide as its content. */}
          <span className="k3-card__body">
            <b>{sat.label}</b>
            <span className="k3-card__sub">{sat.descriptor}</span>
            {sat.count != null && (
              <em className="k3-card__count">
                {sat.count.toLocaleString()} {sat.countLabel}
              </em>
            )}
          </span>
        </motion.button>
      </Html>
    </Float>
  );
}

/**
 * The node ring, built in the camera's own plane.
 *
 * Positions come from the camera's right/up basis rather than the world XY
 * plane: a world-plane ring is foreshortened by the three-quarter camera and
 * clusters at the edges. Building it in the view plane keeps the composition
 * symmetric so every card stays in frame at every rotation, while the depth
 * offset still sends them genuinely in front of and behind the orb.
 */
function NodeRing({ satellites, reduced }: { satellites: Satellite[]; reduced: boolean }) {
  const router = useRouter();
  const [hot, setHot] = useState<string | null>(null);
  const [t, setT] = useState(0);
  const { viewport } = useThree();

  const basis = useMemo(() => {
    const eye = new THREE.Vector3(...CAMERA_POS);
    const forward = eye.clone().normalize(); // camera → origin
    const right = new THREE.Vector3().crossVectors(new THREE.Vector3(0, 1, 0), forward).normalize();
    const up = new THREE.Vector3().crossVectors(forward, right).normalize();
    return { forward, right, up };
  }, []);

  useEffect(() => {
    if (reduced) return;
    let raf = 0;
    const t0 = performance.now();
    const tick = (now: number) => {
      setT(((now - t0) / 1000 / RING_PERIOD) * Math.PI * 2);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [reduced]);

  const placed = useMemo(() => {
    // Shrink the ring on narrow viewports so cards never leave the canvas.
    const fit = Math.min(1, Math.max(0.62, viewport.width / 12.5));
    return satellites.map((s, i) => {
      const a = -Math.PI / 2 + (i / satellites.length) * Math.PI * 2 + t + s.phase * 0.08;
      const radius = RING_RADIUS[s.ring] * fit;
      const depth = Math.sin(a) * RING_DEPTH[s.ring];
      const p = new THREE.Vector3()
        .addScaledVector(basis.right, Math.cos(a) * radius)
        .addScaledVector(basis.up, Math.sin(a) * radius * 0.72)
        .addScaledVector(basis.forward, -depth);
      const d = (depth / RING_DEPTH[1] + 1) / 2; // near = 1
      return { sat: s, position: [p.x, p.y, p.z] as [number, number, number], depth: d };
    });
  }, [satellites, t, basis, viewport.width]);

  return (
    <>
      {placed.map(({ sat, position, depth }) => (
        <NodeCard
          key={sat.id}
          sat={sat}
          position={position}
          depth={depth}
          dim={hot !== null && hot !== sat.id}
          hot={hot === sat.id}
          onEnter={() => setHot(sat.id)}
          onLeave={() => setHot(null)}
          onClick={() => router.push(sat.href)}
        />
      ))}
    </>
  );
}

/* -------------------------------------------------------------------- scene */

export function KnowledgeCore3D({
  satellites,
  reduced = false,
  onOpenCore,
}: {
  satellites: Satellite[];
  reduced?: boolean;
  onOpenCore?: () => void;
}) {
  const [coreHover, setCoreHover] = useState(false);
  /**
   * Whether the scene should be rendering.
   *
   * A transmissive material with its own render target plus a 1,600-point cloud
   * is expensive *per frame*, and the home page is a console page an operator may
   * leave open in a background tab or scroll past. Rendering it continuously in
   * either case spends the main thread on pixels nobody is looking at, so the
   * loop drops to `demand` while the canvas is off screen or the tab is hidden.
   * Nothing about the scene changes; it simply stops drawing.
   */
  const [onScreen, setOnScreen] = useState(true);
  const hostRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = hostRef.current;
    let visible = document.visibilityState !== "hidden";
    const evaluate = () => setOnScreen(visible && inView);
    let inView = true;
    const io =
      el && typeof IntersectionObserver !== "undefined"
        ? new IntersectionObserver(
            (entries) => {
              inView = entries.some((e) => e.isIntersecting);
              evaluate();
            },
            { rootMargin: "120px" },
          )
        : null;
    if (io && el) io.observe(el);
    const onVis = () => {
      visible = document.visibilityState !== "hidden";
      evaluate();
    };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      io?.disconnect();
      document.removeEventListener("visibilitychange", onVis);
    };
  }, []);

  return (
    <div className="k3" data-testid="knowledge-core-3d" ref={hostRef}>
      {/* Animated gradient mesh behind the scene: the ice-blue field the orb sits
          in, so the glass has something with depth to refract. */}
      <div className="k3-mesh" aria-hidden="true">
        <span className="k3-mesh__a" />
        <span className="k3-mesh__b" />
        <span className="k3-mesh__c" />
      </div>

      <Canvas
        shadows
        dpr={[1, 1.75]}
        camera={{ position: CAMERA_POS, fov: 46 }}
        gl={{ antialias: true, alpha: true }}
        frameloop={reduced || !onScreen ? "demand" : "always"}
        onCreated={({ camera }) => camera.lookAt(0, 0.05, 0)}
      >
        <ambientLight intensity={0.9} />
        <hemisphereLight args={["#ffffff", "#cbd5e1", 0.8]} />
        <directionalLight position={[6, 9, 6]} intensity={1.6} castShadow />
        <directionalLight position={[-7, 4, -5]} intensity={0.6} color="#c7d2fe" />
        <pointLight position={[0, 0.5, 0]} intensity={2.2} color="#67e8f9" distance={9} />

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
          <GlassOrb reduced={reduced} hovered={coreHover} />
        </group>

        <NodeRing satellites={satellites} reduced={reduced} />
      </Canvas>
    </div>
  );
}
