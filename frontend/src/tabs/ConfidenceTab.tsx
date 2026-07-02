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
    <span className={`px-2 py-0.5 rounded border text-[10px] font-semibold tracking-widest ${styles[signal] ?? styles.NEUTRAL}`}>
      {signal}
    </span>
  );
}

function FactorRow({ factor }: { factor: ConfidenceFactor }) {
  const bull = factor.score >= 50;
  const pct  = Math.min(100, Math.max(0, factor.score));
  return (
    <tr className="border-b border-line/50 last:border-0">
      <td className="py-2 pr-4 text-[11px] text-dim whitespace-nowrap">{factor.name}</td>
      <td className="py-2 pr-4 w-36">
        <div className="bg-elevated rounded-full h-1 overflow-hidden">
          <div
            className={`h-full rounded-full ${bull ? 'bg-up' : 'bg-down'}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </td>
      <td className={`py-2 pr-4 text-[11px] font-mono text-right ${bull ? 'text-up' : 'text-down'}`}>
        {factor.score}
      </td>
      <td className="py-2 text-[10px] font-mono text-dim text-right">
        {Math.round(factor.weight * 100)}%
      </td>
    </tr>
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
      <Skeleton className="h-24" />
      <Skeleton className="h-40" />
    </div>
  );
  if (error || !data) return <p className="text-sm text-dim">{error ?? 'No data'}</p>;

  const scoreColor = data.score >= 60 ? 'text-up' : data.score <= 40 ? 'text-down' : 'text-dim';
  const barColor   = data.score >= 60 ? 'bg-up'   : data.score <= 40 ? 'bg-down'   : 'bg-hi';

  const ni = data.newsImpact;
  const newsText = ni?.interpretation ?? ni?.keyEvent ?? null;

  return (
    <div className="space-y-4 max-w-lg">
      {/* Score header */}
      <div className="border border-line rounded bg-surface">
        <div className="flex items-center justify-between px-4 py-3 border-b border-line">
          <div className="flex items-end gap-3">
            <span className={`text-4xl font-mono font-light leading-none ${scoreColor}`}>{data.score}</span>
            <span className="text-[10px] text-dim mb-0.5">/ 100</span>
          </div>
          <SignalBadge signal={data.signal} />
        </div>
        <div className="px-4 py-2">
          <div className="bg-elevated rounded-full h-1 overflow-hidden">
            <div className={`h-full rounded-full ${barColor}`} style={{ width: `${data.score}%` }} />
          </div>
          <div className="flex justify-between text-[9px] text-dim mt-1">
            <span>BEAR</span><span>NEUTRAL</span><span>BULL</span>
          </div>
        </div>
      </div>

      {/* ML model card — the actual RandomForest, with its honest out-of-sample read */}
      {data.mlSignal && (
        <div className="border border-line rounded bg-surface px-3 py-2.5 space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-[10px] text-dim uppercase tracking-wider">RandomForest model</p>
            <SignalBadge signal={data.mlSignal.signal} />
          </div>
          <div className="flex items-center gap-4 text-[11px] font-mono">
            <span className="text-dim">P(outperform) <span className="text-ink">{(data.mlSignal.bullProb * 100).toFixed(0)}%</span></span>
            <span className="text-dim">trained on <span className="text-ink">{data.mlSignal.trainedOn}</span></span>
          </div>
          <div className="flex items-center gap-2 text-[11px]">
            <span className="text-dim">Out-of-sample accuracy:</span>
            {data.mlSignal.oosAccuracy != null ? (
              <span className={`font-mono font-semibold ${
                data.mlSignal.oosAccuracy >= 0.58 ? 'text-up'
                : data.mlSignal.oosAccuracy >= 0.52 ? 'text-ink' : 'text-down'}`}>
                {(data.mlSignal.oosAccuracy * 100).toFixed(1)}%
                <span className="text-dim font-normal"> on {data.mlSignal.oosSamples} held-out days</span>
              </span>
            ) : <span className="text-dim">not evaluated</span>}
          </div>
          <p className="text-[10px] text-dim leading-relaxed">
            Price-only technical momentum classifier, retrained per ticker. Accuracy near 50%
            means the signal has little predictive edge on recent data — treat it as one input,
            not a forecast. The headline score above is a separate weighted heuristic and is not
            driven by this model.
          </p>
        </div>
      )}

      {/* Factors table */}
      {data.factors?.length > 0 && (
        <div className="border border-line rounded bg-surface">
          <div className="px-3 py-2 border-b border-line">
            <p className="text-[10px] text-dim uppercase tracking-wider">Signal Factors</p>
          </div>
          <div className="px-3 py-1">
            <table className="w-full">
              <thead>
                <tr className="border-b border-line">
                  <th className="py-1.5 text-left text-[9px] text-dim uppercase tracking-wider font-medium">Factor</th>
                  <th className="py-1.5 text-[9px] text-dim uppercase tracking-wider font-medium"></th>
                  <th className="py-1.5 text-right text-[9px] text-dim uppercase tracking-wider font-medium">Score</th>
                  <th className="py-1.5 text-right text-[9px] text-dim uppercase tracking-wider font-medium">Wt</th>
                </tr>
              </thead>
              <tbody>
                {data.factors.map((f, i) => <FactorRow key={i} factor={f} />)}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* News impact */}
      {ni && (
        <div className="border border-line rounded bg-surface px-3 py-2.5 space-y-1.5">
          <div className="flex items-center justify-between">
            <p className="text-[10px] text-dim uppercase tracking-wider">News Sentiment</p>
            {ni.ai_generated && (
              <span className="text-[9px] text-dim bg-elevated border border-line px-1.5 py-0.5 rounded">AI</span>
            )}
          </div>
          <div className="flex items-center gap-4 text-[11px]">
            <span className="text-dim">{ni.recentCount} recent articles</span>
            {ni.sentimentScore !== 0 && (
              <span className={`font-mono ${ni.sentimentScore > 0 ? 'text-up' : 'text-down'}`}>
                {ni.sentimentScore > 0 ? '+' : ''}{ni.sentimentScore.toFixed(2)} sentiment
              </span>
            )}
          </div>
          {newsText && (
            <p className="text-[11px] text-ink leading-snug">{newsText}</p>
          )}
        </div>
      )}
    </div>
  );
}
