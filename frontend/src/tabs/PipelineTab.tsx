import { useState, useEffect } from 'react';
import { fetchTrials, fetchPipelineResearch } from '@/api';
import { SkeletonList } from '@/components/Skeleton';
import { fmtDate } from '@/lib/utils';
import { ExternalLink, Sparkles, ChevronDown, ChevronRight, AlertTriangle } from 'lucide-react';
import type { Trial, PipelineProgram, PipelineResearch } from '@/types';

// ── Shared phase / status styles ─────────────────────────────────────────────

function phaseStyle(phase: string | null): string {
  const p = (phase ?? '').toUpperCase().replace(/PHASE\s*/i, '').trim();
  const map: Record<string, string> = {
    'I':   'text-sky-400 bg-sky-500/10 border-sky-500/20',
    '1':   'text-sky-400 bg-sky-500/10 border-sky-500/20',
    '1/2': 'text-sky-400 bg-sky-500/10 border-sky-500/20',
    'II':  'text-amber-400 bg-amber-500/10 border-amber-500/20',
    '2':   'text-amber-400 bg-amber-500/10 border-amber-500/20',
    '2/3': 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    'III': 'text-orange-400 bg-orange-500/10 border-orange-500/20',
    '3':   'text-orange-400 bg-orange-500/10 border-orange-500/20',
    'IV':  'text-purple-400 bg-purple-500/10 border-purple-500/20',
    '4':   'text-purple-400 bg-purple-500/10 border-purple-500/20',
  };
  return map[p] ?? (
    p.includes('PRECLIN') ? 'text-dim bg-elevated border-line' :
    p.includes('APPROV') ? 'text-up bg-up/10 border-up/30' :
    'text-dim bg-elevated border-line'
  );
}

function statusColor(status: string | null): string {
  const s = (status ?? '').toUpperCase();
  if (s.includes('RECRUIT') || s === 'ACTIVE' || s.includes('ONGOING')) return 'text-up';
  if (s.includes('TERMINAT') || s.includes('SUSPEND') || s.includes('WITHDRAWN') || s.includes('DISCONTINUED')) return 'text-down';
  return 'text-dim';
}

const RISK_STYLE: Record<string, string> = {
  LOW:       'text-up bg-up/10 border-up/30',
  MEDIUM:    'text-amber-400 bg-amber-500/10 border-amber-500/20',
  HIGH:      'text-orange-400 bg-orange-500/10 border-orange-500/20',
  VERY_HIGH: 'text-down bg-down/10 border-down/30',
};

// ── CT.gov basic view ─────────────────────────────────────────────────────────

function CTView({ trials }: { trials: Trial[] }) {
  if (!trials.length) return null;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[11px] border-separate border-spacing-y-0">
        <thead>
          <tr className="text-dim text-[10px] uppercase tracking-wider">
            <th className="text-left py-2 pr-4 font-medium whitespace-nowrap border-b border-line">NCT ID</th>
            <th className="text-left py-2 pr-4 font-medium border-b border-line">Title</th>
            <th className="text-left py-2 pr-4 font-medium border-b border-line whitespace-nowrap">Phase</th>
            <th className="text-left py-2 pr-4 font-medium border-b border-line">Status</th>
            <th className="text-right py-2 pr-4 font-medium border-b border-line whitespace-nowrap">Enroll.</th>
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
                    {t.nctId}<ExternalLink size={9} />
                  </a>
                ) : '—'}
              </td>
              <td className="py-2.5 pr-4 text-ink max-w-xs">
                <p className="line-clamp-2 leading-snug">{t.title || '—'}</p>
                {t.isLeadSponsor === false && (
                  <span
                    title={t.sponsor ? `Lead sponsor: ${t.sponsor}` : 'Not lead-sponsored by this company'}
                    className="inline-block mt-0.5 text-[8px] uppercase tracking-wider text-amber-400/80 bg-amber-500/10 border border-amber-500/20 rounded px-1 py-0.5"
                  >
                    collaborator
                  </span>
                )}
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
  );
}

// ── AI Research program row ───────────────────────────────────────────────────

function ProgramRow({ prog }: { prog: PipelineProgram }) {
  const [expanded, setExpanded] = useState(false);
  const liveStatus = prog.ct_status ?? prog.status;
  const liveEnroll = prog.ct_enrollment;

  return (
    <>
      <tr
        className="row-hover cursor-pointer transition-colors"
        onClick={() => setExpanded(e => !e)}
      >
        {/* Drug name */}
        <td className="py-2.5 pr-3 align-top">
          <div className="flex items-center gap-1">
            {expanded ? <ChevronDown size={10} className="text-dim flex-none" /> : <ChevronRight size={10} className="text-dim flex-none" />}
            <span className="text-[11px] font-semibold text-ink">{prog.drug_name}</span>
          </div>
          {prog.partner && (
            <p className="text-[9px] text-dim mt-0.5 ml-3.5">via {prog.partner}</p>
          )}
        </td>

        {/* Target / mechanism */}
        <td className="py-2.5 pr-3 align-top">
          <p className="text-[11px] text-ink font-medium">{prog.target ?? '—'}</p>
          <p className="text-[9px] text-dim mt-0.5 line-clamp-1">{prog.mechanism ?? ''}</p>
        </td>

        {/* Indication */}
        <td className="py-2.5 pr-3 align-top">
          <p className="text-[11px] text-ink">{prog.indication}</p>
          {prog.secondary_indications?.length ? (
            <p className="text-[9px] text-dim mt-0.5">+{prog.secondary_indications.length} more</p>
          ) : null}
        </td>

        {/* Phase */}
        <td className="py-2.5 pr-3 align-top whitespace-nowrap">
          <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${phaseStyle(prog.phase)}`}>
            {prog.phase}
          </span>
        </td>

        {/* Status */}
        <td className={`py-2.5 pr-3 align-top text-[11px] font-medium whitespace-nowrap ${statusColor(liveStatus)}`}>
          {liveStatus ?? '—'}
          {prog.ct_status && prog.ct_status !== prog.status && (
            <span className="ml-1 text-[9px] text-dim font-normal">(CT.gov)</span>
          )}
        </td>

        {/* TAM */}
        <td className="py-2.5 pr-3 align-top text-right">
          {prog.tam_usd_bn != null ? (
            <span className="text-[11px] font-mono text-ink">${prog.tam_usd_bn.toFixed(1)}B</span>
          ) : (
            <span className="text-[10px] text-dim">—</span>
          )}
        </td>

        {/* Risk */}
        <td className="py-2.5 align-top">
          {prog.risk ? (
            <span className={`text-[9px] font-semibold tracking-wide px-1.5 py-0.5 rounded border ${RISK_STYLE[prog.risk] ?? 'text-dim bg-elevated border-line'}`}>
              {prog.risk}
            </span>
          ) : '—'}
        </td>
      </tr>

      {/* Expanded detail row */}
      {expanded && (
        <tr>
          <td colSpan={7} className="pb-3 pr-3">
            <div className="ml-3.5 p-3 rounded-lg bg-elevated/60 border border-line/60 space-y-2.5">

              {/* Rights & enrollment */}
              <div className="flex flex-wrap gap-4 text-[10px]">
                {prog.rights && (
                  <span className="text-dim">Rights: <span className="text-ink">{prog.rights}</span></span>
                )}
                {liveEnroll != null && (
                  <span className="text-dim">Enrollment: <span className="text-ink font-mono">{liveEnroll.toLocaleString()}</span></span>
                )}
                {prog.owned_or_licensed && (
                  <span className="text-dim">Structure: <span className="text-ink">{prog.owned_or_licensed}</span></span>
                )}
              </div>

              {/* TAM rationale */}
              {prog.tam_basis && (
                <div>
                  <p className="text-[9px] text-dim uppercase tracking-wider mb-1">Market Opportunity</p>
                  <p className="text-[10px] text-ink leading-snug">{prog.tam_basis}</p>
                </div>
              )}

              {/* Key data */}
              {prog.key_data?.length > 0 && (
                <div>
                  <p className="text-[9px] text-dim uppercase tracking-wider mb-1">Key Data Points</p>
                  <ul className="space-y-0.5">
                    {prog.key_data.map((d, i) => (
                      <li key={i} className="text-[10px] text-ink flex items-start gap-1.5">
                        <span className="text-hi flex-none mt-0.5">·</span>{d}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Next catalyst */}
              {prog.next_catalyst && (
                <div>
                  <p className="text-[9px] text-dim uppercase tracking-wider mb-1">Next Catalyst</p>
                  <p className="text-[10px] text-ink">{prog.next_catalyst}</p>
                </div>
              )}

              {/* Competition */}
              {prog.competition?.length > 0 && (
                <div>
                  <p className="text-[9px] text-dim uppercase tracking-wider mb-1">Competing Drugs</p>
                  <p className="text-[10px] text-dim">{prog.competition.join(' · ')}</p>
                </div>
              )}

              {/* NCT / ChiCTR links */}
              {(prog.nct_ids?.length > 0 || prog.chictr_ids?.length > 0) && (
                <div className="flex flex-wrap gap-2 pt-0.5">
                  {prog.nct_ids?.map(id => (
                    <a
                      key={id}
                      href={`https://clinicaltrials.gov/study/${id}`}
                      target="_blank" rel="noopener noreferrer"
                      className="text-[9px] text-hi hover:underline flex items-center gap-0.5 font-mono"
                    >
                      {id}<ExternalLink size={8} />
                    </a>
                  ))}
                  {prog.chictr_ids?.map(id => (
                    <a
                      key={id}
                      href={`http://www.chictr.org.cn/showprojen.aspx?proj=${id}`}
                      target="_blank" rel="noopener noreferrer"
                      className="text-[9px] text-hi hover:underline flex items-center gap-0.5 font-mono"
                    >
                      {id} (ChiCTR)<ExternalLink size={8} />
                    </a>
                  ))}
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// ── AI Research view ──────────────────────────────────────────────────────────

function AIResearchView({ data }: { data: PipelineResearch }) {
  // When the model didn't produce a result, say why plainly rather than showing an
  // "AI assessment" of an error string followed by a misleading "No programs found".
  if (!data.ai_generated) {
    const notConfigured = data.ai_available === false;
    return (
      <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3">
        <div className="flex items-center gap-2 mb-1.5">
          <Sparkles size={12} className="text-amber-400" />
          <span className="text-[11px] font-semibold text-amber-300">
            {notConfigured ? 'AI research not configured' : 'AI research unavailable'}
          </span>
        </div>
        <p className="text-[11px] text-amber-200/90 leading-relaxed">{data.pipeline_summary}</p>
        <p className="text-[10px] text-dim mt-2 leading-relaxed">
          The ClinicalTrials.gov pipeline above is unaffected — switch back to the CT.gov view
          for registered trials.
          {notConfigured && ' AI research needs an LLM API key (Anthropic, Groq, OpenRouter, or Gemini) set on the server.'}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Summary */}
      {data.pipeline_summary && (
        <div className="p-3 rounded-lg bg-surface border border-line">
          <div className="flex items-center gap-2 mb-1.5">
            <Sparkles size={11} className="text-hi" />
            <span className="text-[9px] text-dim uppercase tracking-wider">AI Pipeline Assessment</span>
            <span className="ml-auto text-[9px] text-dim bg-elevated border border-line px-1.5 py-0.5 rounded">AI</span>
          </div>
          <p className="text-[11px] text-ink leading-relaxed">{data.pipeline_summary}</p>
          {data.hk_china_angle && (
            <p className="text-[10px] text-dim mt-1.5 leading-relaxed">{data.hk_china_angle}</p>
          )}
        </div>
      )}

      {/* Programs table */}
      {data.programs.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full text-[11px] border-separate border-spacing-y-0">
            <thead>
              <tr className="text-dim text-[9px] uppercase tracking-wider">
                <th className="text-left py-2 pr-3 font-medium border-b border-line whitespace-nowrap">Drug / Program</th>
                <th className="text-left py-2 pr-3 font-medium border-b border-line">Target</th>
                <th className="text-left py-2 pr-3 font-medium border-b border-line">Indication</th>
                <th className="text-left py-2 pr-3 font-medium border-b border-line whitespace-nowrap">Phase</th>
                <th className="text-left py-2 pr-3 font-medium border-b border-line">Status</th>
                <th className="text-right py-2 pr-3 font-medium border-b border-line whitespace-nowrap">TAM</th>
                <th className="text-left py-2 font-medium border-b border-line">Risk</th>
              </tr>
            </thead>
            <tbody>
              {data.programs.map((prog, i) => (
                <ProgramRow key={i} prog={prog} />
              ))}
            </tbody>
          </table>
          <p className="text-[9px] text-dim mt-2 flex items-center gap-1">
            <ChevronRight size={9} /> Click any row to expand TAM analysis, key data, and catalysts.
          </p>
        </div>
      ) : (
        <p className="text-[11px] text-dim">No programs found for this company.</p>
      )}

      {/* Data note */}
      {data.data_note && (
        <div className="flex items-start gap-2 p-2.5 rounded bg-elevated/60 border border-line/60">
          <AlertTriangle size={11} className="text-amber-400 flex-none mt-0.5" />
          <p className="text-[9px] text-dim leading-snug">{data.data_note}</p>
        </div>
      )}
    </div>
  );
}

// ── Main export ───────────────────────────────────────────────────────────────

export function PipelineTab({ ticker }: { ticker: string }) {
  const [trials,    setTrials]    = useState<Trial[]>([]);
  const [ctLoading, setCtLoading] = useState(true);
  const [ctError,   setCtError]   = useState<string | null>(null);

  const [research,    setResearch]    = useState<PipelineResearch | null>(null);
  const [aiLoading,   setAiLoading]   = useState(false);
  const [aiError,     setAiError]     = useState<string | null>(null);
  const [showAI,      setShowAI]      = useState(false);

  // Load CT.gov data on mount
  useEffect(() => {
    setCtLoading(true); setCtError(null);
    setResearch(null); setShowAI(false); setAiError(null);
    fetchTrials(ticker)
      .then(d => setTrials(d.trials ?? []))
      .catch(() => setCtError('Failed to load ClinicalTrials.gov data'))
      .finally(() => setCtLoading(false));
  }, [ticker]);

  function runAIResearch() {
    setAiLoading(true); setAiError(null);
    fetchPipelineResearch(ticker)
      .then(d => {
        setResearch(d);
        setShowAI(true);
      })
      .catch(() => setAiError('AI pipeline research failed — please try again'))
      .finally(() => setAiLoading(false));
  }

  return (
    <div className="space-y-4">

      {/* ── Header row: counts + AI button ── */}
      <div className="flex items-center justify-between gap-4">
        <p className="text-[11px] text-dim">
          {ctLoading
            ? 'Loading…'
            : `${trials.length} trial${trials.length !== 1 ? 's' : ''} on ClinicalTrials.gov`}
          {!ctLoading && trials.filter(t => t.isLeadSponsor === false).length > 0 && (
            <span className="text-amber-400/80">
              {' '}· {trials.filter(t => t.isLeadSponsor === false).length} collaborator-sponsored
            </span>
          )}
        </p>
        <div className="flex items-center gap-2">
          {showAI && (
            <button
              onClick={() => setShowAI(false)}
              className="text-[10px] text-dim hover:text-ink transition-colors"
            >
              CT.gov view
            </button>
          )}
          <button
            onClick={runAIResearch}
            disabled={aiLoading}
            className={[
              'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-medium transition-all border',
              aiLoading
                ? 'border-line text-dim cursor-wait'
                : 'border-hi/40 text-hi hover:bg-hi/10',
            ].join(' ')}
          >
            <Sparkles size={11} />
            {aiLoading ? 'Researching…' : research ? 'Refresh AI Research' : 'Research with AI'}
          </button>
        </div>
      </div>

      {/* ── Error states ── */}
      {aiError && (
        <p className="text-[11px] text-down flex items-center gap-1.5">
          <AlertTriangle size={11} />{aiError}
        </p>
      )}

      {/* ── AI Research view ── */}
      {showAI && research ? (
        <AIResearchView data={research} />
      ) : (
        /* ── CT.gov view ── */
        <>
          {ctLoading && <SkeletonList count={5} className="h-16" />}
          {ctError && <p className="text-sm text-dim">{ctError}</p>}
          {!ctLoading && !ctError && trials.length === 0 && (
            <div className="space-y-2">
              <p className="text-sm text-dim">No trials found under the company name on ClinicalTrials.gov.</p>
              <p className="text-[11px] text-dim opacity-70">
                This is common for HK biotechs where trials are registered under a partner or licensed entity.
                Use "Research with AI" to get the full pipeline.
              </p>
            </div>
          )}
          {!ctLoading && trials.length > 0 && <CTView trials={trials} />}
        </>
      )}
    </div>
  );
}
