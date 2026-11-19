import React, { useState } from 'react';
import type { XAIReport } from '../types';
import { Sparkles, Target, Users, Shield, Zap, ChevronDown, ChevronUp, BarChart3, Filter } from 'lucide-react';

interface ExplainableAIPanelProps {
  xai: XAIReport | null;
}

const SIGNAL_COLORS: Record<string, string> = {
  BULLISH: 'text-emerald-400',
  BEARISH: 'text-rose-400',
  OVERBOUGHT: 'text-amber-400',
  OVERSOLD: 'text-cyan-400',
  STRONG_UPTREND: 'text-emerald-300',
  STRONG_DOWNTREND: 'text-rose-300',
  RANGE_BOUND: 'text-blue-400',
  NEAR_UPPER_BAND: 'text-amber-300',
  NEAR_LOWER_BAND: 'text-cyan-300',
  HIGH_VOLATILITY: 'text-orange-400',
  NORMAL: 'text-slate-400',
  NEUTRAL: 'text-slate-500',
};

const TIER_STYLES: Record<string, { bg: string; border: string; text: string; glow: string }> = {
  HIGH: { bg: 'bg-emerald-950/40', border: 'border-emerald-500/50', text: 'text-emerald-400', glow: 'shadow-emerald-500/10' },
  MODERATE: { bg: 'bg-blue-950/40', border: 'border-blue-500/50', text: 'text-blue-400', glow: 'shadow-blue-500/10' },
  LOW: { bg: 'bg-amber-950/40', border: 'border-amber-500/50', text: 'text-amber-400', glow: 'shadow-amber-500/10' },
  VERY_LOW: { bg: 'bg-rose-950/40', border: 'border-rose-500/50', text: 'text-rose-400', glow: 'shadow-rose-500/10' },
};

export const ExplainableAIPanel: React.FC<ExplainableAIPanelProps> = ({ xai }) => {
  const [expandedSection, setExpandedSection] = useState<string | null>('confidence');

  if (!xai || xai.status !== 'SUCCESS') {
    return null;
  }

  const toggleSection = (section: string) => {
    setExpandedSection(expandedSection === section ? null : section);
  };

  const confidence = xai.confidence_assessment;
  const tierStyle = TIER_STYLES[confidence?.tier || 'LOW'] || TIER_STYLES.LOW;
  const agreement = xai.model_agreement;
  const featureSelection = xai.feature_selection;

  return (
    <div className="glass-panel p-4 flex flex-col gap-3 overflow-y-auto">
      {/* Header */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-tr from-violet-600 to-fuchsia-500 flex items-center justify-center shadow-lg shadow-violet-950/50">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <div>
            <div className="text-xs text-slate-400 tracking-wider">EXPLAINABLE AI</div>
            <div className="text-sm font-bold text-white">Model Transparency Engine</div>
          </div>
        </div>
        <span className="text-[10px] font-mono text-violet-400 bg-violet-950/60 px-2 py-0.5 rounded border border-violet-700/50">
          XAI v3.0
        </span>
      </div>

      {/* Confidence Assessment Card */}
      <button
        onClick={() => toggleSection('confidence')}
        className={`w-full text-left rounded-lg p-3 border transition-all shadow-md ${tierStyle.bg} ${tierStyle.border} ${tierStyle.glow}`}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield className={`w-4 h-4 ${tierStyle.text}`} />
            <span className="text-xs font-semibold text-slate-300">PREDICTION CONFIDENCE</span>
          </div>
          <div className="flex items-center gap-2">
            <span className={`text-lg font-extrabold font-mono ${tierStyle.text}`}>
              {confidence?.confidence_pct ?? 0}%
            </span>
            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${tierStyle.bg} ${tierStyle.text} border ${tierStyle.border}`}>
              {confidence?.tier}
            </span>
            {expandedSection === 'confidence' ? (
              <ChevronUp className="w-3.5 h-3.5 text-slate-500" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
            )}
          </div>
        </div>
        {expandedSection === 'confidence' && (
          <div className="mt-3 space-y-2 animate-in fade-in">
            <div className="text-[11px] text-slate-400 leading-relaxed">
              {confidence?.tier_description}
            </div>
            <div className="grid grid-cols-3 gap-2 mt-2">
              <div className="bg-slate-900/60 p-2 rounded text-center">
                <div className="text-[9px] text-slate-500 uppercase">Prob Margin</div>
                <div className="text-xs font-bold text-slate-200 font-mono">
                  {((confidence?.components?.probability_margin ?? 0) * 100).toFixed(1)}%
                </div>
              </div>
              <div className="bg-slate-900/60 p-2 rounded text-center">
                <div className="text-[9px] text-slate-500 uppercase">Agreement</div>
                <div className="text-xs font-bold text-slate-200 font-mono">
                  {((confidence?.components?.model_agreement ?? 0) * 100).toFixed(1)}%
                </div>
              </div>
              <div className="bg-slate-900/60 p-2 rounded text-center">
                <div className="text-[9px] text-slate-500 uppercase">Hist. Acc.</div>
                <div className="text-xs font-bold text-slate-200 font-mono">
                  {((confidence?.components?.historical_accuracy ?? 0) * 100).toFixed(1)}%
                </div>
              </div>
            </div>
          </div>
        )}
      </button>

      {/* Model Agreement */}
      <button
        onClick={() => toggleSection('agreement')}
        className="w-full text-left glass-card p-3 transition-all"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Users className="w-4 h-4 text-cyan-400" />
            <span className="text-xs font-semibold text-slate-300">MODEL AGREEMENT</span>
          </div>
          <div className="flex items-center gap-2">
            <span className={`text-sm font-bold font-mono ${agreement?.unanimous ? 'text-emerald-400' : 'text-amber-400'}`}>
              {agreement?.agreement_pct ?? 0}%
            </span>
            {agreement?.unanimous && (
              <span className="text-[9px] text-emerald-400 bg-emerald-950/50 px-1.5 py-0.5 rounded border border-emerald-700/40">
                UNANIMOUS
              </span>
            )}
            {expandedSection === 'agreement' ? (
              <ChevronUp className="w-3.5 h-3.5 text-slate-500" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
            )}
          </div>
        </div>
        {expandedSection === 'agreement' && (
          <div className="mt-3 space-y-2 animate-in fade-in">
            <div className="flex items-center gap-2 text-xs">
              <span className="text-slate-400">Majority:</span>
              <span className={`font-bold ${
                agreement?.majority_direction === 'UP' ? 'text-emerald-400' :
                agreement?.majority_direction === 'DOWN' ? 'text-rose-400' : 'text-blue-400'
              }`}>
                {agreement?.majority_direction}
              </span>
              <span className="text-slate-500 font-mono">
                ({agreement?.total_models} models)
              </span>
            </div>
            {agreement?.vote_distribution && (
              <div className="flex gap-1.5 mt-1">
                {Object.entries(agreement.vote_distribution).map(([dir, count]) => (
                  <div key={dir} className={`text-[10px] font-mono px-2 py-1 rounded ${
                    dir === 'UP' ? 'bg-emerald-950/50 text-emerald-400 border border-emerald-800/40' :
                    dir === 'DOWN' ? 'bg-rose-950/50 text-rose-400 border border-rose-800/40' :
                    'bg-blue-950/50 text-blue-400 border border-blue-800/40'
                  }`}>
                    {dir}: {count}
                  </div>
                ))}
              </div>
            )}
            {agreement?.dissenting_models && agreement.dissenting_models.length > 0 && (
              <div className="text-[10px] text-amber-400/80 mt-1">
                ⚠ Dissenters: {agreement.dissenting_models.join(', ')}
              </div>
            )}
          </div>
        )}
      </button>

      {/* Top Feature Drivers */}
      <button
        onClick={() => toggleSection('drivers')}
        className="w-full text-left glass-card p-3 transition-all"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-amber-400" />
            <span className="text-xs font-semibold text-slate-300">TOP PREDICTION DRIVERS</span>
          </div>
          {expandedSection === 'drivers' ? (
            <ChevronUp className="w-3.5 h-3.5 text-slate-500" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
          )}
        </div>
        {expandedSection === 'drivers' && xai.top_drivers && (
          <div className="mt-3 space-y-2 animate-in fade-in">
            {xai.top_drivers.map((driver, idx) => (
              <div key={driver.feature} className="flex items-center justify-between bg-slate-900/60 p-2 rounded">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-slate-600 font-mono w-4">#{idx + 1}</span>
                  <span className="text-xs font-mono text-slate-200">{driver.feature}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] font-bold ${SIGNAL_COLORS[driver.signal] || 'text-slate-500'}`}>
                    {driver.signal.replace(/_/g, ' ')}
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono">
                    {driver.importance_pct?.toFixed(1)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </button>

      {/* Feature Importance Chart */}
      <button
        onClick={() => toggleSection('importance')}
        className="w-full text-left glass-card p-3 transition-all"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-purple-400" />
            <span className="text-xs font-semibold text-slate-300">FEATURE IMPORTANCE</span>
          </div>
          {expandedSection === 'importance' ? (
            <ChevronUp className="w-3.5 h-3.5 text-slate-500" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
          )}
        </div>
        {expandedSection === 'importance' && xai.feature_importance?.aggregated && (
          <div className="mt-3 space-y-1.5 animate-in fade-in">
            {Object.entries(xai.feature_importance.aggregated)
              .slice(0, 10)
              .map(([feature, pct]) => (
                <div key={feature} className="space-y-0.5">
                  <div className="flex justify-between text-[10px] font-mono">
                    <span className="text-slate-300">{feature}</span>
                    <span className="text-purple-400">{pct.toFixed(1)}%</span>
                  </div>
                  <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                    <div
                      className="bg-gradient-to-r from-purple-600 to-fuchsia-500 h-full rounded-full transition-all duration-700"
                      style={{ width: `${Math.min(pct, 100)}%` }}
                    />
                  </div>
                </div>
              ))}
          </div>
        )}
      </button>

      {/* Lasso Feature Selection */}
      <button
        onClick={() => toggleSection('selection')}
        className="w-full text-left glass-card p-3 transition-all"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-teal-400" />
            <span className="text-xs font-semibold text-slate-300">L1 FEATURE SELECTION</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono text-teal-400">
              {featureSelection?.selected_count ?? 0}/{featureSelection?.total_features ?? 0} kept
            </span>
            {expandedSection === 'selection' ? (
              <ChevronUp className="w-3.5 h-3.5 text-slate-500" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
            )}
          </div>
        </div>
        {expandedSection === 'selection' && featureSelection && (
          <div className="mt-3 space-y-2 animate-in fade-in">
            <div className="flex items-center gap-2 text-[10px]">
              <span className="text-slate-400">Sparsity:</span>
              <span className="font-mono text-teal-400">{((featureSelection.sparsity_ratio ?? 0) * 100).toFixed(1)}%</span>
              <span className="text-slate-600">features eliminated by L1</span>
            </div>
            {featureSelection.selected?.length > 0 && (
              <div>
                <div className="text-[9px] text-emerald-500 uppercase mb-1 font-semibold">Selected (Non-Zero)</div>
                <div className="flex flex-wrap gap-1">
                  {featureSelection.selected.map((f: string) => (
                    <span key={f} className="text-[9px] font-mono bg-emerald-950/40 text-emerald-400 px-1.5 py-0.5 rounded border border-emerald-800/30">
                      {f}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {featureSelection.eliminated?.length > 0 && (
              <div>
                <div className="text-[9px] text-rose-500 uppercase mb-1 font-semibold">Eliminated (Zeroed)</div>
                <div className="flex flex-wrap gap-1">
                  {featureSelection.eliminated.map((f: string) => (
                    <span key={f} className="text-[9px] font-mono bg-rose-950/30 text-rose-400/70 px-1.5 py-0.5 rounded border border-rose-800/20 line-through">
                      {f}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </button>

      {/* Decision Rationale */}
      <button
        onClick={() => toggleSection('rationale')}
        className="w-full text-left glass-card p-3 border-violet-500/20 transition-all"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Target className="w-4 h-4 text-violet-400" />
            <span className="text-xs font-semibold text-slate-300">DECISION RATIONALE</span>
          </div>
          {expandedSection === 'rationale' ? (
            <ChevronUp className="w-3.5 h-3.5 text-slate-500" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
          )}
        </div>
        {expandedSection === 'rationale' && (
          <div className="mt-2 text-[11px] text-slate-300 leading-relaxed bg-slate-950/50 p-2.5 rounded border border-slate-800/50 whitespace-pre-line animate-in fade-in">
            {xai.decision_rationale}
          </div>
        )}
      </button>

      {/* Model Weights Footer */}
      <div className="flex items-center justify-between pt-2 border-t border-slate-800/60">
        <span className="text-[9px] text-slate-600 uppercase tracking-wider">Active Models: 6 (XGB • LSTM • Temporal • Ridge • Lasso • Baseline)</span>
      </div>
    </div>
  );
};
