import { useState, useEffect } from 'react';
import { fetchRisk } from '@/api';
import { SkeletonList } from '@/components/Skeleton';
import { RestrictedPanel } from '@/components/PanelState';
import { AlertTriangle, AlertCircle, Info, ShieldAlert } from 'lucide-react';
import type { RiskData, RiskFactor } from '@/types';

const CATEGORY_INFO: Record<string, string> = {
  Financial:  'Cash runway, debt load, dilution risk, and revenue sustainability.',
  Pipeline:   'Clinical trial stage, single-asset concentration, and trial failure history.',
  Technical:  'Price trend, moving averages, and recent drawdown from highs.',
  Valuation:  'Whether the current price/revenue or EV/revenue multiple leaves room for disappointment.',
  Regulatory: 'Binary risk from FDA/NMPA approval decisions, advisory committees, and CRL letters.',
};

function severityLabel(s: number): { label: string; color: string; icon: React.ReactNode } {
  if (s >= 5) return { label: 'Critical', color: 'text-red-400 bg-red-500/10 border-red-500/30',  icon: <ShieldAlert size={11} /> };
  if (s >= 4) return { label: 'High',     color: 'text-orange-400 bg-orange-500/10 border-orange-500/30', icon: <AlertCircle size={11} /> };
  if (s >= 3) return { label: 'Medium',   color: 'text-amber-400 bg-amber-500/10 border-amber-500/30', icon: <AlertTriangle size={11} /> };
  return       { label: 'Low',     color: 'text-sky-400 bg-sky-500/10 border-sky-500/30', icon: <Info size={11} /> };
}

function overallColor(level: string) {
  if (level === 'CRITICAL') return 'text-red-400 bg-red-500/10 border-red-500/30';
  if (level === 'HIGH')     return 'text-orange-400 bg-orange-500/10 border-orange-500/30';
  if (level === 'MEDIUM')   return 'text-amber-400 bg-amber-500/10 border-amber-500/30';
  return 'text-sky-400 bg-sky-500/10 border-sky-500/30';
}

function RiskCard({ factor }: { factor: RiskFactor }) {
  const [open, setOpen] = useState(false);
  const sev = severityLabel(factor.severity);
  return (
    <div className="border border-line rounded-lg overflow-hidden">
      <button
        className="w-full flex items-start gap-3 p-3 text-left hover:bg-elevated/60 transition-colors"
        onClick={() => setOpen(o => !o)}
      >
        <span className={`flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded border shrink-0 mt-0.5 ${sev.color}`}>
          {sev.icon} {sev.label}
        </span>
        <div className="flex-1 min-w-0">
          <p className="text-[12px] font-medium text-ink leading-snug">{factor.title}</p>
          <p className="text-[10px] text-dim mt-0.5">{factor.category}</p>
        </div>
        <span className="text-dim text-xs shrink-0 mt-0.5">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="px-3 pb-3 space-y-2 border-t border-line pt-2">
          <p className="text-[11px] text-ink leading-relaxed">{factor.detail}</p>
          <p className="text-[10px] text-dim font-mono bg-elevated rounded px-2 py-1">{factor.evidence}</p>
        </div>
      )}
    </div>
  );
}

export function RiskTab({ ticker }: { ticker: string }) {
  const [data, setData]       = useState<RiskData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    setLoading(true); setError(null);
    fetchRisk(ticker)
      .then(setData)
      .catch(() => setError('Failed to load risk analysis'))
      .finally(() => setLoading(false));
  }, [ticker]);

  if (loading) return <SkeletonList count={5} className="h-14" />;
  if (error)   return <p className="text-sm text-dim">{error}</p>;
  if (!data)   return null;
  if (data.restricted) return <RestrictedPanel reason={data.restrictedReason} />;

  const { summary, factors } = data;

  // Group factors by category
  const grouped: Record<string, RiskFactor[]> = {};
  for (const f of factors) {
    (grouped[f.category] ??= []).push(f);
  }

  return (
    <div className="space-y-5">

      {/* Overall risk banner */}
      <div className={`flex items-center gap-3 rounded-lg border px-4 py-3 ${overallColor(summary.overall)}`}>
        <ShieldAlert size={18} />
        <div>
          <p className="text-sm font-semibold">Overall Risk: {summary.overall}</p>
          <p className="text-[11px] opacity-80">
            {summary.count} risk factor{summary.count !== 1 ? 's' : ''} identified
            {summary.critical > 0 ? ` · ${summary.critical} critical` : ''}
            {summary.high > 0 ? ` · ${summary.high} high` : ''}
          </p>
        </div>
      </div>

      {/* Disclaimer */}
      <p className="text-[10px] text-dim leading-relaxed">
        This is a systematic bear-case analysis based on publicly available data — not a
        recommendation to buy or sell. Factors are scored on severity 1–5. Click any row
        to see supporting evidence.
      </p>

      {/* Grouped risk cards */}
      {Object.entries(grouped).map(([category, items]) => (
        <div key={category} className="space-y-2">
          <div className="flex items-start gap-2">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-dim">{category}</p>
          </div>
          {CATEGORY_INFO[category] && (
            <p className="text-[10px] text-dim -mt-1">{CATEGORY_INFO[category]}</p>
          )}
          <div className="space-y-1.5">
            {items.map((f, i) => <RiskCard key={i} factor={f} />)}
          </div>
        </div>
      ))}

      {!factors.length && (
        <p className="text-sm text-dim text-center py-4">No significant risk factors identified.</p>
      )}
    </div>
  );
}
