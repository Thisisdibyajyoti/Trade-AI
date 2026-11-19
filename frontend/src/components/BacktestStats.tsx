import React from 'react';
import type { BacktestResult } from '../types';
import { CheckCircle2, AlertCircle, BarChart3 } from 'lucide-react';

interface BacktestProps {
  backtest: BacktestResult | null;
}

export const BacktestStats: React.FC<BacktestProps> = ({ backtest }) => {
  if (!backtest || backtest.status !== 'SUCCESS') {
    return null;
  }

  const isBetter = backtest.outperforms_baseline;

  return (
    <div className="card flex flex-col gap-4 h-full">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold tracking-wide flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-emerald-400" /> Walk-Forward Validation
        </h3>
        <span className="text-xs text-slate-400 font-mono bg-slate-900 px-2.5 py-1 rounded-full border border-slate-800 tabular-nums">
          {backtest.test_period}
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className={`p-3 rounded-2xl border ${isBetter ? 'bg-emerald-950/20 border-emerald-500/40' : 'bg-slate-900/60 border-slate-800'}`}>
          <div className="text-[11px] text-slate-400 uppercase font-semibold">Model Accuracy</div>
          <div className="text-xl font-extrabold text-emerald-400 tabular-nums mt-1">
            {backtest.model_directional_accuracy}%
          </div>
          <div className="text-[10px] text-slate-400 mt-1 flex items-center gap-1 font-mono">
            {isBetter ? (
              <span className="text-emerald-400 flex items-center gap-0.5">
                <CheckCircle2 className="w-3 h-3" /> Beats Baseline ({backtest.baseline_directional_accuracy}%)
              </span>
            ) : (
              <span className="text-rose-400 flex items-center gap-0.5">
                <AlertCircle className="w-3 h-3" /> Below Baseline ({backtest.baseline_directional_accuracy}%)
              </span>
            )}
          </div>
        </div>

        <div className="p-3 rounded-2xl bg-slate-900/60 border border-slate-800">
          <div className="text-[11px] text-slate-400 uppercase font-semibold">Baseline</div>
          <div className="text-xl font-extrabold text-slate-300 tabular-nums mt-1">
            {backtest.baseline_directional_accuracy}%
          </div>
          <div className="text-[10px] text-slate-500 mt-1">Random Walk</div>
        </div>

        <div className="p-3 rounded-2xl bg-slate-900/60 border border-slate-800">
          <div className="text-[11px] text-slate-400 uppercase font-semibold">Sharpe</div>
          <div className="text-xl font-extrabold text-purple-400 tabular-nums mt-1">
            {backtest.sharpe_ratio}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Risk-Adjusted</div>
        </div>

        <div className="p-3 rounded-2xl bg-slate-900/60 border border-slate-800">
          <div className="text-[11px] text-slate-400 uppercase font-semibold">Profit Factor</div>
          <div className="text-xl font-extrabold text-amber-400 tabular-nums mt-1">
            {backtest.profit_factor}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Gains / Losses</div>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-2 text-center text-xs bg-slate-900/40 p-3 rounded-2xl border border-slate-800/80">
        {([
          { label: 'PRECISION', value: `${backtest.precision}%`, danger: false },
          { label: 'RECALL', value: `${backtest.recall}%`, danger: false },
          { label: 'F1', value: `${backtest.f1_score}%`, danger: false },
          { label: 'MAX DD', value: `${backtest.max_drawdown_pct}%`, danger: true },
        ] as const).map((m) => (
          <div key={m.label}>
            <div className="flex justify-between mb-1">
              <span className="text-slate-400 text-[10px] block w-full text-center">{m.label}</span>
            </div>
            <div className="progress-track mb-1">
              <div
                className="progress-fill"
                style={{
                  width: `${Math.min(100, Math.abs(Number(String(m.value).replace('%', ''))))}%`,
                  background: m.danger ? '#EC4899' : undefined,
                }}
              />
            </div>
            <span className={`font-bold tabular-nums ${m.danger ? 'text-rose-400' : 'text-slate-200'}`}>{m.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
};
