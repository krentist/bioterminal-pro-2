import { useState } from 'react';
import { Sun, Moon, Link2, Check } from 'lucide-react';
import { fmt, fmtChange } from '@/lib/utils';
import { TickerInput } from '@/components/TickerInput';
import { WindowsMenu } from '@/components/WindowsMenu';
import type { Quote } from '@/types';

interface Props {
  ticker:          string | null;
  quote:           Quote | null;
  dark:            boolean;
  onToggleDark:    () => void;
  onSelectTicker:  (t: string) => void;
}

export function TopBar({ ticker, quote, dark, onToggleDark, onSelectTicker }: Props) {
  const change = quote ? fmtChange(quote.changePercent) : null;
  const [copied, setCopied] = useState(false);

  function copyLink() {
    const url = new URL(location.href);
    if (ticker) url.searchParams.set('ticker', ticker);
    navigator.clipboard?.writeText(url.toString()).then(
      () => { setCopied(true); setTimeout(() => setCopied(false), 1500); },
      () => { /* clipboard blocked — ignore */ },
    );
  }

  return (
    <header className="flex-none flex items-center gap-3 px-4 h-11 border-b border-line bg-surface z-10">

      {/* Brand */}
      <span className="text-[13px] font-semibold tracking-tight text-ink whitespace-nowrap hidden sm:block">
        Bio<span className="text-hi">Terminal</span>
        <span className="ml-1.5 text-[9px] font-medium text-dim bg-elevated border border-line px-1.5 py-0.5 rounded align-middle">
          PRO
        </span>
      </span>

      <div className="w-px h-4 bg-line hidden sm:block flex-none" />

      {/* Command input */}
      <TickerInput
        value={ticker ?? ''}
        placeholder={ticker ?? 'Type a ticker…'}
        onSelect={onSelectTicker}
        className="flex-1 max-w-sm"
      />

      {/* Live price badge */}
      {ticker && quote && (
        <div className="hidden sm:flex items-center gap-2 text-[12px] font-mono">
          <span className="text-ink font-semibold">{ticker}</span>
          <span className="text-ink">{fmt(quote.price, quote.currencySymbol)}</span>
          {change && change.pos !== null && (
            <span className={[
              'px-1.5 py-0.5 rounded text-[10px] font-medium',
              change.pos ? 'text-up bg-up/10' : 'text-down bg-down/10',
            ].join(' ')}>
              {change.text}
            </span>
          )}
        </div>
      )}

      <div className="flex-1" />

      {/* Share permalink */}
      {ticker && (
        <button
          onClick={copyLink}
          className={`flex items-center gap-1 p-1.5 rounded-md transition-colors ${
            copied ? 'text-up' : 'text-dim hover:text-ink hover:bg-elevated'}`}
          title={copied ? 'Link copied' : 'Copy shareable link to this ticker'}
        >
          {copied ? <Check size={14} /> : <Link2 size={14} />}
          <span className="text-[10px] hidden sm:inline">{copied ? 'Copied' : 'Share'}</span>
        </button>
      )}

      <WindowsMenu />

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
