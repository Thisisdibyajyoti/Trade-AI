import React, { useState } from 'react';
import { X, Eye, ShieldAlert, CheckCircle2 } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE || '/api';

interface ScreenVerifierProps {
  currentSymbol: string;
  currentApiPrice: number;
  onClose: () => void;
}

export const ScreenVerifierModal: React.FC<ScreenVerifierProps> = ({ currentSymbol, currentApiPrice, onClose }) => {
  const [screenPrice, setScreenPrice] = useState<string>(currentApiPrice.toString());
  const [result, setResult] = useState<any>(null);

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE}/verify-screen`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          screen_symbol: currentSymbol,
          screen_price: parseFloat(screenPrice),
          api_price: currentApiPrice,
        }),
      });
      const data = await res.json();
      setResult(data);
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="glass-panel w-full max-w-md p-6 rounded-2xl flex flex-col gap-4 border border-cyan-500/30">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Eye className="w-5 h-5 text-cyan-400" />
            <h2 className="text-base font-bold text-slate-100">Screen Vision / Price Feed Audit</h2>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleVerify} className="space-y-3 font-mono">
          <div>
            <label className="text-xs text-slate-400 block mb-1">Target Symbol</label>
            <input type="text" value={currentSymbol} disabled className="w-full bg-slate-900 border border-slate-800 rounded p-2 text-xs text-slate-300" />
          </div>
          <div>
            <label className="text-xs text-slate-400 block mb-1">Verified API Price</label>
            <input type="text" value={`$${currentApiPrice}`} disabled className="w-full bg-slate-900 border border-slate-800 rounded p-2 text-xs text-emerald-400 font-bold" />
          </div>
          <div>
            <label className="text-xs text-slate-400 block mb-1">Screen / Trading View Displayed Price</label>
            <input
              type="number"
              step="0.01"
              value={screenPrice}
              onChange={(e) => setScreenPrice(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-xs text-white focus:border-cyan-500"
            />
          </div>
          <button type="submit" className="w-full bg-cyan-600 hover:bg-cyan-500 text-white font-sans text-xs py-2.5 rounded-lg font-bold transition">
            Run Mismatch Audit
          </button>
        </form>

        {result && (
          <div className={`p-3 rounded-lg border text-xs font-mono space-y-1 ${result.mismatch_detected ? 'bg-rose-950/40 border-rose-500/50 text-rose-300' : 'bg-emerald-950/40 border-emerald-500/50 text-emerald-300'}`}>
            <div className="font-bold flex items-center gap-1.5">
              {result.mismatch_detected ? <ShieldAlert className="w-4 h-4 text-rose-400" /> : <CheckCircle2 className="w-4 h-4 text-emerald-400" />}
              {result.mismatch_detected ? 'PRICE MISMATCH DETECTED' : 'SYNCHRONIZED'}
            </div>
            <p>{result.message}</p>
          </div>
        )}
      </div>
    </div>
  );
};
