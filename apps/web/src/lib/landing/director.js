/**
 * Landing director — the single rAF loop that owns the whole page.
 * Scroll progress is lerped into a smooth value, then applied to the film
 * canvas (Section 1) via a `film` adapter, the three procedural engines, and
 * every DOM beat ([data-beat="a,b"]), with special handlers for the morph
 * word, workflow rail, sandbox, self-drawing graph, artifact assembly,
 * verification and the finale.
 */
import { clamp01, easeInOutCubic, easeOutCubic, ramp } from "./easing.js";
import { InfoField } from "./infoField.js";
import { SecurityScene } from "./security.js";
import { NetworkScene } from "./network.js";

/**
 * The film occupies the first window of the page only (the canvas fades out by
 * WINDOWS.filmFade[1]). FILM_END normalises scroll into that window so the
 * whole 120-frame sequence plays 0 → 119 across it instead of stalling while
 * the procedural sections take over.
 */
export const FILM_END = 0.68;
export const WINDOWS = {
  film: [0, 0.62],       // canvas opacity stays full until 0.62 (covers S1 + most of S2)
  filmFade: [0.62, 0.7], // then gently exits by 0.70 so S3 has clean air
  info: [0.325, 0.535],
  security: [0.515, 0.68],
  network: [0.655, 0.815],
};
export const CHAPTER_WINDOWS = [
  [0.0, 0.62],  // S1: full-frame film (photos 0–62 across the photo cut story)
  [0.62, 0.7],  // film exit
  [0.7, 0.8],   // S2: system section (procedural / info beats)
  [0.8, 1.0],   // S3: action / finale
];

/* ---------------- special beat handlers ---------------- */

function applyMorph(el, t) {
  const words = el.querySelectorAll(".p117-morphword");
  const n = words.length;
  if (!n) return;
  const phase = t * (n - 1) + 0.0001;
  words.forEach((word, k) => {
    const d = phase - k;
    const letters = word.children;
    for (let i = 0; i < letters.length; i++) {
      const lag = i * 0.045;
      const dl = Math.max(-1, Math.min(1, d * (1.6 + lag)));
      const o = Math.max(0, 1 - Math.abs(dl) * 1.35);
      const letter = letters[i];
      letter.style.opacity = o.toFixed(3);
      letter.style.transform = `translateY(${(-dl * 26 * (0.75 + i * 0.06)).toFixed(1)}px)`;
      letter.style.filter = Math.abs(dl) > 0.15 ? `blur(${(Math.abs(dl) * 4).toFixed(1)}px)` : "none";
    }
  });
}

function applySteps(el, t) {
  const steps = el.querySelectorAll(".p117-step");
  steps.forEach((step, k) => {
    const s = clamp01(t * 4.6 - k * 1.08);
    const e = easeOutCubic(s);
    step.style.opacity = (0.18 + 0.82 * e).toFixed(3);
    step.style.transform = `translateX(${((1 - e) * 16).toFixed(1)}px)`;
    const dot = step.querySelector("i");
    if (dot) dot.style.background = s > 0.6 ? "var(--cyan)" : "var(--ink-3)";
  });
}

function applyAgents(el, t) {
  const nodes = el.querySelectorAll(".p117-agentnode");
  const n = nodes.length;
  nodes.forEach((node, k) => {
    const s = clamp01(t * (n + 0.6) - k * 0.95);
    node.style.opacity = (0.2 + 0.8 * easeOutCubic(s)).toFixed(3);
    node.style.color = s > 0.55 ? "var(--cyan)" : "var(--ink-3)";
  });
  el.style.setProperty("--dotx", `${(clamp01(t * 1.15) * 100).toFixed(1)}%`);
}

function applySandbox(el, t) {
  const code = el.querySelector(".p117-code");
  const frame = el.querySelector(".p117-sandbox");
  const badges = el.querySelectorAll(".p117-badge");
  const slide = easeInOutCubic(ramp(t, 0.02, 0.42));
  if (code) {
    code.style.transform = `translate(${((1 - slide) * -130).toFixed(1)}%, ${((1 - slide) * -40).toFixed(1)}%)`;
    code.style.opacity = (0.15 + slide * 0.85).toFixed(3);
  }
  if (frame) {
    const glow = ramp(t, 0.38, 0.6);
    frame.style.borderColor = `rgba(70,184,232,${(0.25 + glow * 0.55).toFixed(3)})`;
    frame.style.boxShadow = glow > 0.02 ? `0 0 ${(glow * 34).toFixed(0)}px rgba(70,184,232,${(glow * 0.14).toFixed(3)})` : "none";
  }
  badges.forEach((b, i) => {
    b.style.opacity = ramp(t, 0.55 + i * 0.12, 0.68 + i * 0.12).toFixed(3);
  });
}

function applyGraph(el, t) {
  const path = el.querySelector("[data-graph-line]");
  const dot = el.querySelector("[data-graph-dot]");
  const caption = el.querySelector(".p117-graphcaption");
  const draw = easeInOutCubic(ramp(t, 0.05, 0.72));
  if (path) path.style.strokeDashoffset = (1 - draw).toFixed(4);
  if (dot) dot.style.opacity = ramp(t, 0.68, 0.78).toFixed(3);
  if (caption) caption.style.opacity = ramp(t, 0.6, 0.8).toFixed(3);
}

function applyArtifacts(el, t) {
  const docs = el.querySelectorAll(".p117-doc");
  docs.forEach((doc, k) => {
    const assemble = ramp(t, 0.04 + k * 0.11, 0.2 + k * 0.11);
    const collapse = easeInOutCubic(ramp(t, 0.8, 0.99));
    const dirX = (k % 2 === 0 ? -1 : 1) * (k < 2 ? 1 : 0.6);
    const dirY = k < 2 ? -0.5 : 0.6;
    doc.style.opacity = (assemble * (1 - collapse)).toFixed(3);
    doc.style.transform =
      `translate(${(dirX * collapse * -46).toFixed(1)}%, ${(dirY * collapse * -46).toFixed(1)}%)` +
      ` scale(${((0.6 + assemble * 0.4) * (1 - collapse * 0.75)).toFixed(3)})`;
    const parts = doc.children;
    for (let j = 0; j < parts.length; j++) {
      const c = easeOutCubic(clamp01(assemble * 1.6 - j * 0.14));
      parts[j].style.opacity = c.toFixed(3);
      parts[j].style.transform = `translateY(${((1 - c) * 9).toFixed(1)}px)`;
    }
  });
}

function applyVerify(el, t) {
  const q = (sel) => el.querySelector(sel);
  const claim = q(".p117-claim");
  const source = q(".p117-source");
  const link = q(".p117-link");
  const verdict = q(".p117-verdict");
  const checks = el.querySelectorAll(".p117-check");
  if (claim) claim.style.opacity = ramp(t, 0.0, 0.14).toFixed(3);
  if (source) source.style.opacity = ramp(t, 0.18, 0.32).toFixed(3);
  if (link) link.style.transform = `scaleX(${easeInOutCubic(ramp(t, 0.34, 0.52)).toFixed(3)})`;
  if (verdict) {
    const v = ramp(t, 0.55, 0.7);
    verdict.style.opacity = v.toFixed(3);
    verdict.style.transform = `scale(${(0.85 + easeOutCubic(v) * 0.15).toFixed(3)})`;
  }
  checks.forEach((c, i) => {
    c.style.opacity = ramp(t, 0.68 + i * 0.09, 0.78 + i * 0.09).toFixed(3);
  });
}

function applyFinal(el, t) {
  const ring = el.querySelectorAll(".p117-ringitem");
  const stmt = el.querySelector(".p117-finalstmt");
  const brand = el.querySelector(".p117-finalbrand");
  const cta = el.querySelector(".p117-cta");
  ring.forEach((r, i) => {
    r.style.opacity = ramp(t, 0.05 + i * 0.05, 0.2 + i * 0.05).toFixed(3);
  });
  if (stmt) stmt.style.opacity = ramp(t, 0.3, 0.48).toFixed(3);
  if (brand) brand.style.opacity = ramp(t, 0.55, 0.7).toFixed(3);
  if (cta) {
    cta.style.opacity = ramp(t, 0.7, 0.85).toFixed(3);
    cta.classList.toggle("is-live", t > 0.8);
  }
}

const SPECIAL = {
  morph: applyMorph,
  s5steps: applySteps,
  s5agents: applyAgents,
  s5sandbox: applySandbox,
  s5graph: applyGraph,
  s5artifacts: applyArtifacts,
  s5verify: applyVerify,
  s5final: applyFinal,
};

/* ---------------- director ---------------- */

export function createDirector({ track, stage, film, onChapter }) {
  const canvases = {
    info: stage.querySelector('[data-fx="info"]'),
    security: stage.querySelector('[data-fx="security"]'),
    network: stage.querySelector('[data-fx="network"]'),
  };
  const engines = {
    info: canvases.info ? new InfoField(canvases.info) : null,
    security: canvases.security ? new SecurityScene(canvases.security) : null,
    network: canvases.network ? new NetworkScene(canvases.network) : null,
  };
  const dim = stage.querySelector("[data-dim]");
  const root = track.parentElement ?? stage.parentElement ?? document;
  const bar = root.querySelector("[data-progress]");
  const hint = root.querySelector("[data-hint]");

  const beats = Array.from(stage.querySelectorAll("[data-beat]")).map((el) => {
    const [a, b] = el.dataset.beat.split(",").map(Number);
    return { el, a, b, id: el.dataset.beatId || null, lastHidden: false };
  });

  const mouse = { x: 0, y: 0, tx: 0, ty: 0 };
  const onPointer = (e) => {
    mouse.tx = (e.clientX / window.innerWidth - 0.5) * 2;
    mouse.ty = (e.clientY / window.innerHeight - 0.5) * 2;
  };
  window.addEventListener("pointermove", onPointer, { passive: true });

  let raf = 0;
  let smooth = -1;
  let time = 0;
  let lastTs = 0;
  let chapter = -1;
  const wasActive = { info: false, security: false, network: false };

  const readProgress = () => {
    const total = track.offsetHeight - window.innerHeight;
    return total <= 0 ? 0 : clamp01(window.scrollY / total);
  };

  const local = (p, win) => clamp01((p - win[0]) / (win[1] - win[0]));

  const applyEngine = (key, p) => {
    const engine = engines[key];
    const canvas = canvases[key];
    if (!engine || !canvas) return;
    const win = WINDOWS[key];
    const active = p > win[0] - 0.01 && p < win[1] + 0.01;
    if (active) {
      engine.draw(local(p, win), time, mouse);
      wasActive[key] = true;
    } else if (wasActive[key]) {
      const ctx = canvas.getContext("2d");
      if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
      wasActive[key] = false;
    }
  };

  const tick = (ts) => {
    raf = requestAnimationFrame(tick);
    if (document.hidden) {
      lastTs = ts;
      return;
    }
    const dt = Math.min(0.05, (ts - lastTs) / 1000 || 0.016);
    lastTs = ts;
    time += dt;

    const raw = readProgress();
    smooth = smooth < 0 ? raw : smooth + (raw - smooth) * 0.13;
    mouse.x += (mouse.tx - mouse.x) * 0.06;
    mouse.y += (mouse.ty - mouse.y) * 0.06;

    const filmP = clamp01(smooth / FILM_END); // FILM_END=1.0 → progress = smooth everywhere
    film.draw(filmP);
    if (film.canvas) {
      const win = WINDOWS.film;
      const inFilm = smooth < win[1] + 0.04;
      if (inFilm) {
        // Full opacity until filmFade start, then gentle egress so S2 reads clean.
        const fadeP = clamp01((smooth - win[0]) / (WINDOWS.filmFade[1] - win[0]));
        const exit = WINDOWS.filmFade[1] <= win[0] ? 0 : Math.max(0, easeOutCubic(fadeP - 0.78) * 1.02);
        film.canvas.style.opacity = (1 - exit).toFixed(3);
        film.canvas.style.transform = `scale(${(1 + exit * 0.07).toFixed(4)})`;
      } else {
        film.canvas.style.opacity = "0";
        film.canvas.style.transform = `scale(1)`;
      }
    }

    if (dim) {
      dim.style.opacity = (ramp(smooth, 0.29, 0.34) * 0.6 * (1 - ramp(smooth, 0.35, 0.38))).toFixed(3);
    }

    applyEngine("info", smooth);
    applyEngine("security", smooth);
    applyEngine("network", smooth);

    for (const beat of beats) {
      const { el, a, b, id } = beat;
      if (smooth < a - 0.02 || smooth > b + 0.02) {
        if (!beat.lastHidden) {
          el.style.opacity = "0";
          el.style.visibility = "hidden";
          beat.lastHidden = true;
        }
        continue;
      }
      beat.lastHidden = false;
      const t = clamp01((smooth - a) / (b - a));
      // A beat anchored at the very top of the page is already on screen when
      // the page loads, so it must not start its fade-in from zero.
      const fi = a <= 0.002 ? 1 : ramp(t, 0, 0.12);
      const fo = b >= 0.999 ? 1 : ramp(1 - t, 0, 0.12);
      const o = Math.min(fi, fo);
      el.style.opacity = o.toFixed(3);
      el.style.visibility = o > 0.01 ? "visible" : "hidden";
      el.style.transform = `translateY(${((0.5 - t) * 22).toFixed(1)}px)`;
      if (id && SPECIAL[id]) SPECIAL[id](el, t);
    }

    if (bar) bar.style.transform = `scaleX(${smooth.toFixed(4)})`;
    if (hint) hint.style.opacity = smooth > 0.01 ? "0" : "1";

    let cur = 0;
    CHAPTER_WINDOWS.forEach((win, i) => {
      if (smooth >= win[0]) cur = i;
    });
    if (cur !== chapter) {
      chapter = cur;
      if (onChapter) onChapter(cur);
    }
  };

  raf = requestAnimationFrame(tick);
  film.draw(0);

  return {
    destroy() {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", onPointer);
    },
    goTo(p) {
      const total = track.offsetHeight - window.innerHeight;
      window.scrollTo({
        top: p * total,
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
      });
    },
  };
}
