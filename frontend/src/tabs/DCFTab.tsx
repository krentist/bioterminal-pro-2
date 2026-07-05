import { useState, useEffect, useRef, useCallback } from 'react';
import { fetchDCF, postDCF } from '@/api';
import { Skeleton } from '@/components/Skeleton';
import { RestrictedPanel } from '@/components/PanelState';
import { fmt } from '@/lib/utils';
import type { DCFData } from '@/types';

interface Assumptions {
  revenueGrowthY1: number;
  revenueGrowthY2: number;
  revenueGrowthY3: number;
  revenueGrowthY4: number;
  revenueGrowthY5: number;
  wacc: number;
  terminalGrowth: number;
  operatingMargin: number;
  taxRate: number;
  capexPercent: number;
}

function extractAssumptions(dcf: Record<string, number | string | null> | undefined): Assumptions {
  const n = (k: string, d: number) =>
    typeof dcf?.[k] === 'number' ? (dcf[k] as number) : d;
  return {
    revenueGrowthY1: n('revenueGrowthY1', 0.15),
    revenueGrowthY2: n('revenueGrowthY2', 0.12),
    revenueGrowthY3: n('revenueGrowthY3', 0.10),
    revenueGrowthY4: n('revenueGrowthY4', 0.08),
    revenueGrowthY5: n('revenueGrowthY5', 0.06),
    wacc:            n('wacc',            0.10),
    terminalGrowth:  n('terminalGrowth',  0.03),
    operatingMargin: n('operatingMargin', 0.20),
    taxRate:         n('taxRate',         0.21),
    capexPercent:    n('capexPercent',    0.05),
  };
}

function pctLabel(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

interface SliderRowProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
}

function SliderRow({ label, value, min, max, step, onChange }: SliderRowProps) {
  const pos = value >= 0;
  return (
    <div className="flex items-center gap-3 py-2">
      <span className="text-[10px] text-dim w-32 flex-none leading-none">{label}</span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={e => onChange(parseFloat(e.target.value))}
        className="flex-1 dcf-slider"
      />
      <span className={`text-[11px] font-mono w-14 text-right flex-none ${pos ? 'text-up' : 'text-down'}`}>
        {pctLabel(value)}
      </span>
    </div>
  );
}

interface SliderGroupProps {
  title: string;
  children: React.ReactNode;
}

function SliderGroup({ title, children }: SliderGroupProps) {
  return (
    <div className="border border-line rounded bg-surface">
      <div className="px-3 py-2 border-b border-line">
        <p className="text-[10px] text-dim uppercase tracking-wider font-medium">{title}</p>
      </div>
      <div className="px-3 py-1">{children}</div>
    </div>
  );
}

export function DCFTab({ ticker }: { ticker: string }) {
  const [result,       setResult]       = useState<DCFData | null>(null);
  const [assumptions,  setAssumptions]  = useState<Assumptions | null>(null);
  const [loading,      setLoading]      = useState(true);
  const [recalculating,setRecalculating]= useState(false);
  const [error,        setError]        = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    setLoading(true); setError(null);
    fetchDCF(ticker)
      .then(data => {
        setResult(data);
        setAssumptions(extractAssumptions(data.dcf ?? undefined));
      })
      .catch(() => setError('Failed to load DCF valuation'))
      .finally(() => setLoading(false));
  }, [ticker]);

  const update = useCallback(<K extends keyof Assumptions>(key: K, value: number) => {
    setAssumptions(prev => {
      if (!prev) return prev;
      const next = { ...prev, [key]: value };
      clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(async () => {
        setRecalculating(true);
        try {
          const data = await postDCF(ticker, next);
          setResult(data);
        } catch { /* keep previous result */ }
        finally { setRecalculating(false); }
      }, 400);
      return next;
    });
  }, [ticker]);

  if (loading) return (
    <div className="space-y-3 max-w-lg">
      <Skeleton className="h-20" />
      <Skeleton className="h-48" />
      <Skeleton className="h-28" />
      <Skeleton className="h-36" />
    </div>
  );
  if (error || !result || !assumptions) return (
    <p className="text-sm text-dim">{error ?? 'No DCF data available'}</p>
  );
  if (result.restricted) return <RestrictedPanel reason={result.restrictedReason} />;

  // The backend routes pre-revenue / loss-making companies to rNPV, because a DCF
  // built on assumed positive margins would be fictitious. Say so plainly rather
  // than rendering rNPV numbers under DCF sliders that don't apply.
  if (result.valuationMethod === 'rNPV') {
    const sym = result.currencySymbol || '$';
    return (
      <div className="space-y-4 max-w-lg">
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-[11px] text-amber-300/90 leading-relaxed">
          <strong className="text-amber-300">DCF not applicable.</strong> This company has no
          positive operating profit, so a discounted-cash-flow model built on assumed margins
          would be misleading. Clinical-stage biotech is valued by its risk-adjusted pipeline —
          use the <strong>rNPV</strong> panel. The figure below is that rNPV result.
        </div>
        <div className="border border-line rounded bg-surface px-4 py-3">
          <p className="text-[10px] text-dim uppercase tracking-wider mb-1.5">Intrinsic value — rNPV</p>
          <p className="text-3xl font-mono font-light text-ink leading-none">
            {fmt(result.impliedSharePrice, sym)}
          </p>
          {result.upside != null && (
            <p className={`text-[11px] font-mono mt-1 ${result.upside >= 0 ? 'text-up' : 'text-down'}`}>
              {result.upside >= 0 ? '+' : ''}{(result.upside * 100).toFixed(1)}% vs current price
            </p>
          )}
          {result.assumptionNote && (
            <p className="text-[10px] text-dim mt-2 leading-relaxed">{result.assumptionNote}</p>
          )}
        </div>
      </div>
    );
  }

  const sym     = result.currencySymbol || '$';
  const upside  = result.upside ?? 0;
  const positive = upside >= 0;

  return (
    <div className="space-y-4 max-w-lg">
      {/* Result card */}
      <div className={`border border-line rounded bg-surface transition-opacity ${recalculating ? 'opacity-50' : ''}`}>
        <div className="px-4 pt-3 pb-2 border-b border-line flex items-end justify-between gap-4">
          <div>
            <p className="text-[10px] text-dim uppercase tracking-wider mb-1.5">Intrinsic Value — DCF</p>
            <p className="text-3xl font-mono font-light text-ink leading-none">
              {fmt(result.impliedSharePrice, sym)}
            </p>
            <p className="text-[10px] text-dim mt-1">Implied share price</p>
          </div>
          <div className={`text-right flex-none ${positive ? 'text-up' : 'text-down'}`}>
            <p className="text-[10px] text-dim mb-1">vs. current</p>
            <p className="text-2xl font-mono font-semibold leading-none">
              {positive ? '+' : ''}{upside.toFixed(1)}%
            </p>
          </div>
        </div>
        <div className="px-4 py-2.5">
          <div className="bg-elevated rounded-full h-1 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${positive ? 'bg-up' : 'bg-down'}`}
              style={{ width: `${Math.min(100, Math.abs(upside))}%` }}
            />
          </div>
        </div>
        {recalculating && (
          <p className="px-4 pb-2 text-[10px] text-dim animate-pulse">Recalculating…</p>
        )}
      </div>

      {/* Revenue growth sliders */}
      <SliderGroup title="Revenue Growth">
        {(['revenueGrowthY1','revenueGrowthY2','revenueGrowthY3','revenueGrowthY4','revenueGrowthY5'] as const).map((key, i) => (
          <SliderRow
            key={key}
            label={`Year ${i + 1}`}
            value={assumptions[key]}
            min={-0.20} max={0.60} step={0.005}
            onChange={v => update(key, v)}
          />
        ))}
      </SliderGroup>

      {/* Discount rate */}
      <SliderGroup title="Discount Rate">
        <SliderRow label="WACC" value={assumptions.wacc} min={0.05} max={0.20} step={0.005} onChange={v => update('wacc', v)} />
        <SliderRow label="Terminal Growth" value={assumptions.terminalGrowth} min={0.00} max={0.05} step={0.005} onChange={v => update('terminalGrowth', v)} />
      </SliderGroup>

      {/* Margins & capital */}
      <SliderGroup title="Margins &amp; Capital">
        <SliderRow label="Operating Margin" value={assumptions.operatingMargin} min={0.00} max={0.50} step={0.005} onChange={v => update('operatingMargin', v)} />
        <SliderRow label="Tax Rate" value={assumptions.taxRate} min={0.00} max={0.40} step={0.005} onChange={v => update('taxRate', v)} />
        <SliderRow label="CapEx %" value={assumptions.capexPercent} min={0.00} max={0.20} step={0.005} onChange={v => update('capexPercent', v)} />
      </SliderGroup>
    </div>
  );
}
