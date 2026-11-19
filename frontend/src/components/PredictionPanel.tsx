import React, { useState } from 'react';
import type { AnalysisPayload } from '../types';
import { Brain, ShieldCheck, Activity, History, AlertTriangle, Layers, Clock } from 'lucide-react';

interface PredictionPanelProps {
  analysis: AnalysisPayload | null;
  loading: boolean;
  onPaperTradeLog: () => void;
}

export const PredictionPanel: React.FC<PredictionPanelProps> = ({ analysis, loading, onPaperTradeLog }) => {
  const [activeHorizon, setActiveHorizon] = useState<string>('15M');

  if (loading) {
    return (
      <div className="card flex flex-col items-center justify-center h-full text-center gap-3 min-h-[280px]">
        <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
        <div className="text-sm font-semibold text-slate-300">Executing Walk-Forward Ensemble…</div>
        <div className="text-xs text-slate-500">Fetching market data · Feature engineering · Training models</div>
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="card flex flex-col items-center justify-center h-full text-center text-slate-400 gap-2 min-h-[280px]">
        <Activity className="w-8 h-8 text-slate-600 animate-pulse" />
        <p className="text-sm">Select an asset to trigger live data-driven AI prediction.</p>
      </div>
    );
  }

  if (analysis.status === 'UNIDENTIFIED' || analysis.status === 'INSUFFICIENT_DATA') {
    return (
      <div className="card flex flex-col items-center justify-center h-full text-center gap-3 border-amber-500/40 bg-amber-950/10 min-h-[280px]">
        <AlertTriangle className="w-10 h-10 text-amber-400" />
        <h3 className="text-base font-bold text-amber-300">Prediction Paused</h3>
        <p className="text-xs text-slate-300 max-w-xs">{analysis.message}</p>
        <span className="text-[10px] text-amber-400/80 bg-amber-900/40 px-2.5 py-1 rounded-md border border-amber-700/50">
          STRICT SAFETY RULE ENFORCED
        </span>
      </div>
    );
  }

  const { probabilities, prediction_intervals, multi_horizons, market_regime, similarity, transparency_card, ai_explanation } = analysis;
  const horizonData = multi_horizons[activeHorizon] || { probabilities, prediction_intervals };
  const hIntervals = horizonData.prediction_intervals || prediction_intervals;

  return (
    <div className="card flex flex-col h-full gap-4 overflow-y-auto">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div>
          <div className="text-xs text-slate-400">Probabilistic Forecast</div>
          <div className="text-lg font-bold text-white flex items-center gap-2">
            {analysis.symbol}{' '}
            <span className="text-emerald-400 tabular-nums text-base">${analysis.current_price.toLocaleString()}</span>
          </div>
        </div>
        <button
          onClick={onPaperTradeLog}
          className="text-xs px-3 py-1.5 rounded-xl border border-slate-700 flex items-center gap-1 transition font-semibold"
          style={{ background: 'linear-gradient(90deg,#D946EF,#EC4899)', color: '#09090B', border: 'none' }}
        >
          Paper Trade
        </button>
      </div>

      <div className="flex items-center justify-between gap-1 bg-slate-900/80 p-1 rounded-lg border border-slate-800 text-[11px] font-mono">
        {['5M', '15M', '30M', '1H', '4H', '1D', '5D'].map((h) => (
          <button
            key={h}
            onClick={() => setActiveHorizon(h)}
            className={`flex-1 py-1 rounded-lg transition font-bold ${
              activeHorizon === h ? 'text-[#09090B] shadow glow-magenta' : 'text-slate-400 hover:text-white'
            }`}
            style={activeHorizon === h ? { background: 'linear-gradient(90deg,#D946EF,#EC4899)' } : undefined}
          >
            {h}
          </button>
        ))}
      </div>

      <div className="glass-card p-3 space-y-2.5">
        <div className="text-xs font-semibold text-slate-300 flex items-center justify-between">
          <span>DIRECTION PROBABILITIES ({activeHorizon})</span>
          <span className="text-[10px] text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded font-mono">CALIBRATED</span>
        </div>

        <div>
          <div className="flex justify-between text-xs font-mono mb-1">
            <span className="text-emerald-400 font-bold">UP</span>
            <span className="text-emerald-400 font-bold tabular-nums">{probabilities.UP}%</span>
          </div>
          <div className="progress-track">
            <div className="progress-fill transition-all duration-500" style={{ width: `${probabilities.UP}%` }} />
          </div>
        </div>

        <div>
          <div className="flex justify-between text-xs font-mono mb-1">
            <span className="text-rose-400 font-bold">DOWN</span>
            <span className="text-rose-400 font-bold tabular-nums">{probabilities.DOWN}%</span>
          </div>
          <div className="progress-track">
            <div className="progress-fill transition-all duration-500" style={{ width: `${probabilities.DOWN}%`, background: '#EC4899' }} />
          </div>
        </div>

        <div>
          <div className="flex justify-between text-xs font-mono mb-1">
            <span className="text-blue-400 font-bold">SIDEWAYS</span>
            <span className="text-blue-400 font-bold tabular-nums">{probabilities.SIDEWAYS}%</span>
          </div>
          <div className="progress-track">
            <div className="progress-fill transition-all duration-500" style={{ width: `${probabilities.SIDEWAYS}%`, background: '#818CF8' }} />
          </div>
        </div>
      </div>

      <div className="glass-card p-3 space-y-2">
        <div className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
          <Clock className="w-3.5 h-3.5 text-purple-400" /> PREDICTION INTERVALS ({activeHorizon})
        </div>
        <div className="grid grid-cols-3 gap-2 text-center font-mono">
          <div className="bg-slate-900/80 p-2 rounded border border-slate-800">
            <div className="text-[10px] text-slate-400">50% Interval</div>
            <div className="text-xs font-bold text-slate-200 mt-0.5">
              ${hIntervals.interval_50?.lower?.toLocaleString()} – ${hIntervals.interval_50?.upper?.toLocaleString()}
            </div>
          </div>
          <div className="bg-slate-900/80 p-2 rounded border border-slate-800">
            <div className="text-[10px] text-slate-400">80% Interval</div>
            <div className="text-xs font-bold text-purple-300 mt-0.5">
              ${hIntervals.interval_80?.lower?.toLocaleString()} – ${hIntervals.interval_80?.upper?.toLocaleString()}
            </div>
          </div>
          <div className="bg-slate-900/80 p-2 rounded border border-slate-800">
            <div className="text-[10px] text-slate-400">95% Interval</div>
            <div className="text-xs font-bold text-indigo-300 mt-0.5">
              ${hIntervals.interval_95?.lower?.toLocaleString()} – ${hIntervals.interval_95?.upper?.toLocaleString()}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div className="glass-card p-2.5">
          <div className="text-[10px] text-slate-400 flex items-center gap-1">
            <Layers className="w-3 h-3 text-cyan-400" /> MARKET REGIME
          </div>
          <div className="text-xs font-bold text-cyan-300 mt-1">{market_regime?.regime}</div>
          <div className="text-[10px] text-slate-400 mt-1 font-mono">ADX Trend: {market_regime?.trend_strength_adx}</div>
        </div>
        <div className="glass-card p-2.5">
          <div className="text-[10px] text-slate-400 flex items-center gap-1">
            <History className="w-3 h-3 text-amber-400" /> SIMILARITY MATCHES
          </div>
          <div className="text-xs font-bold text-amber-300 mt-1">{similarity?.similar_matches_found} Periods</div>
          <div className="text-[10px] text-emerald-400 mt-1 font-mono">{similarity?.positive_pct}% Positive Outcomes</div>
        </div>
      </div>

      <div className="glass-card p-3 space-y-2 border-emerald-500/20">
        <div className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
          <Brain className="w-4 h-4 text-emerald-400" /> QUANTITATIVE AI REASONING
        </div>
        <div className="text-xs text-slate-300 leading-relaxed font-sans bg-slate-950/60 p-2.5 rounded border border-slate-800/80 whitespace-pre-line">
          {ai_explanation}
        </div>
      </div>

      <div className="glass-card p-3 space-y-1.5 bg-slate-900/60 border border-slate-800 text-[11px]">
        <div className="text-slate-400 font-semibold flex items-center gap-1 mb-1">
          <ShieldCheck className="w-3.5 h-3.5 text-blue-400" /> DATA SOURCE TRANSPARENCY
        </div>
        <div className="flex justify-between text-slate-400 font-mono">
          <span>Data Provider:</span> <span className="text-slate-200">{transparency_card.data_source}</span>
        </div>
        <div className="flex justify-between text-slate-400 font-mono">
          <span>Historical Span:</span> <span className="text-slate-200">{transparency_card.historical_period} ({transparency_card.years_available} Yrs)</span>
        </div>
        <div className="flex justify-between text-slate-400 font-mono">
          <span>Observations:</span> <span className="text-slate-200">{transparency_card.observation_count?.toLocaleString()} candles</span>
        </div>
        <div className="flex justify-between text-slate-400 font-mono">
          <span>Validation:</span> <span className="text-slate-200">{transparency_card.validation_method}</span>
        </div>
      </div>
    </div>
  );
};
