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
  score: number;
  weight: number;
}

export interface ConfidenceData {
  score: number;
  signal: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  factors: ConfidenceFactor[];
  newsImpact: {
    keyEvent: string | null;
    recentCount: number;
    sentimentScore: number;
    interpretation?: string | null;
    keyEvents?: string[];
    ai_generated?: boolean;
  } | null;
}

export interface DCFData {
  impliedSharePrice: number;
  upside: number;
  currencySymbol: string;
  dcf: Record<string, number | string | null>;
}

export interface Scenario {
  label: string;
  targetPrice: number;
  returnPct: number;
  probability?: number | null;
}

export interface ScenariosData {
  currentPrice: number;
  currencySymbol: string;
  scenarios: Scenario[];
  monteCarlo?: {
    percentile5:  number;
    percentile25: number;
    median:       number;
    percentile75: number;
    percentile95: number;
  } | null;
}

export interface SearchResult {
  symbol: string;
  shortname: string;
  exchange: string;
  quoteType: string;
}
