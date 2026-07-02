import { useState } from 'react';
import { Rnd } from 'react-rnd';
import { HelpCircle, ExternalLink, Settings, X, RefreshCw, Link2 } from 'lucide-react';
import type { AppTab } from '@/types';
import type { WindowInstance } from '@/lib/windowManager';
import { useWindowManager } from '@/lib/windowManager';
import { PANEL_DEFS, type PanelHelpers } from '@/lib/panelRegistry';
import { TickerInput } from '@/components/TickerInput';

interface Props {
  panelId: AppTab;
  win:     WindowInstance;
  helpers: PanelHelpers;
}

export function Window({ panelId, win, helpers }: Props) {
  const wm = useWindowManager();
  const def = PANEL_DEFS[panelId];
  const [settingsOpen, setSettingsOpen] = useState(false);

  function popout() {
    const url = `${location.origin}${location.pathname}?popout=${panelId}&ticker=${encodeURIComponent(win.ticker)}`;
    window.open(url, `_bt_${panelId}`, 'width=760,height=640,noopener,noreferrer');
  }

  return (
    <Rnd
      size={{ width: win.w, height: win.h }}
      position={{ x: win.x, y: win.y }}
      minWidth={320}
      minHeight={260}
      bounds="parent"
      dragHandleClassName={`win-drag-${panelId}`}
      style={{ zIndex: win.z }}
      onDragStop={(_e, d) => wm.setRect(panelId, { ...win, x: d.x, y: d.y })}
      onResizeStop={(_e, _dir, ref, _delta, position) => {
        wm.setRect(panelId, {
          x: position.x, y: position.y,
          w: parseInt(ref.style.width, 10),
          h: parseInt(ref.style.height, 10),
        });
      }}
      onMouseDown={() => wm.focus(panelId)}
      className="win-shell"
    >
      <div className="h-full w-full flex flex-col bg-surface border border-line rounded-md overflow-hidden shadow-2xl">
        {/* Title bar */}
        <div className={`win-drag-${panelId} cursor-move flex items-center gap-2 h-[30px] flex-none px-2 bg-elevated border-b border-line select-none`}>
          <span className="text-[10px] font-semibold tracking-wide text-ink uppercase whitespace-nowrap">
            {def.label}
          </span>

          <TickerInput
            size="sm"
            value={win.ticker}
            placeholder={win.ticker}
            onSelect={t => wm.setWindowTicker(panelId, t)}
            className="ml-1"
          />

          {!win.syncTicker && (
            <span className="text-[8px] text-hi bg-hi/10 border border-hi/30 rounded px-1 py-0.5 leading-none flex-none" title="Independent ticker — not synced to the global symbol">
              OWN
            </span>
          )}

          <div className="flex-1" />

          <button
            title={def.description}
            className="p-1 text-dim hover:text-ink hover:bg-line/40 rounded transition-colors"
          >
            <HelpCircle size={12} />
          </button>

          <button
            title="Pop out into a new window"
            onClick={popout}
            className="p-1 text-dim hover:text-ink hover:bg-line/40 rounded transition-colors"
          >
            <ExternalLink size={12} />
          </button>

          <div className="relative">
            <button
              title="Window settings"
              onClick={() => setSettingsOpen(o => !o)}
              className="p-1 text-dim hover:text-ink hover:bg-line/40 rounded transition-colors"
            >
              <Settings size={12} />
            </button>
            {settingsOpen && (
              <div className="absolute top-full right-0 mt-1 w-52 bg-elevated border border-line rounded-lg dropdown-shadow z-[10001] py-1">
                <button
                  onClick={() => { wm.toggleSync(panelId); setSettingsOpen(false); }}
                  className="w-full flex items-center gap-2 px-3 py-1.5 text-[11px] text-ink hover:bg-surface text-left"
                >
                  <Link2 size={11} className={win.syncTicker ? 'text-hi' : 'text-dim'} />
                  {win.syncTicker ? 'Synced with global ticker' : 'Sync with global ticker'}
                </button>
                <button
                  onClick={() => {
                    const d = PANEL_DEFS[panelId].defaultSize;
                    wm.setRect(panelId, { x: win.x, y: win.y, w: d.w, h: d.h });
                    setSettingsOpen(false);
                  }}
                  className="w-full flex items-center gap-2 px-3 py-1.5 text-[11px] text-ink hover:bg-surface text-left"
                >
                  <RefreshCw size={11} className="text-dim" />
                  Reset size &amp; position
                </button>
              </div>
            )}
          </div>

          <button
            title="Close"
            onClick={() => wm.close(panelId)}
            className="p-1 text-dim hover:text-down hover:bg-line/40 rounded transition-colors"
          >
            <X size={12} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 min-h-0 overflow-y-auto p-3">
          {def.render(win.ticker, helpers)}
        </div>
      </div>
    </Rnd>
  );
}
