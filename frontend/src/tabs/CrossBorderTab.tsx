import { useState, useEffect } from 'react';
import { fetchCrossBorder } from '@/api';
import { PanelHeader, PanelLoading, PanelMessage, Callout } from '@/components/PanelState';
import type { CrossBorderData, CrossBorderLeg } from '@/types';

const EXCH_META: Record<string, { flag: string; name: string; sym: string }> = {
  CN: { flag: '🇨🇳', name: 'Shanghai/Shenzhen', sym: '¥' },
  HK: { flag: '🇭🇰', name: 'Hong Kong',         sym: 'HK$' },
  US: { flag: '🇺🇸', name: 'US ADS',            sym: '$' },
};

function premColor(p: number | null): string {
  if (p == null) return 'text-ink';
  if (p > 2) return 'text-down';   // trades at a premium to reference
  if (p < -2) return 'text-up';    // trades at a discount (cheaper)
  return 'text-ink';
}

function LegRow({ leg, isRef }: { leg: CrossBorderLeg; isRef: boolean }) {
  const m = EXCH_META[leg.exchange] ?? { flag: '', name: leg.exchange, sym: '' };
  const prem = leg.premiumVsRefPct;
  return (
    <tr className="row-hover transition-colors">
      <td className="py-2.5 pr-4 whitespace-nowrap">
        <span className="mr-1.5">{m.flag}</span>
        <span className="font-mono text-ink">{leg.ticker}</span>
        {isRef && (
          <span className="ml-2 text-[8px] uppercase tracking-wider text-hi bg-hi/10 border border-hi/25 rounded px-1 py-0.5">
            ref
          </span>
        )}
        <div className="text-[9px] text-dim mt-0.5">{m.name}</div>
      </td>
      <td className="py-2.5 pr-4 text-right font-mono text-ink whitespace-nowrap">
        {leg.priceLocal != null ? `${m.sym}${leg.priceLocal.toLocaleString(undefined, { maximumFractionDigits: 2 })}` : '—'}
        <div className="text-[9px] text-dim">{leg.currency}{leg.adsRatio ? ` · ADS×${leg.adsRatio}` : ''}</div>
      </td>
      <td className="py-2.5 pr-4 text-right font-mono text-ink whitespace-nowrap">
        {leg.pricePerShareUsd != null ? `$${leg.pricePerShareUsd.toFixed(4)}` : '—'}
      </td>
      <td className={`py-2.5 text-right font-mono font-semibold whitespace-nowrap ${premColor(prem)}`}>
        {isRef ? '—' : prem != null ? `${prem > 0 ? '+' : ''}${prem.toFixed(2)}%` : '—'}
      </td>
    </tr>
  );
}

export function CrossBorderTab({ ticker }: { ticker: string }) {
  const [data, setData]       = useState<CrossBorderData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    setLoading(true); setError(null);
    fetchCrossBorder(ticker)
      .then(setData)
      .catch(() => setError('Failed to load cross-border data'))
      .finally(() => setLoading(false));
  }, [ticker]);

  if (loading) return <PanelLoading variant="grid" />;
  if (error)   return <PanelMessage kind="error" title={error} />;
  if (!data)   return null;

  if (!data.cross_border) {
    return (
      <PanelMessage
        kind="empty"
        title={`${ticker.toUpperCase()} is not part of a tracked A/H/US group.`}
        detail="Cross-border view covers biotechs listed across Mainland China (A-share), Hong Kong (H-share), and/or the US simultaneously — e.g. BeiGene, WuXi AppTec, Junshi, CanSino."
      />
    );
  }

  const refExch = data.referenceExchange;

  return (
    <div className="space-y-4">
      <PanelHeader
        title={data.name || 'Cross-border'}
        source="Yahoo Finance"
        right={<span className="text-[9px] text-dim">{(data.listedExchanges ?? []).join(' · ')}</span>}
      />

      <Callout tone="info" title="One asset, multiple exchanges">
        Each share class is priced on a common <strong>per-ordinary-share USD</strong> basis
        (the US ADS is divided by its ratio) and compared to the{' '}
        {refExch ? EXCH_META[refExch]?.name ?? refExch : 'reference'} listing. A large positive
        A-share premium is the well-known A/H gap driven by mainland capital controls.
      </Callout>

      <div className="overflow-x-auto">
        <table className="w-full text-[11px] border-separate border-spacing-y-0">
          <thead>
            <tr className="text-dim text-[10px] uppercase tracking-wider">
              <th className="text-left  py-2 pr-4 font-medium border-b border-line">Listing</th>
              <th className="text-right py-2 pr-4 font-medium border-b border-line">Local price</th>
              <th className="text-right py-2 pr-4 font-medium border-b border-line whitespace-nowrap">USD / share</th>
              <th className="text-right py-2 font-medium border-b border-line whitespace-nowrap">vs ref</th>
            </tr>
          </thead>
          <tbody>
            {(data.legs ?? []).map(leg => (
              <LegRow key={leg.ticker} leg={leg} isRef={leg.exchange === refExch} />
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex gap-4 text-[9px] text-dim">
        {data.usdhkd_rate != null && <span>USD/HKD {data.usdhkd_rate.toFixed(3)}</span>}
        {data.usdcny_rate != null && <span>USD/CNY {data.usdcny_rate.toFixed(3)}</span>}
      </div>
    </div>
  );
}
