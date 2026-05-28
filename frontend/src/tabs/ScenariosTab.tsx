import { useState, useEffect } from 'react';
import { fetchScenarios } from '@/api';
import { Skeleton } from '@/components/Skeleton';
import { fmt } from '@/lib/utils';
import type { ScenariosData, Scenario } from '@/types';

const LABEL_STYLE: Record<string, string> = {
  bear:    'border-down/40 bg-down/5 text-down',
  base:    'border-line bg-surface text-dim',
  bull:    'border-up/40 bg-up/5 text-up',
};

function labelStyle(label: string): string {
  return LABEL_STYLE[label.toLowerCase()] ?? 'border-line bg-surface text-dim';
}

function ScenarioCard({ s, sym }: { s: Scenario; sym: string }) {
  const pos = s.returnPct >= 0;
  return (
    <div className={`p-3 rounded border ${labelStyle(s.label)}`}>
      <p className="text-[10px] font-medium uppercase tracking-wider mb-2 opacity-70">{s.label}</p>
      <p className="text-xl font-mono font-medium text-ink leading-none mb-1">
        {fmt(s.targetPrice, sym)}
      </p>
      <p className={`text-[12px] font-mono font-semibold ${pos ? 'text-up' : 'text-down'}`}>
        {pos ? '+' : ''}{s.returnPct.toFixed(1)}%
      </p>
      {s.probability != null && (
        <p className="text-[10px] text-dim mt-1.5">{(s.probability * 100).toFixed(0)}% prob</p>
      )}
    </div>
  );
}

export function ScenariosTab({ ticker }: { ticker: string }) {
  const [data,    setData]    = useState<ScenariosData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);

  useEffect(() => {
    setLoading(true); setError(null);
    fetchScenarios(ticker)
      .then(setData)
      .catch(() => setError('Failed to load scenarios'))
      .finally(() => setLoading(false));
  }, [ticker]);

  if (loading) return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-3">
        <Skeleton className="h-24" /><Skeleton className="h-24" /><Skeleton className="h-24" />
      </div>
      <Skeleton className="h-20" />
    </div>
  );
  if (error || !data) return <p className="text-sm text-dim">{error ?? 'No scenario data'}</p>;

  const sym = data.currencySymbol || '$';
  const mc  = data.monteCarlo;

  return (
    <div className="space-y-4 max-w-2xl">
      <div className="flex items-center gap-2">
        <span className="text-[10px] text-dim uppercase tracking-wider">Current</span>
        <span className="font-mono text-[12px] text-ink">{fmt(data.currentPrice, sym)}</span>
      </div>

      {data.scenarios?.length > 0 && (
        <div className="grid grid-cols-3 gap-3">
          {data.scenarios.map((s, i) => (
            <ScenarioCard key={i} s={s} sym={sym} />
          ))}
        </div>
      )}

      {mc && (
        <div className="border border-line rounded bg-surface">
          <div className="px-3 py-2 border-b border-line">
            <p className="text-[10px] text-dim uppercase tracking-wider">Monte Carlo — 1Y Simulation</p>
          </div>
          <div className="grid grid-cols-5 divide-x divide-line">
            {([
              { label: 'P5',     v: mc.percentile5  },
              { label: 'P25',    v: mc.percentile25 },
              { label: 'Median', v: mc.median       },
              { label: 'P75',    v: mc.percentile75 },
              { label: 'P95',    v: mc.percentile95 },
            ] as const).map(col => (
              <div key={col.label} className="px-3 py-2.5 text-center">
                <p className="text-[9px] text-dim mb-1">{col.label}</p>
                <p className="text-[11px] font-mono text-ink">{fmt(col.v, sym)}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
