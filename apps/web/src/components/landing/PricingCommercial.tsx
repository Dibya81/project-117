"use client";

/**
 * PricingCommercial — the industrial commercial section.
 *
 * Deliberately NOT a SaaS pricing table. Three positions follow from that:
 *
 *  1. **No prices.** Deployment cost depends on site complexity, integration
 *     surface and operational scope, so every tier says "Custom Deployment" and
 *     the same sentence about what the number depends on. Inventing a figure
 *     would be inventing a quotation.
 *  2. **The tiers differ by capability depth, not by seat count.** The ladder at
 *     the top (DEPLOYMENT → INTELLIGENCE → INTEGRATION → GOVERNANCE → SCALE)
 *     shows how far each tier reaches, which is what an industrial buyer is
 *     actually comparing. No "BEST VALUE" badges: the reference deployment is
 *     marked with a plain technical label.
 *  3. **The value model is transparent arithmetic.** Every input is adjustable,
 *     every fixed assumption is printed next to the figure it produces, and the
 *     result is labelled illustrative in the UI and in the arithmetic itself.
 *     Nothing here claims a validated customer result.
 *
 * Styling reuses the landing design system (`p117` tokens and typography) under
 * its own `p117-com-` namespace, so nothing in the existing cinematic CSS is
 * touched.
 */
import { useMemo, useState } from "react";
import Link from "next/link";

/** The capability ladder. Each tier reaches further down this list. */
const LADDER = ["Deployment", "Intelligence", "Integration", "Governance", "Scale"] as const;

interface Tier {
  id: string;
  index: string;
  name: string;
  positioner: string;
  /** How many rungs of the ladder this tier covers. */
  depth: number;
  /** Short line for the comparison strip. */
  intent: string;
  includes: string[];
  cta: string;
  /** Marked as the reference deployment — a technical label, not a sales badge. */
  reference?: boolean;
}

const TIERS: Tier[] = [
  {
    id: "pilot",
    index: "01",
    name: "Pilot Deployment",
    positioner: "For proving Project 117 inside a plant or site",
    depth: 2,
    intent: "Prove it on your plant, on your data, on your network.",
    includes: [
      "On-prem deployment",
      "AI Workbench",
      "Industrial Simulation",
      "Knowledge Base / RAG",
      "Core Agent Workflows",
      "Initial equipment integration",
      "Analytics",
    ],
    cta: "Start a Pilot",
  },
  {
    id: "enterprise",
    index: "02",
    name: "Enterprise Deployment",
    positioner: "For production industrial operations",
    depth: 4,
    intent: "Run it as operational infrastructure, under your governance.",
    includes: [
      "Everything in Pilot",
      "Multi-agent orchestration",
      "Industrial Memory / Knowledge Graph",
      "Equipment & telemetry integration",
      "Custom agents",
      "Mobile field interface",
      "Governance / RBAC / Audit",
      "Enterprise support",
    ],
    cta: "Request Enterprise Assessment",
    reference: true,
  },
  {
    id: "scale",
    index: "03",
    name: "Multi-Site / Industrial Scale",
    positioner: "For organizations operating multiple plants and sites",
    depth: 5,
    intent: "One industrial intelligence layer across every site you run.",
    includes: [
      "Everything in Enterprise",
      "Multi-site deployment",
      "Cross-site industrial intelligence",
      "Central governance",
      "Site-specific agents / workflows",
      "Advanced integrations",
      "Fleet-level analytics",
    ],
    cta: "Discuss Industrial Scale",
  },
  {
    id: "custom",
    index: "04",
    name: "Custom Deployment",
    positioner: "For specialized industrial environments",
    depth: 5,
    intent: "Air-gapped, classified, or non-standard plant — scoped to your constraints.",
    includes: [
      "Deployment topology designed to your constraints",
      "Air-gapped and restricted-network operation",
      "Non-standard equipment and protocol integration",
      "Bespoke agent and workflow development",
      "Site-specific governance and audit requirements",
      "Custom model and hardware sizing",
    ],
    cta: "Request an Industrial AI Assessment",
  },
];

const CUSTOM_PRICING = "Custom Deployment";
const CUSTOM_PRICING_NOTE =
  "Pricing is based on site complexity, deployment scope, integrations and operational requirements.";

/* ------------------------------------------------------------------ value */

interface Assumptions {
  engineers: number;
  analysisHours: number;
  hourlyCost: number;
  maintenanceEvents: number;
  inventoryValue: number;
}

const DEFAULTS: Assumptions = {
  engineers: 40,
  analysisHours: 6,
  hourlyCost: 1_450,
  maintenanceEvents: 240,
  inventoryValue: 250_000_000,
};

/**
 * The fixed factors the model uses.
 *
 * Printed in the breakdown rather than buried in the arithmetic: an estimate
 * whose assumptions are hidden cannot be argued with, and an estimate that
 * cannot be argued with is marketing, not engineering.
 */
const MODEL = {
  weeksPerYear: 52,
  /** Share of analysis hours the deployment is modelled to return to engineering. */
  recoverableShare: 0.3,
  /** Hours of maintenance response modelled per event. */
  hoursPerEvent: 6,
  /** Share of inventory value modelled as released working capital. */
  inventoryReleaseShare: 0.05,
} as const;

const inr = (n: number) =>
  n >= 1e7
    ? `₹${(n / 1e7).toFixed(2)} Cr`
    : n >= 1e5
      ? `₹${(n / 1e5).toFixed(2)} L`
      : `₹${Math.round(n).toLocaleString("en-IN")}`;

const hours = (n: number) => `${Math.round(n).toLocaleString("en-IN")} h`;

interface ValueLine {
  label: string;
  basis: string;
  amount: string;
  value: number;
}

function computeValue(a: Assumptions): { lines: ValueLine[]; total: number } {
  const annualAnalysisHours = a.engineers * a.analysisHours * MODEL.weeksPerYear;
  const recoveredHours = annualAnalysisHours * MODEL.recoverableShare;
  const analysisValue = recoveredHours * a.hourlyCost;

  const maintenanceHours = a.maintenanceEvents * MODEL.hoursPerEvent;
  const maintenanceValue = maintenanceHours * a.hourlyCost;

  const inventoryRelease = a.inventoryValue * MODEL.inventoryReleaseShare;

  const lines: ValueLine[] = [
    {
      label: "Engineering analysis capacity returned",
      basis: `${a.engineers} engineers × ${a.analysisHours} h/week × ${MODEL.weeksPerYear} weeks = ${hours(
        annualAnalysisHours,
      )}/yr in scope · ${Math.round(MODEL.recoverableShare * 100)}% modelled recoverable = ${hours(
        recoveredHours,
      )} × ${inr(a.hourlyCost)}/h`,
      amount: inr(analysisValue),
      value: analysisValue,
    },
    {
      label: "Maintenance response effort represented",
      basis: `${a.maintenanceEvents} events/yr × ${MODEL.hoursPerEvent} h/event = ${hours(
        maintenanceHours,
      )} × ${inr(a.hourlyCost)}/h`,
      amount: inr(maintenanceValue),
      value: maintenanceValue,
    },
    {
      label: "Inventory working capital in scope",
      basis: `${inr(a.inventoryValue)} inventory × ${Math.round(
        MODEL.inventoryReleaseShare * 100,
      )}% modelled release`,
      amount: inr(inventoryRelease),
      value: inventoryRelease,
    },
  ];

  return { lines, total: analysisValue + maintenanceValue + inventoryRelease };
}

const FIELDS: { key: keyof Assumptions; label: string; unit: string; step: number; min: number; max: number }[] = [
  { key: "engineers", label: "Engineers", unit: "people", step: 1, min: 1, max: 2000 },
  { key: "analysisHours", label: "Analysis hours", unit: "h / week each", step: 1, min: 1, max: 40 },
  { key: "hourlyCost", label: "Engineer cost", unit: "₹ / hour", step: 50, min: 100, max: 20_000 },
  { key: "maintenanceEvents", label: "Maintenance events", unit: "per year", step: 10, min: 1, max: 20_000 },
  { key: "inventoryValue", label: "Inventory value", unit: "₹", step: 1_000_000, min: 100_000, max: 5_000_000_000 },
];

export default function PricingCommercial() {
  const [selected, setSelected] = useState<string>("enterprise");
  const [a, setA] = useState<Assumptions>(DEFAULTS);
  const { lines, total } = useMemo(() => computeValue(a), [a]);

  const chosen = TIERS.find((t) => t.id === selected) ?? TIERS[1];

  return (
    <section className="p117-com" id="commercial" aria-labelledby="p117-com-title">
      <div className="p117-com__inner">
        <header className="p117-com__head">
          <p className="p117-mono-line">06 — Commercial</p>
          <h2 className="p117-com__title" id="p117-com-title">
            DEPLOYMENT,
            <br />
            NOT SUBSCRIPTION.
          </h2>
          <p className="p117-com__lede">
            Project 117 is installed inside your boundary and scoped to your plant. Every deployment is
            quoted from site complexity, integration surface and operational requirements — never from a
            seat count.
          </p>
        </header>

        {/* ---- capability ladder ------------------------------------------ */}
        <div className="p117-com__ladder" role="list" aria-label="Capability progression">
          {LADDER.map((rung, i) => (
            <div className="p117-com__rung" role="listitem" key={rung}>
              <span className="p117-com__rungindex">{String(i + 1).padStart(2, "0")}</span>
              <span className="p117-com__runglabel">{rung}</span>
              {i < LADDER.length - 1 && <span className="p117-com__runglink" aria-hidden="true" />}
            </div>
          ))}
        </div>

        {/* ---- tiers ------------------------------------------------------ */}
        <div className="p117-com__tiers">
          {TIERS.map((tier) => {
            const isOn = tier.id === selected;
            return (
              <article
                key={tier.id}
                className={`p117-com__tier${isOn ? " is-on" : ""}${tier.reference ? " is-ref" : ""}`}
                data-tier={tier.id}
              >
                <header className="p117-com__tierhead">
                  <span className="p117-com__tierindex">{tier.index}</span>
                  <h3 className="p117-com__tiername">{tier.name}</h3>
                  {tier.reference && <span className="p117-com__reflag">Reference deployment</span>}
                </header>
                <p className="p117-com__positioner">{tier.positioner}</p>
                <p className="p117-com__intent">{tier.intent}</p>

                {/* Depth on the ladder — the actual comparison axis. */}
                <div className="p117-com__depth" aria-label={`Reaches ${tier.depth} of ${LADDER.length} capability stages`}>
                  {LADDER.map((rung, i) => (
                    <span key={rung} className={`p117-com__depthbar${i < tier.depth ? " is-lit" : ""}`} />
                  ))}
                </div>

                <p className="p117-com__price">{CUSTOM_PRICING}</p>

                <ul className="p117-com__includes">
                  {tier.includes.map((f) => (
                    <li key={f}>
                      <span className="p117-com__tick" aria-hidden="true" />
                      {f}
                    </li>
                  ))}
                </ul>

                <div className="p117-com__tierfoot">
                  <button
                    type="button"
                    className={`p117-com__cta${isOn ? " is-on" : ""}`}
                    onClick={() => setSelected(tier.id)}
                    aria-pressed={isOn}
                  >
                    {tier.cta}
                  </button>
                </div>
              </article>
            );
          })}
        </div>

        <p className="p117-com__pricingnote">
          <b>{CUSTOM_PRICING}</b> — {CUSTOM_PRICING_NOTE} No published list price, no per-user billing, and
          no indicative figure is shown here because none has been approved for publication.
        </p>

        {/* ---- industrial value ------------------------------------------- */}
        <div className="p117-com__value">
          <div className="p117-com__valuehead">
            <p className="p117-mono-line">Industrial value</p>
            <h3 className="p117-com__valuetitle">Model the scope, on your own numbers.</h3>
            <p className="p117-com__valuelede">
              Adjust the assumptions below. The arithmetic is shown beside every line, so you can replace
              the modelled factors with your own before this figure means anything.
            </p>
          </div>

          <div className="p117-com__valuegrid">
            <form className="p117-com__assumptions" aria-label="Value assumptions">
              {FIELDS.map((f) => (
                <label className="p117-com__field" key={f.key}>
                  <span className="p117-com__fieldlabel">{f.label}</span>
                  <span className="p117-com__fieldunit">{f.unit}</span>
                  <input
                    type="number"
                    min={f.min}
                    max={f.max}
                    step={f.step}
                    value={a[f.key]}
                    onChange={(e) => {
                      const raw = Number(e.target.value);
                      setA((cur) => ({
                        ...cur,
                        [f.key]: Number.isFinite(raw) ? Math.min(f.max, Math.max(f.min, raw)) : cur[f.key],
                      }));
                    }}
                  />
                </label>
              ))}
              <button
                type="button"
                className="p117-com__reset"
                onClick={() => setA(DEFAULTS)}
              >
                Reset to defaults
              </button>
            </form>

            <div className="p117-com__breakdown">
              <table className="p117-com__table">
                <caption className="p117-com__caption">
                  Illustrative annual value in scope — arithmetic shown per line
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Component</th>
                    <th scope="col">Basis</th>
                    <th scope="col">Illustrative value</th>
                  </tr>
                </thead>
                <tbody>
                  {lines.map((l) => (
                    <tr key={l.label}>
                      <th scope="row">{l.label}</th>
                      <td className="p117-com__basis">{l.basis}</td>
                      <td className="p117-com__amount">{l.amount}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <th scope="row" colSpan={2}>
                      Illustrative total
                    </th>
                    <td className="p117-com__amount p117-com__amount--total">{inr(total)}</td>
                  </tr>
                </tfoot>
              </table>

              <p className="p117-com__disclaimer">
                <b>Illustrative estimate — actual value depends on site data and deployment scope.</b>{" "}
                This is a transparent model over your own inputs, not a validated customer result, a
                guarantee, or a quotation. Modelled factors:{" "}
                {Math.round(MODEL.recoverableShare * 100)}% recoverable analysis share,{" "}
                {MODEL.hoursPerEvent} h per maintenance event,{" "}
                {Math.round(MODEL.inventoryReleaseShare * 100)}% inventory release. Annualised over{" "}
                {MODEL.weeksPerYear} weeks.
              </p>
            </div>
          </div>
        </div>

        {/* ---- engagement ------------------------------------------------ */}
        <div className="p117-com__engage" id="p117-com-engage">
          <div>
            <p className="p117-mono-line">How engagement starts</p>
            <p className="p117-com__engageline">
              Selected position — <b>{chosen.name}</b>
            </p>
          </div>
          <ol className="p117-com__steps">
            <li>
              <span>01</span> Industrial AI assessment — plant, network boundary and integration surface
              reviewed on site.
            </li>
            <li>
              <span>02</span> Pilot scope — one unit or line, one evidence base, success criteria agreed
              before installation.
            </li>
            <li>
              <span>03</span> Deployment — installed inside your boundary, governed by your roles and audit
              policy.
            </li>
            <li>
              <span>04</span> Scale — additional sites, agents and integrations added against the same
              governance.
            </li>
          </ol>
          <div className="p117-com__engageacts">
            <Link href="/console/home" className="p117-com__cta is-on">
              Open the workbench
            </Link>
            <span className="p117-com__engagenote">
              The running system is available to inspect. Deployment is scoped per site.
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}
