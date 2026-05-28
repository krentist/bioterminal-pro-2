import { useState, useEffect } from 'react';
import { fetchBacktest } from '@/api';
import { SkeletonList } from '@/components/Skeleton';
import { fmtPct } from '@/lib/utils';
import type { BacktestData, EquityPoint } from '@/types';

const PERIODS = ['1y', '2y', '5y'] as const;

function MetricRow({ label, value, color = 'text-ink', tooltip }: { label: string; value: string; color?: string; tooltip?: string }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-line last:border-0 group relative">
      <span className="text-[11px] text-dim flex items-center gap-1">
        {label}
        {tooltip && (
          <span className="hidden group-hover:block absolute left-0 top-full mt-1 bg-black border border-line rounded px-2 py-1 text-[10px] text-ink z-10 w-52 whitespace-normal leading-relaxed shadow-xl">
            {tooltip}
          </span>
        )}
      </span>
      <span className={`text-[12px] font-mono font-semibold ${color}`}>{value}</span>
    </div>
  );
}

function EquityChart({ points }: { points: EquityPoint[] }) {
  if (points.length < 2) return null;
  const values = points.map(p => p.value);
  const minV = Math.min(...values);
  const maxV = Math.max(...values);
  const range = maxV - minV || 1;
  const w = 600;
  const h = 100;
  const pts = points.map((p, i) => {
    const x = (i / (points.length - 1)) * w;
    const y = h - ((p.value - minV) / range) * (h - 10) - 5;
    return `${x},${y}`;
  });
  const last = values[values.length - 1];
  const first = values[0];
  const isUp = last >= first;

  return (
    <div className="space-y-1">
      <p className="text-[11px] text-dim uppercase tracking-wider">Equity Curve</p>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-24" preserveAspectRatio="none">
        <polyline
          points={pts.join(' ')}
          fill="none"
          stroke={isUp ? '#4ade80' : '#f87171'}
          strokeWidth="1.5"
          vectorEffect="non-scaling-stroke"
        />
        {/* Fill area */}
        <polygon
          points={`0,${h} ${pts.join(' ')} ${w},${h}`}
          fill={isUp ? 'rgba(74,222,128,0.08)' : 'rgba(248,113,113,0.08)'}
        />
      </svg>
      <div className="flex justify-between text-[9px] text-dim font-mono">
        <span>{points[0]?.date}</span>
        <span>{points[points.length - 1]?.date}</span>
      </div>
    </div>
  );
}

export function BacktestTab({ ticker }: { ticker: string }) {
  const [period, setPeriod]   = useState<typeof PERIODS[number]>('2y');
  const [data, setData]       = useState<BacktestData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    setLoading(true); setError(null);
    fetchBacktest(ticker, period)
      .then(setData)
      .catch(() => setError('Failed to run backtest'))
      .finally(() => setLoading(false));
  }, [ticker, period]);

  return (
    <div className="space-y-5">

      {/* Strategy explainer */}
      <div className="bg-sky-900/20 border border-sky-700/30 rounded-lg px-4 py-3 text-[11px] text-sky-300/80 leading-relaxed">
        <strong className="text-sky-300">Strategy:</strong>{' '}
        RSI mean-reversion + MACD momentum combo. Buys when RSI &lt; 35 <em>and</em> MACD
        histogram turns positive. Exits when RSI &gt; 65 or MACD turns negative, or after
        20 trading days maximum. Assumes 0.1% commission per trade.{' '}
        <strong>Past performance does not predict future results.</strong>
      </div>

      {/* Period selector */}
      <div className="flex gap-1.5">
        {PERIODS.map(p => (
          <button
            key={p}
            onClick={() => setPeriod(p)}
            className={`text-[11px] px-3 py-1 rounded border transition-colors ${
              period === p
                ? 'bg-sky-600/20 border-sky-500/40 text-sky-300'
                : 'border-line text-dim hover:text-ink hover:border-dim'
            }`}
          >
            {p}
          </button>
        ))}
      </div>

      {loading && <SkeletonList count={3} className="h-12" />}
      {error   && <p className="text-sm text-dim">{error}</p>}

      {!loading && !error && data && (
        <>
          {/* Equity curve */}
          {data.equityCurve?.length > 1 && <EquityChart points={data.equityCurve} />}

          {/* Performance metrics */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6">
            <div>
              <p className="text-[10px] uppercase tracking-wider text-dim mb-1">Returns</p>
              <MetricRow
                label="Total return"
                value={data.metrics.total_return_pct != null ? fmtPct(data.metrics.total_return_pct) : '—'}
                color={data.metrics.total_return_pct >= 0 ? 'text-up' : 'text-down'}
              />
              <MetricRow
                label="CAGR"
                value={data.metrics.cagr_pct != null ? fmtPct(data.metrics.cagr_pct) : '—'}
                color={data.metrics.cagr_pct >= 0 ? 'text-up' : 'text-down'}
              />
              <MetricRow
                label="vs Buy & Hold"
                value={data.metrics.bh_return_pct != null ? fmtPct(data.metrics.bh_return_pct) : '—'}
                color="text-dim"
              />
              <MetricRow
                label="Alpha"
                value={data.metrics.alpha_pct != null ? fmtPct(data.metrics.alpha_pct) : '—'}
                color={data.metrics.alpha_pct >= 0 ? 'text-up' : 'text-down'}
                tooltip="Strategy return minus buy-and-hold return. Positive = strategy added value."
              />
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-wider text-dim mb-1">Risk</p>
              <MetricRow
                label="Sharpe ratio"
                value={data.metrics.sharpe_ratio?.toFixed(2) ?? '—'}
                color={data.metrics.sharpe_ratio >= 1 ? 'text-up' : data.metrics.sharpe_ratio >= 0 ? 'text-ink' : 'text-down'}
                tooltip="Return per unit of risk. >1.0 is considered good; >2.0 is excellent."
              />
              <MetricRow
                label="Max drawdown"
                value={data.metrics.max_drawdown_pct != null ? fmtPct(data.metrics.max_drawdown_pct) : '—'}
                color="text-down"
                tooltip="Largest peak-to-trough decline during the period."
              />
              <MetricRow label="Trades" value={String(data.metrics.n_trades ?? '—')} />
              <MetricRow
                label="Win rate"
                value={data.metrics.win_rate_pct != null ? fmtPct(data.metrics.win_rate_pct) : '—'}
                color={data.metrics.win_rate_pct >= 50 ? 'text-up' : 'text-down'}
              />
            </div>
          </div>

          {/* Trade log */}
          {data.trades?.length > 0 && (
            <div className="space-y-2">
              <p className="text-[11px] text-dim uppercase tracking-wider">
                Recent Trades (last {data.trades.length})
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-[10px]">
                  <thead>
                    <tr className="text-dim border-b border-line">
                      <th className="text-left py-1.5 pr-3 font-medium">Entry</th>
                      <th className="text-left py-1.5 pr-3 font-medium">Exit</th>
                      <th className="text-right py-1.5 pr-3 font-medium">Entry $</th>
                      <th className="text-right py-1.5 pr-3 font-medium">Exit $</th>
                      <th className="text-right py-1.5 pr-3 font-medium">P&L %</th>
                      <th className="text-right py-1.5 font-medium">Days</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.trades.slice(-15).reverse().map((t, i) => (
                      <tr key={i} className="border-b border-line/50 last:border-0">
                        <td className="py-1.5 pr-3 font-mono text-dim">{t.entryDate}</td>
                        <td className="py-1.5 pr-3 font-mono text-dim">{t.exitDate}</td>
                        <td className="py-1.5 pr-3 font-mono text-right text-ink">{t.entryPrice?.toFixed(2)}</td>
                        <td className="py-1.5 pr-3 font-mono text-right text-ink">{t.exitPrice?.toFixed(2)}</td>
                        <td className={`py-1.5 pr-3 font-mono text-right font-semibold ${t.pnlPct >= 0 ? 'text-up' : 'text-down'}`}>
                          {fmtPct(t.pnlPct)}
                        </td>
                        <td className="py-1.5 font-mono text-right text-dim">{t.holdDays}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
