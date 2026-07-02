import { createContext, useContext, useEffect, useMemo, useReducer, useRef, type ReactNode } from 'react';
import type { AppTab } from '@/types';
import { PANEL_DEFS, DEFAULT_OPEN_PANELS } from '@/lib/panelRegistry';

export interface WindowRect { x: number; y: number; w: number; h: number; }

export interface WindowInstance extends WindowRect {
  panelId:    AppTab;
  ticker:     string;
  syncTicker: boolean;
  z:          number;
}

interface WMState {
  globalTicker: string;
  windows: Partial<Record<AppTab, WindowInstance>>;
  order:   AppTab[];
}

type Action =
  | { type: 'OPEN';  panelId: AppTab; ticker?: string }
  | { type: 'CLOSE'; panelId: AppTab }
  | { type: 'FOCUS'; panelId: AppTab }
  | { type: 'RECT';  panelId: AppTab; rect: WindowRect }
  | { type: 'SET_TICKER';    panelId: AppTab; ticker: string }
  | { type: 'TOGGLE_SYNC';   panelId: AppTab }
  | { type: 'SET_GLOBAL_TICKER'; ticker: string }
  | { type: 'RESET_LAYOUT' }
  | { type: 'HYDRATE'; state: WMState };

const STORAGE_KEY = 'bioterminal.windows.v1';
const TOPBAR_H = 44;

function cascadeRect(panelId: AppTab, openCount: number): WindowRect {
  const def = PANEL_DEFS[panelId].defaultSize;
  const vw = typeof window !== 'undefined' ? window.innerWidth  : 1440;
  const vh = typeof window !== 'undefined' ? window.innerHeight : 900;
  const step = 28;
  const cols = Math.max(1, Math.floor((vw - 80) / (def.w + step)));
  const col = openCount % Math.max(cols, 1);
  const row = Math.floor(openCount / Math.max(cols, 1));
  const baseX = 24 + col * step + Math.floor((openCount / Math.max(cols, 1)) % 3) * 40;
  const baseY = TOPBAR_H + 16 + row * step + (openCount % 4) * 12;
  const x = Math.min(baseX, Math.max(8, vw - def.w - 8));
  const y = Math.min(baseY, Math.max(TOPBAR_H + 8, vh - def.h - 8));
  return { x, y, w: def.w, h: def.h };
}

function nextZ(state: WMState): number {
  let max = 0;
  for (const id of state.order) max = Math.max(max, state.windows[id]?.z ?? 0);
  return max + 1;
}

function reducer(state: WMState, action: Action): WMState {
  switch (action.type) {
    case 'HYDRATE':
      return action.state;

    case 'OPEN': {
      const existing = state.windows[action.panelId];
      const ticker = action.ticker ?? existing?.ticker ?? state.globalTicker;
      if (existing) {
        return {
          ...state,
          windows: { ...state.windows, [action.panelId]: { ...existing, ticker, z: nextZ(state) } },
          order: [...state.order.filter(id => id !== action.panelId), action.panelId],
        };
      }
      const rect = cascadeRect(action.panelId, state.order.length);
      const win: WindowInstance = {
        panelId: action.panelId,
        ticker,
        syncTicker: true,
        z: nextZ(state),
        ...rect,
      };
      return {
        ...state,
        windows: { ...state.windows, [action.panelId]: win },
        order: [...state.order, action.panelId],
      };
    }

    case 'CLOSE': {
      const windows = { ...state.windows };
      delete windows[action.panelId];
      return { ...state, windows, order: state.order.filter(id => id !== action.panelId) };
    }

    case 'FOCUS': {
      if (!state.windows[action.panelId]) return state;
      return {
        ...state,
        windows: {
          ...state.windows,
          [action.panelId]: { ...state.windows[action.panelId]!, z: nextZ(state) },
        },
        order: [...state.order.filter(id => id !== action.panelId), action.panelId],
      };
    }

    case 'RECT': {
      const win = state.windows[action.panelId];
      if (!win) return state;
      return { ...state, windows: { ...state.windows, [action.panelId]: { ...win, ...action.rect } } };
    }

    case 'SET_TICKER': {
      const win = state.windows[action.panelId];
      if (!win) return state;
      return {
        ...state,
        windows: { ...state.windows, [action.panelId]: { ...win, ticker: action.ticker, syncTicker: false } },
      };
    }

    case 'TOGGLE_SYNC': {
      const win = state.windows[action.panelId];
      if (!win) return state;
      const syncTicker = !win.syncTicker;
      return {
        ...state,
        windows: {
          ...state.windows,
          [action.panelId]: { ...win, syncTicker, ticker: syncTicker ? state.globalTicker : win.ticker },
        },
      };
    }

    case 'SET_GLOBAL_TICKER': {
      const windows = { ...state.windows };
      for (const id of Object.keys(windows) as AppTab[]) {
        const w = windows[id]!;
        if (w.syncTicker) windows[id] = { ...w, ticker: action.ticker };
      }
      return { ...state, globalTicker: action.ticker, windows };
    }

    case 'RESET_LAYOUT': {
      const windows = { ...state.windows };
      let order: AppTab[] = [];
      for (const id of state.order) {
        const rect = cascadeRect(id, order.length);
        windows[id] = { ...windows[id]!, ...rect, z: order.length + 1 };
        order.push(id);
      }
      return { ...state, windows, order };
    }

    default:
      return state;
  }
}

function initialState(): WMState {
  return { globalTicker: '', windows: {}, order: [] };
}

function loadPersisted(): WMState | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as WMState;
    if (!parsed || typeof parsed !== 'object' || !parsed.windows || !Array.isArray(parsed.order)) return null;
    return parsed;
  } catch {
    return null;
  }
}

interface WMContextValue {
  globalTicker: string;
  windows: WMState['windows'];
  order:   AppTab[];
  open:    (panelId: AppTab, ticker?: string) => void;
  close:   (panelId: AppTab) => void;
  focus:   (panelId: AppTab) => void;
  setRect: (panelId: AppTab, rect: WindowRect) => void;
  setWindowTicker: (panelId: AppTab, ticker: string) => void;
  toggleSync: (panelId: AppTab) => void;
  setGlobalTicker: (ticker: string) => void;
  resetLayout: () => void;
  openTicker: (ticker: string) => void;
}

const WindowManagerContext = createContext<WMContextValue | null>(null);

export function WindowManagerProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, undefined, initialState);
  const hydrated = useRef(false);

  useEffect(() => {
    const persisted = loadPersisted();
    if (persisted) dispatch({ type: 'HYDRATE', state: persisted });
    hydrated.current = true;
  }, []);

  useEffect(() => {
    if (!hydrated.current) return;
    const t = setTimeout(() => {
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch { /* ignore */ }
    }, 250);
    return () => clearTimeout(t);
  }, [state]);

  const value = useMemo<WMContextValue>(() => ({
    globalTicker: state.globalTicker,
    windows: state.windows,
    order:   state.order,
    open:    (panelId, ticker) => dispatch({ type: 'OPEN', panelId, ticker }),
    close:   panelId => dispatch({ type: 'CLOSE', panelId }),
    focus:   panelId => dispatch({ type: 'FOCUS', panelId }),
    setRect: (panelId, rect) => dispatch({ type: 'RECT', panelId, rect }),
    setWindowTicker: (panelId, ticker) => dispatch({ type: 'SET_TICKER', panelId, ticker }),
    toggleSync: panelId => dispatch({ type: 'TOGGLE_SYNC', panelId }),
    setGlobalTicker: ticker => dispatch({ type: 'SET_GLOBAL_TICKER', ticker }),
    resetLayout: () => dispatch({ type: 'RESET_LAYOUT' }),
    openTicker: ticker => {
      dispatch({ type: 'SET_GLOBAL_TICKER', ticker });
      dispatch({ type: 'OPEN', panelId: 'overview', ticker });
    },
  }), [state]);

  return <WindowManagerContext.Provider value={value}>{children}</WindowManagerContext.Provider>;
}

export function useWindowManager(): WMContextValue {
  const ctx = useContext(WindowManagerContext);
  if (!ctx) throw new Error('useWindowManager must be used within WindowManagerProvider');
  return ctx;
}

export function openDefaultPanels(wm: WMContextValue, ticker: string) {
  wm.setGlobalTicker(ticker);
  DEFAULT_OPEN_PANELS.forEach(panelId => wm.open(panelId, ticker));
}
