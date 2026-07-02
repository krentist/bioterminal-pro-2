import { useEffect, useState } from 'react';
import { fetchStock } from '@/api';
import type { Bar } from '@/types';

export function useChartData(ticker: string, range: string) {
  const [bars,    setBars]    = useState<Bar[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchStock(ticker, range)
      .then(d => { if (!cancelled) setBars(d.bars ?? []); })
      .catch(console.error)
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [ticker, range]);

  return { bars, loading };
}
