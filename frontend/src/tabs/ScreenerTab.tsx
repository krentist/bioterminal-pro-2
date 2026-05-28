import { useState, useEffect, useCallback } from 'react';
import { fetchScreen } from '@/api';
import { SkeletonList } from '@/components/Skeleton';
import { fmtBig, fmtPctFrac, timeAgo } from '@/lib/utils';
import type { ScreenerData, ScreenerRow } from '@/types';

const DIM_INFO: Record<string, string> = {
  Momentum: 'Price vs 50-day SMA, RSI, and 3-month return. High = stock trending up.',
  Value:    'P/S and EV/Revenue ratios. High = cheaper relative to revenue.',
  Pipeline: 'Phase-weighted trial count and catalysts within 12 months. High = strong clinical pipeline.',
  Quality:  'Revenue growth, profit margin, and cash-to-market-cap ratio. High = financially healthy.',
  Technical:'MACD histogram, Bollinger Band position, and volume spike. High = technically constructive.',
};

function ScoreBar({ score, max = 20 }: { score: number; max?: number }) {
  const pct = Math.min(Math.max((score / max) * 100, 0), 100);
  const color = pct >= 70 ? 'bg-green-500/70' : pct >= 40 ? 'bg-amber-500/70' : 'bg-red-500/60';
  return (
    <div className="flex items-center gap-1.5">
      <div className="flex-1 bg-elevated rounded-sm h-1.5 overflow-hidden">
        <div className={`h-full rounded-sm ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[10px] font-mono text-dim w-5 text-right">{score.toFixed(0)}</span>
    </div>
  );
}

function topDimension(row: ScreenerRow): string {
  const dims = { Momentum: row.momentum, Value: row.value, Pipeline: row.pipeline, Quality: row.quality, Technical: row.technical };
  return Object.entries(dims).sort((a, b) => b[1] - a[1])[0][0];
}

export function ScreenerTab({ onTickerSelect }: { onTickerSelect?: (t: string) => void }) {
  const [region, setRegion]   = useState<'HK' | 'US'>('HK');
  const [data, setData]       = useState<ScreenerData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true); setError(null);
    fetchScreen(region)
      .then(setData)
      .catch(() => setError('Screener failed — this may take 30–60s on first load'))
      .finally(() => setLoading(false));
  }, [region]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-5">

      {/* Explainer */}
      <div className="bg-sky-900/20 border border-sky-700/30 rounded-lg px-4 py-3 text-[11px] text-sky-300/80 leading-relaxed">
        <strong className="text-sky-300">Alpha Screener</strong>{' '}
        Scores each stock across 5 dimensions (0–20 pts each, max 100). Results are cached
        for 30 minutes. First load may take 30–60 seconds while fetching data for{' '}
        {region === 'HK' ? '26 GBA biotech' : '20 US biotech'} stocks in parallel.
      </div>

      {/* Region toggle */}
      <div className="flex items-center gap-3">
        <div className="flex gap-1">
          {(['HK', 'US'] as const).map(r => (
            <button
              key={r}
              onClick={() => setRegion(r)}
              className={`text-[11px] px-3 py-1 rounded border transition-colors ${
                region === r
                  ? 'bg-sky-600/20 border-sky-500/40 text-sky-300'
                  : 'border-line text-dim hover:text-ink'
              }`}
            >
              {r === 'HK' ? 'HK / GBA' : 'US Biotech'}
            </button>
          ))}
        </div>
        {data?.cachedAt && (
          <span className="text-[10px] text-dim ml-auto">Updated {timeAgo(data.cachedAt)}</span>
        )}
        <button
          onClick={load}
          className="text-[10px] text-dim hover:text-ink border border-line rounded px-2 py-0.5"
        >
          Refresh
        </button>
      </div>

      {loading && (
        <div className="space-y-2">
          <p className="text-[11px] text-dim animate-pulse">Scoring {region === 'HK' ? '26' : '20'} stocks… this takes ~30s on first load</p>
          <SkeletonList count={8} className="h-10" />
        </div>
      )}
      {error && <p className="text-sm text-down">{error}</p>}

      {!loading && !error && data && (
        <>
          {/* Dimension key */}
          <div className="flex flex-wrap gap-2">
            {Object.entries(DIM_INFO).map(([dim, desc]) => (
              <div key={dim} className="relative group cursor-help">
                <span className="text-[10px] bg-elevated border border-line rounded px-2 py-0.5 text-dim">
                  {dim} <span className="text-[9px]">?</span>
                </span>
                <div className="hidden group-hover:block absolute bottom-full mb-1 left-0 bg-black border border-line rounded px-2 py-1.5 text-[10px] w-52 z-10 shadow-xl text-ink leading-relaxed">
                  {desc}
                </div>
              </div>
            ))}
          </div>

          {/* Ranked table */}
          <div className="overflow-x-auto">
            <table className="w-full text-[11px]">
              <thead>
                <tr className="text-dim text-[10px] uppercase tracking-wider border-b border-line">
                  <th className="text-left py-2 pr-3 font-medium w-6">#</th>
                  <th className="text-left py-2 pr-3 font-medium">Ticker</th>
                  <th className="text-right py-2 pr-3 font-medium">Score</th>
                  <th className="text-left py-2 pr-3 font-medium min-w-[80px]">Momentum</th>
                  <th className="text-left py-2 pr-3 font-medium min-w-[80px]">Value</th>
                  <th className="text-left py-2 pr-3 font-medium min-w-[80px]">Pipeline</th>
                  <th className="text-left py-2 pr-3 font-medium min-w-[80px]">Quality</th>
                  <th className="text-left py-2 font-medium min-w-[80px]">Technical</th>
                </tr>
              </thead>
              <tbody>
                {data.results.map(row => {
                  const top = topDimension(row);
                  return (
                    <tr
                      key={row.ticker}
                      className="row-hover border-b border-line/50 last:border-0 cursor-pointer"
                      onClick={() => onTickerSelect?.(row.ticker)}
                    >
                      <td className="py-2.5 pr-3 text-dim font-mono">{row.rank}</td>
                      <td className="py-2.5 pr-3">
                        <p className="font-semibold text-hi">{row.ticker}</p>
                        <p className="text-[9px] text-dim">{top} leader</p>
                      </td>
                      <td className="py-2.5 pr-3 text-right">
                        <span className={`font-mono font-bold text-sm ${row.totalScore >= 60 ? 'text-up' : row.totalScore < 40 ? 'text-down' : 'text-ink'}`}>
                          {row.totalScore.toFixed(0)}
                        </span>
                        <span className="text-dim text-[9px]">/100</span>
                      </td>
                      <td className="py-2.5 pr-3"><ScoreBar score={row.momentum} /></td>
                      <td className="py-2.5 pr-3"><ScoreBar score={row.value} /></td>
                      <td className="py-2.5 pr-3"><ScoreBar score={row.pipeline} /></td>
                      <td className="py-2.5 pr-3"><ScoreBar score={row.quality} /></td>
                      <td className="py-2.5"><ScoreBar score={row.technical} /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <p className="text-[10px] text-dim">
            Scores are relative, not absolute recommendations. Click a ticker to load it in the terminal.
          </p>
        </>
      )}
    </div>
  );
}
