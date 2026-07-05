export type AppTab =
  | 'overview' | 'fundamentals' | 'pipeline' | 'catalysts' | 'rnpv' | 'dcf'
  | 'scenarios' | 'confidence'  | 'earnings' | 'risk' | 'backtest'
  | 'screener'  | 'filings'     | 'ccas'     | 'duallisting' | 'ownership' | 'peers'
  | 'competition' | 'crossborder' | 'notes' | 'privateco'
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
  // Cash runway (clinical-stage biotech's key survival metric)
  cash?: number | null;
  freeCashflow?: number | null;
  operatingCashflow?: number | null;
  annualBurn?: number | null;
  runwayYears?: number | null;
  cashGenerating?: boolean | null;
  burnBasis?: 'freeCashflow' | 'operatingCashflow' | null;
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
  probApproval?: number | null;
  sponsor?: string | null;
  isLeadSponsor?: boolean;
  // Trial-level depth (Phase L)
  enrollmentType?: string | null;      // ACTUAL | ESTIMATED
  primaryEndpoint?: string | null;
  comparator?: string | null;
  hasComparator?: boolean;
  primaryPurpose?: string | null;
  primaryCompletionDate?: string | null;
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
    ai_available?: boolean;
  } | null;
  restricted?: boolean;
  restrictedReason?: string;
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
  restricted?: boolean;
  restrictedReason?: string;
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
  restricted?: boolean;
  restrictedReason?: string;
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
  restricted?: boolean;
  restrictedReason?: string;
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
  restricted?: boolean;
  restrictedReason?: string;
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

// ── Catalyst calendar ─────────────────────────────────────────────────────────

export interface Catalyst {
  nctId: string;
  title: string;
  phase: string | null;
  status: string | null;
  condition: string | null;
  date: string | null;
  daysAway: number | null;
  sponsor: string | null;
  isLeadSponsor: boolean;
  probApproval: number | null;
  source_url: string | null;
}

export interface CatalystsData {
  catalysts: Catalyst[];
  withinDays: number;
}

// ── Ownership & short interest ────────────────────────────────────────────────

export interface InstitutionalHolder {
  holder: string;
  pctHeld: number | null;
  shares: number | null;
  value: number | null;
  pctChange: number | null;
  dateReported: string | null;
}

export interface OwnershipData {
  heldPctInstitutions: number | null;
  heldPctInsiders: number | null;
  shortPctOfFloat: number | null;
  sharesShort: number | null;
  sharesShortPriorMonth: number | null;
  shortInterestChangePct: number | null;
  daysToCover: number | null;
  dateShortInterest: string | null;
  floatShares: number | null;
  sharesOutstanding: number | null;
  topInstitutions: InstitutionalHolder[];
}

// ── Peer comparables ──────────────────────────────────────────────────────────

export interface PeerRow {
  ticker: string;
  name: string;
  marketCap: number | null;
  price: number | null;
  currency: string;
  evToRevenue: number | null;
  psRatio: number | null;
  revenueGrowth: number | null;
  grossMargin: number | null;
  profitMargin: number | null;
  cash: number | null;
  targetUpside: number | null;
  isSubject: boolean;
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
  ai_available?:    boolean;
  ticker:           string;
  company_name:     string;
}

// ── Private company entity model (Phase K) ────────────────────────────────────

export interface PrivateCompany {
  id: string;
  name: string;
  aliases: string[];
  listingStatus: 'private' | 'pre_ipo' | 'public';
  ctSponsorName: string | null;
  linkedTicker: string | null;
  description: string;
  createdAt: string;
  updatedAt: string;
}

export interface CompanyProgram {
  title: string;
  phase: string | null;
  status: string | null;
  condition: string | null;
  enrollment: number | null;
}

export interface CompanyRnpvAsset {
  name: string;
  phase: string | null;
  probApproval: number;
  peakSales: number | null;
  rnpv: number | null;
  netRnpv: number | null;
}

export interface FundingRound {
  id: string;
  date: string | null;
  roundType: string | null;
  amountUsd: number | null;
  postMoneyUsd: number | null;
  leadInvestor: string | null;
  source: string | null;
  sourceUrl: string | null;
}

export interface CompanyNote {
  id: string;
  createdAt: string;
  source: string | null;
  text: string;
}

export interface CompanyView {
  company: PrivateCompany;
  listingStatus: string;
  pipeline: {
    programs: CompanyProgram[];
    sponsorMatched: boolean;
    trialsFound: number;
    source: string;
  };
  valuation: {
    valuationMethod: 'rNPV';
    rnpvTotal: number;
    programs: CompanyRnpvAsset[];
    assumptions: { defaultPeakSalesUsd: number; discountRate: number | null; note: string };
    licensingComps: { basis: string; low: number; mid: number; high: number } | null;
  };
  fundingComps: {
    rounds: FundingRound[];
    impliedByRnpv: {
      lastPostMoneyUsd: number;
      asOf: string | null;
      rnpvTotal: number;
      rnpvVsPostMoney: number | null;
      source: string | null;
      sourceUrl: string | null;
    } | null;
  };
  notes: CompanyNote[];
  sources: { field: string; source: string; url: string | null }[];
}

// ── Compliance wall: private notes + restricted list (Phase J) ────────────────

export interface NoteEntry {
  id: string;
  createdAt: string;
  subject: string;
  subjectTicker: string | null;
  source: string | null;
  isPublicSubject: boolean;
  isMaterialNonpublic: boolean;
  restricted: boolean;
}

export interface NoteCreateResult {
  id: string;
  subject: string;
  subjectTicker: string | null;
  restrictedTriggered: boolean;
}

export interface RestrictedEntry {
  ticker: string;
  reason: string;
  createdAt: string;
}

// ── Competitive landscape (Phase L) ───────────────────────────────────────────

export interface Competitor {
  sponsor: string;
  nctId: string | null;
  title: string | null;
  phase: string | null;
  status: string | null;
  condition: string | null;
  probApproval: number | null;
  source_url: string | null;
}

export interface CompetitionData {
  indication: string | null;
  leadPhase: string | null;
  leadProgram?: { title: string | null; nctId: string | null };
  competitorCount?: number;
  competitors: Competitor[];
  note?: string;
  source?: string;
  source_url?: string;
}

// ── Cross-border A/H/US (Phase M) ─────────────────────────────────────────────

export interface CrossBorderLeg {
  exchange: 'CN' | 'HK' | 'US';
  ticker: string;
  currency: string;
  priceLocal: number | null;
  pricePerShareUsd: number | null;
  premiumVsRefPct: number | null;
  adsRatio?: number;
}

export interface CrossBorderData {
  ticker: string;
  cross_border: boolean;
  name?: string;
  referenceExchange?: 'CN' | 'HK' | 'US' | null;
  usdhkd_rate?: number;
  usdcny_rate?: number;
  legs?: CrossBorderLeg[];
  listedExchanges?: string[];
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
