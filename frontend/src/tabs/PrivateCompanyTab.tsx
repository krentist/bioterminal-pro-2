import { useState, useEffect, useCallback } from 'react';
import { ArrowLeft, Plus, Building2, ChevronRight } from 'lucide-react';
import {
  listCompanies, getCompany, createCompany, addFunding, addCompanyNote,
} from '@/api';
import { PanelHeader, PanelMessage, Callout, PrivateBadge } from '@/components/PanelState';
import type { PrivateCompany, CompanyView } from '@/types';

function money(v: number | null | undefined): string {
  if (v == null) return '—';
  const a = Math.abs(v);
  if (a >= 1e9) return `$${(v / 1e9).toFixed(2)}B`;
  if (a >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (a >= 1e3) return `$${(v / 1e3).toFixed(0)}K`;
  return `$${v.toFixed(0)}`;
}

function StatusBadge({ status }: { status: string }) {
  if (status === 'private') return <PrivateBadge />;
  const label = status === 'pre_ipo' ? 'Pre-IPO' : 'Public';
  return (
    <span className="text-[8px] uppercase tracking-wider text-sky-300 bg-sky-500/10 border border-sky-500/25 rounded px-1 py-0.5">
      {label}
    </span>
  );
}

// ── List / create view ─────────────────────────────────────────────────────────

function CompanyList({ onOpen }: { onOpen: (id: string) => void }) {
  const [q, setQ]             = useState('');
  const [companies, setList]  = useState<PrivateCompany[]>([]);
  const [loading, setLoading] = useState(true);
  const [showNew, setShowNew] = useState(false);

  const [name, setName]       = useState('');
  const [sponsor, setSponsor] = useState('');
  const [status, setStatus]   = useState('private');
  const [desc, setDesc]       = useState('');
  const [busy, setBusy]       = useState(false);
  const [err, setErr]         = useState<string | null>(null);

  const load = useCallback((query: string) => {
    setLoading(true);
    listCompanies(query || undefined)
      .then(d => setList(d.companies ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { const t = setTimeout(() => load(q), 200); return () => clearTimeout(t); }, [q, load]);

  async function create() {
    if (!name.trim() || busy) return;
    setBusy(true); setErr(null);
    try {
      const c = await createCompany({
        name: name.trim(),
        ctSponsorName: sponsor.trim() || undefined,
        listingStatus: status,
        description: desc.trim() || undefined,
      });
      setName(''); setSponsor(''); setDesc(''); setShowNew(false);
      onOpen(c.id);
    } catch {
      setErr('Failed to create company');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <PanelHeader
        title="Private Companies"
        right={
          <button
            onClick={() => setShowNew(v => !v)}
            className="flex items-center gap-1 text-[10px] text-hi hover:bg-hi/10 border border-hi/30 rounded px-2 py-1 transition-colors"
          >
            <Plus size={11} /> New
          </button>
        }
      />

      <Callout tone="info">
        Model a <strong>private or pre-IPO</strong> biotech that has no ticker. It's valued by its
        actual ClinicalTrials.gov pipeline (rNPV only — no price, DCF, or backtest) with funding and
        licensing-deal comps, and your own data-room notes attach directly here.
      </Callout>

      {showNew && (
        <div className="bg-surface border border-line rounded-lg p-3 space-y-2.5">
          <div>
            <label className="text-[9px] uppercase tracking-wider text-dim">Company name *</label>
            <input
              value={name} onChange={e => setName(e.target.value)}
              placeholder="e.g. Acme Therapeutics"
              className="w-full mt-0.5 bg-base border border-line rounded px-2 py-1 text-[11px] text-ink focus:border-hi outline-none"
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[9px] uppercase tracking-wider text-dim">CT.gov sponsor name</label>
              <input
                value={sponsor} onChange={e => setSponsor(e.target.value)}
                placeholder="defaults to name"
                className="w-full mt-0.5 bg-base border border-line rounded px-2 py-1 text-[11px] text-ink focus:border-hi outline-none"
              />
            </div>
            <div>
              <label className="text-[9px] uppercase tracking-wider text-dim">Listing status</label>
              <select
                value={status} onChange={e => setStatus(e.target.value)}
                className="w-full mt-0.5 bg-base border border-line rounded px-2 py-1 text-[11px] text-ink focus:border-hi outline-none"
              >
                <option value="private">Private</option>
                <option value="pre_ipo">Pre-IPO</option>
                <option value="public">Public</option>
              </select>
            </div>
          </div>
          <div>
            <label className="text-[9px] uppercase tracking-wider text-dim">Description</label>
            <input
              value={desc} onChange={e => setDesc(e.target.value)}
              className="w-full mt-0.5 bg-base border border-line rounded px-2 py-1 text-[11px] text-ink focus:border-hi outline-none"
            />
          </div>
          <button
            onClick={create} disabled={busy || !name.trim()}
            className="w-full py-1.5 rounded text-[11px] font-medium border border-hi/40 text-hi hover:bg-hi/10 transition-all disabled:opacity-40"
          >
            {busy ? 'Creating…' : 'Create company'}
          </button>
          {err && <Callout tone="danger">{err}</Callout>}
        </div>
      )}

      <input
        value={q} onChange={e => setQ(e.target.value)}
        placeholder="Search companies…"
        className="w-full bg-base border border-line rounded px-2.5 py-1.5 text-[11px] text-ink focus:border-hi outline-none"
      />

      {loading ? (
        <p className="text-[11px] text-dim">Loading…</p>
      ) : companies.length === 0 ? (
        <PanelMessage kind="empty" title="No private companies yet." detail="Create one with “New” to model its pipeline rNPV and attach diligence notes." />
      ) : (
        <div className="space-y-1.5">
          {companies.map(c => (
            <button
              key={c.id} onClick={() => onOpen(c.id)}
              className="w-full flex items-center justify-between gap-2 bg-elevated border border-line rounded px-3 py-2 hover:border-hi/50 transition-colors text-left"
            >
              <div className="min-w-0 flex items-center gap-2">
                <Building2 size={13} className="text-dim flex-none" />
                <div className="min-w-0">
                  <p className="text-[11px] text-ink font-medium truncate">{c.name}</p>
                  {c.description && <p className="text-[9px] text-dim truncate">{c.description}</p>}
                </div>
              </div>
              <div className="flex items-center gap-2 flex-none">
                <StatusBadge status={c.listingStatus} />
                <ChevronRight size={12} className="text-dim" />
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Detail view ──────────────────────────────────────────────────────────────

function CompanyDetail({ id, onBack }: { id: string; onBack: () => void }) {
  const [view, setView]       = useState<CompanyView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  // funding form
  const [fRound, setFRound]   = useState('');
  const [fPost, setFPost]     = useState('');
  const [fLead, setFLead]     = useState('');
  const [fSource, setFSource] = useState('');
  // note form
  const [noteText, setNoteText]     = useState('');
  const [noteSource, setNoteSource] = useState('');
  const [busy, setBusy]             = useState(false);

  const load = useCallback(() => {
    setLoading(true); setError(null);
    getCompany(id)
      .then(setView)
      .catch(() => setError('Failed to load company'))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => { load(); }, [load]);

  async function submitFunding() {
    if (busy) return;
    setBusy(true);
    try {
      await addFunding(id, {
        roundType: fRound.trim() || undefined,
        postMoneyUsd: fPost ? Number(fPost) : undefined,
        leadInvestor: fLead.trim() || undefined,
        source: fSource.trim() || undefined,
      });
      setFRound(''); setFPost(''); setFLead(''); setFSource('');
      load();
    } finally { setBusy(false); }
  }

  async function submitNote() {
    if (!noteText.trim() || busy) return;
    setBusy(true);
    try {
      await addCompanyNote(id, { text: noteText.trim(), source: noteSource.trim() || undefined });
      setNoteText(''); setNoteSource('');
      load();
    } finally { setBusy(false); }
  }

  const back = (
    <button onClick={onBack} className="flex items-center gap-1 text-[10px] text-dim hover:text-ink transition-colors mb-3">
      <ArrowLeft size={11} /> All companies
    </button>
  );

  if (loading) return <div>{back}<p className="text-[11px] text-dim">Loading…</p></div>;
  if (error || !view) return <div>{back}<PanelMessage kind="error" title={error ?? 'No data'} /></div>;

  const v = view.valuation;
  const lc = v.licensingComps;
  const fc = view.fundingComps;

  return (
    <div className="space-y-4">
      {back}

      {/* Header */}
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold text-ink">{view.company.name}</h3>
        <StatusBadge status={view.listingStatus} />
      </div>

      {/* rNPV headline */}
      <div className="bg-elevated border border-line rounded-lg p-4">
        <p className="text-[10px] uppercase tracking-wider text-dim mb-1">Pipeline rNPV (total)</p>
        <p className="text-3xl font-mono font-light text-ink leading-none">{money(v.rnpvTotal)}</p>
        <p className="text-[9px] text-dim mt-2 leading-relaxed">{v.assumptions.note}</p>
      </div>

      {/* Licensing comps */}
      {lc && (
        <div>
          <p className="text-[10px] uppercase tracking-wider text-dim mb-1.5">Licensing-deal comp</p>
          <div className="grid grid-cols-3 gap-2">
            {([['Low', lc.low], ['Mid', lc.mid], ['High', lc.high]] as const).map(([k, val]) => (
              <div key={k} className="bg-elevated border border-line rounded-lg p-2.5 text-center">
                <p className="text-[9px] uppercase tracking-wider text-dim">{k}</p>
                <p className="text-sm font-mono font-semibold text-ink">{money(val)}</p>
              </div>
            ))}
          </div>
          <p className="text-[9px] text-dim mt-1">{lc.basis}</p>
        </div>
      )}

      {/* Funding comps */}
      <div>
        <p className="text-[10px] uppercase tracking-wider text-dim mb-1.5">Funding rounds</p>
        {fc.rounds.length > 0 ? (
          <div className="space-y-1">
            {fc.rounds.map(r => (
              <div key={r.id} className="flex items-center justify-between bg-elevated border border-line rounded px-3 py-1.5 text-[11px]">
                <span className="text-ink">{r.roundType || 'Round'} {r.leadInvestor ? <span className="text-dim">· {r.leadInvestor}</span> : null}</span>
                <span className="font-mono text-ink">{money(r.postMoneyUsd)} <span className="text-dim text-[9px]">post</span></span>
              </div>
            ))}
            {fc.impliedByRnpv?.rnpvVsPostMoney != null && (
              <p className="text-[9px] text-dim mt-1">
                rNPV vs last post-money: <span className={fc.impliedByRnpv.rnpvVsPostMoney >= 0 ? 'text-up' : 'text-down'}>
                  {(fc.impliedByRnpv.rnpvVsPostMoney * 100).toFixed(0)}%
                </span>
              </p>
            )}
          </div>
        ) : (
          <p className="text-[10px] text-dim">No funding rounds entered.</p>
        )}
        {/* add funding */}
        <div className="grid grid-cols-2 gap-1.5 mt-2">
          <input value={fRound} onChange={e => setFRound(e.target.value)} placeholder="Round (e.g. Series B)"
            className="bg-base border border-line rounded px-2 py-1 text-[10px] text-ink focus:border-hi outline-none" />
          <input value={fPost} onChange={e => setFPost(e.target.value)} placeholder="Post-money USD" inputMode="numeric"
            className="bg-base border border-line rounded px-2 py-1 text-[10px] text-ink focus:border-hi outline-none" />
          <input value={fLead} onChange={e => setFLead(e.target.value)} placeholder="Lead investor"
            className="bg-base border border-line rounded px-2 py-1 text-[10px] text-ink focus:border-hi outline-none" />
          <input value={fSource} onChange={e => setFSource(e.target.value)} placeholder="Source"
            className="bg-base border border-line rounded px-2 py-1 text-[10px] text-ink focus:border-hi outline-none" />
        </div>
        <button onClick={submitFunding} disabled={busy}
          className="w-full mt-1.5 py-1 rounded text-[10px] text-dim border border-line hover:text-ink hover:border-dim transition-colors disabled:opacity-40">
          + Add funding round
        </button>
      </div>

      {/* Pipeline */}
      <div>
        <p className="text-[10px] uppercase tracking-wider text-dim mb-1.5">
          Pipeline · {view.pipeline.programs.length} program{view.pipeline.programs.length !== 1 ? 's' : ''}
          {!view.pipeline.sponsorMatched && view.pipeline.trialsFound > 0 && (
            <span className="text-amber-400/80"> · sponsor not matched, showing all {view.pipeline.trialsFound} trials</span>
          )}
        </p>
        {view.pipeline.programs.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-[11px] border-separate border-spacing-y-0">
              <thead>
                <tr className="text-dim text-[10px] uppercase tracking-wider">
                  <th className="text-left py-1.5 pr-3 font-medium border-b border-line">Program</th>
                  <th className="text-left py-1.5 pr-3 font-medium border-b border-line">Phase</th>
                  <th className="text-left py-1.5 pr-3 font-medium border-b border-line">Indication</th>
                  <th className="text-right py-1.5 font-medium border-b border-line">Enroll.</th>
                </tr>
              </thead>
              <tbody>
                {view.pipeline.programs.map((p, i) => (
                  <tr key={i} className="row-hover">
                    <td className="py-2 pr-3 text-ink max-w-[12rem]"><p className="truncate" title={p.title}>{p.title}</p></td>
                    <td className="py-2 pr-3 text-dim whitespace-nowrap">{p.phase ?? '—'}</td>
                    <td className="py-2 pr-3 text-dim max-w-[10rem]"><p className="truncate" title={p.condition ?? ''}>{p.condition ?? '—'}</p></td>
                    <td className="py-2 text-right font-mono text-ink">{p.enrollment != null ? p.enrollment.toLocaleString() : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-[10px] text-dim">No pipeline found on ClinicalTrials.gov for this sponsor name.</p>
        )}
      </div>

      {/* Notes / data room */}
      <div>
        <p className="text-[10px] uppercase tracking-wider text-dim mb-1.5">Data-room notes ({view.notes.length})</p>
        <div className="space-y-1">
          {view.notes.map(n => (
            <div key={n.id} className="bg-elevated border border-line rounded px-3 py-2">
              <p className="text-[11px] text-ink leading-snug">{n.text}</p>
              <p className="text-[9px] text-dim mt-0.5">{n.source || 'no source'} · {n.createdAt?.slice(0, 10)}</p>
            </div>
          ))}
        </div>
        <div className="mt-2 space-y-1.5">
          <textarea value={noteText} onChange={e => setNoteText(e.target.value)} rows={2}
            placeholder="Diligence note (private company — stored locally)…"
            className="w-full bg-base border border-line rounded px-2 py-1.5 text-[11px] text-ink focus:border-hi outline-none resize-none" />
          <div className="flex gap-1.5">
            <input value={noteSource} onChange={e => setNoteSource(e.target.value)} placeholder="Source"
              className="flex-1 bg-base border border-line rounded px-2 py-1 text-[10px] text-ink focus:border-hi outline-none" />
            <button onClick={submitNote} disabled={busy || !noteText.trim()}
              className="px-3 py-1 rounded text-[10px] font-medium border border-hi/40 text-hi hover:bg-hi/10 transition-all disabled:opacity-40">
              Add note
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Export ──────────────────────────────────────────────────────────────────

export function PrivateCompanyTab(_: { ticker: string }) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  return selectedId
    ? <CompanyDetail id={selectedId} onBack={() => setSelectedId(null)} />
    : <CompanyList onOpen={setSelectedId} />;
}
