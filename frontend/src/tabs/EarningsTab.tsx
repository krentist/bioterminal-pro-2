import { useState, useEffect } from 'react';
import { fetchEarnings } from '@/api';
import { SkeletonGrid, SkeletonList } from '@/components/Skeleton';
import { fmtBig, fmtPct } from '@/lib/utils';
import type { EarningsData, EarningsQuarter } from '@/types';

function StatPill({ label, value, color = 'text-ink' }: { label: string; value: string; color?: string }) {
  return (
    <div className="bg-elevated border border-line rounded-lg p-3 flex flex-col gap-0.5">
      <p className="text-[10px] uppercase tracking-wider text-dim">{label}</p>
      <p className={`text-base font-mono font-semibold ${color}`}>{value}</p>
    </div>
  );
}

function EPSChart({ quarters }: { quarters: EarningsQuarter[] }) {
  if (!quarters.length) return null;
  const q = [...quarters].reverse().slice(-8);
  const maxAbs = Math.max(...q.map(r => Math.max(Math.abs(r.reported ?? 0), Math.abs(r.estimated ?? 0))), 0.01);

  return (
    <div className="space-y-2">
      <p className="text-[11px] text-dim uppercase tracking-wider">Quarterly EPS vs Estimate (last 8Q)</p>
      <div className="flex items-end gap-2 h-28">
        {q.map((row, i) => {
          const repH = row.reported != null ? Math.abs(row.reported) / maxAbs * 80 : 0;
          const estH = row.estimated != null ? Math.abs(row.estimated) / maxAbs * 80 : 0;
          const beat  = row.beat;
          return (
            <div key={i} className="flex-1 flex flex-col items-center gap-1 group relative">
              <div className="flex items-end gap-0.5 h-20">
                {/* Estimated bar */}
                <div
                  className="w-2 bg-line rounded-sm opacity-60"
                  style={{ height: `${estH}%` }}
                />
                {/* Reported bar */}
                <div
                  className={`w-2 rounded-sm ${beat === true ? 'bg-up' : beat === false ? 'bg-down' : 'bg-dim'}`}
                  style={{ height: `${repH}%` }}
                />
              </div>
              <p className="text-[9px] text-dim truncate w-full text-center">
                {row.date ? row.date.slice(0, 7) : ''}
              </p>
              {/* Hover tooltip */}
              <div className="absolute bottom-full mb-1 left-1/2 -translate-x-1/2 bg-black border border-line rounded px-2 py-1 text-[10px] whitespace-nowrap hidden group-hover:block z-10">
                <p className="text-ink">Rep: {row.reported != null ? row.reported.toFixed(2) : '—'}</p>
                <p className="text-dim">Est: {row.estimated != null ? row.estimated.toFixed(2) : '—'}</p>
                {row.surprisePct != null && (
                  <p className={row.beat ? 'text-up' : 'text-down'}>
                    {row.beat ? '+' : ''}{row.surprisePct.toFixed(1)}%
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
      <div className="flex items-center gap-4 text-[10px] text-dim">
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-up inline-block" /> Beat</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-down inline-block" /> Miss</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-line opacity-60 inline-block" /> Estimate</span>
      </div>
    </div>
  );
}

function RevenueChart({ data }: { data: { date: string; revenue: number | null; yoyGrowthPct: number | null }[] }) {
  if (!data.length) return null;
  const sorted = [...data].sort((a, b) => a.date.localeCompare(b.date)).slice(-5);
  const maxRev = Math.max(...sorted.map(r => r.revenue ?? 0), 1);

  return (
    <div className="space-y-2">
      <p className="text-[11px] text-dim uppercase tracking-wider">Annual Revenue Trend</p>
      <div className="space-y-1.5">
        {sorted.map((row, i) => {
          const barW = row.revenue != null ? (row.revenue / maxRev) * 100 : 0;
          const growthColor = (row.yoyGrowthPct ?? 0) >= 0 ? 'text-up' : 'text-down';
          return (
            <div key={i} className="flex items-center gap-3 text-[11px]">
              <span className="w-14 text-dim shrink-0">{row.date?.slice(0, 4) ?? '—'}</span>
              <div className="flex-1 bg-elevated rounded-sm h-4 relative overflow-hidden">
                <div
                  className="absolute left-0 top-0 h-full bg-sky-600/50 rounded-sm transition-all"
                  style={{ width: `${barW}%` }}
                />
                <span className="absolute left-2 top-0 h-full flex items-center text-[10px] text-ink font-mono">
                  {fmtBig(row.revenue)}
                </span>
              </div>
              <span className={`w-14 text-right font-mono shrink-0 ${growthColor}`}>
                {row.yoyGrowthPct != null ? fmtPct(row.yoyGrowthPct) : '—'}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function EarningsTab({ ticker }: { ticker: string }) {
  const [data, setData]       = useState<EarningsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    setLoading(true); setError(null);
    fetchEarnings(ticker)
      .then(setData)
      .catch(() => setError('Failed to load earnings data'))
      .finally(() => setLoading(false));
  }, [ticker]);

  if (loading) return <SkeletonList count={4} className="h-12" />;
  if (error)   return <p className="text-sm text-dim">{error}</p>;
  if (!data)   return null;

  const noHistory = !data.quarterlyEps?.length && !data.annualRevenue?.length;

  return (
    <div className="space-y-5">

      {/* Next earnings date banner */}
      {data.nextEarningsDate && (
        <div className="bg-amber-900/20 border border-amber-700/30 rounded-lg px-4 py-2.5 flex items-center gap-3">
          <span className="text-amber-400 text-sm font-semibold">Next Earnings</span>
          <span className="text-amber-200 font-mono text-sm">{data.nextEarningsDate}</span>
        </div>
      )}

      {/* Stats grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatPill
          label="EPS beat rate (8Q)"
          value={data.beatRate8q != null ? `${(data.beatRate8q * 100).toFixed(0)}%` : '—'}
          color={data.beatRate8q != null && data.beatRate8q >= 0.6 ? 'text-up' : data.beatRate8q != null && data.beatRate8q < 0.4 ? 'text-down' : 'text-ink'}
        />
        <StatPill
          label="Avg EPS surprise"
          value={data.avgSurprisePct != null ? fmtPct(data.avgSurprisePct) : '—'}
          color={data.avgSurprisePct != null ? (data.avgSurprisePct >= 0 ? 'text-up' : 'text-down') : 'text-ink'}
        />
        <StatPill
          label="Revenue CAGR 3Y"
          value={data.revenueCagr3y != null ? fmtPct(data.revenueCagr3y * 100) : '—'}
          color={data.revenueCagr3y != null ? (data.revenueCagr3y >= 0 ? 'text-up' : 'text-down') : 'text-ink'}
        />
        <StatPill
          label="Analyst consensus"
          value={data.recommendation ?? '—'}
          color={
            data.recommendation === 'BUY' || data.recommendation === 'STRONG_BUY' ? 'text-up'
            : data.recommendation === 'SELL' || data.recommendation === 'STRONG_SELL' ? 'text-down'
            : 'text-ink'
          }
        />
      </div>

      {/* Analyst price target range */}
      {(data.targetMean || data.targetHigh || data.targetLow) && (
        <div className="bg-elevated border border-line rounded-lg p-3">
          <p className="text-[10px] uppercase tracking-wider text-dim mb-2">
            Analyst Price Target
            {data.nAnalysts ? ` · ${data.nAnalysts} analysts` : ''}
          </p>
          <div className="flex items-center gap-4 text-[11px]">
            <span className="text-dim">Low <span className="text-down font-mono">{data.targetLow?.toFixed(2) ?? '—'}</span></span>
            <span className="text-ink">Mean <span className="text-hi font-mono font-semibold">{data.targetMean?.toFixed(2) ?? '—'}</span></span>
            <span className="text-dim">High <span className="text-up font-mono">{data.targetHigh?.toFixed(2) ?? '—'}</span></span>
          </div>
        </div>
      )}

      {noHistory ? (
        <div className="bg-elevated border border-line rounded-lg p-4 text-center space-y-1">
          <p className="text-sm text-dim">No earnings history available</p>
          <p className="text-[11px] text-dim">
            This appears to be a pre-revenue pipeline company. Valuation is based on
            clinical pipeline potential — see the <strong>rNPV</strong> tab for pipeline value analysis.
          </p>
        </div>
      ) : (
        <>
          {data.quarterlyEps?.length > 0 && <EPSChart quarters={data.quarterlyEps} />}
          {data.annualRevenue?.length > 0 && <RevenueChart data={data.annualRevenue} />}
        </>
      )}
    </div>
  );
}
