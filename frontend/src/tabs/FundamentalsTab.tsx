import { useState, useEffect } from 'react';
import { fetchFundamentals } from '@/api';
import { SkeletonGrid } from '@/components/Skeleton';
import { fmtBig, fmtMultiple, fmtPctFrac, fmt } from '@/lib/utils';
import type { Fundamentals } from '@/types';

function Row({ label, value }: { label: string; value: string }) {
  return (
    <tr className="border-b border-line/50 last:border-0">
      <td className="py-1.5 pr-6 text-[10px] text-dim whitespace-nowrap">{label}</td>
      <td className="py-1.5 text-[11px] font-mono text-ink text-right whitespace-nowrap">{value}</td>
    </tr>
  );
}

export function FundamentalsTab({ ticker }: { ticker: string }) {
  const [data,    setData]    = useState<Fundamentals | null>(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);

  useEffect(() => {
    setLoading(true); setError(null); setData(null);
    fetchFundamentals(ticker)
      .then(setData)
      .catch(() => setError('Failed to load fundamentals'))
      .finally(() => setLoading(false));
  }, [ticker]);

  if (loading) return <SkeletonGrid count={11} />;
  if (error)   return <p className="text-sm text-dim">{error}</p>;
  if (!data)   return <p className="text-sm text-dim">No data available</p>;

  const s = data.currencySymbol || '$';

  const leftCol = [
    ['Market Cap',     fmtBig(data.marketCap, s)],
    ['Revenue TTM',    fmtBig(data.revenue, s)],
    ['Rev Growth',     fmtPctFrac(data.revenueGrowth)],
    ['Gross Margin',   fmtPctFrac(data.grossMargin)],
    ['Op. Margin',     fmtPctFrac(data.operatingMargin)],
    ['Profit Margin',  fmtPctFrac(data.profitMargin)],
  ] as [string, string][];

  const rightCol = [
    ['Forward P/E',    fmtMultiple(data.forwardPE)],
    ['EV / Revenue',   fmtMultiple(data.evToRevenue)],
    ['EV / EBITDA',    fmtMultiple(data.evToEbitda)],
    ['ROE',            fmtPctFrac(data.roe)],
    ['Beta',           data.beta != null ? data.beta.toFixed(2) : '—'],
    ['Analyst Target', data.targetPrice != null ? fmt(data.targetPrice, s) : '—'],
  ] as [string, string][];

  // Runway framing: <1y is critical, <2y is a watch-item, otherwise comfortable.
  const runway = data.runwayYears;
  const runwayColor =
    runway == null ? 'text-ink'
    : runway < 1 ? 'text-down'
    : runway < 2 ? 'text-amber-400'
    : 'text-up';
  const showRunwayCard =
    data.cash != null || data.annualBurn != null || data.cashGenerating != null;

  return (
    <div className="space-y-4 max-w-3xl">
      {/* Company header */}
      {(data.name || data.sector) && (
        <div className="border-b border-line pb-3">
          {data.name   && <p className="text-[13px] font-medium text-ink">{data.name}</p>}
          {data.sector && <p className="text-[11px] text-dim mt-0.5">{data.sector}</p>}
        </div>
      )}

      {/* Cash runway — the headline biotech survival metric */}
      {showRunwayCard && (
        <div className="border border-line rounded-lg bg-surface">
          <div className="px-3 py-2 border-b border-line flex items-center justify-between">
            <span className="text-[9px] uppercase tracking-widest text-dim font-semibold">Cash Runway</span>
            {data.burnBasis && (
              <span className="text-[9px] text-dim">
                burn from {data.burnBasis === 'freeCashflow' ? 'free cash flow' : 'operating cash flow'}
              </span>
            )}
          </div>
          <div className="grid grid-cols-3 divide-x divide-line">
            <div className="px-3 py-2.5">
              <p className="text-[9px] text-dim uppercase tracking-wider">Cash</p>
              <p className="text-base font-mono font-semibold text-ink mt-0.5">{fmtBig(data.cash, s)}</p>
            </div>
            <div className="px-3 py-2.5">
              <p className="text-[9px] text-dim uppercase tracking-wider">Annual Burn</p>
              <p className="text-base font-mono font-semibold text-ink mt-0.5">
                {data.cashGenerating ? '—' : data.annualBurn != null ? fmtBig(data.annualBurn, s) : '—'}
              </p>
            </div>
            <div className="px-3 py-2.5">
              <p className="text-[9px] text-dim uppercase tracking-wider">Runway</p>
              <p className={`text-base font-mono font-semibold mt-0.5 ${runwayColor}`}>
                {data.cashGenerating
                  ? 'Cash-flow +'
                  : runway != null
                    ? `${runway.toFixed(1)} yr`
                    : '—'}
              </p>
            </div>
          </div>
          <p className="px-3 pb-2 text-[9px] text-dim leading-relaxed">
            {data.cashGenerating
              ? 'Company generated positive cash flow over the trailing period — not currently burning cash.'
              : runway != null
                ? 'Cash ÷ trailing annual cash burn. A rough survival estimate before a likely capital raise; does not include undrawn facilities, milestone payments, or pipeline financing.'
                : 'Insufficient cash-flow data to estimate runway for this ticker.'}
          </p>
        </div>
      )}

      {/* Two-column metrics table */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-0">
        <table className="w-full">
          <tbody>
            {leftCol.map(([label, value]) => (
              <Row key={label} label={label} value={value} />
            ))}
          </tbody>
        </table>
        <table className="w-full">
          <tbody>
            {rightCol.map(([label, value]) => (
              <Row key={label} label={label} value={value} />
            ))}
          </tbody>
        </table>
      </div>

      {/* Description */}
      {data.description && (
        <div className="pt-1">
          <p className="text-[10px] text-dim uppercase tracking-wider mb-1.5">Business Description</p>
          <p className="text-[11px] text-dim leading-relaxed line-clamp-4">{data.description}</p>
        </div>
      )}
    </div>
  );
}
