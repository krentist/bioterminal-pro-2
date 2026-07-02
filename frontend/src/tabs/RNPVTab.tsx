import { useState, useEffect } from 'react';
import { fetchRNPV } from '@/api';
import { SkeletonGrid } from '@/components/Skeleton';
import { fmtBig, fmtPctFrac } from '@/lib/utils';
import type { RNPVData } from '@/types';

const PROB_APPROVAL: Record<string, { pct: string; color: string }> = {
  'Phase 1':  { pct: '7.3%',  color: 'text-sky-400' },
  'Phase 2':  { pct: '14.0%', color: 'text-amber-400' },
  'Phase 3':  { pct: '49.1%', color: 'text-orange-400' },
  'NDA/BLA':  { pct: '85.3%', color: 'text-green-400' },
  'Approved': { pct: '100%',  color: 'text-green-400' },
};

function Pill({ label, value, sub, color = 'text-ink' }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="bg-elevated border border-line rounded-lg p-3 flex flex-col gap-0.5">
      <p className="text-[10px] uppercase tracking-wider text-dim">{label}</p>
      <p className={`text-base font-mono font-semibold ${color}`}>{value}</p>
      {sub && <p className="text-[10px] text-dim">{sub}</p>}
    </div>
  );
}

export function RNPVTab({ ticker }: { ticker: string }) {
  const [data, setData]     = useState<RNPVData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState<string | null>(null);

  useEffect(() => {
    setLoading(true); setError(null);
    fetchRNPV(ticker)
      .then(setData)
      .catch(() => setError('Failed to load rNPV data'))
      .finally(() => setLoading(false));
  }, [ticker]);

  if (loading) return <SkeletonGrid count={4} className="h-16" />;
  if (error)   return <p className="text-sm text-dim">{error}</p>;
  if (!data)   return null;

  const noTrials = !data.rnpvDetail || data.rnpvDetail.length === 0;
  const discountColor = data.pipelineDiscount == null ? 'text-ink'
    : data.pipelineDiscount > 0 ? 'text-down' : 'text-up';

  return (
    <div className="space-y-5">

      {/* Explainer */}
      <div className="bg-sky-900/20 border border-sky-700/30 rounded-lg px-4 py-3 text-[11px] text-sky-300/80 leading-relaxed">
        <strong className="text-sky-300">What is rNPV?</strong>{' '}
        Risk-adjusted Net Present Value weights each drug's projected peak revenue by the
        industry-average probability it reaches approval (source: BIO/Informa 2023).
        Phase 1 drugs have a ~7% chance of approval; Phase 3 drugs have ~49%.
        This is the standard valuation method for clinical-stage biotech companies.
      </div>

      {/* What was actually valued — scope + assumption transparency */}
      {(data.programsValued != null || data.assumptionNote) && (
        <div className={`rounded-lg border px-4 py-3 text-[11px] leading-relaxed ${
          data.sponsorMatched === false
            ? 'border-amber-500/30 bg-amber-500/10 text-amber-300/90'
            : 'border-line bg-elevated text-dim'}`}>
          {data.programsValued != null && (
            <p className="mb-1 text-ink">
              Valuing <strong>{data.programsValued}</strong> program
              {data.programsValued !== 1 ? 's' : ''}
              {data.trialsFound != null && <> from <strong>{data.trialsFound}</strong> matched trial{data.trialsFound !== 1 ? 's' : ''}</>}
              {data.sponsorMatched === false && ' (no lead-sponsor match — see caveat)'}.
            </p>
          )}
          {data.assumptionNote && <p>{data.assumptionNote}</p>}
        </div>
      )}

      {/* Summary pills */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Pill
          label="Total pipeline rNPV"
          value={fmtBig(data.rnpvTotal)}
          sub="net of dev costs"
        />
        <Pill
          label="rNPV per share"
          value={data.rnpvPerShare != null ? `${data.currencySymbol}${data.rnpvPerShare.toFixed(2)}` : '—'}
          sub="vs current price"
        />
        <Pill
          label="Implied upside"
          value={data.upside != null ? fmtPctFrac(data.upside) : '—'}
          color={data.upside != null ? (data.upside >= 0 ? 'text-up' : 'text-down') : 'text-ink'}
          sub="rNPV vs market price"
        />
        <Pill
          label="Pipeline vs mkt cap"
          value={data.pipelineDiscount != null ? fmtPctFrac(data.pipelineDiscount) : '—'}
          color={discountColor}
          sub="discount = market is cautious"
        />
      </div>

      {/* Phase probability reference */}
      <div className="flex flex-wrap gap-2">
        {Object.entries(PROB_APPROVAL).map(([phase, { pct, color }]) => (
          <span key={phase} className="text-[10px] bg-elevated border border-line rounded px-2 py-1">
            <span className="text-dim">{phase}: </span>
            <span className={`font-mono font-semibold ${color}`}>{pct}</span>
            <span className="text-dim"> approval</span>
          </span>
        ))}
      </div>

      {/* Asset breakdown table */}
      {noTrials ? (
        <p className="text-sm text-dim">No clinical trial data available to compute rNPV.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-[11px] border-separate border-spacing-y-0">
            <thead>
              <tr className="text-dim text-[10px] uppercase tracking-wider">
                <th className="text-left py-2 pr-4 font-medium border-b border-line">Asset / Trial</th>
                <th className="text-left py-2 pr-4 font-medium border-b border-line whitespace-nowrap">Phase</th>
                <th className="text-right py-2 pr-4 font-medium border-b border-line whitespace-nowrap">P(approval)</th>
                <th className="text-right py-2 pr-4 font-medium border-b border-line whitespace-nowrap">Peak Sales</th>
                <th className="text-right py-2 pr-4 font-medium border-b border-line whitespace-nowrap">rNPV</th>
                <th className="text-right py-2 font-medium border-b border-line whitespace-nowrap">Net rNPV</th>
              </tr>
            </thead>
            <tbody>
              {data.rnpvDetail.map((asset, i) => (
                <tr key={i} className="row-hover transition-colors">
                  <td className="py-2.5 pr-4 text-ink max-w-xs">
                    <p className="line-clamp-2 leading-snug">{asset.name || '—'}</p>
                  </td>
                  <td className="py-2.5 pr-4">
                    <span className={`text-[10px] font-medium ${PROB_APPROVAL[asset.phase]?.color ?? 'text-dim'}`}>
                      {asset.phase || '—'}
                    </span>
                  </td>
                  <td className="py-2.5 pr-4 text-right font-mono text-dim">
                    {asset.probApproval != null ? `${(asset.probApproval * 100).toFixed(1)}%` : '—'}
                  </td>
                  <td className="py-2.5 pr-4 text-right font-mono text-dim">
                    {fmtBig(asset.peakSales)}
                  </td>
                  <td className="py-2.5 pr-4 text-right font-mono text-ink">
                    {fmtBig(asset.rnpv)}
                  </td>
                  <td className={`py-2.5 text-right font-mono font-semibold ${asset.netRnpv >= 0 ? 'text-up' : 'text-down'}`}>
                    {fmtBig(asset.netRnpv)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-[10px] text-dim leading-relaxed">
        Assumptions: $500M peak annual sales per program (uniform placeholder, not drug-specific) ·
        phase-adjusted WACC (8–15%) and remaining dev cost · 12-year patent life · 35% operating
        margin. Phase probabilities from the BIO/Informa 2023 report. Because peak sales are a
        blanket assumption, treat the total as a rough pipeline-scale estimate, not a per-asset
        valuation.
      </p>
    </div>
  );
}
