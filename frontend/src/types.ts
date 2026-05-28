export interface Bar {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface Quote {
  price: number;
  changePercent: number;
  currency: string;
  currencySymbol: string;
}

export interface Fundamentals {
  marketCap: number | null;
  forwardPE: number | null;
  evToRevenue: number | null;
  evToEbitda: number | null;
  beta: number | null;
  revenue: number | null;
  revenueGrowth: number | null;
  grossMargin: number | null;
  operatingMargin: number | null;
  profitMargin: number | null;
  roe: number | null;
  targetPrice: number | null;
  currencySymbol: string;
  description: string | null;
  name: string | null;
  sector: string | null;
}

export interface Trial {
  nctId: string;
  title: string;
  phase: string | null;
  status: string | null;
  enrollment: number | null;
  startDate?: string | null;
  completionDate?: string | null;
  conditions?: string[];
  interventions?: string[];
  prob_approval?: number | null;
}

export interface NewsItem {
  title: string;
  publisher: string;
  publishedAt: string;
  url: string;
  summary?: string | null;
}

export interface ConfidenceFactor {
  name: string;
  value: number;
  direction: string;
}

export interface ConfidenceData {
  score: number;
  signal: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  factors: ConfidenceFactor[];
  newsImpact: string;
}

export interface DCFData {
  impliedSharePrice: number;
  upside: number;
  currencySymbol: string;
  dcf: Record<string, number | string | null>;
}

export interface Scenario {
  name: string;
  price: number;
  upside: number;
  probability?: number | null;
}

export interface ScenariosData {
  currentPrice: number;
  currencySymbol: string;
  scenarios: Scenario[];
  monteCarlo?: {
    mean: number;
    p10: number;
    p25: number;
    p75: number;
    p90: number;
  } | null;
}

export interface SearchResult {
  symbol: string;
  shortname: string;
  exchange: string;
  quoteType: string;
}
