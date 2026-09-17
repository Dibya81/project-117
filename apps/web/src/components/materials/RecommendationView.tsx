"use client";

/**
 * RecommendationView — the backend's composed procurement proposal, rendered
 * read-only.
 *
 * The endpoint is a POST because it *composes* a proposal, not because it acts:
 * it returns `PENDING_APPROVAL` and places nothing. This view therefore never
 * offers an "approve" or "buy" affordance. The only action it carries is a link
 * to the Approvals surface, because that is where a human decision — and any
 * write — is actually recorded. The approval banner is rendered from the
 * backend's own `approval` object, so the console cannot claim a decision the
 * engine has not recorded.
 */
import Link from "next/link";
import { ShieldCheck } from "lucide-react";
import { Lucide } from "@/components/ui/LucideIcon";
import {
  CoverageChip,
  Figure,
  LimitationNote,
  MaterialPanel,
  Money,
  MovementBadge,
  ProvenanceLine,
  StatusChip,
  statusTone,
} from "@/components/materials/MaterialsKit";
import LimitationInline from "@/components/materials/LimitationInline";
import type { RecommendationRecord } from "@/lib/api";

const COVER_TONE: Record<string, string> = {
  COVERED: "text-emerald-600",
  SHORTFALL: "text-red-600",
};

export default function RecommendationView({ recommendation }: { recommendation: RecommendationRecord }) {
  const approval = recommendation.approval;
  const cost = recommendation.estimated_material_cost;
  const lines = recommendation.lines ?? [];

  return (
    <MaterialPanel
      title="Procurement recommendation"
      subtitle={
        <span className="font-mono text-[10.5px] text-slate-400">
          {recommendation.equipment_id}
          {recommendation.failure_mode ? ` · ${recommendation.failure_mode}` : " · all requirements"}
        </span>
      }
      actions={<StatusChip label={recommendation.status} tone={statusTone(recommendation.status)} />}
      testId="material-recommendation"
    >
      {/* The decision boundary, stated first. */}
      <div className="mat-approval" data-approval-state={approval?.state ?? "NONE"}>
        <span className="mat-approval__icon" aria-hidden="true">
          <ShieldCheck size={18} strokeWidth={1.9} />
        </span>
        <div className="mat-approval__body">
          <p className="mat-approval__title">
            {approval?.required ? "Engineer review required" : "No approval attached to this proposal"}
          </p>
          <p className="mat-approval__reason">
            {approval?.reason ??
              "The recommendation endpoint did not return an approval object, so no decision state can be shown."}
          </p>
          <p className="mat-approval__note">
            This proposal places no order. Any procurement is executed only after an engineer records a decision in the
            Approvals surface.
          </p>
        </div>
        <Link href="/console/approvals" className="cs-btn cs-btn--primary mat-approval__cta">
          <Lucide name="shield" size={13} /> Review in Approvals
        </Link>
      </div>

      {/* The engine's own sentence, quoted rather than paraphrased. */}
      <blockquote className="mat-rec__sentence">{recommendation.recommendation}</blockquote>

      <div className="mat-rec__summary">
        <div className="mat-rec__stat">
          <span className="mat-rec__statlabel">Overall coverage</span>
          <span className="mat-rec__statvalue">
            <CoverageChip coverage={recommendation.overall_coverage} />
          </span>
        </div>
        <div className="mat-rec__stat">
          <span className="mat-rec__statlabel">Estimated material cost</span>
          <span className="mat-rec__statvalue">
            {cost ? (
              <>
                <Money amount={cost.amount} currency={cost.currency} className="text-[16px] font-semibold text-slate-900" />
                <StatusChip label={cost.calculation_status} tone={statusTone(cost.calculation_status)} />
              </>
            ) : (
              <span className="text-slate-400">not returned</span>
            )}
          </span>
        </div>
        <div className="mat-rec__stat">
          <span className="mat-rec__statlabel">Confidence</span>
          <span className="mat-rec__statvalue">
            {recommendation.confidence ? (
              <>
                <StatusChip label={recommendation.confidence} tone={statusTone(recommendation.confidence)} />
                <span className="mat-rec__basis">{recommendation.confidence_basis}</span>
              </>
            ) : (
              <span className="text-slate-400">not returned</span>
            )}
          </span>
        </div>
        <div className="mat-rec__stat">
          <span className="mat-rec__statlabel">Procurement required</span>
          <span className="mat-rec__statvalue">
            {recommendation.procurement_required === undefined ? (
              <span className="text-slate-400">not returned</span>
            ) : (
              <StatusChip
                label={recommendation.procurement_required ? "Proposed" : "Not required"}
                tone={recommendation.procurement_required ? "warn" : "ok"}
              />
            )}
          </span>
        </div>
        <div className="mat-rec__stat">
          <span className="mat-rec__statlabel">Generated</span>
          <span className="mat-rec__statvalue mat-rec__basis">
            {recommendation.generated_at ? new Date(recommendation.generated_at).toLocaleString() : "—"}
          </span>
        </div>
      </div>

      {cost ? (
        <div className="mat-rec__costbasis">
          <ProvenanceLine
            calculationStatus={cost.calculation_status}
            basis={{ basis: cost.basis, currency: cost.currency }}
          />
        </div>
      ) : null}

      {lines.length === 0 ? (
        <p className="mat-rec__empty">The recommendation returned no requirement lines.</p>
      ) : (
        <div className="mat-rec__scroll">
          <div className="mat-rec__table" aria-label="Recommendation lines">
            <div className="mat-rec__row mat-rec__row--head">
              <span>Item</span>
              <span className="mat-rec__num">Required</span>
              <span className="mat-rec__num">Available</span>
              <span className="mat-rec__num">Safety</span>
              <span className="mat-rec__num">Surplus</span>
              <span>Coverage</span>
              <span className="mat-rec__num">Unit price</span>
              <span className="mat-rec__num">Cost</span>
              <span className="mat-rec__num">Order qty</span>
            </div>
            {lines.map((line) => {
              const price = line.price?.current ?? null;
              return (
                <div className="mat-rec__row" key={line.item_id} data-recommendation-item={line.item_id}>
                  <span className="mat-rec__item">
                    <span className="mat-rec__itemname">{line.item_name?.trim() ? line.item_name : line.item_id}</span>
                    <span className="mat-rec__itemid">{line.item_id}</span>
                    {line.purpose ? <span className="mat-rec__itemmeta">{line.purpose}</span> : null}
                    {line.schedule ? <span className="mat-rec__itemmeta">schedule · {line.schedule}</span> : null}
                  </span>
                  <span className="mat-rec__num">
                    <Figure value={line.required_quantity} unit={line.unit} className="text-[12.5px] text-slate-700" />
                  </span>
                  <span className="mat-rec__num">
                    <Figure value={line.available} unit={line.unit} className="text-[12.5px] text-slate-700" />
                  </span>
                  <span className="mat-rec__num">
                    <Figure value={line.safety_stock} unit={line.unit} className="text-[12.5px] text-slate-500" />
                  </span>
                  <span className="mat-rec__num mat-rec__surplus">
                    {line.surplus_after_requirement_and_safety === null ||
                    line.surplus_after_requirement_and_safety === undefined ? (
                      <LimitationInline limitations={line.limitations} />
                    ) : (
                      <>
                        <span className={COVER_TONE[line.coverage] ?? "text-slate-600"}>
                          <Figure value={line.surplus_after_requirement_and_safety} unit={line.unit} className="text-[12.5px] font-semibold" />
                        </span>
                        {line.coverage === "SHORTFALL" ? (
                          <span className="mat-rec__short">
                            short <Figure value={line.shortfall_quantity} unit={line.unit} className="text-[11px]" />
                          </span>
                        ) : null}
                      </>
                    )}
                  </span>
                  <span>
                    <CoverageChip coverage={line.coverage} />
                  </span>
                  <span className="mat-rec__num mat-rec__price">
                    {price ? (
                      <>
                        <Money amount={price.price} className="text-[12.5px] text-slate-700" />
                        <span className="mat-rec__unitbasis">{price.unit}</span>
                        <span className="mat-rec__pricemove">
                          <MovementBadge movement={line.price?.movement} />
                          {line.price?.change_percent !== null && line.price?.change_percent !== undefined ? (
                            <Figure value={line.price.change_percent} unit="%" className="text-[10.5px] text-slate-500" />
                          ) : null}
                        </span>
                      </>
                    ) : (
                      <LimitationInline limitations={line.limitations} label="no price" />
                    )}
                  </span>
                  <span className="mat-rec__num mat-rec__cost">
                    {line.cost?.amount === null || line.cost?.amount === undefined ? (
                      <LimitationInline limitations={line.limitations} label="no cost" />
                    ) : (
                      <>
                        <Money amount={line.cost.amount} currency={line.cost.currency} className="text-[12.5px] font-semibold text-slate-800" />
                        {line.cost.calculation_status ? (
                          <span className="mat-rec__calcstatus">{line.cost.calculation_status}</span>
                        ) : null}
                      </>
                    )}
                  </span>
                  <span className="mat-rec__num">
                    {line.recommended_order_quantity === null || line.recommended_order_quantity === undefined ? (
                      <span className="text-slate-300">—</span>
                    ) : (
                      <Figure value={line.recommended_order_quantity} unit={line.unit} className="text-[12.5px] text-slate-700" />
                    )}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="mat-rec__foot">
        <LimitationNote limitations={recommendation.limitations} />
      </div>
    </MaterialPanel>
  );
}
