import { useEffect, useRef, useState } from 'react';
import { LayoutGrid, RotateCcw } from 'lucide-react';
import { useWindowManager } from '@/lib/windowManager';
import { PANEL_DEFS, PANEL_ORDER } from '@/lib/panelRegistry';

export function WindowsMenu() {
  const wm = useWindowManager();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handle(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1.5 p-1.5 rounded-md text-dim hover:text-ink hover:bg-elevated transition-colors"
        title="Windows"
      >
        <LayoutGrid size={14} />
      </button>

      {open && (
        <div className="absolute top-full right-0 mt-1 w-64 bg-elevated border border-line rounded-lg dropdown-shadow z-[10000] py-1 max-h-[70vh] overflow-y-auto">
          <div className="flex items-center justify-between px-3 py-1.5">
            <span className="text-[9px] uppercase tracking-widest text-dim font-semibold">Windows</span>
            <button
              onClick={() => { wm.resetLayout(); setOpen(false); }}
              className="flex items-center gap-1 text-[9px] text-dim hover:text-hi transition-colors"
              title="Reset layout"
            >
              <RotateCcw size={9} /> Reset
            </button>
          </div>
          <div className="my-1 border-t border-line" />
          {PANEL_ORDER.map(panelId => {
            const isOpen = !!wm.windows[panelId];
            return (
              <button
                key={panelId}
                onClick={() => { wm.open(panelId); setOpen(false); }}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-[11px] hover:bg-surface text-left transition-colors"
              >
                <span className={`w-1.5 h-1.5 rounded-full flex-none ${isOpen ? 'bg-hi' : 'bg-line'}`} />
                <span className={isOpen ? 'text-ink' : 'text-dim'}>{PANEL_DEFS[panelId].label}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
