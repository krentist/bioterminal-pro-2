export function cn(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(' ');
}

export function fmt(price: number | null | undefined, sym = '$'): string {
  if (price == null || isNaN(price)) return '—';
  return `${sym}${price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function fmtChange(pct: number | null | undefined): { text: string; pos: boolean | null } {
  if (pct == null || isNaN(pct)) return { text: '—', pos: null };
  const pos = pct >= 0;
  return { text: `${pos ? '+' : ''}${pct.toFixed(2)}%`, pos };
}

/** Compact B/M/K notation for market cap and revenue */
export function fmtBig(v: number | null | undefined, sym = '$'): string {
  if (v == null || isNaN(v) || v === 0) return '—';
  const abs = Math.abs(v);
  if (abs >= 1e12) return `${sym}${(v / 1e12).toFixed(2)}T`;
  if (abs >= 1e9)  return `${sym}${(v / 1e9).toFixed(2)}B`;
  if (abs >= 1e6)  return `${sym}${(v / 1e6).toFixed(2)}M`;
  return `${sym}${v.toFixed(0)}`;
}

export function fmtMultiple(v: number | null | undefined): string {
  if (v == null || isNaN(v)) return '—';
  return `${v.toFixed(1)}x`;
}

/** Percentage value that is already a decimal fraction, e.g. 0.682 → +68.2% */
export function fmtPctFrac(v: number | null | undefined): string {
  if (v == null || isNaN(v)) return '—';
  const pct = v * 100;
  return `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%`;
}

/** Percentage value already in percentage points, e.g. 12.3 → +12.3% */
export function fmtPct(v: number | null | undefined): string {
  if (v == null || isNaN(v)) return '—';
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;
}

export function fmtVol(v: number | null | undefined): string {
  if (v == null || isNaN(v)) return '—';
  if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(0)}K`;
  return v.toFixed(0);
}

export function timeAgo(dateStr: string | null | undefined): string {
  if (!dateStr) return '';
  const diff = Date.now() - new Date(dateStr).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 60)  return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24)  return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export function fmtDate(s: string | null | undefined): string {
  if (!s) return '—';
  try {
    return new Date(s).toLocaleDateString('en-US', { year: 'numeric', month: 'short' });
  } catch {
    return s;
  }
}
