import React, { useEffect, useState } from 'react';
import { X, Trophy } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE || '/api';

interface PaperTradingModalProps {
  onClose: () => void;
}

export const PaperTradingModal: React.FC<PaperTradingModalProps> = ({ onClose }) => {
  const [summary, setSummary] = useState<any>(null);

  useEffect(() => {
    fetch(`${API_BASE}/paper-trading/summary`)
      .then((res) => res.json())
      .then((data) => setSummary(data))
      .catch((err) => console.error(err));
  }, []);

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="glass-panel w-full max-w-2xl p-6 rounded-2xl flex flex-col gap-4 border border-emerald-500/30">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Trophy className="w-5 h-5 text-amber-400" />
            <h2 className="text-base font-bold text-slate-100">Paper Trading Performance Evaluator</h2>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        {summary ? (
          <div className="space-y-4">
            <div className="grid grid-cols-4 gap-3 text-center font-mono">
              <div className="bg-slate-900/80 p-3 rounded-xl border border-slate-800">
                <div className="text-[10px] text-slate-400">TOTAL TRADES</div>
                <div className="text-lg font-bold text-slate-200 mt-1">{summary.total_trades}</div>
              </div>
              <div className="bg-slate-900/80 p-3 rounded-xl border border-slate-800">
                <div className="text-[10px] text-slate-400">WIN RATE</div>
                <div className="text-lg font-bold text-emerald-400 mt-1">{summary.win_rate_pct}%</div>
              </div>
              <div className="bg-slate-900/80 p-3 rounded-xl border border-slate-800">
                <div className="text-[10px] text-slate-400">PROFIT FACTOR</div>
                <div className="text-lg font-bold text-amber-400 mt-1">{summary.profit_factor}</div>
              </div>
              <div className="bg-slate-900/80 p-3 rounded-xl border border-slate-800">
                <div className="text-[10px] text-slate-400">AVG ERROR</div>
                <div className="text-lg font-bold text-purple-300 mt-1">{summary.avg_prediction_error_pct}%</div>
              </div>
            </div>

            <div className="glass-card p-3 overflow-x-auto">
              <div className="text-xs font-semibold text-slate-300 mb-2">PAPER TRADES FEEDBACK LOG</div>
              {summary.trades_history && summary.trades_history.length > 0 ? (
                <table className="w-full text-left text-xs font-mono">
                  <thead>
                    <tr className="border-b border-slate-800 text-slate-500">
                      <th className="py-2">ID</th>
                      <th className="py-2">Asset</th>
                      <th className="py-2">Entry</th>
                      <th className="py-2">Predicted</th>
                      <th className="py-2">Status</th>
                      <th className="py-2">Outcome</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 text-slate-300">
                    {summary.trades_history.map((t: any) => (
                      <tr key={t.id}>
                        <td className="py-2 text-slate-400">{t.id}</td>
                        <td className="py-2 font-bold">{t.asset}</td>
                        <td className="py-2">${t.entry_price}</td>
                        <td className="py-2 text-emerald-400 font-bold">{t.predicted_direction}</td>
                        <td className="py-2">
                          <span className={`px-2 py-0.5 rounded text-[10px] ${t.status === 'OPEN' ? 'bg-amber-950 text-amber-400' : 'bg-slate-800 text-slate-300'}`}>
                            {t.status}
                          </span>
                        </td>
                        <td className="py-2 font-bold">
                          {t.outcome === 'WIN' && <span className="text-emerald-400">WIN ({t.actual_return_pct}%)</span>}
                          {t.outcome === 'LOSS' && <span className="text-rose-400">LOSS ({t.actual_return_pct}%)</span>}
                          {(!t.outcome || t.outcome === 'NEUTRAL') && <span className="text-slate-400">PENDING</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="text-center text-xs text-slate-500 py-6">No paper trades logged yet. Click "Paper Trade" on any prediction card.</div>
              )}
            </div>
          </div>
        ) : (
          <div className="text-center text-slate-400 py-10">Loading performance data...</div>
        )}
      </div>
    </div>
  );
};
