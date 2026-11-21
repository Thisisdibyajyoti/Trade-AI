import { useCallback, useEffect, useRef, useState } from 'react';
import type { AnalysisPayload, FeedStatus, LiveCandle } from '../types';

const API_BASE =
  import.meta.env.VITE_API_BASE || import.meta.env.VITE_API_URL || '/api';

/** Build the live WebSocket URL for an instrument + timeframe. */
function buildWsUrl(symbol: string, timeframe: string): string {
  const explicit = import.meta.env.VITE_WS_URL as string | undefined;
  let base: string;
  if (explicit) {
    base = explicit;
  } else if (API_BASE.startsWith('http')) {
    // http://host:8000/api -> ws://host:8000
    base = API_BASE.replace(/^http/, 'ws').replace(/\/api\/?$/, '');
  } else {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    base = `${proto}://${window.location.host}`;
  }
  base = base.replace(/\/$/, '');
  return `${base}/ws/live/${encodeURIComponent(symbol)}?timeframe=${encodeURIComponent(timeframe)}`;
}

export interface LiveFeedState {
  candles: LiveCandle[];
  forming: LiveCandle | null;
  price: number | null;
  status: FeedStatus | null;
  analysis: AnalysisPayload | null;
  connected: boolean;
  error: string | null;
}

const INITIAL: LiveFeedState = {
  candles: [],
  forming: null,
  price: null,
  status: null,
  analysis: null,
  connected: false,
  error: null,
};

// The backend already throttles snapshots to ~4/s; this is a client-side
// safety net so bursts of ticks never trigger more than 4 renders per second.
const FLUSH_MS = 250;

/**
 * Subscribes to the backend live feed for one instrument/timeframe.
 *
 * - `history` seeds the closed candles + the forming candle.
 * - `snapshot` (throttled) updates the live price / forming candle.
 * - `candle` appends a freshly closed candle.
 * - `prediction` replaces the analysis (only fires on candle close).
 * - `feed_status` drives the LIVE / DELAYED / CLOSED / STALE badge.
 */
export function useLiveFeed(symbol: string, timeframe: string): LiveFeedState {
  const [state, setState] = useState<LiveFeedState>(INITIAL);

  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);
  const reconnectTimer = useRef<number | null>(null);
  const intentionalClose = useRef(false);

  const timeframeRef = useRef(timeframe);
  timeframeRef.current = timeframe;

  const candlesRef = useRef<LiveCandle[]>([]);
  const formingRef = useRef<LiveCandle | null>(null);
  const priceRef = useRef<number | null>(null);
  const dirtyRef = useRef(false);

  const flush = useCallback(() => {
    if (!dirtyRef.current) return;
    dirtyRef.current = false;
    setState((prev) => ({ ...prev, price: priceRef.current, forming: formingRef.current }));
  }, []);

  const connect = useCallback(
    (sym: string) => {
      if (!sym) return;
      intentionalClose.current = false;
      const url = buildWsUrl(sym, timeframeRef.current);
      let ws: WebSocket;
      try {
        ws = new WebSocket(url);
      } catch (err) {
        setState((prev) => ({ ...prev, error: String(err) }));
        return;
      }
      wsRef.current = ws;

      ws.onopen = () => {
        retryRef.current = 0;
        setState((prev) => ({ ...prev, connected: true, error: null }));
      };

      ws.onmessage = (event) => {
        let msg: any;
        try {
          msg = JSON.parse(event.data);
        } catch {
          return;
        }

        switch (msg.type) {
          case 'history': {
            const closed: LiveCandle[] = [];
            let forming: LiveCandle | null = null;
            for (const c of msg.candles as LiveCandle[]) {
              if (c.is_closed === false) forming = c;
              else closed.push(c);
            }
            candlesRef.current = closed;
            if (forming) {
              formingRef.current = forming;
              priceRef.current = forming.close;
            } else if (closed.length) {
              priceRef.current = closed[closed.length - 1].close;
            }
            setState((prev) => ({
              ...prev,
              candles: closed,
              forming: formingRef.current,
              price: priceRef.current,
              error: null,
            }));
            break;
          }
          case 'snapshot': {
            if (typeof msg.price === 'number') priceRef.current = msg.price;
            const tf = msg.forming?.[timeframeRef.current];
            if (tf) formingRef.current = { ...tf, is_closed: false };
            dirtyRef.current = true;
            break;
          }
          case 'candle': {
            if (msg.is_closed) {
              const candle = msg.candle as LiveCandle;
              const list = candlesRef.current;
              if (list.length && list[list.length - 1].time === candle.time) {
                list[list.length - 1] = candle;
              } else if (!list.length || list[list.length - 1].time < candle.time) {
                list.push(candle);
              }
              if (formingRef.current && formingRef.current.time <= candle.time) {
                formingRef.current = null;
              }
              setState((prev) => ({ ...prev, candles: [...list] }));
            }
            break;
          }
          case 'prediction': {
            const analysis = msg as AnalysisPayload;
            setState((prev) => ({ ...prev, analysis }));
            break;
          }
          case 'feed_status': {
            setState((prev) => ({ ...prev, status: msg as FeedStatus }));
            break;
          }
          case 'error': {
            setState((prev) => ({ ...prev, error: msg.message || 'Feed error' }));
            // Unidentifiable symbol: do not hammer the server with retries.
            intentionalClose.current = true;
            break;
          }
          default:
            break;
        }
      };

      ws.onclose = () => {
        setState((prev) => ({ ...prev, connected: false }));
        if (intentionalClose.current) return;
        // Exponential backoff: 1s, 2s, 4s, ... capped at 30s.
        retryRef.current += 1;
        const delay = Math.min(30000, 1000 * 2 ** Math.min(retryRef.current - 1, 5));
        reconnectTimer.current = window.setTimeout(() => connect(sym), delay);
      };

      ws.onerror = () => {
        setState((prev) => ({ ...prev, connected: false }));
      };
    },
    [],
  );

  // (Re)connect whenever the instrument changes.
  useEffect(() => {
    candlesRef.current = [];
    formingRef.current = null;
    priceRef.current = null;
    retryRef.current = 0;
    setState(INITIAL);
    connect(symbol);

    return () => {
      intentionalClose.current = true;
      if (reconnectTimer.current) window.clearTimeout(reconnectTimer.current);
      const ws = wsRef.current;
      if (ws) {
        ws.onclose = null;
        ws.onmessage = null;
        ws.onerror = null;
        ws.close();
      }
      wsRef.current = null;
    };
  }, [symbol, connect]);

  // Switch timeframe on the existing socket (no reconnect, no gap).
  useEffect(() => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ action: 'set_timeframe', timeframe }));
    }
  }, [timeframe]);

  // Throttled flush loop for price / forming-candle updates.
  useEffect(() => {
    const id = window.setInterval(flush, FLUSH_MS);
    return () => window.clearInterval(id);
  }, [flush]);

  return state;
}
