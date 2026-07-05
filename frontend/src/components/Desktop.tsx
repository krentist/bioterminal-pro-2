import type { ReactNode } from 'react';
import { useWindowManager } from '@/lib/windowManager';
import { Window } from '@/components/Window';

interface Props {
  emptyState: ReactNode;
}

export function Desktop({ emptyState }: Props) {
  const wm = useWindowManager();
  const helpers = { openWindow: wm.open, openTicker: wm.openTicker };

  return (
    <div className="relative flex-1 min-h-0 overflow-hidden bg-base desktop-grid">
      {wm.order.length === 0 ? (
        emptyState
      ) : (
        wm.order.map(panelId => {
          const win = wm.windows[panelId];
          if (!win) return null;
          return <Window key={panelId} panelId={panelId} win={win} helpers={helpers} />;
        })
      )}
    </div>
  );
}
