import { useState, useRef, useEffect } from 'react';
import { Search, X } from 'lucide-react';
import { fetchSearch } from '@/api';
import type { SearchResult } from '@/types';

interface Props {
  value:        string;
  placeholder?: string;
  onSelect:     (ticker: string) => void;
  size?:        'md' | 'sm';
  className?:   string;
}

export function TickerInput({ value, placeholder, onSelect, size = 'md', className = '' }: Props) {
  const [query,   setQuery]   = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open,    setOpen]    = useState(false);
  const [focused, setFocused] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const inputRef    = useRef<HTMLInputElement>(null);
  const dropRef     = useRef<HTMLDivElement>(null);

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

  useEffect(() => {
    function handle(e: MouseEvent) {
      if (dropRef.current && !dropRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, []);

  function select(symbol: string) {
    setQuery('');
    setOpen(false);
    inputRef.current?.blur();
    onSelect(symbol.toUpperCase());
  }

  const isSm = size === 'sm';

  return (
    <div ref={dropRef} className={`relative ${className}`}>
      <div className={[
        'flex items-center gap-2 rounded-lg border transition-colors bg-elevated',
        isSm ? 'px-2 py-1' : 'px-2.5 py-1.5',
        focused ? 'border-hi ring-1 ring-hi/20' : 'border-line',
      ].join(' ')}>
        <Search size={isSm ? 10 : 12} className="text-dim flex-none" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          onKeyDown={e => {
            if (e.key === 'Enter' && results.length > 0) select(results[0].symbol);
            else if (e.key === 'Enter' && query.trim()) select(query.trim());
            if (e.key === 'Escape') { setQuery(''); setOpen(false); inputRef.current?.blur(); }
          }}
          placeholder={placeholder ?? value ?? 'Enter symbol…'}
          className={[
            'flex-1 min-w-0 bg-transparent font-mono uppercase text-ink placeholder:text-dim placeholder:normal-case outline-none',
            isSm ? 'text-[10px] w-16' : 'text-[12px]',
          ].join(' ')}
        />
        {query && (
          <button onMouseDown={e => e.preventDefault()} onClick={() => setQuery('')} className="text-dim hover:text-ink">
            <X size={10} />
          </button>
        )}
      </div>

      {open && results.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-elevated border border-line rounded-lg overflow-hidden dropdown-shadow z-[10000] min-w-[220px]">
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
  );
}
