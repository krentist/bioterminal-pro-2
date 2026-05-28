import { useState, useEffect } from 'react';
import { fetchTrials } from '@/api';
import { SkeletonList } from '@/components/Skeleton';
import { fmtDate } from '@/lib/utils';
import { ExternalLink } from 'lucide-react';
import type { Trial } from '@/types';

function phaseStyle(phase: string | null): string {
  const p = (phase ?? '').toUpperCase().replace(/PHASE\s*/i, '').trim();
  const map: Record<string, string> = {
    'I':   'text-sky-400 dark:text-sky-400 bg-sky-500/10 border-sky-500/20',
    '1':   'text-sky-400 dark:text-sky-400 bg-sky-500/10 border-sky-500/20',
    'II':  'text-amber-400 bg-amber-500/10 border-amber-500/20',
    '2':   'text-amber-400 bg-amber-500/10 border-amber-500/20',
    'III': 'text-orange-400 bg-orange-500/10 border-orange-500/20',
    '3':   'text-orange-400 bg-orange-500/10 border-orange-500/20',
    'IV':  'text-purple-400 bg-purple-500/10 border-purple-500/20',
    '4':   'text-purple-400 bg-purple-500/10 border-purple-500/20',
  };
  return map[p] ?? 'text-dim bg-elevated border-line';
}

function statusColor(status: string | null): string {
  const s = (status ?? '').toUpperCase();
  if (s.includes('RECRUIT') || s === 'ACTIVE' || s.includes('ONGOING')) return 'text-up';
  if (s === 'COMPLETED' || s === 'ENROLLING') return 'text-dim';
  if (s.includes('TERMINAT') || s.includes('SUSPEND') || s.includes('WITHDRAWN')) return 'text-down';
  return 'text-dim';
}

export function PipelineTab({ ticker }: { ticker: string }) {
  const [trials,  setTrials]  = useState<Trial[]>([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);

  useEffect(() => {
    setLoading(true); setError(null);
    fetchTrials(ticker)
      .then(d => setTrials(d.trials ?? []))
      .catch(() => setError('Failed to load pipeline data'))
      .finally(() => setLoading(false));
  }, [ticker]);

  if (loading) return <SkeletonList count={5} className="h-16" />;
  if (error)   return <p className="text-sm text-dim">{error}</p>;
  if (!trials.length) return (
    <p className="text-sm text-dim">No clinical trials found for {ticker}</p>
  );

  return (
    <div className="space-y-3">
      <p className="text-[11px] text-dim">{trials.length} trial{trials.length !== 1 ? 's' : ''} registered</p>

      <div className="overflow-x-auto">
        <table className="w-full text-[11px] border-separate border-spacing-y-0">
          <thead>
            <tr className="text-dim text-[10px] uppercase tracking-wider">
              <th className="text-left py-2 pr-4 font-medium whitespace-nowrap border-b border-line">NCT ID</th>
              <th className="text-left py-2 pr-4 font-medium border-b border-line">Title</th>
              <th className="text-left py-2 pr-4 font-medium border-b border-line whitespace-nowrap">Phase</th>
              <th className="text-left py-2 pr-4 font-medium border-b border-line">Status</th>
              <th className="text-right py-2 pr-4 font-medium border-b border-line whitespace-nowrap">Enrollment</th>
              <th className="text-left py-2 font-medium border-b border-line whitespace-nowrap">Completion</th>
            </tr>
          </thead>
          <tbody>
            {trials.map((t, i) => (
              <tr key={t.nctId || i} className="row-hover transition-colors">
                <td className="py-2.5 pr-4 font-mono whitespace-nowrap">
                  {t.nctId ? (
                    <a
                      href={`https://clinicaltrials.gov/study/${t.nctId}`}
                      target="_blank" rel="noopener noreferrer"
                      className="text-hi hover:underline flex items-center gap-1"
                    >
                      {t.nctId}
                      <ExternalLink size={9} />
                    </a>
                  ) : '—'}
                </td>
                <td className="py-2.5 pr-4 text-ink max-w-xs">
                  <p className="line-clamp-2 leading-snug">{t.title || '—'}</p>
                </td>
                <td className="py-2.5 pr-4 whitespace-nowrap">
                  {t.phase ? (
                    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${phaseStyle(t.phase)}`}>
                      {t.phase}
                    </span>
                  ) : '—'}
                </td>
                <td className={`py-2.5 pr-4 font-medium whitespace-nowrap ${statusColor(t.status)}`}>
                  {t.status ?? '—'}
                </td>
                <td className="py-2.5 pr-4 text-right font-mono text-ink">
                  {t.enrollment != null ? t.enrollment.toLocaleString() : '—'}
                </td>
                <td className="py-2.5 text-dim font-mono whitespace-nowrap">
                  {fmtDate(t.completionDate)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
