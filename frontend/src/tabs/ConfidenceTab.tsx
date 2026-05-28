import { useState, useEffect } from 'react';
import { fetchConfidence } from '@/api';
import { Skeleton } from '@/components/Skeleton';
import type { ConfidenceData, ConfidenceFactor } from '@/types';

function SignalBadge({ signal }: { signal: string }) {
  const styles: Record<string, string> = {
    BULLISH: 'bg-up/10 text-up border-up/30',
    BEARISH: 'bg-down/10 text-down border-down/30',
    NEUTRAL: 'bg-elevated text-dim border-line',
  };
  return (
    <span className={`px-2.5 py-0.5 rounded border text-[11px] font-semibold tracking-wide ${styles[signal] ?? styles.NEUTRAL}`}>
      {signal}
    </span>
  );
}

function FactorRow({ factor }: { factor: ConfidenceFactor }) {
  const pct     = Math.min(100, Math.max(0, Math.abs(factor.value) * 100));
  const positive = factor.direction === 'up' || factor.direction === 'positive' || factor.value > 0;
  return (
    <div className="flex items-center gap-3 py-1.5">
      <span className="text-[11px] text-dim w-40 flex-none truncate">{factor.name}</span>
      <div className="flex-1 bg-elevated rounded-full h-1 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${positive ? 'bg-up' : 'bg-down'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`text-[10px] font-mono w-4 flex-none ${positive ? 'text-up' : 'text-down'}`}>
        {positive ? '▲' : '▼'}
      </span>
    </div>
  );
}

export function ConfidenceTab({ ticker }: { ticker: string }) {
  const [data,    setData]    = useState<ConfidenceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);

  useEffect(() => {
    setLoading(true); setError(null);
    fetchConfidence(ticker)
      .then(setData)
      .catch(() => setError('Failed to load ML signal'))
      .finally(() => setLoading(false));
  }, [ticker]);

  if (loading) return (
    <div className="space-y-3 max-w-sm">
      <Skeleton className="h-28" />
      <Skeleton className="h-44" />
    </div>
  );
  if (error || !data) return <p className="text-sm text-dim">{error ?? 'No data'}</p>;

  const scoreColor =
    data.score >= 60 ? 'text-up' :
    data.score <= 40 ? 'text-down' : 'text-dim';

  const barColor =
    data.score >= 60 ? 'bg-up' :
    data.score <= 40 ? 'bg-down' : 'bg-hi';

  return (
    <div className="space-y-4 max-w-sm">
      {/* Score card */}
      <div className="p-4 bg-surface rounded-lg border border-line">
        <div className="flex items-start justify-between mb-4">
          <div>
            <p className="text-[10px] text-dim uppercase tracking-wider mb-1">Confidence Score</p>
            <p className={`text-4xl font-mono font-light leading-none ${scoreColor}`}>{data.score}</p>
            <p className="text-[10px] text-dim mt-1">out of 100</p>
          </div>
          <SignalBadge signal={data.signal} />
        </div>

        {/* Score bar */}
        <div className="bg-elevated rounded-full h-1.5 overflow-hidden mb-1">
          <div
            className={`h-full rounded-full transition-all duration-500 ${barColor}`}
            style={{ width: `${data.score}%` }}
          />
        </div>
        <div className="flex justify-between text-[10px] text-dim">
          <span>Bear 0</span>
          <span>Neutral 50</span>
          <span>Bull 100</span>
        </div>
      </div>

      {/* Factors */}
      {data.factors?.length > 0 && (
        <div className="p-4 bg-surface rounded-lg border border-line">
          <p className="text-[10px] text-dim uppercase tracking-wider mb-3">Signal Factors</p>
          {data.factors.map((f, i) => <FactorRow key={i} factor={f} />)}
        </div>
      )}

      {/* News impact */}
      {data.newsImpact && (
        <div className="p-3 bg-surface rounded-lg border border-line">
          <p className="text-[10px] text-dim uppercase tracking-wider mb-1">News Impact</p>
          <p className="text-[12px] text-ink">{data.newsImpact}</p>
        </div>
      )}
    </div>
  );
}
