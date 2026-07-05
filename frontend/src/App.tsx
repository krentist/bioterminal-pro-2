import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { TopBar }   from '@/components/TopBar';
import { Desktop }  from '@/components/Desktop';
import { fetchQuote } from '@/api';
import { WindowManagerProvider, useWindowManager, openDefaultPanels } from '@/lib/windowManager';
import { PANEL_DEFS, PANEL_ORDER } from '@/lib/panelRegistry';
import type { Quote, AppTab } from '@/types';
import {
  FlaskConical, TrendingUp, BrainCircuit, BarChart3,
  ChevronRight, Zap, Globe2, Shield,
} from 'lucide-react';

const QUICK_PICKS = [
  { ticker: 'MRNA',    name: 'Moderna',        exchange: 'NASDAQ', flag: '🇺🇸' },
  { ticker: 'NVAX',    name: 'Novavax',         exchange: 'NASDAQ', flag: '🇺🇸' },
  { ticker: '6160.HK', name: 'BeiGene',         exchange: 'HKEX',   flag: '🇭🇰' },
  { ticker: 'ZLAB',    name: 'Zai Lab',         exchange: 'NASDAQ', flag: '🇺🇸' },
  { ticker: '9688.HK', name: 'Zai Lab HK',      exchange: 'HKEX',   flag: '🇭🇰' },
  { ticker: '2269.HK', name: 'WuXi Biologics',  exchange: 'HKEX',   flag: '🇭🇰' },
];

const FEATURES = [
  { icon: FlaskConical, title: 'Clinical Pipeline',  desc: 'CT.gov trials enriched by AI — phases, TAM, next catalysts.' },
  { icon: TrendingUp,   title: 'rNPV Valuation',     desc: 'Risk-adjusted NPV using BIO phase-probability curves.' },
  { icon: BrainCircuit, title: 'ML Confidence Signal', desc: 'RandomForest model scores momentum, fundamentals & sentiment.' },
  { icon: BarChart3,    title: 'CCASS Flow',         desc: 'HK institutional shareholding snapshots — 12 months deep.' },
];

// ── Landing hero (shown on the desktop canvas when no windows are open) ────────

function LandingHero({ onSelect }: { onSelect: (t: string) => void }) {
  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center px-6 landing-fade-in overflow-y-auto">

      <div className="flex items-center gap-2 px-3 py-1 rounded-full border border-hi/30 bg-hi/5 text-[10px] font-medium tracking-widest text-hi mb-8">
        <span className="live-dot" />
        LIVE DATA · AI-POWERED · HK + US MARKETS
      </div>

      <h1 className="text-5xl sm:text-6xl font-light text-ink tracking-tight text-center leading-none mb-3">
        Bio<span className="text-hi font-semibold">Terminal</span> Pro
      </h1>
      <p className="text-sm text-dim text-center max-w-md leading-relaxed mb-10">
        Bloomberg-level biotech research — clinical pipelines, rNPV valuations,
        ML signals, and HK institutional flow. No $24,000/yr subscription.
      </p>

      <div className="flex items-center gap-8 sm:gap-12 mb-10">
        {[
          { n: '16',   label: 'Research Modules' },
          { n: '2',    label: 'Markets Covered'  },
          { n: 'AI',   label: 'Pipeline Analysis' },
          { n: 'Live', label: 'Market Data'       },
        ].map(({ n, label }) => (
          <div key={label} className="text-center">
            <div className="text-2xl font-mono font-light text-hi leading-none">{n}</div>
            <div className="text-[9px] text-dim uppercase tracking-widest mt-1">{label}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-2 w-full max-w-sm mb-10">
        {FEATURES.map(({ icon: Icon, title, desc }) => (
          <div
            key={title}
            className="p-3 rounded-lg border border-line bg-surface hover:border-hi/50 hover:bg-hi/5 transition-all cursor-default group"
          >
            <Icon size={13} className="text-hi mb-2 opacity-80 group-hover:opacity-100 transition-opacity" />
            <p className="text-[11px] font-semibold text-ink leading-snug">{title}</p>
            <p className="text-[9px] text-dim mt-1 leading-snug">{desc}</p>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-4 text-[10px] text-dim mb-8 flex-wrap justify-center">
        <span className="flex items-center gap-1"><Globe2 size={10} className="text-hi" /> GBA &amp; US biotech investors</span>
        <span className="text-line hidden sm:inline">·</span>
        <span className="flex items-center gap-1"><Zap size={10} className="text-hi" /> Retail &amp; small fund managers</span>
        <span className="text-line hidden sm:inline">·</span>
        <span className="flex items-center gap-1"><Shield size={10} className="text-hi" /> No login required</span>
      </div>

      <p className="text-[9px] text-dim uppercase tracking-[0.2em] mb-3">Try it now — pick a ticker</p>
      <div className="flex flex-wrap justify-center gap-2 max-w-lg">
        {QUICK_PICKS.map(({ ticker, name, exchange, flag }) => (
          <button
            key={ticker}
            onClick={() => onSelect(ticker)}
            className="group flex items-center gap-2 px-3 py-2 rounded-lg border border-line bg-surface hover:border-hi hover:bg-hi/5 transition-all"
          >
            <span className="text-sm leading-none">{flag}</span>
            <span className="flex flex-col items-start">
              <span className="text-[11px] font-mono font-semibold text-ink group-hover:text-hi transition-colors leading-none">{ticker}</span>
              <span className="text-[9px] text-dim leading-none mt-0.5">{name}</span>
            </span>
            <span className="text-[8px] text-dim bg-elevated border border-line/60 px-1 py-0.5 rounded ml-1">{exchange}</span>
            <ChevronRight size={10} className="text-dim group-hover:text-hi group-hover:translate-x-0.5 transition-all flex-none" />
          </button>
        ))}
      </div>

      <p className="text-[10px] text-dim mt-5 opacity-60">
        or type any ticker in the command bar above
        <span className="ml-2 font-mono text-[9px] bg-elevated border border-line px-1.5 py-0.5 rounded">/</span>
      </p>
    </div>
  );
}

// ── Popout view: a single panel, detached into its own browser window ──────────

function PopoutView({ panelId, ticker }: { panelId: AppTab; ticker: string }) {
  useEffect(() => { document.documentElement.classList.add('dark'); }, []);
  const def = PANEL_DEFS[panelId];
  const helpers = { openWindow: () => {}, openTicker: () => {} };
  return (
    <div className="h-screen w-screen flex flex-col bg-base text-ink font-sans overflow-hidden">
      <div className="flex-none flex items-center gap-2 h-10 px-3 border-b border-line bg-surface">
        <span className="text-[11px] font-semibold text-ink uppercase tracking-wide">{def.label}</span>
        <span className="text-[11px] font-mono text-hi">{ticker}</span>
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto p-3">
        {def.render(ticker, helpers)}
      </div>
    </div>
  );
}

// ── Mobile / narrow-viewport fallback: simple stacked tab switcher ─────────────

function MobileLayout({ ticker, onSelectTicker }: { ticker: string; onSelectTicker: (t: string) => void }) {
  const [tab, setTab] = useState<AppTab>('overview');
  const helpers = { openWindow: (id: AppTab) => setTab(id), openTicker: onSelectTicker };

  return (
    <>
      <div className="flex-none flex items-stretch bg-surface border-b border-line overflow-x-auto shrink-0">
        {PANEL_ORDER.map(id => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={[
              'px-3 py-2.5 text-[11px] font-medium tracking-wide whitespace-nowrap transition-colors border-b-2',
              tab === id ? 'border-hi text-hi' : 'border-transparent text-dim hover:text-ink',
            ].join(' ')}
          >
            {PANEL_DEFS[id].label}
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-y-auto bg-base p-4">
        {PANEL_DEFS[tab].render(ticker, helpers)}
      </div>
    </>
  );
}

// ── App shell (inside WindowManagerProvider) ────────────────────────────────────

function AppShell({ dark, onToggleDark }: { dark: boolean; onToggleDark: () => void }) {
  const wm = useWindowManager();
  const [quote, setQuote] = useState<Quote | null>(null);
  const [isDesktopViewport, setIsDesktopViewport] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(min-width: 1024px)').matches
  );

  const userSearched = useRef(false);
  const autoLoaded   = useRef(false);

  // Shareable permalink: a ?ticker=… in the URL loads that ticker on arrival.
  const initialTicker = useMemo(() => {
    const t = new URLSearchParams(location.search).get('ticker');
    return t ? t.toUpperCase() : null;
  }, []);

  useEffect(() => {
    const mql = window.matchMedia('(min-width: 1024px)');
    const handle = () => setIsDesktopViewport(mql.matches);
    mql.addEventListener('change', handle);
    return () => mql.removeEventListener('change', handle);
  }, []);

  const selectTicker = useCallback((t: string) => {
    userSearched.current = true;
    const upper = t.toUpperCase();
    if (wm.order.length === 0) {
      openDefaultPanels(wm, upper);
    } else {
      wm.setGlobalTicker(upper);
    }
  }, [wm]);

  // On arrival: honour a shared ?ticker= link; otherwise auto-demo BeiGene after 1.4s.
  // The short delay lets persisted window state hydrate first so we don't clobber it.
  useEffect(() => {
    const delay = initialTicker ? 200 : 1400;
    const t = setTimeout(() => {
      if (autoLoaded.current) return;
      if (!userSearched.current && wm.order.length === 0) {
        autoLoaded.current = true;
        selectTicker(initialTicker ?? '6160.HK');
      } else if (initialTicker && wm.order.length > 0) {
        // A session was restored — just point it at the shared ticker.
        autoLoaded.current = true;
        userSearched.current = true;
        wm.setGlobalTicker(initialTicker);
      }
    }, delay);
    return () => clearTimeout(t);
  }, [selectTicker, wm.order.length, initialTicker, wm]);

  // Keep the URL's ?ticker= in sync so the address bar / Share button is a permalink.
  useEffect(() => {
    if (!wm.globalTicker) return;
    const url = new URL(location.href);
    if (url.searchParams.get('ticker') !== wm.globalTicker) {
      url.searchParams.set('ticker', wm.globalTicker);
      history.replaceState(null, '', url.toString());
    }
  }, [wm.globalTicker]);

  useEffect(() => {
    if (!wm.globalTicker) { setQuote(null); return; }
    let cancelled = false;
    fetchQuote(wm.globalTicker).then(q => { if (!cancelled) setQuote(q); }).catch(() => setQuote(null));
    return () => { cancelled = true; };
  }, [wm.globalTicker]);

  // Global keyboard shortcut: '/' focuses the command input
  useEffect(() => {
    function handle(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement).tagName;
      if (e.key === '/' && tag !== 'INPUT' && tag !== 'TEXTAREA') {
        e.preventDefault();
        document.querySelector<HTMLInputElement>('header input[type="text"]')?.focus();
      }
    }
    document.addEventListener('keydown', handle);
    return () => document.removeEventListener('keydown', handle);
  }, []);

  return (
    <div className="h-screen flex flex-col bg-base text-ink font-sans overflow-hidden select-text">
      <TopBar
        ticker={wm.globalTicker || null}
        quote={quote}
        dark={dark}
        onToggleDark={onToggleDark}
        onSelectTicker={selectTicker}
      />
      {isDesktopViewport ? (
        <Desktop emptyState={<LandingHero onSelect={selectTicker} />} />
      ) : wm.globalTicker ? (
        <MobileLayout ticker={wm.globalTicker} onSelectTicker={selectTicker} />
      ) : (
        <div className="relative flex-1 min-h-0">
          <LandingHero onSelect={selectTicker} />
        </div>
      )}
    </div>
  );
}

// ── App ───────────────────────────────────────────────────────────────────────

export function App() {
  const [dark, setDark] = useState(true);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
  }, [dark]);

  const popout = useMemo(() => {
    const params = new URLSearchParams(location.search);
    const panelId = params.get('popout') as AppTab | null;
    const ticker  = params.get('ticker');
    if (panelId && ticker && PANEL_DEFS[panelId]) return { panelId, ticker };
    return null;
  }, []);

  if (popout) {
    return <PopoutView panelId={popout.panelId} ticker={popout.ticker} />;
  }

  return (
    <WindowManagerProvider>
      <AppShell dark={dark} onToggleDark={() => setDark(d => !d)} />
    </WindowManagerProvider>
  );
}
