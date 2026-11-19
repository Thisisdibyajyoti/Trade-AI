import React, { useState } from 'react';
import type { WatchlistItem } from '../types';
import { Search, TrendingUp, Cpu, Coins, BarChart2 } from 'lucide-react';

interface WatchlistProps {
  items: WatchlistItem[];
  activeSymbol: string;
  onSelectSymbol: (symbol: string) => void;
  compact?: boolean;
}

export const Watchlist: React.FC<WatchlistProps> = ({ items, activeSymbol, onSelectSymbol, compact }) => {
  const [search, setSearch] = useState('');
  const [customInput, setCustomInput] = useState('');

  const filtered = items.filter(
    (item) =>
      item.symbol.toLowerCase().includes(search.toLowerCase()) ||
      item.name.toLowerCase().includes(search.toLowerCase())
  );

  const handleCustomSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (customInput.trim()) {
      onSelectSymbol(customInput.trim().toUpperCase());
      setCustomInput('');
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'Crypto':
        return <Coins className="w-3.5 h-3.5" color={activeSymbol ? '#F0ABFC' : '#8E8E98'} />;
      case 'Indian Stock':
      case 'US Stock':
        return <TrendingUp className="w-3.5 h-3.5" color="#E879F9" />;
      case 'Index':
        return <BarChart2 className="w-3.5 h-3.5" color="#A5B4FC" />;
      default:
        return <Cpu className="w-3.5 h-3.5" color="#8E8E98" />;
    }
  };

  return (
    <div className={`flex flex-col gap-2 ${compact ? 'h-full' : 'glass-panel p-4 h-full gap-3'}`}>
      {!compact && (
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-200 tracking-wide uppercase flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-emerald-400" /> Watchlist
          </h2>
          <span className="text-xs text-slate-400 bg-slate-800 px-2 py-0.5 rounded-full">{items.length}</span>
        </div>
      )}

      <div className="relative">
        <Search className="w-3.5 h-3.5 absolute left-3 top-2.5" color="#8E8E98" />
        <input
          type="text"
          placeholder="Filter…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full bg-slate-900/90 border border-slate-700/60 rounded-xl pl-9 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500"
        />
      </div>

      <form onSubmit={handleCustomSubmit} className="flex gap-2">
        <input
          type="text"
          placeholder="Ticker…"
          value={customInput}
          onChange={(e) => setCustomInput(e.target.value)}
          className="flex-1 bg-slate-900/90 border border-slate-700/60 rounded-xl px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500 uppercase"
        />
        <button
          type="submit"
          className="text-xs px-3 py-1.5 rounded-xl font-bold transition"
          style={{ background: 'linear-gradient(90deg, #D946EF, #EC4899)', color: '#09090B' }}
        >
          Load
        </button>
      </form>

      <div className="flex-1 overflow-y-auto space-y-1 pr-1">
        {filtered.map((item) => {
          const isActive = item.symbol === activeSymbol;
          return (
            <button
              key={item.symbol}
              type="button"
              onClick={() => onSelectSymbol(item.symbol)}
              className={`watch-item ${isActive ? 'active' : ''}`}
            >
              <div className="flex items-center gap-2">
                {getCategoryIcon(item.category)}
                <div>
                  <div className="font-bold text-xs">{item.symbol}</div>
                  <div className={`text-[10px] watch-sub ${isActive ? '' : 'text-slate-400'}`}>{item.name}</div>
                </div>
              </div>
              {!compact && (
                <span className={`text-[10px] px-2 py-0.5 rounded-full watch-cat ${isActive ? '' : 'bg-slate-800 text-slate-400'}`}>
                  {item.category}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
};
