import { useState, useEffect } from 'react';
import { fetchFundamentals } from '@/api';
import { SkeletonGrid } from '@/components/Skeleton';
import { fmtBig, fmtMultiple, fmtPctFrac, fmt } from '@/lib/utils';
import type { Fundamentals } from '@/types';

function Metric({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="p-3 bg-surface rounded-lg border border-line">
      <div className="text-[10px] text-dim uppercase tracking-wider mb-1.5 leading-none">{label}</div>
      <div className={`text-[13px] font-mono font-medium leading-none ${accent ? 'text-hi' : 'text-ink'}`}>
        {value}
      </div>
    </div>
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

  return (
    <div className="space-y-4">
      {/* Header row */}
      {(data.name || data.sector) && (
        <div className="flex items-start justify-between gap-4 pb-1">
          <div>
            {data.name   && <p className="text-sm font-medium text-ink">{data.name}</p>}
            {data.sector && <p className="text-xs text-dim mt-0.5">{data.sector}</p>}
          </div>
          {data.targetPrice != null && (
            <div className="text-right flex-none">
              <p className="text-[10px] text-dim uppercase tracking-wider">Analyst Target</p>
              <p className="text-sm font-mono text-ink mt-0.5">{fmt(data.targetPrice, s)}</p>
            </div>
          )}
        </div>
      )}

      {/* Metrics grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Metric label="Market Cap"     value={fmtBig(data.marketCap, s)} />
        <Metric label="Forward P/E"    value={fmtMultiple(data.forwardPE)} />
        <Metric label="EV / Revenue"   value={fmtMultiple(data.evToRevenue)} />
        <Metric label="EV / EBITDA"    value={fmtMultiple(data.evToEbitda)} />
        <Metric label="Beta"           value={data.beta != null ? data.beta.toFixed(2) : '—'} />
        <Metric label="Revenue (TTM)"  value={fmtBig(data.revenue, s)} />
        <Metric label="Revenue Growth" value={fmtPctFrac(data.revenueGrowth)} />
        <Metric label="Gross Margin"   value={fmtPctFrac(data.grossMargin)} />
        <Metric label="Op. Margin"     value={fmtPctFrac(data.operatingMargin)} />
        <Metric label="Profit Margin"  value={fmtPctFrac(data.profitMargin)} />
        <Metric label="ROE"            value={fmtPctFrac(data.roe)} />
      </div>

      {/* Description */}
      {data.description && (
        <div className="p-3 bg-surface rounded-lg border border-line">
          <p className="text-[10px] text-dim uppercase tracking-wider mb-2">About</p>
          <p className="text-[12px] text-dim leading-relaxed line-clamp-4">{data.description}</p>
        </div>
      )}
    </div>
  );
}
