import { useState, useEffect } from 'react';
import { fetchCatalysts } from '@/api';
import { SkeletonList } from '@/components/Skeleton';
import { fmtDate, downloadCSV } from '@/lib/utils';
import { CalendarClock, ExternalLink, Download } from 'lucide-react';
import type { Catalyst } from '@/types';

function phaseStyle(phase: string | null): string {
  const p = (phase ?? '').toUpperCase();
  if (p.includes('NDA') || p.includes('BLA')) return 'text-up bg-up/10 border-up/30';
  if (p.includes('3')) return 'text-orange-400 bg-orange-500/10 border-orange-500/20';
  if (p.includes('2')) return 'text-amber-400 bg-amber-500/10 border-amber-500/20';
  if (p.includes('1')) return 'text-sky-400 bg-sky-500/10 border-sky-500/20';
  return 'text-dim bg-elevated border-line';
}

function timeframe(days: number | null): { label: string; color: string } {
  if (days == null) return { label: '—', color: 'text-dim' };
  if (days <= 90)  return { label: `${days}d`, color: 'text-down' };
  if (days <= 180) return { label: `${Math.round(days / 30)}mo`, color: 'text-amber-400' };
  if (days <= 365) return { label: `${Math.round(days / 30)}mo`, color: 'text-ink' };
  return { label: `${(days / 365).toFixed(1)}y`, color: 'text-dim' };
}

function CatalystRow({ c }: { c: Catalyst }) {
  const tf = timeframe(c.daysAway);
  return (
    <div className="flex items-start gap-3 py-2.5 border-b border-line/40 last:border-0">
      <div className="w-12 flex-none text-right">
        <span className={`text-[12px] font-mono font-semibold ${tf.color}`}>{tf.label}</span>
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 flex-wrap">
          {c.phase && (
            <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded border leading-none ${phaseStyle(c.phase)}`}>
              {c.phase}
            </span>
          )}
          <span className="text-[10px] font-mono text-dim">{fmtDate(c.date)}</span>
          {!c.isLeadSponsor && (
            <span
              title={c.sponsor ? `Lead sponsor: ${c.sponsor}` : undefined}
              className="text-[8px] uppercase tracking-wider text-amber-400/80 bg-amber-500/10 border border-amber-500/20 rounded px-1 py-0.5"
            >
              collaborator
            </span>
          )}
        </div>
        <p className="text-[11px] text-ink leading-snug mt-1 line-clamp-2">{c.title || '—'}</p>
        <div className="flex items-center gap-2 mt-0.5">
          {c.status && <span className="text-[9px] text-dim">{c.status.replace(/_/g, ' ')}</span>}
          {c.nctId && (
            <a
              href={c.source_url ?? `https://clinicaltrials.gov/study/${c.nctId}`}
              target="_blank" rel="noopener noreferrer"
              className="text-[9px] font-mono text-hi hover:underline flex items-center gap-0.5"
            >
              {c.nctId}<ExternalLink size={8} />
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

export function CatalystsTab({ ticker }: { ticker: string }) {
  const [data,    setData]    = useState<Catalyst[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);

  useEffect(() => {
    setLoading(true); setError(null); setData(null);
    fetchCatalysts(ticker)
      .then(d => setData(d.catalysts ?? []))
      .catch(() => setError('Failed to load catalyst calendar'))
      .finally(() => setLoading(false));
  }, [ticker]);

  if (loading) return <SkeletonList count={5} className="h-14" />;
  if (error)   return <p className="text-sm text-dim">{error}</p>;
  if (!data)   return null;

  function exportCSV() {
    downloadCSV(
      `${ticker}_catalysts.csv`,
      ['NCT ID', 'Title', 'Phase', 'Status', 'Condition', 'Primary Completion', 'Days Away', 'Sponsor', 'Lead Sponsor'],
      (data ?? []).map(c => [
        c.nctId, c.title, c.phase, c.status, c.condition, c.date, c.daysAway, c.sponsor,
        c.isLeadSponsor ? 'yes' : 'no',
      ]),
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <CalendarClock size={14} className="text-hi" />
        <p className="text-[11px] text-dim">
          {data.length === 0
            ? 'No upcoming interventional trial readouts in the next 18 months.'
            : `${data.length} upcoming readout${data.length !== 1 ? 's' : ''} — nearest first`}
        </p>
        {data.length > 0 && (
          <button
            onClick={exportCSV}
            className="ml-auto flex items-center gap-1.5 px-2.5 py-1 text-[10px] border border-line rounded text-dim hover:text-hi hover:border-hi/50 transition-colors"
          >
            <Download size={11} /> Export CSV
          </button>
        )}
      </div>

      {data.length > 0 && (
        <div className="border border-line rounded-lg bg-surface px-3">
          {data.map((c, i) => <CatalystRow key={c.nctId || i} c={c} />)}
        </div>
      )}

      <p className="text-[10px] text-dim leading-relaxed">
        Dates are estimated <em>primary completion dates</em> from ClinicalTrials.gov — the point
        a trial expects to finish collecting primary-endpoint data, not a confirmed readout or
        PDUFA date. Only interventional trials (Phase 1–3, NDA/BLA) are shown; retrospective and
        observational studies are excluded. Collaborator-sponsored trials are tagged.
      </p>
    </div>
  );
}
