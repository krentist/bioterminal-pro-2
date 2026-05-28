import { useState, useEffect } from 'react';
import { fetchScenarios } from '@/api';
import { Skeleton } from '@/components/Skeleton';
import { fmt } from '@/lib/utils';
import type { ScenariosData, Scenario } from '@/types';

const SCENARIO_COLORS: Record<string, string> = {
  bear:    'border-down/30 bg-down/5',
  base:    'border-line bg-surface',
  bull:    'border-up/30 bg-up/5',
  bearish: 'border-down/30 bg-down/5',
  bullish: 'border-up/30 bg-up/5',
};

function scenarioStyle(name: string): string {
  return SCENARIO_COLORS[name.toLowerCase()] ?? 'border-line bg-surface';
}

function ScenarioCard({ s, sym }: { s: Scenario; sym: string }) {
  const positive = (s.upside ?? 0) >= 0;
  return (
    <div className={`p-4 rounded-lg border ${scenarioStyle(s.name)}`}>
      <p className="text-[10px] text-dim uppercase tracking-wider mb-2">{s.name}</p>
      <p className="text-2xl font-mono font-light text-ink leading-none mb-1">
        {fmt(s.price, sym)}
      </p>
      <p className={`text-sm font-mono font-medium ${positive ? 'text-up' : 'text-down'}`}>
        {positive ? '+' : ''}{(s.upside ?? 0).toFixed(1)}%
      </p>
      {s.probability != null && (
        <p className="text-[10px] text-dim mt-2">{(s.probability * 100).toFixed(0)}% probability</p>
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
      <div className="grid grid-cols-3 gap-3"><Skeleton className="h-28" /><Skeleton className="h-28" /><Skeleton className="h-28" /></div>
      <Skeleton className="h-24" />
    </div>
  );
  if (error || !data) return <p className="text-sm text-dim">{error ?? 'No scenario data available'}</p>;

  const sym = data.currencySymbol || '$';

  return (
    <div className="space-y-4">
      <p className="text-[11px] text-dim">
        Current: <span className="font-mono text-ink">{fmt(data.currentPrice, sym)}</span>
      </p>

      {/* Scenario cards */}
      {data.scenarios?.length > 0 && (
        <div className={`grid gap-3 ${data.scenarios.length === 3 ? 'grid-cols-3' : 'grid-cols-2 sm:grid-cols-4'}`}>
          {data.scenarios.map((s, i) => (
            <ScenarioCard key={i} s={s} sym={sym} />
          ))}
        </div>
      )}

      {/* Monte Carlo */}
      {data.monteCarlo && (
        <div className="p-4 bg-surface rounded-lg border border-line">
          <p className="text-[10px] text-dim uppercase tracking-wider mb-4">Monte Carlo Percentiles</p>
          <div className="relative">
            {/* Bar track */}
            <div className="flex items-end gap-1 h-10 mb-2">
              {([
                { label: 'P10', v: data.monteCarlo.p10,  h: '25%'  },
                { label: 'P25', v: data.monteCarlo.p25,  h: '55%'  },
                { label: 'Mean',v: data.monteCarlo.mean, h: '100%' },
                { label: 'P75', v: data.monteCarlo.p75,  h: '60%'  },
                { label: 'P90', v: data.monteCarlo.p90,  h: '30%'  },
              ] as const).map(col => (
                <div key={col.label} className="flex-1 flex flex-col items-center justify-end gap-0.5">
                  <div
                    className="w-full rounded-sm bg-hi/40"
                    style={{ height: col.h }}
                  />
                </div>
              ))}
            </div>
            {/* Values */}
            <div className="grid grid-cols-5 gap-1 text-center">
              {[
                { label: 'P10',  v: data.monteCarlo.p10  },
                { label: 'P25',  v: data.monteCarlo.p25  },
                { label: 'Mean', v: data.monteCarlo.mean },
                { label: 'P75',  v: data.monteCarlo.p75  },
                { label: 'P90',  v: data.monteCarlo.p90  },
              ].map(col => (
                <div key={col.label}>
                  <p className="text-[9px] text-dim mb-0.5">{col.label}</p>
                  <p className="text-[10px] font-mono text-ink">{fmt(col.v, sym)}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
