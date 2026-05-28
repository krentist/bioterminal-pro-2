import { useState, useEffect } from 'react';
import { fetchFilings } from '@/api';
import { SkeletonList } from '@/components/Skeleton';
import { ExternalLink } from 'lucide-react';
import type { Filing } from '@/types';

const TYPE_COLORS: Record<string, string> = {
  'Results':                     'text-green-400 bg-green-500/10 border-green-500/20',
  'Announcements and Notices':   'text-sky-400 bg-sky-500/10 border-sky-500/20',
  'Circulars':                   'text-amber-400 bg-amber-500/10 border-amber-500/20',
  'Prospectuses':                'text-purple-400 bg-purple-500/10 border-purple-500/20',
};

function typeColor(type: string): string {
  for (const [key, color] of Object.entries(TYPE_COLORS)) {
    if (type.toLowerCase().includes(key.toLowerCase())) return color;
  }
  return 'text-dim bg-elevated border-line';
}

const FILTERS = ['All', 'Results', 'Announcements', 'Circulars'];

export function FilingsTab({ ticker }: { ticker: string }) {
  const isHK = ticker.toUpperCase().endsWith('.HK');

  const [filings, setFilings]   = useState<Filing[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);
  const [filter, setFilter]     = useState('All');

  useEffect(() => {
    if (!isHK) { setLoading(false); return; }
    setLoading(true); setError(null);
    fetchFilings(ticker)
      .then(setFilings)
      .catch(() => setError('Failed to load HKEXnews filings'))
      .finally(() => setLoading(false));
  }, [ticker, isHK]);

  if (!isHK) {
    return (
      <div className="bg-elevated border border-line rounded-lg p-5 text-center space-y-2">
        <p className="text-sm text-dim">HKEXnews filings are only available for HK-listed stocks.</p>
        <a
          href={`https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=${ticker}&type=10-K`}
          target="_blank" rel="noopener noreferrer"
          className="text-[11px] text-hi hover:underline flex items-center justify-center gap-1"
        >
          View SEC EDGAR filings for {ticker} <ExternalLink size={10} />
        </a>
      </div>
    );
  }

  if (loading) return <SkeletonList count={6} className="h-12" />;
  if (error)   return <p className="text-sm text-dim">{error}</p>;

  const filtered = filter === 'All'
    ? filings
    : filings.filter(f => f.type.toLowerCase().includes(filter.toLowerCase()));

  return (
    <div className="space-y-4">

      {/* Header */}
      <div className="flex items-center justify-between">
        <p className="text-[11px] text-dim">
          {filings.length} filing{filings.length !== 1 ? 's' : ''} from HKEXnews
        </p>
        <a
          href={`https://www1.hkexnews.hk/search/titlesearch.xhtml?kw=${ticker.replace('.HK', '').replace(/^0+/, '')}`}
          target="_blank" rel="noopener noreferrer"
          className="text-[10px] text-hi hover:underline flex items-center gap-1"
        >
          HKEXnews <ExternalLink size={9} />
        </a>
      </div>

      {/* Filter chips */}
      <div className="flex gap-1.5 flex-wrap">
        {FILTERS.map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`text-[10px] px-2.5 py-0.5 rounded border transition-colors ${
              filter === f ? 'bg-sky-600/20 border-sky-500/40 text-sky-300' : 'border-line text-dim hover:text-ink'
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      {/* Filing list */}
      {!filtered.length ? (
        <p className="text-sm text-dim">No filings match this filter.</p>
      ) : (
        <div className="space-y-1.5">
          {filtered.map((filing, i) => (
            <div key={i} className="flex items-start gap-3 p-2.5 rounded-lg border border-line hover:bg-elevated/60 transition-colors">
              <span className="text-[10px] font-mono text-dim shrink-0 mt-0.5 w-20">{filing.date}</span>
              <div className="flex-1 min-w-0">
                {filing.url ? (
                  <a
                    href={filing.url}
                    target="_blank" rel="noopener noreferrer"
                    className="text-[11px] text-ink hover:text-hi line-clamp-2 leading-snug flex items-start gap-1"
                  >
                    {filing.title}
                    <ExternalLink size={9} className="shrink-0 mt-0.5" />
                  </a>
                ) : (
                  <p className="text-[11px] text-ink line-clamp-2 leading-snug">{filing.title}</p>
                )}
              </div>
              {filing.type && (
                <span className={`text-[9px] font-medium px-1.5 py-0.5 rounded border shrink-0 ${typeColor(filing.type)}`}>
                  {filing.type.split(' ').slice(0, 2).join(' ')}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
