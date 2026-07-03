import { useState, useEffect } from 'react';
import { fetchOwnership } from '@/api';
import { SkeletonGrid } from '@/components/Skeleton';
import { fmtBig, fmtPctFrac } from '@/lib/utils';
import { Users, TrendingDown } from 'lucide-react';
import type { OwnershipData } from '@/types';

function pct(v: number | null | undefined): string {
  if (v == null || isNaN(v)) return '—';
  return `${(v * 100).toFixed(1)}%`;
}

function Stat({ label, value, color = 'text-ink', sub }: { label: string; value: string; color?: string; sub?: string }) {
  return (
    <div className="px-3 py-2.5">
      <p className="text-[9px] text-dim uppercase tracking-wider">{label}</p>
      <p className={`text-base font-mono font-semibold mt-0.5 ${color}`}>{value}</p>
      {sub && <p className="text-[9px] text-dim mt-0.5">{sub}</p>}
    </div>
  );
}

export function OwnershipTab({ ticker }: { ticker: string }) {
  const [data,    setData]    = useState<OwnershipData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);

  useEffect(() => {
    setLoading(true); setError(null); setData(null);
    fetchOwnership(ticker)
      .then(setData)
      .catch(() => setError('Failed to load ownership data'))
      .finally(() => setLoading(false));
  }, [ticker]);

  if (loading) return <SkeletonGrid count={6} />;
  if (error)   return <p className="text-sm text-dim">{error}</p>;
  if (!data)   return null;

  const hasShort = data.shortPctOfFloat != null || data.sharesShort != null;
  // Short interest framing: >20% of float is heavily shorted, >10% elevated.
  const shortColor =
    data.shortPctOfFloat == null ? 'text-ink'
    : data.shortPctOfFloat >= 0.20 ? 'text-down'
    : data.shortPctOfFloat >= 0.10 ? 'text-amber-400'
    : 'text-ink';
  const siChange = data.shortInterestChangePct;

  return (
    <div className="space-y-4">

      {/* Ownership split */}
      <div className="border border-line rounded-lg bg-surface">
        <div className="px-3 py-2 border-b border-line flex items-center gap-1.5">
          <Users size={12} className="text-hi" />
          <span className="text-[9px] uppercase tracking-widest text-dim font-semibold">Ownership</span>
        </div>
        <div className="grid grid-cols-2 divide-x divide-line">
          <Stat label="Institutional" value={pct(data.heldPctInstitutions)} />
          <Stat label="Insider" value={pct(data.heldPctInsiders)} />
        </div>
        {(data.floatShares != null || data.sharesOutstanding != null) && (
          <div className="grid grid-cols-2 divide-x divide-line border-t border-line">
            <Stat label="Float" value={fmtBig(data.floatShares, '')} sub="shares" />
            <Stat label="Shares Out" value={fmtBig(data.sharesOutstanding, '')} sub="shares" />
          </div>
        )}
      </div>

      {/* Short interest */}
      <div className="border border-line rounded-lg bg-surface">
        <div className="px-3 py-2 border-b border-line flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <TrendingDown size={12} className="text-hi" />
            <span className="text-[9px] uppercase tracking-widest text-dim font-semibold">Short Interest</span>
          </div>
          {data.dateShortInterest && (
            <span className="text-[9px] text-dim">as of {data.dateShortInterest}</span>
          )}
        </div>
        {hasShort ? (
          <>
            <div className="grid grid-cols-3 divide-x divide-line">
              <Stat label="% of Float" value={pct(data.shortPctOfFloat)} color={shortColor} />
              <Stat label="Days to Cover" value={data.daysToCover != null ? data.daysToCover.toFixed(1) : '—'} sub="short ratio" />
              <Stat
                label="MoM Change"
                value={siChange != null ? `${siChange >= 0 ? '+' : ''}${(siChange * 100).toFixed(1)}%` : '—'}
                color={siChange == null ? 'text-ink' : siChange > 0 ? 'text-down' : 'text-up'}
                sub="vs prior month"
              />
            </div>
            <p className="px-3 pb-2 text-[9px] text-dim leading-relaxed">
              {data.sharesShort != null && <>{fmtBig(data.sharesShort, '')} shares short. </>}
              Days-to-cover is short interest ÷ average daily volume — higher means a short squeeze
              would take longer to unwind. Biotech short interest often reflects binary-event risk.
            </p>
          </>
        ) : (
          <p className="px-3 py-3 text-[11px] text-dim leading-relaxed">
            Short-interest data isn't reported for this listing (it's a US-exchange metric). For HK
            names, institutional positioning is visible in the <strong>CCASS</strong> panel instead.
          </p>
        )}
      </div>

      {/* Top institutional holders */}
      {data.topInstitutions.length > 0 && (
        <div>
          <p className="text-[10px] text-dim uppercase tracking-wider mb-1.5">Top Institutional Holders</p>
          <div className="overflow-x-auto">
            <table className="w-full text-[11px]">
              <thead>
                <tr className="text-dim text-[9px] uppercase tracking-wider border-b border-line">
                  <th className="text-left py-1.5 pr-3 font-medium">Holder</th>
                  <th className="text-right py-1.5 pr-3 font-medium">% Held</th>
                  <th className="text-right py-1.5 pr-3 font-medium whitespace-nowrap">Value</th>
                  <th className="text-right py-1.5 font-medium whitespace-nowrap">Δ Shares</th>
                </tr>
              </thead>
              <tbody>
                {data.topInstitutions.map((h, i) => (
                  <tr key={i} className="border-b border-line/50 last:border-0">
                    <td className="py-1.5 pr-3 text-ink">{h.holder || '—'}</td>
                    <td className="py-1.5 pr-3 text-right font-mono text-ink">{pct(h.pctHeld)}</td>
                    <td className="py-1.5 pr-3 text-right font-mono text-dim">{fmtBig(h.value, '$')}</td>
                    <td className={`py-1.5 text-right font-mono ${h.pctChange == null ? 'text-dim' : h.pctChange >= 0 ? 'text-up' : 'text-down'}`}>
                      {h.pctChange != null ? fmtPctFrac(h.pctChange) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[9px] text-dim mt-1.5">
            13F institutional positions (US-reported), most recent filing date per holder.
          </p>
        </div>
      )}
    </div>
  );
}
