import { useState, useEffect, useCallback } from 'react';
import { TopBar } from '@/components/TopBar';
import { ChartPane } from '@/components/ChartPane';
import { FundamentalsTab } from '@/tabs/FundamentalsTab';
import { PipelineTab }     from '@/tabs/PipelineTab';
import { NewsTab }         from '@/tabs/NewsTab';
import { ConfidenceTab }   from '@/tabs/ConfidenceTab';
import { DCFTab }          from '@/tabs/DCFTab';
import { ScenariosTab }    from '@/tabs/ScenariosTab';
import { WatchlistTab }    from '@/tabs/WatchlistTab';
import { fetchQuote, fetchStock } from '@/api';
import type { Quote, Bar } from '@/types';

type Tab = 'fundamentals' | 'pipeline' | 'news' | 'confidence' | 'dcf' | 'scenarios' | 'watchlist';

const TABS: { id: Tab; label: string }[] = [
  { id: 'fundamentals', label: 'Fundamentals' },
  { id: 'pipeline',     label: 'Pipeline'     },
  { id: 'news',         label: 'News'         },
  { id: 'confidence',   label: 'ML Signal'    },
  { id: 'dcf',          label: 'DCF'          },
  { id: 'scenarios',    label: 'Scenarios'    },
  { id: 'watchlist',    label: 'Watchlist'    },
];

const RANGES = ['1D', '1W', '1M', '3M', '1Y', '5Y'];
const QUICK  = ['MRNA', 'BGNE', '6160.HK', 'ZLAB', 'NVAX'];

export function App() {
  const [ticker, setTicker]   = useState<string | null>(null);
  const [dark,   setDark]     = useState(true);
  const [tab,    setTab]      = useState<Tab>('fundamentals');
  const [quote,  setQuote]    = useState<Quote | null>(null);
  const [bars,   setBars]     = useState<Bar[]>([]);
  const [range,  setRange]    = useState('3M');
  const [chartLoading, setChartLoading] = useState(false);

  // Apply dark class
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
  }, [dark]);

  const loadTicker = useCallback(async (t: string) => {
    const upper = t.toUpperCase();
    setTicker(upper);
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

  // Reload chart bars when range changes (ticker already set)
  useEffect(() => {
    if (!ticker) return;
    setChartLoading(true);
    fetchStock(ticker, range)
      .then(d => setBars(d.bars ?? []))
      .catch(console.error)
      .finally(() => setChartLoading(false));
  }, [range]); // eslint-disable-line

  return (
    <div className="h-screen flex flex-col bg-base text-ink font-sans overflow-hidden select-none">

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
          {/* ── Chart ── */}
          <div className="flex-none h-[38vh] min-h-[200px] border-b border-line">
            <ChartPane
              bars={bars}
              range={range}
              ranges={RANGES}
              onRangeChange={setRange}
              dark={dark}
              loading={chartLoading}
            />
          </div>

          {/* ── Tab bar ── */}
          <div className="flex-none flex bg-surface border-b border-line overflow-x-auto shrink-0">
            {TABS.map(t => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={[
                  'px-4 py-2.5 text-[11px] font-medium tracking-wide whitespace-nowrap transition-colors border-b-2',
                  tab === t.id
                    ? 'border-hi text-hi'
                    : 'border-transparent text-dim hover:text-ink',
                ].join(' ')}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* ── Tab content ── */}
          <div className="flex-1 overflow-y-auto bg-base p-4">
            {tab === 'fundamentals' && <FundamentalsTab ticker={ticker} />}
            {tab === 'pipeline'     && <PipelineTab     ticker={ticker} />}
            {tab === 'news'         && <NewsTab          ticker={ticker} />}
            {tab === 'confidence'   && <ConfidenceTab    ticker={ticker} />}
            {tab === 'dcf'          && <DCFTab           ticker={ticker} />}
            {tab === 'scenarios'    && <ScenariosTab     ticker={ticker} />}
            {tab === 'watchlist'    && <WatchlistTab currentTicker={ticker} onSelect={loadTicker} />}
          </div>
        </>
      ) : (
        /* ── Empty state ── */
        <div className="flex-1 flex flex-col items-center justify-center gap-4">
          <div>
            <p className="text-3xl font-light text-dim tracking-tight text-center">BioTerminal Pro</p>
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
