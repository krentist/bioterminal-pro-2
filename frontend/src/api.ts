import type {
  Quote, Bar, Fundamentals, Trial, NewsItem,
  ConfidenceData, DCFData, ScenariosData, SearchResult,
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
export const fetchNews         = (t: string) => get<NewsItem[]>(`/api/news/${enc(t)}`);
export const fetchConfidence   = (t: string) => get<ConfidenceData>(`/api/confidence/${enc(t)}`);
export const fetchDCF          = (t: string) => get<DCFData>(`/api/dcf/${enc(t)}`);
export const fetchScenarios    = (t: string) => get<ScenariosData>(`/api/scenarios/${enc(t)}`);
export const fetchSearch       = (q: string) => get<{ quotes: SearchResult[] }>(`/api/search?q=${enc(q)}`);
export const fetchWatchlist    = ()           => get<string[]>('/api/watchlist');

export async function addToWatchlist(ticker: string): Promise<void> {
  await fetch(`/api/watchlist/${enc(ticker)}`, { method: 'POST' });
}

export async function removeFromWatchlist(ticker: string): Promise<void> {
  await fetch(`/api/watchlist/${enc(ticker)}`, { method: 'DELETE' });
}

function enc(s: string) { return encodeURIComponent(s); }
