import { useState, useEffect } from 'react';
import { fetchPeers } from '@/api';
import { SkeletonList } from '@/components/Skeleton';
import { fmtBig, fmtMultiple, fmtPctFrac } from '@/lib/utils';
import type { PeerRow } from '@/types';

const CCY: Record<string, string> = { USD: '$', HKD: 'HK$', CNY: '¥', EUR: '€', GBP: '£' };

function sym(c: string): string { return CCY[c] ?? '$'; }

export function PeersTab({ ticker, onSelect }: { ticker: string; onSelect?: (t: string) => void }) {
  const [rows,    setRows]    = useState<PeerRow[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);

  useEffect(() => {
    setLoading(true); setError(null); setRows(null);
    fetchPeers(ticker)
      .then(d => setRows(d.peers ?? []))
      .catch(() => setError('Failed to load peer comparables'))
      .finally(() => setLoading(false));
  }, [ticker]);

  if (loading) return <SkeletonList count={6} className="h-9" />;
  if (error)   return <p className="text-sm text-dim">{error}</p>;
  if (!rows || rows.length === 0) return <p className="text-sm text-dim">No peer data available.</p>;

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto">
        <table className="w-full text-[11px] border-separate border-spacing-y-0">
          <thead>
            <tr className="text-dim text-[9px] uppercase tracking-wider">
              <th className="text-left py-2 pr-3 font-medium border-b border-line">Ticker</th>
              <th className="text-right py-2 pr-3 font-medium border-b border-line whitespace-nowrap">Mkt Cap</th>
              <th className="text-right py-2 pr-3 font-medium border-b border-line whitespace-nowrap">EV/Rev</th>
              <th className="text-right py-2 pr-3 font-medium border-b border-line whitespace-nowrap">P/S</th>
              <th className="text-right py-2 pr-3 font-medium border-b border-line whitespace-nowrap">Rev Gr.</th>
              <th className="text-right py-2 pr-3 font-medium border-b border-line whitespace-nowrap">Gross M.</th>
              <th className="text-right py-2 font-medium border-b border-line whitespace-nowrap">Target ↑</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr
                key={r.ticker}
                className={`transition-colors ${r.isSubject ? 'bg-hi/5' : 'row-hover'}`}
              >
                <td className="py-2 pr-3">
                  <button
                    onClick={() => onSelect?.(r.ticker)}
                    disabled={!onSelect || r.isSubject}
                    className={`text-left ${r.isSubject ? 'cursor-default' : 'hover:text-hi'} ${onSelect && !r.isSubject ? 'cursor-pointer' : ''}`}
                    title={r.name}
                  >
                    <span className={`font-mono font-semibold ${r.isSubject ? 'text-hi' : 'text-ink'}`}>{r.ticker}</span>
                    <span className="block text-[9px] text-dim truncate max-w-[120px]">{r.name}</span>
                  </button>
                </td>
                <td className="py-2 pr-3 text-right font-mono text-ink whitespace-nowrap">{fmtBig(r.marketCap, sym(r.currency))}</td>
                <td className="py-2 pr-3 text-right font-mono text-dim">{fmtMultiple(r.evToRevenue)}</td>
                <td className="py-2 pr-3 text-right font-mono text-dim">{fmtMultiple(r.psRatio)}</td>
                <td className={`py-2 pr-3 text-right font-mono ${r.revenueGrowth == null ? 'text-dim' : r.revenueGrowth >= 0 ? 'text-up' : 'text-down'}`}>
                  {fmtPctFrac(r.revenueGrowth)}
                </td>
                <td className="py-2 pr-3 text-right font-mono text-dim">{fmtPctFrac(r.grossMargin)}</td>
                <td className={`py-2 text-right font-mono ${r.targetUpside == null ? 'text-dim' : r.targetUpside >= 0 ? 'text-up' : 'text-down'}`}>
                  {fmtPctFrac(r.targetUpside)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[10px] text-dim leading-relaxed">
        Peers are a <strong>curated comparable set</strong> (region-matched biotech), not an
        exhaustive screen. The highlighted row is the current ticker. Multiples come from
        yfinance and are blank for pre-revenue names (no meaningful revenue-based ratio).
        {onSelect && ' Click a peer ticker to load it.'}
      </p>
    </div>
  );
}
