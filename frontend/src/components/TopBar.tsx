import { useState, useRef, useEffect } from 'react';
import { Search, Sun, Moon, X } from 'lucide-react';
import { fetchSearch } from '@/api';
import { fmt, fmtChange } from '@/lib/utils';
import type { Quote, SearchResult } from '@/types';

interface Props {
  ticker:          string | null;
  quote:           Quote | null;
  dark:            boolean;
  onToggleDark:    () => void;
  onSelectTicker:  (t: string) => void;
}

export function TopBar({ ticker, quote, dark, onToggleDark, onSelectTicker }: Props) {
  const [query,   setQuery]   = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open,    setOpen]    = useState(false);
  const [focused, setFocused] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const inputRef    = useRef<HTMLInputElement>(null);
  const dropRef     = useRef<HTMLDivElement>(null);

  // Debounced search
  useEffect(() => {
    clearTimeout(debounceRef.current);
    if (!query.trim()) { setResults([]); setOpen(false); return; }
    debounceRef.current = setTimeout(async () => {
      try {
        const d = await fetchSearch(query);
        setResults(d.quotes?.slice(0, 8) ?? []);
        setOpen(true);
      } catch { /* ignore */ }
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [query]);

  // Close dropdown on outside click
  useEffect(() => {
    function handle(e: MouseEvent) {
      if (dropRef.current && !dropRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, []);

  function select(symbol: string) {
    setQuery('');
    setOpen(false);
    inputRef.current?.blur();
    onSelectTicker(symbol);
  }

  const change = quote ? fmtChange(quote.changePercent) : null;

  return (
    <header className="flex-none flex items-center gap-3 px-4 h-12 border-b border-line bg-surface z-10">

      {/* Brand */}
      <span className="hidden sm:block text-[13px] font-semibold tracking-tight text-ink whitespace-nowrap">
        Bio<span className="text-hi">Terminal</span>
      </span>

      <div className="w-px h-4 bg-line hidden sm:block" />

      {/* Search box */}
      <div ref={dropRef} className="relative flex-1 max-w-sm">
        <div className={[
          'flex items-center gap-2 px-2.5 py-1.5 rounded-lg border transition-colors bg-elevated',
          focused ? 'border-hi' : 'border-line',
        ].join(' ')}>
          <Search size={12} className="text-dim flex-none" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            onKeyDown={e => {
              if (e.key === 'Enter' && results.length > 0) select(results[0].symbol);
              if (e.key === 'Escape') { setQuery(''); setOpen(false); }
            }}
            placeholder={ticker ?? 'Search ticker…'}
            className="flex-1 min-w-0 bg-transparent text-[12px] font-mono text-ink placeholder:text-dim outline-none"
          />
          {query && (
            <button onClick={() => setQuery('')} className="text-dim hover:text-ink">
              <X size={10} />
            </button>
          )}
        </div>

        {/* Dropdown */}
        {open && results.length > 0 && (
          <div className="absolute top-full left-0 right-0 mt-1 bg-elevated border border-line rounded-lg overflow-hidden dropdown-shadow z-50">
            {results.map(r => (
              <button
                key={r.symbol}
                onMouseDown={() => select(r.symbol)}
                className="w-full flex items-center gap-3 px-3 py-2 hover:bg-surface text-left transition-colors"
              >
                <span className="font-mono text-[11px] text-hi font-medium w-20 truncate flex-none">{r.symbol}</span>
                <span className="text-[11px] text-dim flex-1 truncate">{r.shortname}</span>
                <span className="text-[10px] text-dim bg-elevated px-1.5 py-0.5 rounded border border-line flex-none">
                  {r.exchange}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Live price badge */}
      {ticker && quote && (
        <div className="hidden sm:flex items-center gap-2 text-[12px] font-mono">
          <span className="text-ink font-semibold">{ticker}</span>
          <span className="text-ink">{fmt(quote.price, quote.currencySymbol)}</span>
          {change && change.pos !== null && (
            <span className={change.pos ? 'text-up' : 'text-down'}>{change.text}</span>
          )}
        </div>
      )}

      <div className="flex-1" />

      {/* Theme toggle */}
      <button
        onClick={onToggleDark}
        className="p-1.5 rounded-md text-dim hover:text-ink hover:bg-elevated transition-colors"
        title="Toggle theme"
      >
        {dark ? <Sun size={14} /> : <Moon size={14} />}
      </button>
    </header>
  );
}
