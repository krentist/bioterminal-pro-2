import { useState, useEffect } from 'react';
import { fetchFlow } from '@/api';
import { SkeletonList } from '@/components/Skeleton';
import type { FlowEntry } from '@/types';

export function CCASFlowTab({ ticker }: { ticker: string }) {
  const isHK = ticker.toUpperCase().endsWith('.HK');

  const [flow, setFlow]         = useState<FlowEntry[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<string>('');

  useEffect(() => {
    if (!isHK) { setLoading(false); return; }
    setLoading(true); setError(null);
    fetchFlow(ticker)
      .then(data => {
        setFlow(data);
        if (data.length > 0) setSnapshot(data[0].snapshot_date);
      })
      .catch(() => setError('Failed to load CCASS ownership data'))
      .finally(() => setLoading(false));
  }, [ticker, isHK]);

  if (!isHK) {
    return (
      <div className="bg-elevated border border-line rounded-lg p-5 text-center space-y-1">
        <p className="text-sm text-dim">CCASS ownership data is only available for HK-listed stocks.</p>
        <p className="text-[10px] text-dim">
          CCASS (Central Clearing and Settlement System) tracks broker and institutional holdings
          in HKEX-listed securities.
        </p>
      </div>
    );
  }

  if (loading) return (
    <div className="space-y-3">
      <div className="bg-amber-900/20 border border-amber-700/30 rounded-lg px-4 py-2.5 text-[11px] text-amber-300/80">
        Fetching 12 months of CCASS ownership data from HKEX… this takes ~30 seconds.
      </div>
      <SkeletonList count={10} className="h-10" />
    </div>
  );

  if (error) return <p className="text-sm text-dim">{error}</p>;

  // Get available snapshot dates
  const snapshots = [...new Set(flow.map(f => f.snapshot_date))].sort((a, b) => b.localeCompare(a));
  const activeSnap = snapshot || snapshots[0] || '';
  const filtered = flow.filter(f => f.snapshot_date === activeSnap);

  // Sort by shares desc, take top 20
  const top20 = [...filtered].sort((a, b) => (b.shares ?? 0) - (a.shares ?? 0)).slice(0, 20);

  // For sparkline: get history of a participant across all snapshots
  const totalShares = top20.reduce((s, r) => s + (r.shares ?? 0), 0);

  return (
    <div className="space-y-5">

      {/* Explainer */}
      <div className="bg-sky-900/20 border border-sky-700/30 rounded-lg px-4 py-3 text-[11px] text-sky-300/80 leading-relaxed">
        <strong className="text-sky-300">What is CCASS?</strong>{' '}
        The Central Clearing and Settlement System tracks which brokers and institutions hold
        shares in HK-listed companies at end-of-month. Large increases in a participant's
        position may indicate institutional accumulation. Data covers end-of-month snapshots.
      </div>

      {/* Snapshot selector */}
      {snapshots.length > 1 && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[10px] text-dim">Snapshot:</span>
          {snapshots.map(s => (
            <button
              key={s}
              onClick={() => setSnapshot(s)}
              className={`text-[10px] px-2 py-0.5 rounded border transition-colors ${
                activeSnap === s ? 'bg-sky-600/20 border-sky-500/40 text-sky-300' : 'border-line text-dim hover:text-ink'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Summary */}
      {filtered.length > 0 && (
        <div className="flex gap-4 text-[11px]">
          <span className="text-dim">
            Top participants: <span className="text-ink font-semibold">{filtered.length}</span>
          </span>
          <span className="text-dim">
            Top 20 shares tracked: <span className="text-ink font-mono">{totalShares.toLocaleString()}</span>
          </span>
        </div>
      )}

      {/* Holdings table */}
      {!top20.length ? (
        <p className="text-sm text-dim">No CCASS data available for {activeSnap || 'this period'}.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-[11px]">
            <thead>
              <tr className="text-dim text-[10px] uppercase tracking-wider border-b border-line">
                <th className="text-left py-2 pr-3 font-medium">Participant ID</th>
                <th className="text-left py-2 pr-3 font-medium">Participant Name</th>
                <th className="text-right py-2 pr-3 font-medium">Shares</th>
                <th className="text-right py-2 font-medium">% Held</th>
              </tr>
            </thead>
            <tbody>
              {top20.map((row, i) => (
                <tr key={i} className="border-b border-line/50 last:border-0 row-hover">
                  <td className="py-2 pr-3 font-mono text-dim text-[10px]">{row.participant_id}</td>
                  <td className="py-2 pr-3 text-ink">{row.participant_name || '—'}</td>
                  <td className="py-2 pr-3 text-right font-mono text-ink">
                    {row.shares != null ? row.shares.toLocaleString() : '—'}
                  </td>
                  <td className={`py-2 text-right font-mono font-semibold ${
                    (row.percentage ?? 0) >= 5 ? 'text-up' : 'text-ink'
                  }`}>
                    {row.percentage != null ? `${row.percentage.toFixed(2)}%` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-[10px] text-dim">
        Source: HKEX CCASS Shareholding Disclosure. End-of-month snapshots for the past 12 months.
        Holdings reflect shares settled through CCASS participants, not total market float.
      </p>
    </div>
  );
}
