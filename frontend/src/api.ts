import type {
  Quote, Bar, Fundamentals, Trial, NewsItem,
  ConfidenceData, DCFData, ScenariosData, SearchResult,
  RNPVData, EarningsData, RiskData, BacktestData, ScreenerData,
  Filing, FlowEntry, DualListingData, CatalystsData, OwnershipData, PeerRow,
  CompetitionData, CrossBorderData,
} from './types';

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${path}`);
  return res.json();
}

export const fetchQuote        = (t: string) => get<Quote>(`/api/quote/${enc(t)}`);
export const fetchRealtime     = (t: string) => get<Quote>(`/api/realtime/${enc(t)}`);
export const fetchStock        = (t: string, range: string) =>
  get<{ bars: Bar[] }>(`/api/stock/${enc(t)}?range=${range}`);
export const fetchFundamentals = (t: string) => get<Fundamentals>(`/api/fundamentals/${enc(t)}`);
export const fetchTrials       = (t: string) => get<{ trials: Trial[] }>(`/api/trials/${enc(t)}`);
export const fetchCatalysts    = (t: string) => get<CatalystsData>(`/api/catalysts/${enc(t)}`);
export const fetchNews         = (t: string) => get<NewsItem[]>(`/api/news/${enc(t)}`);
export const fetchConfidence   = (t: string) => get<ConfidenceData>(`/api/confidence/${enc(t)}`);
export const fetchDCF          = (t: string) => get<DCFData>(`/api/dcf/${enc(t)}`);

export async function postDCF(t: string, assumptions: Record<string, number>): Promise<DCFData> {
  const res = await fetch(`/api/dcf/${enc(t)}`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(assumptions),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
export const fetchScenarios    = (t: string) => get<ScenariosData>(`/api/scenarios/${enc(t)}`);
export const fetchSearch       = (q: string) => get<{ quotes: SearchResult[] }>(`/api/search?q=${enc(q)}`);
export const fetchWatchlist    = ()           => get<string[]>('/api/watchlist');

export async function addToWatchlist(ticker: string): Promise<void> {
  await fetch(`/api/watchlist/${enc(ticker)}`, { method: 'POST' });
}

export async function removeFromWatchlist(ticker: string): Promise<void> {
  await fetch(`/api/watchlist/${enc(ticker)}`, { method: 'DELETE' });
}

export const fetchRNPV         = (t: string) => get<RNPVData>(`/api/rnpv/${enc(t)}`);
export const fetchEarnings     = (t: string) => get<EarningsData>(`/api/earnings/${enc(t)}`);
export const fetchRisk         = (t: string) => get<RiskData>(`/api/risk/${enc(t)}`);
export const fetchBacktest     = (t: string, period = '2y') =>
  get<BacktestData>(`/api/backtest/${enc(t)}?period=${period}`);
export const fetchScreen       = (region: 'HK' | 'US') =>
  get<ScreenerData>(`/api/screen?region=${region}`);
export const fetchFilings      = (t: string) => get<Filing[]>(`/api/filings/${enc(t)}`);
export const fetchFlow         = (t: string) => get<FlowEntry[]>(`/api/flow/${enc(t)}`);
export const fetchDualListing  = (t: string) => get<DualListingData>(`/api/dual-listing/${enc(t)}`);
export const fetchOwnership    = (t: string) => get<OwnershipData>(`/api/ownership/${enc(t)}`);
export const fetchCompetition  = (t: string) => get<CompetitionData>(`/api/competition/${enc(t)}`);
export const fetchCrossBorder  = (t: string) => get<CrossBorderData>(`/api/cross-border/${enc(t)}`);
export const fetchPeers        = (t: string) => get<{ peers: PeerRow[] }>(`/api/peers/${enc(t)}`);
export const fetchPipelineSummary = (t: string) =>
  get<{ summary: string; key_risks: string[]; upcoming_catalysts: string[]; ai_generated: boolean }>(
    `/api/pipeline-summary/${enc(t)}`
  );

export const fetchPipelineResearch = (t: string) =>
  get<import('./types').PipelineResearch>(`/api/pipeline-research/${enc(t)}`);

function enc(s: string) { return encodeURIComponent(s); }
