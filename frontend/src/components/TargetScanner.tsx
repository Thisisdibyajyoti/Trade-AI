import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Crosshair, Search, X, TrendingUp, TrendingDown, Minus, Loader2 } from 'lucide-react';
import type { CryptoMarketCoin } from '../types';

const API_BASE = import.meta.env.VITE_API_BASE || '/api';
const TOOLBAR_H = 64;

export interface CryptoHit {
  name: string;
  symbol: string;
  ticker: string;
  blurb: string;
}

export interface QuickGrowth {
  status: string;
  message?: string;
  symbol: string;
  resolved_ticker?: string;
  current_price?: number;
  potential_growth_pct?: number;
  bias?: string;
  returns?: {
    '7d_pct': number | null;
    '30d_pct': number | null;
    '90d_pct': number | null;
  };
  expected_30d_move_pct?: number;
  probabilities?: {
    UP: number;
    DOWN: number;
    SIDEWAYS: number;
  };
}

interface TargetScannerProps {
  active: boolean;
  onStop: () => void;
}

export const TargetScanner: React.FC<TargetScannerProps> = ({ active, onStop }) => {
  const [query, setQuery] = useState('');
  const [pos, setPos] = useState({ x: 420, y: 320 });
  const [dragging, setDragging] = useState(false);
  const [locked, setLocked] = useState<CryptoHit | null>(null);
  const [growth, setGrowth] = useState<QuickGrowth | null>(null);
  const [loadingGrowth, setLoadingGrowth] = useState(false);
  const [coins, setCoins] = useState<CryptoMarketCoin[]>([]);
  const [loadingCoins, setLoadingCoins] = useState(false);
  const [coinsError, setCoinsError] = useState<string | null>(null);
  const dragOffset = useRef({ x: 0, y: 0 });
  const reticleRef = useRef<HTMLDivElement>(null);
  const cacheRef = useRef<Record<string, QuickGrowth>>({});
  const lastSymbolRef = useRef<string | null>(null);
  const onStopRef = useRef(onStop);
  onStopRef.current = onStop;

  // Load the real, live crypto list (CoinGecko-backed) so the search surface is
  // built from actual market data instead of a hard-coded catalog.
  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    setLoadingCoins(true);
    setCoinsError(null);
    fetch(`${API_BASE}/crypto-list?limit=100`)
      .then((res) => res.json())
      .then((data) => {
        if (cancelled) return;
        if (data.status === 'SUCCESS' && Array.isArray(data.coins)) {
          setCoins(data.coins);
        } else {
          setCoins([]);
          setCoinsError('Live crypto list is unavailable right now. Please retry shortly.');
        }
      })
      .catch(() => {
        if (!cancelled) setCoinsError('Failed to load the live crypto list.');
      })
      .finally(() => {
        if (!cancelled) setLoadingCoins(false);
      });
    return () => {
      cancelled = true;
    };
  }, [active]);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return coins;
    return coins.filter(
      (c) =>
        (c.name || '').toLowerCase().includes(q) ||
        (c.ticker || '').toLowerCase().includes(q) ||
        (c.trade_symbol || '').toLowerCase().includes(q),
    );
  }, [coins, query]);

  const blurbFor = (c: CryptoMarketCoin) => {
    const bits = [`Ranked #${c.rank ?? '—'} by market cap.`];
    if (typeof c.change_7d === 'number') bits.push(`7d ${c.change_7d.toFixed(2)}%.`);
    if (typeof c.change_30d === 'number') bits.push(`30d ${c.change_30d.toFixed(2)}%.`);
    return bits.join(' ');
  };

  const clampPos = useCallback((x: number, y: number) => ({
    x: Math.max(8, Math.min(window.innerWidth - 88, x)),
    y: Math.max(TOOLBAR_H + 8, Math.min(window.innerHeight - 88, y)),
  }), []);

  const fetchGrowth = useCallback(async (hit: CryptoHit) => {
    const key = hit.symbol.toUpperCase();
    if (cacheRef.current[key]) {
      setGrowth(cacheRef.current[key]);
      return;
    }
    setLoadingGrowth(true);
    setGrowth(null);
    try {
      const res = await fetch(`${API_BASE}/quick-growth?symbol=${encodeURIComponent(hit.symbol)}`);
      const data: QuickGrowth = await res.json();
      if (data.status === 'SUCCESS') cacheRef.current[key] = data;
      setGrowth(data);
    } catch {
      setGrowth({ status: 'ERROR', symbol: hit.symbol, message: 'Failed to load growth data.' });
    } finally {
      setLoadingGrowth(false);
    }
  }, []);

  const detectUnderTarget = useCallback(() => {
    const el = reticleRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;

    el.style.pointerEvents = 'none';
    const under = document.elementFromPoint(cx, cy) as HTMLElement | null;
    el.style.pointerEvents = 'auto';

    if (!under) {
      setLocked(null);
      lastSymbolRef.current = null;
      return;
    }

    const cryptoNode = under.closest('[data-crypto-symbol]') as HTMLElement | null;
    if (!cryptoNode) {
      setLocked(null);
      lastSymbolRef.current = null;
      return;
    }

    const symbol = cryptoNode.getAttribute('data-crypto-symbol') || '';
    const name = cryptoNode.getAttribute('data-crypto-name') || symbol;
    const ticker = cryptoNode.getAttribute('data-crypto-ticker') || symbol;
    const hit: CryptoHit = {
      name,
      symbol,
      ticker,
      blurb: cryptoNode.getAttribute('data-crypto-blurb') || '',
    };

    setLocked(hit);
    if (lastSymbolRef.current !== symbol) {
      lastSymbolRef.current = symbol;
      void fetchGrowth(hit);
    }
  }, [fetchGrowth]);

  useEffect(() => {
    if (!active) return;
    detectUnderTarget();
  }, [active, pos, detectUnderTarget]);

  // Esc always stops the scanner
  useEffect(() => {
    if (!active) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onStopRef.current();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [active]);

  useEffect(() => {
    if (!dragging) return;
    const onMove = (e: PointerEvent) => {
      setPos(clampPos(e.clientX - dragOffset.current.x, e.clientY - dragOffset.current.y));
    };
    const onUp = () => setDragging(false);
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    return () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };
  }, [dragging, clampPos]);

  if (!active) return null;

  const growthPct = growth?.potential_growth_pct;
  const BiasIcon =
    growth?.bias === 'BULLISH' ? TrendingUp : growth?.bias === 'BEARISH' ? TrendingDown : Minus;

  const stop = (e?: React.MouseEvent) => {
    e?.preventDefault();
    e?.stopPropagation();
    onStop();
  };

  return (
    <div
      className="scanner-root"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 90,
        display: 'flex',
        flexDirection: 'column',
        background: '#09090B',
        fontFamily: "'Plus Jakarta Sans', Inter, system-ui, sans-serif",
      }}
    >
      {/* Always-on-top toolbar — above the reticle so Stop always works */}
      <div
        className="scanner-toolbar"
        style={{
          position: 'relative',
          zIndex: 200,
          height: TOOLBAR_H,
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 1.25rem',
          background: 'rgba(18, 18, 22, 0.96)',
          borderBottom: '1px solid rgba(217, 70, 239, 0.35)',
          boxShadow: '0 8px 32px rgba(217, 70, 239, 0.15)',
          pointerEvents: 'auto',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: '#F0ABFC' }}>
          <Crosshair size={18} />
          <span style={{ fontSize: 12, fontWeight: 800, letterSpacing: '0.08em' }}>TARGET SCANNER</span>
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: 99,
              background: 'linear-gradient(90deg,#D946EF,#EC4899)',
              boxShadow: '0 0 12px rgba(217,70,239,0.8)',
            }}
          />
          <span style={{ fontSize: 11, color: '#8E8E98' }}>Press Esc to stop</span>
        </div>

        <button
          type="button"
          onClick={stop}
          onPointerDown={(e) => e.stopPropagation()}
          style={{
            background: 'linear-gradient(90deg, #EC4899, #D946EF)',
            color: '#09090B',
            border: 'none',
            borderRadius: 12,
            padding: '10px 18px',
            fontWeight: 800,
            fontSize: 13,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            boxShadow: '0 0 24px rgba(217, 70, 239, 0.45)',
            pointerEvents: 'auto',
            fontFamily: 'inherit',
          }}
        >
          <X size={16} strokeWidth={3} /> Stop Scanner
        </button>
      </div>

      {/* Search surface */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '2rem 1rem', position: 'relative', zIndex: 1 }}>
        <div style={{ maxWidth: 672, margin: '0 auto' }}>
          <div style={{ textAlign: 'center', marginBottom: 32 }}>
            <div style={{ fontSize: 36, fontWeight: 800, letterSpacing: '-0.03em', marginBottom: 24 }}>
              <span style={{ color: '#D946EF' }}>Trade</span>
              <span style={{ color: '#fff' }}>AI</span>
              <span style={{ color: '#8E8E98', fontSize: 14, marginLeft: 10, fontWeight: 600 }}>crypto search</span>
            </div>
            <form
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                background: '#141418',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: 16,
                padding: '12px 16px',
              }}
              onSubmit={(e) => {
                e.preventDefault();
              }}
            >
              <Search size={16} color="#8E8E98" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search crypto (bitcoin, ethereum, solana…)"
                style={{
                  flex: 1,
                  background: 'transparent',
                  border: 'none',
                  outline: 'none',
                  color: '#fff',
                  fontSize: 14,
                  fontFamily: 'inherit',
                }}
              />
              {loadingCoins && <Loader2 size={14} className="animate-spin" color="#8E8E98" />}
            </form>
            <p style={{ fontSize: 11, color: '#8E8E98', marginTop: 12 }}>
              Drag the magenta target onto a crypto name to see potential growth
            </p>
          </div>

          {coinsError && (
            <div style={{ fontSize: 12, color: '#F9A8D4', textAlign: 'center', marginBottom: 16 }}>
              {coinsError}
            </div>
          )}

          <div style={{ fontSize: 12, color: '#8E8E98', marginBottom: 16 }}>
            Showing {results.length} live coins{query.trim() ? ` for "${query.trim()}"` : ''} · source: CoinGecko
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            {results.map((c) => {
              const blurb = blurbFor(c);
              return (
                <article
                  key={c.id || c.trade_symbol}
                  data-crypto-symbol={c.trade_symbol}
                  data-crypto-name={c.name}
                  data-crypto-ticker={c.ticker}
                  data-crypto-blurb={blurb}
                  style={{
                    padding: 16,
                    borderRadius: 16,
                    background: '#121216',
                    border: '1px solid rgba(255,255,255,0.07)',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      fontSize: 11,
                      color: '#8E8E98',
                      marginBottom: 4,
                    }}
                  >
                    <span>crypto · {c.ticker}</span>
                    {typeof c.price === 'number' && (
                      <span style={{ color: '#F0ABFC', fontFamily: 'ui-monospace, monospace' }}>
                        ${c.price.toLocaleString(undefined, { maximumFractionDigits: 6 })}
                      </span>
                    )}
                  </div>
                  <h3
                    data-crypto-symbol={c.trade_symbol}
                    data-crypto-name={c.name}
                    data-crypto-ticker={c.ticker}
                    style={{ margin: 0, fontSize: 20, color: '#E879F9', fontWeight: 700 }}
                  >
                    {c.name} ({c.ticker}) — Cryptocurrency
                  </h3>
                  <p
                    data-crypto-symbol={c.trade_symbol}
                    data-crypto-name={c.name}
                    data-crypto-ticker={c.ticker}
                    style={{ margin: '8px 0 0', fontSize: 14, color: '#B4B4BE', lineHeight: 1.6 }}
                  >
                    <span
                      data-crypto-symbol={c.trade_symbol}
                      data-crypto-name={c.name}
                      data-crypto-ticker={c.ticker}
                      style={{ color: '#F0ABFC', fontWeight: 700 }}
                    >
                      {c.name}
                    </span>{' '}
                    {blurb} Ticker{' '}
                    <span
                      data-crypto-symbol={c.trade_symbol}
                      data-crypto-name={c.name}
                      data-crypto-ticker={c.ticker}
                      style={{ color: '#EC4899', fontFamily: 'ui-monospace, monospace' }}
                    >
                      {c.trade_symbol}
                    </span>
                    .
                  </p>
                </article>
              );
            })}
            {!loadingCoins && results.length === 0 && !coinsError && (
              <p style={{ color: '#8E8E98', fontSize: 14 }}>No matches. Try bitcoin, ethereum, or solana.</p>
            )}
          </div>
        </div>
      </div>

      {/* Movable target — below toolbar */}
      <div
        ref={reticleRef}
        onPointerDown={(e) => {
          e.preventDefault();
          const rect = reticleRef.current?.getBoundingClientRect();
          if (!rect) return;
          dragOffset.current = { x: e.clientX - rect.left, y: e.clientY - rect.top };
          setDragging(true);
          (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
        }}
        className={`target-reticle ${locked ? 'target-reticle--locked' : ''} ${dragging ? 'target-reticle--dragging' : ''}`}
        style={{ left: pos.x, top: pos.y, zIndex: 95 }}
        title="Drag over a crypto name"
      >
        <div className="target-ring" />
        <div className="target-ring target-ring--inner" />
        <div className="target-crosshair-h" />
        <div className="target-crosshair-v" />
        <div className="target-dot" />
      </div>

      {/* Growth card */}
      {locked && (
        <div
          style={{
            position: 'fixed',
            zIndex: 96,
            width: 288,
            pointerEvents: 'none',
            left: Math.min(pos.x + 90, window.innerWidth - 300),
            top: Math.min(Math.max(pos.y, TOOLBAR_H + 8), window.innerHeight - 240),
          }}
        >
          <div
            style={{
              background: 'rgba(18,18,22,0.95)',
              backdropFilter: 'blur(12px)',
              border: '1px solid rgba(217,70,239,0.45)',
              borderRadius: 16,
              padding: 14,
              boxShadow: '0 0 28px rgba(217,70,239,0.35)',
              color: '#fff',
              fontFamily: 'ui-monospace, monospace',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#F0ABFC', marginBottom: 8 }}>
              <span style={{ fontWeight: 800, letterSpacing: '0.08em' }}>POTENTIAL GROWTH</span>
              <span style={{ color: '#8E8E98' }}>{locked.ticker}</span>
            </div>
            <div style={{ fontSize: 14, fontWeight: 800, marginBottom: 8 }}>{locked.name}</div>

            {loadingGrowth && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#8E8E98', padding: '12px 0' }}>
                <Loader2 size={14} className="animate-spin" /> Computing from live market data…
              </div>
            )}

            {!loadingGrowth && growth?.status === 'SUCCESS' && (
              <>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <BiasIcon size={16} color={(growthPct ?? 0) >= 0 ? '#F0ABFC' : '#F9A8D4'} />
                  <span style={{ fontSize: 28, fontWeight: 800, color: (growthPct ?? 0) >= 0 ? '#F0ABFC' : '#F9A8D4' }}>
                    {(growthPct ?? 0) >= 0 ? '+' : ''}
                    {growthPct?.toFixed(2)}%
                  </span>
                </div>
                <div style={{ fontSize: 10, color: '#8E8E98', marginBottom: 8 }}>
                  Bias: <span style={{ color: '#e2e8f0' }}>{growth.bias}</span> · Price: $
                  {growth.current_price?.toLocaleString(undefined, { maximumFractionDigits: 4 })}
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 6, fontSize: 10, marginBottom: 8 }}>
                  {(['7d_pct', '30d_pct', '90d_pct'] as const).map((k, i) => {
                    const labels = ['7D', '30D', '90D'];
                    const v = growth.returns?.[k];
                    return (
                      <div key={k} style={{ background: '#16161C', borderRadius: 8, padding: 8, textAlign: 'center' }}>
                        <div style={{ color: '#8E8E98' }}>{labels[i]}</div>
                        <div style={{ color: (v ?? 0) >= 0 ? '#F0ABFC' : '#F9A8D4', fontWeight: 700 }}>
                          {v ?? '—'}%
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div style={{ fontSize: 10, borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: 8 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                    <span style={{ color: '#D946EF' }}>UP</span>
                    <span>{growth.probabilities?.UP}%</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                    <span style={{ color: '#EC4899' }}>DOWN</span>
                    <span>{growth.probabilities?.DOWN}%</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#818CF8' }}>SIDEWAYS</span>
                    <span>{growth.probabilities?.SIDEWAYS}%</span>
                  </div>
                </div>
              </>
            )}

            {!loadingGrowth && growth && growth.status !== 'SUCCESS' && (
              <p style={{ fontSize: 12, color: '#F9A8D4', padding: '8px 0' }}>
                {growth.message || 'Unable to compute growth.'}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Extra floating stop — always reachable */}
      <button
        type="button"
        onClick={stop}
        onPointerDown={(e) => e.stopPropagation()}
        aria-label="Stop scanner"
        style={{
          position: 'fixed',
          right: 20,
          bottom: 24,
          zIndex: 210,
          width: 56,
          height: 56,
          borderRadius: 999,
          border: 'none',
          cursor: 'pointer',
          background: 'linear-gradient(135deg, #EC4899, #D946EF)',
          color: '#09090B',
          boxShadow: '0 0 28px rgba(217,70,239,0.55)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          pointerEvents: 'auto',
        }}
      >
        <X size={22} strokeWidth={3} />
      </button>
    </div>
  );
};
