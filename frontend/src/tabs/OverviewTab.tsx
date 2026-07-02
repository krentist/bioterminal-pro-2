import { useState, useEffect } from 'react';
import { ChartPane } from '@/components/ChartPane';
import { Skeleton } from '@/components/Skeleton';
import { fmt, timeAgo } from '@/lib/utils';
import { fetchConfidence, fetchTrials, fetchDCF, fetchRisk, fetchNews } from '@/api';
import { useChartData } from '@/hooks/useChartData';
import { useIsDark } from '@/hooks/useIsDark';
import type { ConfidenceData, Trial, DCFData, RiskData, NewsItem, AppTab } from '@/types';

const RANGES = ['1D', '1W', '1M', '3M', '1Y', '5Y'];

interface Props {
  ticker:      string;
  onOpenWindow: (panelId: AppTab) => void;
}

// ── Panel shell ──────────────────────────────────────────────────────────────

function Panel({
  label, onFull, children, className = '',
}: {
  label: string;
  onFull: () => void;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`border border-line rounded-lg bg-surface flex flex-col overflow-hidden ${className}`}>
      <div className="flex items-center justify-between px-3 py-2 border-b border-line flex-none">
        <span className="text-[9px] uppercase tracking-widest text-dim font-semibold">{label}</span>
        <button
          onClick={onFull}
          className="text-[9px] text-hi hover:opacity-70 transition-opacity font-medium"
        >
          Full view →
        </button>
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto">
        {children}
      </div>
    </div>
  );
}

// ── Signal panel ─────────────────────────────────────────────────────────────

const SIGNAL_STYLES: Record<string, { text: string; badge: string; bar: string }> = {
  BULLISH: { text: 'text-up',   badge: 'text-up bg-up/10 border-up/30',     bar: 'bg-up'   },
  BEARISH: { text: 'text-down', badge: 'text-down bg-down/10 border-down/30', bar: 'bg-down' },
  NEUTRAL: { text: 'text-dim',  badge: 'text-dim bg-elevated border-line',   bar: 'bg-hi'   },
};

function SignalPanel({ ticker, onFull }: { ticker: string; onFull: () => void }) {
  const [data,    setData]    = useState<ConfidenceData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchConfidence(ticker).then(setData).catch(() => {}).finally(() => setLoading(false));
  }, [ticker]);

  const s = data ? (SIGNAL_STYLES[data.signal] ?? SIGNAL_STYLES.NEUTRAL) : null;

  return (
    <Panel label="ML Signal" onFull={onFull}>
      <div className="px-3 py-3">
        {loading ? (
          <div className="space-y-2.5">
            <Skeleton className="h-10 w-28" />
            <Skeleton className="h-2" />
            <Skeleton className="h-6 w-20" />
            <Skeleton className="h-3" />
            <Skeleton className="h-3" />
            <Skeleton className="h-3" />
          </div>
        ) : data && s ? (
          <>
            <div className="flex items-end gap-2 mb-2">
              <span className={`text-5xl font-mono font-light leading-none ${s.text}`}>
                {data.score}
              </span>
              <span className="text-[9px] text-dim mb-1.5">/ 100</span>
              <span className={`ml-auto text-[9px] font-semibold tracking-widest px-2 py-0.5 rounded border ${s.badge}`}>
                {data.signal}
              </span>
            </div>
            <div className="bg-elevated rounded-full h-1 overflow-hidden mb-3">
              <div className={`h-full rounded-full ${s.bar}`} style={{ width: `${data.score}%` }} />
            </div>
            <div className="space-y-1.5">
              {data.factors?.slice(0, 4).map((f, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className="text-[9px] text-dim w-24 truncate flex-none">{f.name}</span>
                  <div className="flex-1 bg-elevated rounded-full h-0.5 overflow-hidden">
                    <div
                      className={`h-full rounded-full ${f.score >= 50 ? 'bg-up' : 'bg-down'}`}
                      style={{ width: `${f.score}%` }}
                    />
                  </div>
                  <span className={`text-[9px] font-mono w-6 text-right flex-none ${f.score >= 50 ? 'text-up' : 'text-down'}`}>
                    {f.score}
                  </span>
                </div>
              ))}
            </div>
          </>
        ) : (
          <p className="text-[11px] text-dim">No signal data</p>
        )}
      </div>
    </Panel>
  );
}

// ── Pipeline panel ────────────────────────────────────────────────────────────

function phaseStyle(phase: string | null): string {
  const p = (phase ?? '').toUpperCase().replace(/PHASE\s*/i, '').trim();
  const m: Record<string, string> = {
    'I':   'text-sky-400 bg-sky-500/10 border-sky-500/20',
    '1':   'text-sky-400 bg-sky-500/10 border-sky-500/20',
    'II':  'text-amber-400 bg-amber-500/10 border-amber-500/20',
    '2':   'text-amber-400 bg-amber-500/10 border-amber-500/20',
    'III': 'text-orange-400 bg-orange-500/10 border-orange-500/20',
    '3':   'text-orange-400 bg-orange-500/10 border-orange-500/20',
    'IV':  'text-purple-400 bg-purple-500/10 border-purple-500/20',
    '4':   'text-purple-400 bg-purple-500/10 border-purple-500/20',
  };
  return m[p] ?? 'text-dim bg-elevated border-line';
}

function statusDot(status: string | null): string {
  const s = (status ?? '').toUpperCase();
  if (s.includes('RECRUIT') || s === 'ACTIVE' || s.includes('ONGOING')) return 'text-up';
  if (s.includes('TERMINAT') || s.includes('SUSPEND') || s.includes('WITHDRAWN')) return 'text-down';
  return 'text-dim';
}

function PipelinePanel({ ticker, onFull }: { ticker: string; onFull: () => void }) {
  const [trials,  setTrials]  = useState<Trial[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchTrials(ticker).then(d => setTrials(d.trials ?? [])).catch(() => {}).finally(() => setLoading(false));
  }, [ticker]);

  return (
    <Panel label="Clinical Pipeline" onFull={onFull}>
      <div className="px-3 py-2">
        {loading ? (
          <div className="space-y-2 pt-1">
            {[0, 1, 2, 3].map(i => <Skeleton key={i} className="h-9" />)}
          </div>
        ) : trials.length === 0 ? (
          <p className="text-[11px] text-dim py-1">No trials found for {ticker}</p>
        ) : (
          <>
            <p className="text-[10px] text-dim mb-2 pt-1">
              {trials.length} trial{trials.length !== 1 ? 's' : ''} registered
            </p>
            <div>
              {trials.slice(0, 5).map((t, i) => (
                <div key={i} className="flex items-start gap-2 py-1.5 border-b border-line/40 last:border-0">
                  {t.phase ? (
                    <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded border flex-none leading-none ${phaseStyle(t.phase)}`}>
                      {t.phase.replace(/Phase\s+/i, 'Ph')}
                    </span>
                  ) : (
                    <span className="w-6 flex-none" />
                  )}
                  <span className="text-[10px] text-ink leading-snug flex-1 line-clamp-2 min-w-0">
                    {t.title || '—'}
                  </span>
                  <span className={`text-[9px] flex-none mt-0.5 font-medium ${statusDot(t.status)}`}>
                    {t.status?.split(/\s+/)[0] ?? '—'}
                  </span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </Panel>
  );
}

// ── DCF / rNPV panel ──────────────────────────────────────────────────────────

function ValuationPanel({ ticker, onFull }: { ticker: string; onFull: () => void }) {
  const [data,    setData]    = useState<DCFData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchDCF(ticker).then(setData).catch(() => {}).finally(() => setLoading(false));
  }, [ticker]);

  const sym    = data?.currencySymbol ?? '$';
  const upside = data?.upside ?? null;
  const pos    = (upside ?? 0) >= 0;
  const method = data?.valuationMethod === 'rNPV' ? 'rNPV' : 'DCF';

  return (
    <Panel label={`${method} Valuation`} onFull={onFull}>
      <div className="px-3 py-3">
        {loading ? (
          <div className="space-y-2.5">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-10 w-32" />
            <Skeleton className="h-6 w-20" />
            <Skeleton className="h-2" />
          </div>
        ) : data ? (
          <>
            <p className="text-[9px] text-dim uppercase tracking-widest mb-1.5">Intrinsic Value</p>
            <p className="text-4xl font-mono font-light text-ink leading-none mb-2">
              {fmt(data.impliedSharePrice, sym)}
            </p>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-[10px] text-dim">vs. current</span>
              {upside !== null && (
                <span className={`text-xl font-mono font-semibold leading-none ${pos ? 'text-up' : 'text-down'}`}>
                  {pos ? '+' : ''}{upside.toFixed(1)}%
                </span>
              )}
            </div>
            {upside !== null && (
              <div className="bg-elevated rounded-full h-1 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${pos ? 'bg-up' : 'bg-down'}`}
                  style={{ width: `${Math.min(100, Math.abs(upside))}%` }}
                />
              </div>
            )}
            {data.rnpvTotal != null && (
              <p className="text-[9px] text-dim mt-2">
                Pipeline rNPV: {fmt(data.rnpvTotal, sym)}
              </p>
            )}
          </>
        ) : (
          <p className="text-[11px] text-dim">No valuation data</p>
        )}
      </div>
    </Panel>
  );
}

// ── Risk panel ────────────────────────────────────────────────────────────────

const RISK_BADGE: Record<string, string> = {
  LOW:      'text-up bg-up/10 border-up/30',
  MEDIUM:   'text-amber-400 bg-amber-500/10 border-amber-500/20',
  HIGH:     'text-orange-400 bg-orange-500/10 border-orange-500/20',
  CRITICAL: 'text-down bg-down/10 border-down/30',
};

function RiskPanel({ ticker, onFull }: { ticker: string; onFull: () => void }) {
  const [data,    setData]    = useState<RiskData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchRisk(ticker).then(setData).catch(() => {}).finally(() => setLoading(false));
  }, [ticker]);

  return (
    <Panel label="Bear Case Risk" onFull={onFull}>
      <div className="px-3 py-3">
        {loading ? (
          <div className="space-y-2.5">
            <Skeleton className="h-6 w-24" />
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
          </div>
        ) : data ? (
          <>
            <div className="flex items-center gap-2 mb-2.5">
              <span className={`text-[9px] font-semibold tracking-widest px-2 py-0.5 rounded border ${RISK_BADGE[data.summary.overall] ?? 'text-dim bg-elevated border-line'}`}>
                {data.summary.overall}
              </span>
              <span className="text-[10px] text-dim">{data.summary.count} factors identified</span>
            </div>
            <div className="flex items-center gap-3 text-[10px] mb-3">
              <span className="text-down font-mono">{data.summary.critical} critical</span>
              <span className="text-orange-400 font-mono">{data.summary.high} high</span>
            </div>
            <div className="space-y-2">
              {data.factors.slice(0, 2).map((f, i) => (
                <div key={i} className="p-2 rounded bg-elevated/60">
                  <p className="text-[10px] font-medium text-ink leading-snug">{f.title}</p>
                  <p className="text-[9px] text-dim mt-0.5 line-clamp-2 leading-snug">{f.detail}</p>
                </div>
              ))}
            </div>
          </>
        ) : (
          <p className="text-[11px] text-dim">No risk data</p>
        )}
      </div>
    </Panel>
  );
}

// ── News panel ────────────────────────────────────────────────────────────────

function NewsPanel({ ticker, onFull }: { ticker: string; onFull: () => void }) {
  const [news,    setNews]    = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchNews(ticker).then(setNews).catch(() => {}).finally(() => setLoading(false));
  }, [ticker]);

  return (
    <Panel label="Recent News" onFull={onFull}>
      <div className="px-3 py-1">
        {loading ? (
          <div className="space-y-3 py-2">
            {[0, 1, 2, 3].map(i => <Skeleton key={i} className="h-11" />)}
          </div>
        ) : news.length === 0 ? (
          <p className="text-[11px] text-dim py-2">No recent news for {ticker}</p>
        ) : (
          news.slice(0, 5).map((item, i) => (
            <a
              key={i}
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="block py-2 border-b border-line/40 last:border-0 hover:opacity-75 transition-opacity"
            >
              <p className="text-[10px] text-ink leading-snug line-clamp-2">{item.title}</p>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-[9px] text-dim truncate flex-1">{item.publisher}</span>
                <span className="text-[9px] text-dim flex-none">{timeAgo(item.publishedAt)}</span>
              </div>
            </a>
          ))
        )}
      </div>
    </Panel>
  );
}

// ── Main export ───────────────────────────────────────────────────────────────

export function OverviewTab({ ticker, onOpenWindow }: Props) {
  const [range, setRange] = useState('3M');
  const { bars, loading: chartLoading } = useChartData(ticker, range);
  const dark = useIsDark();

  return (
    <div className="grid grid-cols-3 gap-3">
      {/* Row 1 */}
      <SignalPanel   ticker={ticker} onFull={() => onOpenWindow('confidence')} />
      <PipelinePanel ticker={ticker} onFull={() => onOpenWindow('pipeline')}   />

      {/* Chart spans both rows in col 3 */}
      <div className="row-span-2 border border-line rounded-lg bg-surface overflow-hidden flex flex-col">
        <div className="flex items-center justify-between px-3 py-2 border-b border-line flex-none">
          <span className="text-[9px] uppercase tracking-widest text-dim font-semibold">Price Chart</span>
          <button
            onClick={() => onOpenWindow('fundamentals')}
            className="text-[9px] text-hi hover:opacity-70 transition-opacity font-medium"
          >
            Full view →
          </button>
        </div>
        <div className="flex-1 min-h-[320px]">
          <ChartPane
            bars={bars}
            range={range}
            ranges={RANGES}
            onRangeChange={setRange}
            dark={dark}
            loading={chartLoading}
          />
        </div>
      </div>

      {/* Row 2 */}
      <ValuationPanel ticker={ticker} onFull={() => onOpenWindow('dcf')}  />
      <RiskPanel      ticker={ticker} onFull={() => onOpenWindow('risk')} />
    </div>
  );
}
