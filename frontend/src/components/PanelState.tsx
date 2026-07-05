import type { ReactNode } from 'react';
import { ExternalLink, AlertTriangle, Inbox, Sparkles, ShieldAlert, Lock } from 'lucide-react';
import { SkeletonGrid, SkeletonList } from '@/components/Skeleton';

/**
 * Shared panel-state contract (Phase O / §5).
 * Every panel should express the same four states — loading / data / empty / error —
 * and the same header pattern (title · as-of · source · AI badge), so the terminal reads
 * as one system regardless of which panel you're in.
 */

// ── Badges ────────────────────────────────────────────────────────────────────

export function AiBadge({ available = true }: { available?: boolean }) {
  return (
    <span
      title={available ? 'AI-generated — not sourced fact' : 'AI analysis not configured'}
      className="inline-flex items-center gap-1 text-[8px] uppercase tracking-wider text-violet-300 bg-violet-500/10 border border-violet-500/25 rounded px-1 py-0.5"
    >
      <Sparkles size={8} /> AI
    </span>
  );
}

export function RestrictedBadge() {
  return (
    <span
      title="Restricted — you hold potential MNPI on this name"
      className="inline-flex items-center gap-1 text-[8px] uppercase tracking-wider text-red-300 bg-red-500/10 border border-red-500/30 rounded px-1 py-0.5"
    >
      <ShieldAlert size={8} /> Restricted
    </span>
  );
}

export function PrivateBadge() {
  return (
    <span
      title="Private company — notes stay local, no public-security signal"
      className="inline-flex items-center gap-1 text-[8px] uppercase tracking-wider text-amber-300 bg-amber-500/10 border border-amber-500/25 rounded px-1 py-0.5"
    >
      <Lock size={8} /> Private
    </span>
  );
}

export function SourceLink({ label, url }: { label: string; url?: string | null }) {
  if (!url) return <span className="text-[9px] text-dim">{label}</span>;
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="text-[9px] text-dim hover:text-hi transition-colors inline-flex items-center gap-0.5"
    >
      {label} <ExternalLink size={8} />
    </a>
  );
}

// ── Header ────────────────────────────────────────────────────────────────────

export function PanelHeader({
  title, asOf, source, sourceUrl, ai, right,
}: {
  title: string;
  asOf?: string | null;
  source?: string;
  sourceUrl?: string | null;
  ai?: boolean;
  right?: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-3 mb-3">
      <div className="flex items-center gap-2 min-w-0">
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-ink truncate">{title}</h3>
        {ai && <AiBadge />}
      </div>
      <div className="flex items-center gap-2 flex-none">
        {right}
        {asOf && <span className="text-[9px] text-dim whitespace-nowrap">as of {asOf}</span>}
        {source && <SourceLink label={source} url={sourceUrl} />}
      </div>
    </div>
  );
}

// ── States ────────────────────────────────────────────────────────────────────

export function PanelLoading({ variant = 'list' }: { variant?: 'list' | 'grid' }) {
  return variant === 'grid'
    ? <SkeletonGrid count={4} className="h-16" />
    : <SkeletonList count={5} className="h-14" />;
}

export function PanelMessage({
  kind = 'info', title, detail,
}: {
  kind?: 'error' | 'empty' | 'info';
  title: string;
  detail?: ReactNode;
}) {
  const Icon = kind === 'error' ? AlertTriangle : kind === 'empty' ? Inbox : AlertTriangle;
  const tone = kind === 'error' ? 'text-down' : 'text-dim';
  return (
    <div className="bg-elevated border border-line rounded-lg p-5 text-center space-y-1">
      <Icon size={16} className={`mx-auto ${tone} opacity-70`} />
      <p className={`text-sm ${kind === 'error' ? 'text-down' : 'text-ink'}`}>{title}</p>
      {detail && <p className="text-[10px] text-dim leading-relaxed">{detail}</p>}
    </div>
  );
}

// ── Callout (colored info box) ─────────────────────────────────────────────────

const CALLOUT_TONE: Record<string, string> = {
  info:    'bg-sky-500/10 border-sky-500/25 text-sky-300/90',
  warn:    'bg-amber-500/10 border-amber-500/25 text-amber-300/90',
  danger:  'bg-red-500/10 border-red-500/30 text-red-300/90',
  success: 'bg-up/10 border-up/30 text-up',
};

export function Callout({
  tone = 'info', title, children,
}: {
  tone?: 'info' | 'warn' | 'danger' | 'success';
  title?: string;
  children: ReactNode;
}) {
  return (
    <div className={`rounded-lg border px-4 py-3 text-[11px] leading-relaxed ${CALLOUT_TONE[tone]}`}>
      {title && <strong className="block mb-0.5">{title}</strong>}
      {children}
    </div>
  );
}

/** Full-panel restricted state — the compliance wall made visible (Phase J / §0). */
export function RestrictedPanel({ reason }: { reason?: string }) {
  return (
    <Callout tone="danger" title="Restricted — signal suppressed">
      {reason || 'You logged potential material non-public information on this name. Trade-oriented '
        + 'signals are suppressed here to keep you on the right side of insider-trading rules.'}
    </Callout>
  );
}
