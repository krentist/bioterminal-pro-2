import { useState, useEffect, useCallback } from 'react';
import { fetchWatchlist, addToWatchlist, removeFromWatchlist, fetchQuote } from '@/api';
import { Skeleton } from '@/components/Skeleton';
import { Plus, X, RefreshCw } from 'lucide-react';
import { fmt, fmtChange } from '@/lib/utils';
import type { Quote } from '@/types';

interface WatchItem { ticker: string; quote?: Quote; }

export function WatchlistTab({ currentTicker, onSelect }: { currentTicker: string; onSelect: (t: string) => void }) {
  const [items,    setItems]    = useState<WatchItem[]>([]);
  const [loading,  setLoading]  = useState(true);
  const [adding,   setAdding]   = useState(false);
  const [newTicker,setNewTicker]= useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const tickers = await fetchWatchlist();
      const withQ = await Promise.allSettled(
        tickers.map(async t => ({ ticker: t, quote: await fetchQuote(t) }))
      );
      setItems(withQ.map((r, i) => r.status === 'fulfilled' ? r.value : { ticker: tickers[i] }));
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleAdd(t: string) {
    const upper = t.trim().toUpperCase();
    if (!upper) return;
    await addToWatchlist(upper);
    setNewTicker('');
    setAdding(false);
    load();
  }

  async function handleRemove(t: string) {
    await removeFromWatchlist(t);
    setItems(prev => prev.filter(i => i.ticker !== t));
  }

  const alreadyWatching = items.some(i => i.ticker === currentTicker);

  if (loading) return (
    <div className="space-y-2 max-w-sm">
      {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-12" />)}
    </div>
  );

  return (
    <div className="space-y-3 max-w-sm">
      {/* Actions */}
      <div className="flex items-center gap-2 flex-wrap">
        {!alreadyWatching && (
          <button
            onClick={() => handleAdd(currentTicker)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] border border-line rounded-lg text-dim hover:border-hi hover:text-hi transition-colors"
          >
            <Plus size={11} />
            Watch {currentTicker}
          </button>
        )}
        <button
          onClick={() => setAdding(a => !a)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] border border-line rounded-lg text-dim hover:border-hi hover:text-hi transition-colors"
        >
          <Plus size={11} />
          Add ticker
        </button>
        <button
          onClick={load}
          className="p-1.5 text-dim hover:text-ink hover:bg-elevated rounded-lg transition-colors"
          title="Refresh"
        >
          <RefreshCw size={12} />
        </button>
      </div>

      {/* Add input */}
      {adding && (
        <div className="flex gap-2">
          <input
            autoFocus
            type="text"
            value={newTicker}
            onChange={e => setNewTicker(e.target.value.toUpperCase())}
            onKeyDown={e => {
              if (e.key === 'Enter')  handleAdd(newTicker);
              if (e.key === 'Escape') setAdding(false);
            }}
            placeholder="Ticker (e.g. MRNA)"
            className="flex-1 px-3 py-1.5 text-[11px] font-mono bg-elevated border border-line rounded-lg text-ink placeholder:text-dim outline-none focus:border-hi transition-colors"
          />
          <button
            onClick={() => handleAdd(newTicker)}
            className="px-3 py-1.5 text-[11px] bg-hi text-white rounded-lg hover:opacity-90 transition-opacity"
          >
            Add
          </button>
        </div>
      )}

      {/* List */}
      {items.length === 0 ? (
        <p className="text-sm text-dim">Your watchlist is empty</p>
      ) : (
        <div className="space-y-1">
          {items.map(item => {
            const change = item.quote ? fmtChange(item.quote.changePercent) : null;
            const isCurrent = item.ticker === currentTicker;
            return (
              <div
                key={item.ticker}
                className={[
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg border transition-colors group',
                  isCurrent ? 'border-hi/40 bg-hi/5' : 'border-line bg-surface hover:border-line/80',
                ].join(' ')}
              >
                <button
                  onClick={() => onSelect(item.ticker)}
                  className="flex-1 flex items-center gap-3 text-left min-w-0"
                >
                  <span className={`text-[11px] font-mono font-medium w-24 flex-none truncate ${isCurrent ? 'text-hi' : 'text-ink'}`}>
                    {item.ticker}
                  </span>
                  {item.quote && (
                    <>
                      <span className="text-[11px] font-mono text-ink">
                        {fmt(item.quote.price, item.quote.currencySymbol)}
                      </span>
                      {change && change.pos !== null && (
                        <span className={`text-[11px] font-mono ${change.pos ? 'text-up' : 'text-down'}`}>
                          {change.text}
                        </span>
                      )}
                    </>
                  )}
                </button>
                <button
                  onClick={() => handleRemove(item.ticker)}
                  className="opacity-0 group-hover:opacity-100 p-0.5 text-dim hover:text-down transition-all"
                >
                  <X size={11} />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
