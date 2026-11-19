import React from 'react';
import type { AnalysisPayload } from '../types';
import { X } from 'lucide-react';

interface OverlayProps {
  analysis: AnalysisPayload | null;
  onClose: () => void;
}

export const TransparentOverlay: React.FC<OverlayProps> = ({ analysis, onClose }) => {
  if (!analysis) return null;

  const { probabilities, prediction_intervals, market_regime, backtest } = analysis;
  const p15 = prediction_intervals.interval_80;

  return (
    <div className="fixed top-6 right-6 z-50 w-80 backdrop-blur-md rounded-2xl p-4 shadow-2xl text-slate-100 animate-pulse-slow font-mono" style={{ background: 'rgba(18,18,22,0.92)', border: '1px solid rgba(217,70,239,0.45)', boxShadow: '0 0 28px rgba(217,70,239,0.3)' }}>
      <div className="flex items-center justify-between pb-2 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full animate-ping" style={{ background: 'linear-gradient(90deg,#D946EF,#EC4899)' }}></span>
          <span className="font-bold text-xs tracking-wider" style={{ color: '#F0ABFC' }}>TRADEAI</span>
        </div>
        <button onClick={onClose} className="text-slate-400 hover:text-white">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="mt-3">
        <div className="text-sm font-extrabold text-white flex justify-between items-center">
          <span>{analysis.symbol}</span>
          <span className="text-emerald-400 font-bold">${analysis.current_price?.toLocaleString()}</span>
        </div>
      </div>

      <div className="my-3 space-y-1.5 text-xs bg-slate-900/80 p-2.5 rounded border border-slate-800">
        <div className="flex justify-between">
          <span className="text-emerald-400 font-bold">UP</span>
          <span className="font-bold text-emerald-400">{probabilities?.UP}%</span>
        </div>
        <div className="flex justify-between">
          <span className="text-rose-400 font-bold">DOWN</span>
          <span className="font-bold text-rose-400">{probabilities?.DOWN}%</span>
        </div>
        <div className="flex justify-between">
          <span className="text-blue-400 font-bold">SIDEWAYS</span>
          <span className="font-bold text-blue-400">{probabilities?.SIDEWAYS}%</span>
        </div>
      </div>

      <div className="text-[11px] mb-3">
        <span className="text-slate-400 block text-[10px]">15M PREDICTION INTERVAL (80%)</span>
        <span className="text-purple-300 font-bold text-xs">${p15?.lower?.toLocaleString()} – ${p15?.upper?.toLocaleString()}</span>
      </div>

      <div className="text-[11px] mb-3 bg-cyan-950/40 border border-cyan-800/50 p-2 rounded">
        <span className="text-cyan-400 font-semibold block text-[10px]">MARKET REGIME</span>
        <span className="text-slate-200">{market_regime?.regime}</span>
      </div>

      <div className="pt-2 border-t border-slate-800 text-[10px] text-slate-400 flex justify-between">
        <span>Accuracy: {backtest?.model_directional_accuracy}%</span>
        <span>Data: Live</span>
      </div>
    </div>
  );
};
