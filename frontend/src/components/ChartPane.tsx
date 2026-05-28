import { useEffect, useRef } from 'react';
import {
  createChart, ColorType, CrosshairMode,
  type IChartApi, type ISeriesApi, type UTCTimestamp,
} from 'lightweight-charts';
import type { Bar } from '@/types';

interface Props {
  bars:           Bar[];
  range:          string;
  ranges:         string[];
  onRangeChange:  (r: string) => void;
  dark:           boolean;
  loading:        boolean;
}

const T = {
  dark: {
    bg:       '#111111',
    text:     '#8b949e',
    grid:     '#1a1a1a',
    border:   '#2a2a2a',
    upColor:  '#3fb950',
    dnColor:  '#f85149',
    upVol:    'rgba(63, 185, 80, 0.25)',
    dnVol:    'rgba(248, 81, 73, 0.25)',
  },
  light: {
    bg:       '#f6f8fa',
    text:     '#656d76',
    grid:     '#eaeef2',
    border:   '#d0d7de',
    upColor:  '#1a7f37',
    dnColor:  '#cf222e',
    upVol:    'rgba(26, 127, 55, 0.2)',
    dnVol:    'rgba(207, 34, 46, 0.2)',
  },
};

function toTime(t: number): UTCTimestamp {
  return (t > 1e10 ? Math.floor(t / 1000) : t) as UTCTimestamp;
}

export function ChartPane({ bars, range, ranges, onRangeChange, dark, loading }: Props) {
  const containerRef  = useRef<HTMLDivElement>(null);
  const chartRef      = useRef<IChartApi | null>(null);
  const candleRef     = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volRef        = useRef<ISeriesApi<'Histogram'> | null>(null);

  // Create / re-create chart when theme changes
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const c = dark ? T.dark : T.light;

    const chart = createChart(el, {
      layout: {
        background: { type: ColorType.Solid, color: c.bg },
        textColor:  c.text,
        fontFamily: '"JetBrains Mono", monospace',
        fontSize:   11,
      },
      grid: {
        vertLines: { color: c.grid },
        horzLines: { color: c.grid },
      },
      crosshair: {
        mode:     CrosshairMode.Normal,
        vertLine: { color: c.border, style: 1, labelBackgroundColor: c.border },
        horzLine: { color: c.border, style: 1, labelBackgroundColor: c.border },
      },
      rightPriceScale: { borderColor: c.border },
      timeScale:       { borderColor: c.border, timeVisible: true, secondsVisible: false },
      width:  el.clientWidth,
      height: el.clientHeight,
    });

    const candle = chart.addCandlestickSeries({
      upColor:        c.upColor,
      downColor:      c.dnColor,
      borderUpColor:  c.upColor,
      borderDownColor:c.dnColor,
      wickUpColor:    c.upColor,
      wickDownColor:  c.dnColor,
    });

    const vol = chart.addHistogramSeries({
      priceFormat:  { type: 'volume' },
      priceScaleId: 'vol',
    });
    chart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });

    chartRef.current  = chart;
    candleRef.current = candle;
    volRef.current    = vol;

    const ro = new ResizeObserver(() => {
      if (el) chart.resize(el.clientWidth, el.clientHeight);
    });
    ro.observe(el);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = candleRef.current = volRef.current = null;
    };
  }, [dark]); // eslint-disable-line

  // Feed data
  useEffect(() => {
    const candle = candleRef.current;
    const vol    = volRef.current;
    if (!candle || !vol || !bars.length) return;

    const c = dark ? T.dark : T.light;

    candle.setData(bars.map(b => ({
      time:  toTime(b.time),
      open:  b.open,
      high:  b.high,
      low:   b.low,
      close: b.close,
    })));

    vol.setData(bars.map(b => ({
      time:  toTime(b.time),
      value: b.volume,
      color: b.close >= b.open ? c.upVol : c.dnVol,
    })));

    chartRef.current?.timeScale().fitContent();
  }, [bars, dark]);

  return (
    <div className="flex flex-col h-full bg-surface">
      {/* Range selector */}
      <div className="flex items-center gap-0.5 px-3 pt-2 pb-1 flex-none">
        {ranges.map(r => (
          <button
            key={r}
            onClick={() => onRangeChange(r)}
            className={[
              'px-2 py-0.5 text-[10px] font-mono rounded transition-colors',
              r === range
                ? 'bg-hi text-white'
                : 'text-dim hover:text-ink hover:bg-elevated',
            ].join(' ')}
          >
            {r}
          </button>
        ))}
      </div>

      {/* Chart */}
      <div className="relative flex-1 min-h-0">
        <div ref={containerRef} className="absolute inset-0" />
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xs text-dim font-mono animate-pulse">Loading chart…</span>
          </div>
        )}
      </div>
    </div>
  );
}
