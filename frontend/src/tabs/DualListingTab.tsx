import { useState, useEffect } from 'react';
import { fetchDualListing } from '@/api';
import { SkeletonGrid } from '@/components/Skeleton';
import { ExternalLink } from 'lucide-react';
import type { DualListingData } from '@/types';

function StatCard({ label, value, sub, color = 'text-ink' }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="bg-elevated border border-line rounded-lg p-3 flex flex-col gap-0.5">
      <p className="text-[10px] uppercase tracking-wider text-dim">{label}</p>
      <p className={`text-base font-mono font-semibold ${color}`}>{value}</p>
      {sub && <p className="text-[10px] text-dim">{sub}</p>}
    </div>
  );
}

export function DualListingTab({ ticker }: { ticker: string }) {
  const [data, setData]       = useState<DualListingData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    setLoading(true); setError(null);
    fetchDualListing(ticker)
      .then(setData)
      .catch(() => setError('Failed to load dual listing data'))
      .finally(() => setLoading(false));
  }, [ticker]);

  if (loading) return <SkeletonGrid count={4} className="h-16" />;
  if (error)   return <p className="text-sm text-dim">{error}</p>;
  if (!data)   return null;

  // Not dual-listed
  if (!data.dual_listed && data.status === 'none') {
    return (
      <div className="bg-elevated border border-line rounded-lg p-5 text-center space-y-1">
        <p className="text-sm text-dim">{ticker.toUpperCase()} is not dual-listed.</p>
        <p className="text-[10px] text-dim">
          Dual-listed stocks trade on both HKEX and a US exchange (NASDAQ/NYSE) simultaneously.
          The same company can trade at different prices in each market, creating a premium or discount.
        </p>
      </div>
    );
  }

  // Delisted ADS
  if (data.status === 'delisted') {
    return (
      <div className="space-y-4">
        <div className="bg-amber-900/20 border border-amber-700/30 rounded-lg px-4 py-3">
          <p className="text-sm font-semibold text-amber-300 mb-1">US ADS Programme Terminated</p>
          <p className="text-[11px] text-amber-200/80 leading-relaxed">{data.note}</p>
          {data.delisted_date && (
            <p className="text-[10px] text-dim mt-2">Delisted: {data.delisted_date}</p>
          )}
        </div>
        <p className="text-[10px] text-dim leading-relaxed">
          When a company voluntarily delists its US ADS, the HK shares remain the primary
          and only trading venue. This is often done to simplify capital structure or when
          US trading volume has become negligible relative to the HK listing.
        </p>
      </div>
    );
  }

  // Active dual listing
  const premDisc = data.premium_discount_pct;
  const premColor = premDisc == null ? 'text-ink' : premDisc > 2 ? 'text-down' : premDisc < -2 ? 'text-up' : 'text-ink';
  const premLabel = premDisc == null ? '—'
    : `${premDisc > 0 ? '+' : ''}${premDisc.toFixed(2)}%`;

  return (
    <div className="space-y-5">

      {/* Explainer */}
      <div className="bg-sky-900/20 border border-sky-700/30 rounded-lg px-4 py-3 text-[11px] text-sky-300/80 leading-relaxed">
        <strong className="text-sky-300">What is a dual listing?</strong>{' '}
        {ticker.toUpperCase()} trades on both HKEX and a US exchange.
        The premium/discount shows whether the HK price is higher or lower than the US price
        after adjusting for the exchange rate and ADS ratio.
        A persistent premium may signal higher HK demand; a persistent discount may indicate
        arbitrage opportunity (adjusted for trading costs and capital controls).
      </div>

      {/* Price comparison */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard
          label={`HK Price (${data.hk_ticker})`}
          value={data.hk_price_hkd != null ? `HK$${data.hk_price_hkd.toFixed(3)}` : '—'}
          sub="HKD"
        />
        <StatCard
          label={`US Price (${data.us_ticker})`}
          value={data.us_price_usd != null ? `$${data.us_price_usd.toFixed(3)}` : '—'}
          sub="USD"
        />
        <StatCard
          label="US Price (HKD equiv.)"
          value={data.us_price_hkd != null ? `HK$${data.us_price_hkd.toFixed(3)}` : '—'}
          sub={`1 USD = ${data.usdhkd_rate?.toFixed(2) ?? '—'} HKD`}
        />
        <StatCard
          label="HK Premium / Discount"
          value={premLabel}
          color={premColor}
          sub={premDisc != null && premDisc > 0 ? 'HK trades above US' : premDisc != null && premDisc < 0 ? 'HK trades below US' : ''}
        />
      </div>

      {/* ADS ratio note */}
      <div className="bg-elevated border border-line rounded-lg px-4 py-3 text-[11px] text-dim">
        <strong className="text-ink">ADS Ratio:</strong>{' '}
        1 {data.us_ticker} ADS = {data.ads_ratio ?? 1} {data.hk_ticker} ordinary share{(data.ads_ratio ?? 1) !== 1 ? 's' : ''}.
        US price has been adjusted for this ratio before computing the premium/discount.
      </div>

      {/* Links */}
      <div className="flex gap-4 text-[10px]">
        {data.hk_ticker && (
          <a
            href={`https://finance.yahoo.com/quote/${data.hk_ticker}`}
            target="_blank" rel="noopener noreferrer"
            className="text-hi hover:underline flex items-center gap-1"
          >
            {data.hk_ticker} on Yahoo <ExternalLink size={9} />
          </a>
        )}
        {data.us_ticker && (
          <a
            href={`https://finance.yahoo.com/quote/${data.us_ticker}`}
            target="_blank" rel="noopener noreferrer"
            className="text-hi hover:underline flex items-center gap-1"
          >
            {data.us_ticker} on Yahoo <ExternalLink size={9} />
          </a>
        )}
      </div>
    </div>
  );
}
