import { useState, useEffect } from 'react';
import { fetchNews } from '@/api';
import { SkeletonList } from '@/components/Skeleton';
import { timeAgo } from '@/lib/utils';
import { ExternalLink } from 'lucide-react';
import type { NewsItem } from '@/types';

export function NewsTab({ ticker }: { ticker: string }) {
  const [news,    setNews]    = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);

  useEffect(() => {
    setLoading(true); setError(null);
    fetchNews(ticker)
      .then(setNews)
      .catch(() => setError('Failed to load news'))
      .finally(() => setLoading(false));
  }, [ticker]);

  if (loading) return <SkeletonList count={5} />;
  if (error)   return <p className="text-sm text-dim">{error}</p>;
  if (!news.length) return <p className="text-sm text-dim">No recent news for {ticker}</p>;

  return (
    <div className="space-y-2 max-w-2xl">
      {news.map((item, i) => (
        <a
          key={i}
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          className="block p-3 bg-surface rounded-lg border border-line hover:border-hi/40 transition-colors group"
        >
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-[10px] text-dim bg-elevated px-1.5 py-0.5 rounded border border-line">
              {item.publisher}
            </span>
            <span className="text-[10px] text-dim ml-auto">{timeAgo(item.publishedAt)}</span>
          </div>
          <div className="flex items-start justify-between gap-2">
            <p className="text-[12px] text-ink font-medium leading-snug group-hover:text-hi transition-colors">
              {item.title}
            </p>
            <ExternalLink size={11} className="text-dim flex-none mt-0.5" />
          </div>
          {item.summary && (
            <p className="text-[11px] text-dim mt-1.5 line-clamp-2 leading-relaxed">
              {item.summary}
            </p>
          )}
        </a>
      ))}
    </div>
  );
}
