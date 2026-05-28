import { useState, useEffect } from 'react';
import { fetchDCF } from '@/api';
import { Skeleton } from '@/components/Skeleton';
import { fmt } from '@/lib/utils';
import type { DCFData } from '@/types';

function camelToLabel(key: string): string {
  return key
    .replace(/([A-Z])/g, ' $1')
    .replace(/_/g, ' ')
    .trim()
    .toLowerCase()
    .replace(/^./, c => c.toUpperCase());
}

function fmtDcfValue(key: string, value: number | string | null): string {
  if (value == null) return '—';
  if (typeof value === 'string') return value;
  const k = key.toLowerCase();
  if (k.includes('rate') || k.includes('growth') || k.includes('margin') || k.includes('wacc')) {
    return `${(value * 100).toFixed(1)}%`;
  }
  return value.toFixed(2);
}

export function DCFTab({ ticker }: { ticker: string }) {
  const [data,    setData]    = useState<DCFData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);

  useEffect(() => {
    setLoading(true); setError(null);
    fetchDCF(ticker)
      .then(setData)
      .catch(() => setError('Failed to load DCF valuation'))
      .finally(() => setLoading(false));
  }, [ticker]);

  if (loading) return (
    <div className="space-y-3 max-w-sm">
      <Skeleton className="h-32" />
      <Skeleton className="h-44" />
    </div>
  );
  if (error || !data) return <p className="text-sm text-dim">{error ?? 'No DCF data available'}</p>;

  const sym      = data.currencySymbol || '$';
  const positive = (data.upside ?? 0) >= 0;

  const dcfEntries = Object.entries(data.dcf ?? {})
    .filter(([_, v]) => v != null && v !== '');

  return (
    <div className="space-y-4 max-w-sm">
      {/* Valuation card */}
      <div className="p-4 bg-surface rounded-lg border border-line">
        <p className="text-[10px] text-dim uppercase tracking-wider mb-3">Intrinsic Value — DCF</p>
        <div className="flex items-end justify-between">
          <div>
            <p className="text-3xl font-mono font-light text-ink leading-none">
              {fmt(data.impliedSharePrice, sym)}
            </p>
            <p className="text-[11px] text-dim mt-1">Implied share price</p>
          </div>
          <div className={`text-right ${positive ? 'text-up' : 'text-down'}`}>
            <p className="text-xl font-mono font-medium leading-none">
              {positive ? '+' : ''}{(data.upside ?? 0).toFixed(1)}%
            </p>
            <p className="text-[10px] text-dim mt-1">vs. current</p>
          </div>
        </div>

        {/* Upside bar */}
        <div className="mt-4 bg-elevated rounded-full h-1 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${positive ? 'bg-up' : 'bg-down'}`}
            style={{ width: `${Math.min(100, Math.abs(data.upside ?? 0))}%` }}
          />
        </div>
      </div>

      {/* Assumptions */}
      {dcfEntries.length > 0 && (
        <div className="p-4 bg-surface rounded-lg border border-line">
          <p className="text-[10px] text-dim uppercase tracking-wider mb-3">Model Assumptions</p>
          <div className="space-y-2">
            {dcfEntries.map(([key, value]) => (
              <div key={key} className="flex justify-between items-center py-0.5 border-b border-line/50 last:border-0">
                <span className="text-[11px] text-dim">{camelToLabel(key)}</span>
                <span className="text-[11px] font-mono text-ink">{fmtDcfValue(key, value)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
