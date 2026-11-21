import React, { useState, useEffect } from 'react';
import { Watchlist } from './components/Watchlist';
import { CandlestickChart } from './components/CandlestickChart';
import { PredictionPanel } from './components/PredictionPanel';
import { BacktestStats } from './components/BacktestStats';
import { TransparentOverlay } from './components/TransparentOverlay';
import { PaperTradingModal } from './components/PaperTradingModal';
import { ScreenVerifierModal } from './components/ScreenVerifierModal';
import { ExplainableAIPanel } from './components/ExplainableAIPanel';
import { TargetScanner } from './components/TargetScanner';
import { FeedStatusBadge } from './components/FeedStatusBadge';
import { useLiveFeed } from './hooks/useLiveFeed';
import type { WatchlistItem, AnalysisPayload } from './types';
import {
  Brain,
  Eye,
  Sliders,
  RefreshCw,
  Lock,
  Sparkles,
  Crosshair,
  Square,
  Search,
  Bell,
  Download,
  ChevronDown,
  LayoutDashboard,
  LineChart,
  Briefcase,
} from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE || '/api';

export const App: React.FC = () => {
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [activeSymbol, setActiveSymbol] = useState<string>('BTC/USDT');
  const [activeTimeframe, setActiveTimeframe] = useState<string>('1d');
  const [restAnalysis, setRestAnalysis] = useState<AnalysisPayload | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const [showOverlay, setShowOverlay] = useState<boolean>(false);
  const [showPaperTrading, setShowPaperTrading] = useState<boolean>(false);
  const [showScreenVerifier, setShowScreenVerifier] = useState<boolean>(false);
  const [showXAI, setShowXAI] = useState<boolean>(false);
  const [scannerRunning, setScannerRunning] = useState<boolean>(false);
  const [openaiKey, setOpenaiKey] = useState<string>('');
  const [headerSearch, setHeaderSearch] = useState('');

  // Live feed: real ticks, forming candle, feed status and candle-close predictions.
  const live = useLiveFeed(activeSymbol, activeTimeframe);
  const candles = live.candles;
  const analysis = live.analysis || restAnalysis;
  const feedStatus = live.status || analysis?.feed_status || null;
  const livePrice = live.price ?? analysis?.current_price ?? null;

  useEffect(() => {
    fetch(`${API_BASE}/watchlist`)
      .then((res) => res.json())
      .then((data) => setWatchlist(data))
      .catch((err) => console.error('Failed to load watchlist:', err));
  }, []);

  // On-demand full analysis (with CV model tuning). The live feed also produces
  // predictions automatically on every candle close, so this is only used when
  // the user explicitly refreshes.
  const runAnalysis = async (symbol: string, timeframe: string) => {
    setLoading(true);
    try {
      const analyzeRes = await fetch(`${API_BASE}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol,
          timeframe,
          openai_api_key: openaiKey || undefined,
        }),
      });
      const analyzeData = await analyzeRes.json();
      setRestAnalysis(analyzeData);
    } catch (err) {
      console.error('Analysis execution failed:', err);
    } finally {
      setLoading(false);
    }
  };

  // Clear the stale REST snapshot whenever the instrument/timeframe changes so
  // only the live feed's fresh prediction is shown.
  useEffect(() => {
    setRestAnalysis(null);
  }, [activeSymbol, activeTimeframe]);

  const handleSelectSymbol = (symbol: string) => {
    setActiveSymbol(symbol);
  };

  const handleLogPaperTrade = async () => {
    if (!analysis || livePrice == null) return;
    try {
      await fetch(`${API_BASE}/paper-trading/log`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: analysis.symbol,
          current_price: livePrice,
          probabilities: analysis.probabilities,
          prediction_interval: analysis.prediction_intervals,
        }),
      });
      setShowPaperTrading(true);
    } catch (err) {
      console.error(err);
    }
  };

  const upPct = analysis?.probabilities?.UP ?? 0;
  const downPct = analysis?.probabilities?.DOWN ?? 0;
  const sidePct = analysis?.probabilities?.SIDEWAYS ?? 0;
  const accuracy = analysis?.backtest?.model_directional_accuracy ?? 0;
  const sharpe = analysis?.backtest?.sharpe_ratio ?? 0;

  const filledDots = (pct: number, total = 20) => Math.round((pct / 100) * total);

  const donutStyle = {
    background: `conic-gradient(
      #D946EF 0% ${upPct}%,
      #EC4899 ${upPct}% ${upPct + downPct}%,
      #818CF8 ${upPct + downPct}% 100%
    )`,
  };

  return (
    <div className="app-shell">
      {/* Left sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="sidebar-logo-mark">
            <Brain className="w-5 h-5" color="#09090B" />
          </div>
          <div>
            <div className="sidebar-logo-text">TradeAI</div>
            <div className="sidebar-logo-sub">QUANT v2.1</div>
          </div>
        </div>

        <div className="nav-section-label">Main</div>
        <button
          className={`nav-item ${!scannerRunning && !showXAI && !showOverlay ? 'active' : ''}`}
          onClick={() => {
            setScannerRunning(false);
            setShowXAI(false);
            setShowOverlay(false);
          }}
        >
          <LayoutDashboard className="w-4 h-4" /> Analytics
        </button>
        <button
          className={`nav-item ${scannerRunning ? 'active' : ''}`}
          onClick={() => setScannerRunning((v) => !v)}
          type="button"
        >
          {scannerRunning ? <Square className="w-4 h-4" /> : <Crosshair className="w-4 h-4" />}
          {scannerRunning ? 'Stop Target' : 'Target Scanner'}
        </button>
        <button className={`nav-item ${showXAI ? 'active' : ''}`} onClick={() => setShowXAI((v) => !v)}>
          <Sparkles className="w-4 h-4" /> Explainable AI
        </button>
        <button className={`nav-item ${showOverlay ? 'active' : ''}`} onClick={() => setShowOverlay((v) => !v)}>
          <Sliders className="w-4 h-4" /> Desktop Overlay
        </button>

        <div className="nav-section-label">Workstation</div>
        <button className="nav-item" onClick={() => setShowScreenVerifier(true)}>
          <Eye className="w-4 h-4" /> Screen Audit
        </button>
        <button className="nav-item" onClick={() => void handleLogPaperTrade()}>
          <Briefcase className="w-4 h-4" /> Paper Trading
        </button>
        <button
          className="nav-item"
          onClick={() => runAnalysis(activeSymbol, activeTimeframe)}
          disabled={loading}
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Refresh Models
        </button>

        <div className="nav-section-label">Watchlist</div>
        <div className="sidebar-watch">
          <Watchlist items={watchlist} activeSymbol={activeSymbol} onSelectSymbol={handleSelectSymbol} compact />
        </div>
      </aside>

      {/* Main column */}
      <div className="main-column">
        <header className="top-header">
          <div className="search-input">
            <Search className="w-4 h-4" color="#8E8E98" />
            <input
              value={headerSearch}
              onChange={(e) => setHeaderSearch(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && headerSearch.trim()) {
                  handleSelectSymbol(headerSearch.trim().toUpperCase());
                  setHeaderSearch('');
                }
              }}
              placeholder="Search ticker, asset, or crypto…"
            />
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden lg:flex items-center gap-2 card" style={{ padding: '0.4rem 0.75rem' }}>
              <Lock className="w-3 h-3" color="#8E8E98" />
              <input
                type="password"
                placeholder="OpenAI key (optional)"
                value={openaiKey}
                onChange={(e) => setOpenaiKey(e.target.value)}
                className="bg-transparent text-xs text-slate-200 placeholder-slate-600 focus:outline-none w-36"
                style={{ border: 'none', outline: 'none', background: 'transparent', color: '#fff', fontSize: '0.75rem', width: '9rem' }}
              />
            </div>
            <button className="icon-btn" type="button" aria-label="Notifications">
              <Bell className="w-4 h-4" />
            </button>
            <div className="profile-chip">
              <div className="profile-avatar">TA</div>
              <div className="hidden lg:flex flex-col">
                <div className="profile-name">Trade Analyst</div>
                <div className="profile-email">quant@tradeai.app</div>
              </div>
            </div>
          </div>
        </header>

        <main className="content-area">
          <div className="page-header">
            <div>
              <h1 className="page-title">Analytics</h1>
              <p className="text-xs text-slate-400 mt-1">
                Data-driven probabilistic forecast · {activeSymbol}
              </p>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              {['1m', '5m', '15m', '30m', '1h', '4h', '1d'].map((tf) => (
                <button
                  key={tf}
                  type="button"
                  className={`filter-pill ${activeTimeframe === tf ? 'active' : ''}`}
                  onClick={() => setActiveTimeframe(tf)}
                >
                  {tf.toUpperCase()}
                </button>
              ))}
              <button type="button" className="filter-pill">
                Filters <ChevronDown className="w-3 h-3" />
              </button>
              <button type="button" className="icon-btn" aria-label="Export">
                <Download className="w-4 h-4" />
              </button>
            </div>
          </div>

          {live.error && (
            <div
              className="card mb-4"
              style={{ borderColor: 'rgba(239,68,68,0.4)', background: 'rgba(239,68,68,0.08)' }}
            >
              <div className="text-xs" style={{ color: '#F87171' }}>
                {live.error}
              </div>
            </div>
          )}
          {analysis?.status && analysis.status !== 'SUCCESS' && (
            <div
              className="card mb-4"
              style={{ borderColor: 'rgba(245,158,11,0.4)', background: 'rgba(245,158,11,0.08)' }}
            >
              <div className="text-xs" style={{ color: '#FBBF24' }}>
                {analysis.message || 'Prediction unavailable for this asset/timeframe.'}
              </div>
            </div>
          )}

          <div className="bento-grid">
            {/* Hero analytics card */}
            <div className="card card-hero col-span-12 lg:col-span-7">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <LineChart className="w-4 h-4" color="#F0ABFC" />
                  <span className="text-sm font-semibold">Market Pulse</span>
                </div>
                <span className="pct-badge up tabular-nums">{activeTimeframe.toUpperCase()}</span>
              </div>

              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <div className="kpi-label">Spot Price</div>
                  <div className="kpi-value tabular-nums">
                    {livePrice != null
                      ? `$${livePrice.toLocaleString(undefined, { maximumFractionDigits: 2 })}`
                      : loading
                        ? '…'
                        : '—'}
                  </div>
                  <div className="mt-2 flex items-center gap-2 flex-wrap">
                    <span className={`pct-badge ${(upPct >= downPct ? 'up' : 'down')} tabular-nums`}>
                      UP {upPct}%
                    </span>
                    <FeedStatusBadge status={feedStatus} showSource compact />
                  </div>
                </div>
                <div>
                  <div className="kpi-label">Model Accuracy</div>
                  <div className="kpi-value tabular-nums">{accuracy ? `${accuracy}%` : '—'}</div>
                  <div className="mt-2">
                    <span className="pct-badge up tabular-nums">Sharpe {sharpe || '—'}</span>
                  </div>
                </div>
              </div>

              <CandlestickChart
                candles={candles}
                forming={live.forming}
                symbol={activeSymbol}
                feedStatus={feedStatus}
              />
            </div>

            {/* Secondary metric stack */}
            <div className="col-span-12 lg:col-span-5 flex flex-col gap-5">
              <div className="card">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-semibold">Direction Confidence</span>
                  <span className="text-xs text-slate-400 tabular-nums">{upPct}% bullish</span>
                </div>
                <div className="mb-3">
                  <div className="flex justify-between text-xs mb-1.5">
                    <span className="text-slate-400">UP signal matrix</span>
                    <span className="tabular-nums text-slate-200">{upPct}%</span>
                  </div>
                  <div className="dot-matrix">
                    {Array.from({ length: 20 }).map((_, i) => (
                      <span key={`u-${i}`} className={`dot ${i < filledDots(upPct) ? 'filled' : ''}`} />
                    ))}
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-xs mb-1.5">
                    <span className="text-slate-400">DOWN signal matrix</span>
                    <span className="tabular-nums text-slate-200">{downPct}%</span>
                  </div>
                  <div className="dot-matrix">
                    {Array.from({ length: 20 }).map((_, i) => (
                      <span key={`d-${i}`} className={`dot ${i < filledDots(downPct) ? 'filled-alt' : ''}`} />
                    ))}
                  </div>
                </div>
              </div>

              <div className="card flex items-center gap-5">
                <div
                  className="donut-wrap"
                  style={{
                    borderRadius: '9999px',
                    padding: 8,
                    ...donutStyle,
                  }}
                >
                  <div
                    style={{
                      width: '100%',
                      height: '100%',
                      borderRadius: '9999px',
                      backgroundColor: '#121216',
                    }}
                  />
                  <div className="donut-center">
                    <div className="text-xs text-slate-400">Total</div>
                    <div className="text-lg font-extrabold tabular-nums">100%</div>
                  </div>
                </div>
                <div className="flex-1 space-y-2.5">
                  <div className="text-sm font-semibold mb-1">Probability Mix</div>
                  {[
                    { label: 'UP', value: upPct, color: '#D946EF' },
                    { label: 'DOWN', value: downPct, color: '#EC4899' },
                    { label: 'SIDEWAYS', value: sidePct, color: '#818CF8' },
                  ].map((row) => (
                    <div key={row.label}>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="flex items-center gap-1.5 text-slate-400">
                          <span style={{ width: 8, height: 8, borderRadius: 99, background: row.color }} />
                          {row.label}
                        </span>
                        <span className="tabular-nums font-semibold">{row.value}%</span>
                      </div>
                      <div className="progress-track">
                        <div className="progress-fill" style={{ width: `${row.value}%`, background: row.color }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Bottom row */}
            <div className="col-span-12 lg:col-span-6">
              <BacktestStats backtest={analysis?.backtest || null} />
            </div>
            <div className="col-span-12 lg:col-span-6 flex flex-col gap-5">
              <PredictionPanel analysis={analysis} loading={loading} onPaperTradeLog={handleLogPaperTrade} />
              {showXAI && analysis?.xai && <ExplainableAIPanel xai={analysis.xai} />}
            </div>
          </div>
        </main>
      </div>

      {showOverlay && <TransparentOverlay analysis={analysis} onClose={() => setShowOverlay(false)} />}
      {showPaperTrading && <PaperTradingModal onClose={() => setShowPaperTrading(false)} />}
      {showScreenVerifier && (
        <ScreenVerifierModal
          currentSymbol={activeSymbol}
          currentApiPrice={livePrice ?? 0}
          onClose={() => setShowScreenVerifier(false)}
        />
      )}
      <TargetScanner
        active={scannerRunning}
        onStop={() => {
          setScannerRunning(false);
        }}
      />
    </div>
  );
};

export default App;
