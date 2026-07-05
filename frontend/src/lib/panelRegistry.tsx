import type { ReactNode } from 'react';
import type { AppTab } from '@/types';
import { OverviewTab }     from '@/tabs/OverviewTab';
import { FundamentalsTab } from '@/tabs/FundamentalsTab';
import { PipelineTab }     from '@/tabs/PipelineTab';
import { CatalystsTab }    from '@/tabs/CatalystsTab';
import { RNPVTab }         from '@/tabs/RNPVTab';
import { DCFTab }          from '@/tabs/DCFTab';
import { ScenariosTab }    from '@/tabs/ScenariosTab';
import { ConfidenceTab }   from '@/tabs/ConfidenceTab';
import { EarningsTab }     from '@/tabs/EarningsTab';
import { RiskTab }         from '@/tabs/RiskTab';
import { BacktestTab }     from '@/tabs/BacktestTab';
import { ScreenerTab }     from '@/tabs/ScreenerTab';
import { FilingsTab }      from '@/tabs/FilingsTab';
import { CCASFlowTab }     from '@/tabs/CCASFlowTab';
import { DualListingTab }  from '@/tabs/DualListingTab';
import { OwnershipTab }    from '@/tabs/OwnershipTab';
import { PeersTab }        from '@/tabs/PeersTab';
import { CompetitionTab }  from '@/tabs/CompetitionTab';
import { CrossBorderTab }  from '@/tabs/CrossBorderTab';
import { NotesTab }        from '@/tabs/NotesTab';
import { PrivateCompanyTab } from '@/tabs/PrivateCompanyTab';
import { NewsTab }         from '@/tabs/NewsTab';
import { WatchlistTab }    from '@/tabs/WatchlistTab';

export interface PanelHelpers {
  openWindow: (panelId: AppTab) => void;
  openTicker: (ticker: string) => void;
}

export interface PanelDef {
  label:       string;
  description: string;
  defaultSize: { w: number; h: number };
  render:      (ticker: string, helpers: PanelHelpers) => ReactNode;
}

export const PANEL_DEFS: Record<AppTab, PanelDef> = {
  overview: {
    label: 'Chart',
    description: 'Price chart plus at-a-glance signal, pipeline, valuation and risk.',
    defaultSize: { w: 920, h: 620 },
    render: (ticker, h) => <OverviewTab ticker={ticker} onOpenWindow={h.openWindow} />,
  },
  fundamentals: {
    label: 'Quote Monitor',
    description: 'Fundamentals, valuation multiples and margins.',
    defaultSize: { w: 460, h: 560 },
    render: ticker => <FundamentalsTab ticker={ticker} />,
  },
  pipeline: {
    label: 'Pipeline',
    description: 'Clinical trial pipeline enriched with AI research and TAM.',
    defaultSize: { w: 620, h: 620 },
    render: ticker => <PipelineTab ticker={ticker} />,
  },
  catalysts: {
    label: 'Catalysts',
    description: 'Forward calendar of upcoming interventional trial readouts.',
    defaultSize: { w: 560, h: 560 },
    render: ticker => <CatalystsTab ticker={ticker} />,
  },
  rnpv: {
    label: 'rNPV',
    description: 'Risk-adjusted NPV valuation using BIO phase-probability curves.',
    defaultSize: { w: 540, h: 560 },
    render: ticker => <RNPVTab ticker={ticker} />,
  },
  dcf: {
    label: 'DCF',
    description: 'Discounted cash flow valuation with interactive assumptions.',
    defaultSize: { w: 540, h: 560 },
    render: ticker => <DCFTab ticker={ticker} />,
  },
  scenarios: {
    label: 'Scenarios',
    description: 'Bull/base/bear price targets and Monte Carlo distribution.',
    defaultSize: { w: 500, h: 480 },
    render: ticker => <ScenariosTab ticker={ticker} />,
  },
  confidence: {
    label: 'ML Signal',
    description: 'RandomForest confidence score across momentum, fundamentals and sentiment.',
    defaultSize: { w: 420, h: 500 },
    render: ticker => <ConfidenceTab ticker={ticker} />,
  },
  earnings: {
    label: 'Earnings',
    description: 'EPS surprise history, revenue CAGR and analyst targets.',
    defaultSize: { w: 580, h: 540 },
    render: ticker => <EarningsTab ticker={ticker} />,
  },
  risk: {
    label: 'Risk',
    description: "Devil's-advocate bear-case risk factor analysis.",
    defaultSize: { w: 540, h: 540 },
    render: ticker => <RiskTab ticker={ticker} />,
  },
  backtest: {
    label: 'Backtest',
    description: 'RSI + MACD signal backtest vs. buy-and-hold.',
    defaultSize: { w: 660, h: 580 },
    render: ticker => <BacktestTab ticker={ticker} />,
  },
  screener: {
    label: 'Screener',
    description: '5-dimension biotech alpha screener across HK and US universes.',
    defaultSize: { w: 660, h: 540 },
    render: (_ticker, h) => <ScreenerTab onTickerSelect={h.openTicker} />,
  },
  filings: {
    label: 'Filings',
    description: 'HKEXnews regulatory announcements.',
    defaultSize: { w: 500, h: 500 },
    render: ticker => <FilingsTab ticker={ticker} />,
  },
  ccas: {
    label: 'CCASS',
    description: 'CCASS institutional shareholding flow, 12-month history.',
    defaultSize: { w: 580, h: 500 },
    render: ticker => <CCASFlowTab ticker={ticker} />,
  },
  duallisting: {
    label: 'Dual Listing',
    description: 'HK/US dual-listing premium or discount vs. the counterpart ticker.',
    defaultSize: { w: 480, h: 440 },
    render: ticker => <DualListingTab ticker={ticker} />,
  },
  ownership: {
    label: 'Ownership',
    description: 'Institutional/insider ownership, short interest, and top 13F holders.',
    defaultSize: { w: 560, h: 560 },
    render: ticker => <OwnershipTab ticker={ticker} />,
  },
  peers: {
    label: 'Peer Comps',
    description: 'Valuation and growth multiples vs. a curated peer set.',
    defaultSize: { w: 640, h: 480 },
    render: (ticker, h) => <PeersTab ticker={ticker} onSelect={h.openTicker} />,
  },
  competition: {
    label: 'Competition',
    description: 'Commercial rivals running trials in this company’s lead indication.',
    defaultSize: { w: 620, h: 520 },
    render: ticker => <CompetitionTab ticker={ticker} />,
  },
  crossborder: {
    label: 'Cross-Border',
    description: 'A/H/US share-class prices on a common USD basis with premium/discount.',
    defaultSize: { w: 560, h: 460 },
    render: ticker => <CrossBorderTab ticker={ticker} />,
  },
  notes: {
    label: 'Notes & Compliance',
    description: 'Private research notes with an MNPI compliance wall and restricted list.',
    defaultSize: { w: 480, h: 620 },
    render: ticker => <NotesTab ticker={ticker} />,
  },
  privateco: {
    label: 'Private Co',
    description: 'Model a private / pre-IPO biotech: pipeline rNPV, funding & deal comps, notes.',
    defaultSize: { w: 640, h: 680 },
    render: ticker => <PrivateCompanyTab ticker={ticker} />,
  },
  news: {
    label: 'News',
    description: 'Recent headlines with AI sentiment context.',
    defaultSize: { w: 440, h: 580 },
    render: ticker => <NewsTab ticker={ticker} />,
  },
  watchlist: {
    label: 'Watchlist',
    description: 'Saved tickers with live price and change.',
    defaultSize: { w: 400, h: 500 },
    render: (ticker, h) => <WatchlistTab currentTicker={ticker} onSelect={h.openTicker} />,
  },
};

export const PANEL_ORDER: AppTab[] = [
  'overview', 'fundamentals', 'pipeline', 'catalysts', 'competition', 'news',
  'confidence', 'rnpv', 'dcf', 'scenarios', 'earnings', 'risk', 'backtest',
  'filings', 'ccas', 'duallisting', 'crossborder', 'ownership', 'peers', 'screener',
  'notes', 'privateco', 'watchlist',
];

export const DEFAULT_OPEN_PANELS: AppTab[] = ['overview', 'fundamentals', 'pipeline', 'news'];
