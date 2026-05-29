import { Fragment, useState, useEffect, useCallback } from 'react';
import { TopBar }        from '@/components/TopBar';
import { FundamentalsTab } from '@/tabs/FundamentalsTab';
import { PipelineTab }    from '@/tabs/PipelineTab';
import { NewsTab }        from '@/tabs/NewsTab';
import { ConfidenceTab }  from '@/tabs/ConfidenceTab';
import { DCFTab }         from '@/tabs/DCFTab';
import { ScenariosTab }   from '@/tabs/ScenariosTab';
import { WatchlistTab }   from '@/tabs/WatchlistTab';
import { RNPVTab }        from '@/tabs/RNPVTab';
import { EarningsTab }    from '@/tabs/EarningsTab';
import { RiskTab }        from '@/tabs/RiskTab';
import { BacktestTab }    from '@/tabs/BacktestTab';
import { ScreenerTab }    from '@/tabs/ScreenerTab';
import { FilingsTab }     from '@/tabs/FilingsTab';
import { CCASFlowTab }    from '@/tabs/CCASFlowTab';
import { DualListingTab } from '@/tabs/DualListingTab';
import { OverviewTab }    from '@/tabs/OverviewTab';
import { fetchQuote, fetchStock } from '@/api';
import type { AppTab, Quote, Bar } from '@/types';

// ── Tab metadata & groups ────────────────────────────────────────────────────

const TAB_LABEL: Record<AppTab, string> = {
  overview:    'Overview',
  pipeline:    'Pipeline',
  rnpv:        'rNPV',
  dcf:         'DCF',
  scenarios:   'Scenarios',
  earnings:    'Earnings',
  confidence:  'ML Signal',
  risk:        'Risk',
  backtest:    'Backtest',
  filings:     'Filings',
  ccas:        'CCASS',
  duallisting: 'Dual Listing',
  fundamentals:'Fundamentals',
  screener:    'Screener',
  news:        'News',
  watchlist:   'Watchlist',
};

// Groups define visual separators in the tab bar
const TAB_GROUPS: AppTab[][] = [
  ['overview'],
  ['pipeline', 'rnpv', 'dcf', 'scenarios', 'earnings'],
  ['confidence', 'risk', 'backtest'],
  ['filings', 'ccas', 'duallisting'],
  ['fundamentals', 'screener', 'news', 'watchlist'],
];

const RANGES = ['1D', '1W', '1M', '3M', '1Y', '5Y'];
const QUICK  = ['MRNA', 'NVAX', '6160.HK', 'ZLAB', '9688.HK', '2269.HK'];

export function App() {
  const [ticker, setTicker]   = useState<string | null>(null);
  const [dark,   setDark]     = useState(true);
  const [tab,    setTab]      = useState<AppTab>('overview');
  const [quote,  setQuote]    = useState<Quote | null>(null);
  const [bars,   setBars]     = useState<Bar[]>([]);
  const [range,  setRange]    = useState('3M');
  const [chartLoading, setChartLoading] = useState(false);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
  }, [dark]);

  const loadTicker = useCallback(async (t: string) => {
    const upper = t.toUpperCase();
    setTicker(upper);
    setTab('overview');
    setQuote(null);
    setBars([]);
    setChartLoading(true);
    try {
      const [q, stock] = await Promise.all([
        fetchQuote(upper),
        fetchStock(upper, range),
      ]);
      setQuote(q);
      setBars(stock.bars ?? []);
    } catch (e) {
      console.error(e);
    } finally {
      setChartLoading(false);
    }
  }, [range]); // eslint-disable-line

  useEffect(() => {
    if (!ticker) return;
    setChartLoading(true);
    fetchStock(ticker, range)
      .then(d => setBars(d.bars ?? []))
      .catch(console.error)
      .finally(() => setChartLoading(false));
  }, [range]); // eslint-disable-line

  return (
    <div className="h-screen flex flex-col bg-base text-ink font-sans overflow-hidden select-text">

      {/* ── Top bar ── */}
      <TopBar
        ticker={ticker}
        quote={quote}
        dark={dark}
        onToggleDark={() => setDark(d => !d)}
        onSelectTicker={loadTicker}
      />

      {ticker ? (
        <>
          {/* ── Tab bar with group separators ── */}
          <div className="flex-none flex items-stretch bg-surface border-b border-line overflow-x-auto shrink-0">
            {TAB_GROUPS.map((group, gi) => (
              <Fragment key={gi}>
                {gi > 0 && (
                  <div className="self-stretch my-1.5 w-px bg-line flex-none" />
                )}
                {group.map(id => (
                  <button
                    key={id}
                    onClick={() => setTab(id)}
                    className={[
                      'px-4 py-2.5 text-[11px] font-medium tracking-wide whitespace-nowrap transition-colors border-b-2',
                      tab === id
                        ? 'border-hi text-hi'
                        : 'border-transparent text-dim hover:text-ink',
                    ].join(' ')}
                  >
                    {TAB_LABEL[id]}
                  </button>
                ))}
              </Fragment>
            ))}
          </div>

          {/* ── Tab content ── */}
          <div className="flex-1 overflow-y-auto bg-base p-4">
            {tab === 'overview'     && (
              <OverviewTab
                ticker={ticker}
                bars={bars}
                range={range}
                ranges={RANGES}
                onRangeChange={setRange}
                dark={dark}
                chartLoading={chartLoading}
                onTabChange={setTab}
              />
            )}
            {tab === 'fundamentals' && <FundamentalsTab ticker={ticker} />}
            {tab === 'pipeline'     && <PipelineTab     ticker={ticker} />}
            {tab === 'rnpv'         && <RNPVTab         ticker={ticker} />}
            {tab === 'dcf'          && <DCFTab          ticker={ticker} />}
            {tab === 'scenarios'    && <ScenariosTab    ticker={ticker} />}
            {tab === 'confidence'   && <ConfidenceTab   ticker={ticker} />}
            {tab === 'earnings'     && <EarningsTab     ticker={ticker} />}
            {tab === 'risk'         && <RiskTab         ticker={ticker} />}
            {tab === 'backtest'     && <BacktestTab     ticker={ticker} />}
            {tab === 'screener'     && <ScreenerTab     onTickerSelect={loadTicker} />}
            {tab === 'filings'      && <FilingsTab      ticker={ticker} />}
            {tab === 'ccas'         && <CCASFlowTab     ticker={ticker} />}
            {tab === 'duallisting'  && <DualListingTab  ticker={ticker} />}
            {tab === 'news'         && <NewsTab         ticker={ticker} />}
            {tab === 'watchlist'    && <WatchlistTab    currentTicker={ticker} onSelect={loadTicker} />}
          </div>
        </>
      ) : (
        /* ── Empty state ── */
        <div className="flex-1 flex flex-col items-center justify-center gap-4">
          <div>
            <p className="text-3xl font-light text-dim tracking-tight text-center">
              Bio<span className="text-hi">Terminal</span> Pro
            </p>
            <p className="text-sm text-dim text-center mt-1 opacity-60">Search a ticker to get started</p>
          </div>
          <div className="flex flex-wrap justify-center gap-2 mt-1">
            {QUICK.map(t => (
              <button
                key={t}
                onClick={() => loadTicker(t)}
                className="px-3 py-1 text-xs font-mono border border-line rounded-md text-dim hover:border-hi hover:text-hi transition-colors"
              >
                {t}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
