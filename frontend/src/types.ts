export type AppTab =
  | 'overview' | 'fundamentals' | 'pipeline' | 'rnpv' | 'dcf'
  | 'scenarios' | 'confidence'  | 'earnings' | 'risk' | 'backtest'
  | 'screener'  | 'filings'     | 'ccas'     | 'duallisting'
  | 'news'      | 'watchlist';

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

export interface MLSignal {
  signal: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  bullProb: number;
  confidence: number;
  trainedOn: number;
  oosAccuracy?: number | null;
  oosSamples?: number;
}

export interface ConfidenceData {
  score: number;
  signal: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  factors: ConfidenceFactor[];
  mlSignal?: MLSignal | null;
  newsImpact: {
    keyEvent: string | null;
    recentCount: number;
    sentimentScore: number;
    interpretation?: string | null;
    keyEvents?: string[];
    ai_generated?: boolean;
  } | null;
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

// ── DCF extended (rNPV fallback) ─────────────────────────────────────────────

export interface RNPVAsset {
  name: string;
  phase: string;
  probApproval: number;
  peakSales: number;
  rnpv: number;
  devCostPv: number;
  netRnpv: number;
}

export interface DCFData {
  impliedSharePrice: number | null;
  upside: number | null;
  currencySymbol: string;
  valuationMethod: 'DCF' | 'rNPV';
  dcf: Record<string, number | string | null> | null;
  rnpvTotal?: number | null;
  rnpvPerShare?: number | null;
  pipelineDiscount?: number | null;
  rnpvDetail?: RNPVAsset[];
  trialsFound?: number;
  programsValued?: number;
  sponsorMatched?: boolean;
  peakSalesAssumption?: number;
  assumptionNote?: string;
}

// ── rNPV standalone ──────────────────────────────────────────────────────────

export interface RNPVData {
  impliedSharePrice: number | null;
  upside: number | null;
  currencySymbol: string;
  valuationMethod: 'rNPV';
  rnpvTotal: number;
  rnpvPerShare: number | null;
  pipelineDiscount: number | null;
  rnpvDetail: RNPVAsset[];
  trialsFound?: number;
  programsValued?: number;
  sponsorMatched?: boolean;
  peakSalesAssumption?: number;
  assumptionNote?: string;
}

// ── Earnings ─────────────────────────────────────────────────────────────────

export interface EarningsQuarter {
  date: string;
  reported: number | null;
  estimated: number | null;
  surprisePct: number | null;
  beat: boolean | null;
}

export interface AnnualRevenue {
  date: string;
  revenue: number | null;
  yoyGrowthPct: number | null;
}

export interface EarningsData {
  ticker: string;
  nextEarningsDate: string | null;
  beatRate8q: number | null;
  avgSurprisePct: number | null;
  revenueCagr3y: number | null;
  targetMean: number | null;
  targetHigh: number | null;
  targetLow: number | null;
  recommendation: string | null;
  nAnalysts: number | null;
  quarterlyEps: EarningsQuarter[];
  annualRevenue: AnnualRevenue[];
}

// ── Risk / Devil's Advocate ───────────────────────────────────────────────────

export interface RiskFactor {
  category: string;
  title: string;
  detail: string;
  severity: number;
  evidence: string;
}

export interface RiskSummary {
  count: number;
  critical: number;
  high: number;
  maxSeverity: number;
  overall: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
}

export interface RiskData {
  ticker: string;
  summary: RiskSummary;
  factors: RiskFactor[];
}

// ── Backtest ──────────────────────────────────────────────────────────────────

export interface EquityPoint {
  date: string;
  value: number;
}

export interface Trade {
  entryDate: string;
  exitDate: string;
  entryPrice: number;
  exitPrice: number;
  pnlPct: number;
  holdDays: number;
  exitReason: string;
}

export interface BacktestMetrics {
  total_return_pct: number;
  cagr_pct: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  bh_return_pct: number;
  alpha_pct: number | null;
  n_trades: number;
  win_rate_pct: number;
  avg_win_pct: number;
  avg_loss_pct: number;
  in_sample?: boolean;
  note?: string;
}

export interface BacktestData {
  ticker: string;
  period: string;
  metrics: BacktestMetrics;
  equityCurve: EquityPoint[];
  trades: Trade[];
}

// ── Screener ──────────────────────────────────────────────────────────────────

export interface ScreenerRow {
  rank: number;
  ticker: string;
  totalScore: number;
  momentum: number;
  value: number;
  pipeline: number;
  quality: number;
  technical: number;
  marketCap: number | null;
  psRatio: number | null;
  revenueGrowth: number | null;
}

export interface ScreenerData {
  region: string;
  results: ScreenerRow[];
  cachedAt: string | null;
}

// ── Filings ───────────────────────────────────────────────────────────────────

export interface Filing {
  date: string;
  title: string;
  type: string;
  url: string;
}

// ── CCASS flow ────────────────────────────────────────────────────────────────

export interface FlowEntry {
  participant_id: string;
  participant_name: string;
  shares: number | null;
  percentage: number | null;
  snapshot_date: string;
}

// ── Pipeline research (AI-powered) ───────────────────────────────────────────

export interface PipelineProgram {
  drug_name:            string;
  target:               string | null;
  mechanism:            string | null;
  indication:           string;
  secondary_indications?: string[];
  phase:                string;
  status:               string | null;
  owned_or_licensed:    string | null;
  partner:              string | null;
  rights:               string | null;
  nct_ids:              string[];
  chictr_ids:           string[];
  tam_usd_bn:           number | null;
  tam_basis:            string | null;
  competition:          string[];
  key_data:             string[];
  risk:                 'LOW' | 'MEDIUM' | 'HIGH' | 'VERY_HIGH' | null;
  next_catalyst:        string | null;
  // CT.gov live enrichment (may be absent)
  ct_status?:           string | null;
  ct_enrollment?:       number | null;
  ct_data?:             {
    status: string | null;
    enrollment: number | null;
    start_date: string | null;
    completion: string | null;
    ct_title: string | null;
    ct_sponsor: string | null;
  };
}

export interface PipelineResearch {
  programs:         PipelineProgram[];
  pipeline_summary: string;
  hk_china_angle:   string;
  data_note:        string;
  ai_generated:     boolean;
  ticker:           string;
  company_name:     string;
}

// ── Dual listing ──────────────────────────────────────────────────────────────

export interface DualListingData {
  dual_listed: boolean;
  status: 'active' | 'delisted' | 'none';
  ticker: string;
  counterpart_ticker?: string;
  hk_ticker?: string;
  us_ticker?: string;
  hk_price_hkd?: number | null;
  us_price_usd?: number | null;
  us_price_hkd?: number | null;
  premium_discount_pct?: number | null;
  usdhkd_rate?: number;
  ads_ratio?: number;
  delisted_date?: string;
  note?: string;
}
