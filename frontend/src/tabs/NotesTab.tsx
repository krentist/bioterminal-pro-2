import { useState, useEffect, useCallback } from 'react';
import { ShieldAlert, Lock, Unlock } from 'lucide-react';
import { fetchNotes, fetchRestricted, createNote, liftRestriction } from '@/api';
import { PanelHeader, PanelMessage, Callout, RestrictedBadge } from '@/components/PanelState';
import type { NoteEntry, RestrictedEntry } from '@/types';

function Check({ label, hint, checked, onChange }: {
  label: string; hint?: string; checked: boolean; onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-start gap-2 cursor-pointer group">
      <input
        type="checkbox"
        checked={checked}
        onChange={e => onChange(e.target.checked)}
        className="mt-0.5 accent-hi"
      />
      <span className="text-[11px] text-ink leading-snug">
        {label}
        {hint && <span className="block text-[9px] text-dim">{hint}</span>}
      </span>
    </label>
  );
}

export function NotesTab({ ticker }: { ticker: string }) {
  const [notes, setNotes]           = useState<NoteEntry[]>([]);
  const [restricted, setRestricted] = useState<RestrictedEntry[]>([]);
  const [loading, setLoading]       = useState(true);

  const [subject, setSubject]     = useState(ticker.toUpperCase());
  const [text, setText]           = useState('');
  const [source, setSource]       = useState('');
  const [isPublic, setIsPublic]   = useState(true);
  const [isMnpi, setIsMnpi]       = useState(false);
  const [busy, setBusy]           = useState(false);
  const [flash, setFlash]         = useState<{ kind: 'ok' | 'restrict'; msg: string } | null>(null);

  const reload = useCallback(() => {
    setLoading(true);
    Promise.all([fetchNotes(), fetchRestricted()])
      .then(([n, r]) => { setNotes(n.notes ?? []); setRestricted(r.restricted ?? []); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { reload(); }, [reload]);
  useEffect(() => { setSubject(ticker.toUpperCase()); }, [ticker]);

  async function submit() {
    if (!subject.trim() || !text.trim() || busy) return;
    setBusy(true); setFlash(null);
    try {
      const r = await createNote({
        subject: subject.trim(),
        text: text.trim(),
        source: source.trim(),
        subjectTicker: subject.trim(),
        isPublicSubject: isPublic,
        isMaterialNonpublic: isMnpi,
      });
      setText('');
      if (r.restrictedTriggered) {
        setFlash({ kind: 'restrict', msg: `${r.subjectTicker ?? subject} is now restricted — trade-oriented signals are suppressed for it.` });
      } else {
        setFlash({ kind: 'ok', msg: 'Note saved. It stays local and is never used in any public signal.' });
      }
      reload();
    } catch {
      setFlash({ kind: 'restrict', msg: 'Failed to save note.' });
    } finally {
      setBusy(false);
    }
  }

  async function lift(t: string) {
    await liftRestriction(t).catch(() => {});
    reload();
  }

  return (
    <div className="space-y-4">
      <PanelHeader title="Private Notes & Compliance Wall" />

      <Callout tone="info">
        Notes you log here stay <strong>local to this workspace</strong> and are never sent to any
        external service or fed into a public-security signal. If you flag a note as material
        non-public information (MNPI) about a listed company, that ticker is added to your{' '}
        <strong>restricted list</strong> and its trade-oriented panels (ML signal, DCF, rNPV,
        scenarios, backtest) are suppressed — an information barrier, by construction.
      </Callout>

      {/* ── Capture form ── */}
      <div className="bg-surface border border-line rounded-lg p-3 space-y-2.5">
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-[9px] uppercase tracking-wider text-dim">Subject / ticker</label>
            <input
              value={subject}
              onChange={e => setSubject(e.target.value)}
              className="w-full mt-0.5 bg-base border border-line rounded px-2 py-1 text-[11px] font-mono text-ink focus:border-hi outline-none"
            />
          </div>
          <div>
            <label className="text-[9px] uppercase tracking-wider text-dim">Source</label>
            <input
              value={source}
              onChange={e => setSource(e.target.value)}
              placeholder="e.g. management call, dinner"
              className="w-full mt-0.5 bg-base border border-line rounded px-2 py-1 text-[11px] text-ink focus:border-hi outline-none"
            />
          </div>
        </div>
        <div>
          <label className="text-[9px] uppercase tracking-wider text-dim">Note</label>
          <textarea
            value={text}
            onChange={e => setText(e.target.value)}
            rows={3}
            placeholder="What you learned…"
            className="w-full mt-0.5 bg-base border border-line rounded px-2 py-1.5 text-[11px] text-ink focus:border-hi outline-none resize-none"
          />
        </div>
        <div className="space-y-1.5">
          <Check label="Subject is a publicly-listed company" checked={isPublic} onChange={setIsPublic} />
          <Check
            label="This is material, non-public information (MNPI)"
            hint="If checked and the subject is public, the ticker is restricted and its signals are suppressed."
            checked={isMnpi}
            onChange={setIsMnpi}
          />
        </div>
        <button
          onClick={submit}
          disabled={busy || !subject.trim() || !text.trim()}
          className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded text-[11px] font-medium border border-hi/40 text-hi hover:bg-hi/10 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <Lock size={11} /> {busy ? 'Saving…' : 'Save private note'}
        </button>
        {flash && (
          <Callout tone={flash.kind === 'restrict' ? 'danger' : 'success'}>{flash.msg}</Callout>
        )}
      </div>

      {/* ── Restricted list ── */}
      {restricted.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[10px] uppercase tracking-wider text-dim flex items-center gap-1">
            <ShieldAlert size={11} className="text-red-400" /> Restricted tickers
          </p>
          {restricted.map(r => (
            <div key={r.ticker} className="flex items-center justify-between gap-2 bg-red-500/5 border border-red-500/25 rounded px-3 py-2">
              <div className="min-w-0">
                <span className="font-mono text-[11px] text-red-300">{r.ticker}</span>
                <p className="text-[9px] text-dim truncate">{r.reason}</p>
              </div>
              <button
                onClick={() => lift(r.ticker)}
                title="Lift restriction (audit-logged)"
                className="flex items-center gap-1 text-[9px] text-dim hover:text-ink border border-line rounded px-1.5 py-0.5 transition-colors flex-none"
              >
                <Unlock size={9} /> Lift
              </button>
            </div>
          ))}
        </div>
      )}

      {/* ── Notes list (provenance only — free text stays local) ── */}
      <div className="space-y-1.5">
        <p className="text-[10px] uppercase tracking-wider text-dim">Logged notes ({notes.length})</p>
        {loading ? (
          <p className="text-[11px] text-dim">Loading…</p>
        ) : notes.length === 0 ? (
          <PanelMessage kind="empty" title="No notes yet." detail="Captured notes are listed here by subject and provenance; the text itself is never surfaced through any signal endpoint." />
        ) : (
          notes.map(n => (
            <div key={n.id} className="bg-elevated border border-line rounded px-3 py-2 flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-[11px] text-ink font-medium truncate">{n.subject}</span>
                  {n.restricted && <RestrictedBadge />}
                </div>
                <p className="text-[9px] text-dim">
                  {n.source || 'no source'} · {n.createdAt?.slice(0, 10)}
                  {n.isPublicSubject ? ' · public' : ' · private'}
                  {n.isMaterialNonpublic ? ' · MNPI' : ''}
                </p>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
