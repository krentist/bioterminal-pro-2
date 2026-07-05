import { useState, useEffect } from 'react';
import { ExternalLink } from 'lucide-react';
import { fetchCompetition } from '@/api';
import { PanelHeader, PanelLoading, PanelMessage, Callout } from '@/components/PanelState';
import type { CompetitionData, Competitor } from '@/types';

function phaseStyle(phase: string | null): string {
  const p = (phase ?? '').toUpperCase();
  if (p.includes('APPROV')) return 'text-up bg-up/10 border-up/30';
  if (p.includes('NDA') || p.includes('BLA')) return 'text-up bg-up/10 border-up/30';
  if (p.includes('3')) return 'text-orange-400 bg-orange-500/10 border-orange-500/20';
  if (p.includes('2')) return 'text-amber-400 bg-amber-500/10 border-amber-500/20';
  if (p.includes('1')) return 'text-sky-400 bg-sky-500/10 border-sky-500/20';
  return 'text-dim bg-elevated border-line';
}

function CompRow({ c }: { c: Competitor }) {
  return (
    <tr className="row-hover transition-colors">
      <td className="py-2.5 pr-4 text-ink font-medium max-w-[16rem]">
        <p className="truncate" title={c.sponsor}>{c.sponsor}</p>
        {c.title && <p className="text-[9px] text-dim truncate" title={c.title}>{c.title}</p>}
      </td>
      <td className="py-2.5 pr-4 whitespace-nowrap">
        {c.phase ? (
          <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${phaseStyle(c.phase)}`}>{c.phase}</span>
        ) : '—'}
      </td>
      <td className="py-2.5 pr-4 text-dim whitespace-nowrap">{c.status ?? '—'}</td>
      <td className="py-2.5 pr-4 text-right font-mono text-ink whitespace-nowrap">
        {c.probApproval != null ? `${(c.probApproval * 100).toFixed(0)}%` : '—'}
      </td>
      <td className="py-2.5 font-mono whitespace-nowrap">
        {c.nctId && c.source_url ? (
          <a href={c.source_url} target="_blank" rel="noopener noreferrer" className="text-hi hover:underline inline-flex items-center gap-1">
            {c.nctId}<ExternalLink size={9} />
          </a>
        ) : '—'}
      </td>
    </tr>
  );
}

export function CompetitionTab({ ticker }: { ticker: string }) {
  const [data, setData]       = useState<CompetitionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    setLoading(true); setError(null);
    fetchCompetition(ticker)
      .then(setData)
      .catch(() => setError('Failed to load competitive landscape'))
      .finally(() => setLoading(false));
  }, [ticker]);

  if (loading) return <PanelLoading />;
  if (error)   return <PanelMessage kind="error" title={error} />;
  if (!data)   return null;

  if (!data.indication || !data.competitors?.length) {
    return (
      <PanelMessage
        kind="empty"
        title="No competitive landscape available."
        detail={data.note || 'No lead indication could be determined from this company’s pipeline, or no commercial rivals were found in the same indication on ClinicalTrials.gov.'}
      />
    );
  }

  return (
    <div className="space-y-4">
      <PanelHeader
        title={`Rivals in ${data.indication}`}
        source={data.source || 'ClinicalTrials.gov'}
        sourceUrl={data.source_url}
        right={
          <span className="text-[9px] text-dim">
            lead {data.leadPhase ?? '—'} · {data.competitorCount ?? data.competitors.length} rivals
          </span>
        }
      />

      {data.note && <Callout tone="warn">{data.note}</Callout>}

      <div className="overflow-x-auto">
        <table className="w-full text-[11px] border-separate border-spacing-y-0">
          <thead>
            <tr className="text-dim text-[10px] uppercase tracking-wider">
              <th className="text-left  py-2 pr-4 font-medium border-b border-line">Sponsor</th>
              <th className="text-left  py-2 pr-4 font-medium border-b border-line whitespace-nowrap">Phase</th>
              <th className="text-left  py-2 pr-4 font-medium border-b border-line">Status</th>
              <th className="text-right py-2 pr-4 font-medium border-b border-line whitespace-nowrap" title="Phase-derived probability of approval">PoS</th>
              <th className="text-left  py-2 font-medium border-b border-line">Trial</th>
            </tr>
          </thead>
          <tbody>
            {data.competitors.map((c, i) => <CompRow key={c.nctId || i} c={c} />)}
          </tbody>
        </table>
      </div>
    </div>
  );
}
