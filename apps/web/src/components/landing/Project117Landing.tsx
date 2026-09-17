"use client";

/**
 * Project117Landing — the complete cinematic first page.
 *
 * Section 1 is the film: the 120-frame sequence scrubbed by CinematicSequence.
 * The director normalizes global scroll into its window and hands off to the
 * procedural sections:
 *   02 information field + 700-page burst   (canvas: InfoField)
 *   03 security boundary + particle reveal  (canvas: SecurityScene)
 *   04 living system / orchestrator network (canvas: NetworkScene)
 *   05 information → action                 (DOM: workflow, sandbox,
 *                                            artifacts, verification, CTA)
 * All choreography lives in lib/landing/director.js — this file is markup.
 * 2026 elevation: preloader, glass nav, magnetic CTA, WebGL reactor finale.
 * prefers-reduced-motion renders the same story as a static stack.
 */
import Link from "next/link";
import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";

import CinematicSequence, { CinematicSequenceHandle } from "./CinematicSequence";
import ChapterNavigation, { Chapter } from "./ChapterNavigation";
import ScrollProgress, { ScrollProgressHandle } from "./ScrollProgress";
import { createDirector } from "@/lib/landing/director";
import { ReactorOrb } from "@/components/fx/ReactorOrb";
import { Magnetic } from "@/components/fx/Magnetic";
import { Counter } from "@/components/fx/Counter";

import "@/styles/project117-landing.css";

/**
 * The commercial section is ~3000vh below the film, so its code is not part of
 * what the first screen needs. `next/dynamic` splits it out of the initial
 * landing chunk and it is mounted once the reader approaches the end of the
 * track — the film's own code, animations and frame sequence are untouched.
 */
const PricingCommercial = dynamic(() => import("./PricingCommercial"), {
  loading: () => <div className="p117-com p117-com--loading" aria-hidden="true" />,
});

const CHAPTERS: Chapter[] = [
  { id: "01", label: "The World", progress: 0.0 },
  { id: "02", label: "Information", progress: 0.36 },
  { id: "03", label: "Security", progress: 0.54 },
  { id: "04", label: "Project 117", progress: 0.68 },
  { id: "05", label: "Action", progress: 0.87 },
];

const MORPH_WORDS = ["INFORMATION.", "KNOWLEDGE.", "DECISIONS."];
const STEPS = ["UNDERSTAND", "REASON", "EXECUTE", "VERIFY"];
const AGENT_CHAIN = ["ORCHESTRATOR", "MAINTENANCE AGENT", "DATA ANALYSIS AGENT", "SAFETY AGENT", "VERIFICATION AGENT"];
const RING = ["DOCUMENTS", "TELEMETRY", "MEMORY", "AGENTS", "TOOLS", "VERIFICATION"];

const FINAL_STATS: { value: number; suffix: string; label: string }[] = [
  { value: 0, suffix: "", label: "external calls" },
  { value: 100, suffix: "%", label: "on-premise" },
  { value: 5, suffix: "", label: "local agents" },
  { value: 6, suffix: "", label: "verification gates" },
];

function MorphWord({ word }: { word: string }) {
  return (
    <span className="p117-morphword" aria-hidden="true">
      {word.split("").map((ch, i) => (
        <span key={i}>{ch}</span>
      ))}
    </span>
  );
}

/** Preloader — brand mark + counter; lifts once the first frames are warm. */
function Preloader() {
  const [pct, setPct] = useState(0);
  const [gone, setGone] = useState(false);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setGone(true);
      return;
    }
    let v = 0;
    const id = setInterval(() => {
      v = Math.min(100, v + (v < 70 ? 7 : v < 92 ? 3 : 2));
      setPct(v);
      if (v >= 100) {
        clearInterval(id);
        setTimeout(() => setGone(true), 420);
      }
    }, 46);
    return () => clearInterval(id);
  }, []);

  if (gone) return null;

  return (
    <div className={`p117-preloader${pct >= 100 ? " is-done" : ""}`} role="status" aria-label="Loading Project 117">
      <div className="p117-preloader__mark">
        PROJECT <b>117</b>
      </div>
      <div className="p117-preloader__bar">
        <i style={{ transform: `scaleX(${pct / 100})` }} />
      </div>
      <div className="p117-preloader__pct">{pct}%</div>
      <div className="p117-preloader__hint">sovereign industrial ai · initializing</div>
    </div>
  );
}

export default function Project117Landing() {
  const sequenceRef = useRef<CinematicSequenceHandle>(null);
  const progressRef = useRef<ScrollProgressHandle>(null);
  const trackRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const directorRef = useRef<{ destroy: () => void; goTo: (p: number) => void } | null>(null);

  const [reduced, setReduced] = useState(false);
  const [chapter, setChapter] = useState(0);
  /**
   * Whether the commercial section has been reached.
   *
   * A sentinel is observed at the end of the film; the section's chunk is
   * fetched only when the reader gets there, so a visitor who never scrolls past
   * the finale never downloads it. `prefers-reduced-motion` renders the film as
   * a static stack, where the section is immediately reachable, so it mounts at
   * once in that case.
   */
  const [commercialReady, setCommercialReady] = useState(false);

  useEffect(() => {
    if (reduced) {
      setCommercialReady(true);
      return;
    }
    const track = trackRef.current;
    if (!track || typeof IntersectionObserver === "undefined") {
      setCommercialReady(true);
      return;
    }
    const sentinel = document.createElement("div");
    sentinel.setAttribute("aria-hidden", "true");
    sentinel.style.cssText = "position:absolute;bottom:0;left:0;width:1px;height:1px;";
    track.appendChild(sentinel);
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setCommercialReady(true);
          io.disconnect();
        }
      },
      // Start loading a screen before the end, so the section is already there
      // when the reader arrives rather than popping in under them.
      { rootMargin: "0px 0px 120% 0px" },
    );
    io.observe(sentinel);
    return () => {
      io.disconnect();
      sentinel.remove();
    };
  }, [reduced]);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  useEffect(() => {
    if (reduced) return;
    const track = trackRef.current;
    const stage = stageRef.current;
    if (!track || !stage) return;

    const director = createDirector({
      track,
      stage,
      film: {
        draw: (p: number) => sequenceRef.current?.draw(p),
        canvas: stage.querySelector(".p117-canvas") ?? undefined,
      },
      onChapter: setChapter,
    });
    directorRef.current = director;
    return () => director.destroy();
  }, [reduced]);

  const goTo = (p: number) => directorRef.current?.goTo(p);

  return (
    <main className={`p117${reduced ? " p117--static" : ""}`}>
      <Preloader />

      <header className="p117-nav">
        <Link href="/" className="p117-brand" aria-label="Project 117 home">
          PROJECT <b>117</b>
        </Link>
        <ul className="p117-nav-links">
          <li><a href="#world" onClick={(e) => { e.preventDefault(); goTo(0); }}>World</a></li>
          <li><a href="#problem" onClick={(e) => { e.preventDefault(); goTo(0.36); }}>Problem</a></li>
          <li><a href="#security" onClick={(e) => { e.preventDefault(); goTo(0.54); }}>Security</a></li>
          <li><a href="#system" onClick={(e) => { e.preventDefault(); goTo(0.68); }}>System</a></li>
          {/* Additive. Reuses the existing item markup and classes so the nav's
              behaviour and look are unchanged; it scrolls past the film to the
              commercial section rather than driving the director. */}
          <li><a href="#commercial" onClick={(e) => { e.preventDefault(); document.getElementById("commercial")?.scrollIntoView({ behavior: "smooth", block: "start" }); }}>Commercial</a></li>
        </ul>
        <Link href="/console/home" className="p117-nav-cta">
          Enter
          <svg width="13" height="10" viewBox="0 0 16 12" fill="none" aria-hidden="true">
            <path d="M0 6h14M9 1l5 5-5 5" stroke="currentColor" strokeWidth="1.4" />
          </svg>
        </Link>
      </header>

      <ChapterNavigation chapters={CHAPTERS} current={chapter} onSelect={goTo} />
      <ScrollProgress ref={progressRef} />
      <div className="p117-scrollhint" data-hint aria-hidden="true">
        <span className="p117-scrollhint__line" />
        Scroll to explore
      </div>

      <div className="p117-track" ref={trackRef}>
        <div className="p117-stage" ref={stageRef}>
          {/* Section 1 — the film (untouched engine) */}
          <CinematicSequence ref={sequenceRef} />
          <div className="p117-vignette" aria-hidden="true" />
          <div className="p117-scene-dark" data-dim aria-hidden="true" />

          {/* Sections 2–4 — procedural canvas layers */}
          <canvas className="p117-canvas p117-fx" data-fx="info" aria-hidden="true" />
          <canvas className="p117-canvas p117-fx" data-fx="security" aria-hidden="true" />
          <canvas className="p117-canvas p117-fx" data-fx="network" aria-hidden="true" />

          <div className="p117-grain" aria-hidden="true" />

          <div className="p117-overlay">
            {/* ================ SECTION 01 — THE WORLD ================ */}
            <section className="p117-beat p117-beat--bl" data-beat="0,0.045" id="world"
              aria-label="Introduction">
              <p className="p117-kicker">Sovereign Industrial AI</p>
              <h1 className="p117-headline">THE INTELLIGENCE<br />BEHIND INDUSTRY.</h1>
              <p className="p117-sub">From information to action.<br />On-prem. In your hands.</p>
            </section>

            <section className="p117-beat p117-beat--bl" data-beat="0.052,0.098"
              aria-label="Industry never stops">
              <p className="p117-mono-line">01 — The industrial world</p>
              <h2 className="p117-headline">INDUSTRY<br />NEVER STOPS.</h2>
              <p className="p117-sub">Machines generate data. Engineers generate decisions.<br />Organizations generate knowledge.</p>
            </section>

            {/* ================ SECTION 02 — THE PROBLEM ================ */}
            <section className="p117-beat" data-beat="0.345,0.402" data-beat-id="morph" id="problem"
              aria-label="Industry runs on information">
              <p className="p117-mono-line">02 — Information</p>
              <h2 className="p117-headline">INDUSTRY<br />RUNS ON</h2>
              <div className="p117-morph" aria-label="Information, knowledge, decisions">
                {MORPH_WORDS.map((w) => <MorphWord key={w} word={w} />)}
                <span className="p117-sr-only">{MORPH_WORDS.join(" ")}</span>
              </div>
            </section>

            <section className="p117-beat" data-beat="0.41,0.445" aria-label="Information is everywhere">
              <h2 className="p117-headline p117-headline--mid">BUT INFORMATION<br />IS EVERYWHERE.</h2>
              <p className="p117-sub">Documents. Systems. Machines. Sensors. People.</p>
            </section>

            <section className="p117-beat" data-beat="0.45,0.475" aria-label="The answer is buried">
              <h2 className="p117-headline p117-headline--mid">AND THE ANSWER IS BURIED<br />SOMEWHERE IN BETWEEN.</h2>
            </section>

            <section className="p117-beat" data-beat="0.478,0.498" aria-label="Seven hundred pages">
              <h2 className="p117-verb">700+<br /><em>PAGES</em></h2>
            </section>

            <section className="p117-beat" data-beat="0.502,0.522" aria-label="Find it">
              <h2 className="p117-verb p117-verb--accent">FIND IT.</h2>
            </section>

            {/* ================ SECTION 03 — THE SECURITY PROBLEM ================ */}
            <section className="p117-beat" data-beat="0.525,0.552" id="security"
              aria-label="Confidential data">
              <p className="p117-kicker p117-kicker--orange">Confidential</p>
              <p className="p117-mono-line">Proprietary industrial data</p>
            </section>

            <section className="p117-beat p117-beat--split" data-beat="0.552,0.575" aria-label="Your data versus external AI">
              <p className="p117-mono-line">Your data</p>
              <p className="p117-mono-line p117-mono-line--danger">External AI</p>
            </section>

            <section className="p117-beat" data-beat="0.578,0.606" aria-label="Critical knowledge cannot leave">
              <h2 className="p117-headline p117-headline--mid">CRITICAL KNOWLEDGE<br />CANNOT LEAVE.</h2>
            </section>

            <section className="p117-beat" data-beat="0.608,0.628" aria-label="Do not send the data">
              <p className="p117-sub p117-sub--big">SO DON&apos;T SEND THE DATA.</p>
            </section>

            <section className="p117-beat" data-beat="0.624,0.65" aria-label="Bring the intelligence">
              <h2 className="p117-verb">BRING THE<br /><em>INTELLIGENCE.</em></h2>
            </section>

            {/* ================ SECTION 04 — PROJECT 117 ================ */}
            <section className="p117-beat" data-beat="0.665,0.7" id="system"
              aria-label="Project 117 reveal">
              <p className="p117-kicker p117-kicker--orange">Project 117</p>
              <h2 className="p117-headline p117-headline--glow">SOVEREIGN<br />INDUSTRIAL AI</h2>
            </section>

            <section className="p117-beat p117-beat--bl" data-beat="0.722,0.748" aria-label="A request enters">
              <p className="p117-request">
                <span>Request</span>
                Analyze compressor C-3
              </p>
            </section>

            <section className="p117-beat p117-beat--bl" data-beat="0.74,0.78" aria-label="Orchestrator flow">
              <p className="p117-mono-line">
                Orchestrator → Maintenance → Data analysis → Safety → Verification
              </p>
            </section>

            <section className="p117-beat" data-beat="0.786,0.81" aria-label="Intelligence where your data lives">
              <h2 className="p117-headline p117-headline--mid">INTELLIGENCE<br />WHERE YOUR DATA LIVES.</h2>
            </section>

            {/* ================ SECTION 05 — INFORMATION TO ACTION ================ */}
            <section className="p117-beat" data-beat="0.802,0.822" id="action" aria-label="A user request">
              <p className="p117-request p117-request--center">
                <span>User request</span>
                Analyze the maintenance history of Compressor C-3.
              </p>
            </section>

            <section className="p117-beat" data-beat="0.818,0.85" data-beat-id="s5steps" aria-label="Understand, reason, execute, verify">
              <div className="p117-steps">
                {STEPS.map((s) => (
                  <div className="p117-step" key={s}><i aria-hidden="true" />{s}</div>
                ))}
              </div>
            </section>

            <section className="p117-beat" data-beat="0.846,0.868" data-beat-id="s5agents" aria-label="Agent delegation">
              <div className="p117-agentrow">
                <i className="p117-agentdot" aria-hidden="true" />
                {AGENT_CHAIN.map((a) => (
                  <span className="p117-agentnode" key={a}>{a}</span>
                ))}
              </div>
            </section>

            <section className="p117-beat" data-beat="0.862,0.89" data-beat-id="s5sandbox" aria-label="Secure sandbox execution">
              <div className="p117-sandbox">
                <pre className="p117-code" aria-hidden="true">{"df = load(\"c3_vibration.csv\")\ntrend = ols(df.vibration ~ df.hours)\nassert trend.pvalue < 0.01"}</pre>
                <div className="p117-badges">
                  <span className="p117-badge">Isolated</span>
                  <span className="p117-badge">No external egress</span>
                  <span className="p117-badge">Resource controlled</span>
                </div>
              </div>
            </section>

            <section className="p117-beat" data-beat="0.884,0.91" data-beat-id="s5graph" aria-label="Vibration trend detected">
              <svg className="p117-graph" viewBox="0 0 300 120" role="img" aria-label="Vibration trend line rising over time">
                <path data-graph-line d="M8 96 L40 92 L72 95 L104 86 L136 88 L168 74 L200 68 L232 52 L264 40 L292 24"
                  fill="none" stroke="#45d5ff" strokeWidth="2" pathLength={1}
                  strokeDasharray={1} strokeDashoffset={1} strokeLinecap="round" />
                <circle data-graph-dot cx="292" cy="24" r="4" fill="#ff7a3d" opacity="0" />
              </svg>
              <p className="p117-mono-line p117-graphcaption" style={{ opacity: 0 }}>
                Vibration trend detected — p &lt; 0.01
              </p>
            </section>

            <section className="p117-beat" data-beat="0.904,0.962" data-beat-id="s5artifacts" aria-label="Artifacts generated">
              <p className="p117-mono-line p117-genlabel">Generate</p>
              <div className="p117-docs">
                <div className="p117-doc p117-doc--pdf" aria-label="report.pdf">
                  <i /><i /><i />
                  <span>REPORT.PDF</span>
                </div>
                <div className="p117-doc p117-doc--xlsx" aria-label="analysis.xlsx">
                  <i /><i /><i /><i /><i /><i />
                  <span>ANALYSIS.XLSX</span>
                </div>
                <div className="p117-doc p117-doc--pptx" aria-label="presentation.pptx">
                  <i /><i />
                  <span>PRESENTATION.PPTX</span>
                </div>
                <div className="p117-doc p117-doc--docx" aria-label="report.docx">
                  <i /><i /><i /><i />
                  <span>REPORT.DOCX</span>
                </div>
              </div>
            </section>

            <section className="p117-beat" data-beat="0.928,0.958" data-beat-id="s5verify" aria-label="Verification">
              <div className="p117-verify">
                <p className="p117-claim">“Recommended maintenance interval: 60 days”</p>
                <i className="p117-link" aria-hidden="true" />
                <p className="p117-source">SOURCE — SOP-14.2, PAGE 143</p>
                <p className="p117-verdict">VERIFIED ✓</p>
                <div className="p117-checks">
                  <p className="p117-check">Evidence checked</p>
                  <p className="p117-check">Calculation checked</p>
                  <p className="p117-check">Artifact checked</p>
                </div>
              </div>
            </section>

            <section className="p117-beat p117-beat--final" data-beat="0.958,1" data-beat-id="s5final" id="enter" aria-label="Enter the workbench">
              {/* WebGL reactor — mounts only when the finale chapter is near */}
              {(chapter >= 4 || reduced) && (
                <div className="p117-orbwrap" aria-hidden="true">
                  <ReactorOrb size="hero" />
                </div>
              )}
              <div className="p117-ring" aria-hidden="true">
                {RING.map((r, i) => (
                  <span className="p117-ringitem" key={r} style={{ transform: `rotate(${i * 60}deg) translateY(-132px) rotate(${-i * 60}deg)` }}>{r}</span>
                ))}
              </div>
              <h2 className="p117-headline p117-finalstmt">FROM INFORMATION<br />TO ACTION.</h2>
              <div className="p117-finalbrand">
                <p className="p117-kicker p117-kicker--orange" style={{ marginBottom: 8 }}>Project 117</p>
                <p className="p117-mono-line">Sovereign industrial AI</p>
              </div>
              <div className="p117-finalstats">
                {FINAL_STATS.map((s) => (
                  <span key={s.label} className="p117-stat">
                    <b><Counter value={s.value} suffix={s.suffix} duration={1200} /></b>
                    <i>{s.label}</i>
                  </span>
                ))}
              </div>
              <Magnetic strength={0.3}>
                <Link href="/console/home" className="p117-cta p117-cta--live" style={{ opacity: 1 }}>
                  Enter the workbench
                  <svg width="16" height="12" viewBox="0 0 16 12" fill="none" aria-hidden="true">
                    <path d="M0 6h14M9 1l5 5-5 5" stroke="currentColor" strokeWidth="1.4" />
                  </svg>
                </Link>
              </Magnetic>
            </section>
          </div>
        </div>
      </div>

      {/* The commercial section begins where the film ends. It is ordinary
          document flow after the sticky stage, so the director's progress maths
          (`window.scrollY / (track.offsetHeight - innerHeight)`) is unaffected:
          neither the track's height nor its offset changes. */}
      {commercialReady && <PricingCommercial />}

      <noscript>
        <style>{".p117-canvas,.p117-fx{display:none}.p117-beat{opacity:1 !important;visibility:visible !important;position:relative;min-height:70vh}"}</style>
      </noscript>
    </main>
  );
}
