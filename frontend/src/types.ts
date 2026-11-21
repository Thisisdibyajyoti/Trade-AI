export interface WatchlistItem {
  symbol: string;
  name: string;
  category: string;
}

export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface ProbabilitySet {
  UP: number;
  DOWN: number;
  SIDEWAYS: number;
}

export interface PredictionInterval {
  interval_50: { lower: number; upper: number };
  interval_80: { lower: number; upper: number };
  interval_95: { lower: number; upper: number };
  residual_volatility_pct: number;
}

export interface HorizonForecast {
  horizon: string;
  probabilities: ProbabilitySet;
  prediction_intervals: PredictionInterval;
}

export interface SimilarityResult {
  status: string;
  similar_matches_found: number;
  positive_outcomes: number;
  negative_outcomes: number;
  neutral_outcomes: number;
  positive_pct: number;
  negative_pct: number;
  neutral_pct: number;
  avg_historical_return_pct: number;
}

export interface BacktestResult {
  status: string;
  validation_method: string;
  test_period: string;
  train_samples: number;
  test_samples: number;
  model_directional_accuracy: number;
  baseline_directional_accuracy: number;
  outperforms_baseline: boolean;
  precision: number;
  recall: number;
  f1_score: number;
  sharpe_ratio: number;
  profit_factor: number;
  max_drawdown_pct: number;
  last_training_date: string;
}

export interface MarketRegime {
  regime: string;
  trend_status: string;
  volatility_status: string;
  rsi: number;
  trend_strength_adx: number;
  volatility_ratio: number;
}

export interface TransparencyCard {
  asset: string;
  resolved_ticker: string;
  data_source: string;
  historical_period: string;
  years_available: number;
  observation_count: number;
  current_data_timestamp: string;
  model_version: string;
  validation_method: string;
}

export interface XAIFeatureImportance {
  aggregated: Record<string, number>;
  per_model: Record<string, Record<string, number> | null>;
  top_5: string[];
}

export interface XAIModelAgreement {
  agreement_score: number;
  agreement_pct: number;
  unanimous: boolean;
  majority_direction: string;
  vote_distribution: Record<string, number>;
  total_models: number;
  dissenting_models: string[];
}

export interface XAIConfidence {
  confidence_score: number;
  confidence_pct: number;
  tier: string;
  tier_description: string;
  components: {
    probability_margin: number;
    model_agreement: number;
    historical_accuracy: number;
  };
}

export interface XAITopDriver {
  feature: string;
  importance_pct: number;
  current_value: number | null;
  signal: string;
}

export interface XAIFeatureSelection {
  selected: string[];
  eliminated: string[];
  total_features: number;
  selected_count: number;
  eliminated_count: number;
  sparsity_ratio: number;
}

export interface XAIReport {
  status: string;
  feature_importance: XAIFeatureImportance;
  feature_selection: XAIFeatureSelection;
  model_agreement: XAIModelAgreement;
  prediction_decomposition: Record<string, any>;
  confidence_assessment: XAIConfidence;
  decision_rationale: string;
  top_drivers: XAITopDriver[];
}

export interface AnalysisPayload {
  status: string;
  message?: string;
  error_code?: string;
  symbol: string;
  current_price: number;
  timeframe: string;
  probabilities: ProbabilitySet;
  prediction_intervals: PredictionInterval;
  multi_horizons: Record<string, HorizonForecast>;
  market_regime: MarketRegime;
  similarity: SimilarityResult;
  backtest: BacktestResult;
  model_weights: Record<string, number>;
  xai: XAIReport;
  data_summary: any;
  transparency_card: TransparencyCard;
  ai_explanation: string;
  feed_status?: FeedStatus;
  disclaimer?: string;
}

/** Real feed freshness label reported by the backend live layer. */
export type FeedMode = 'LIVE' | 'DELAYED' | 'CLOSED' | 'STALE' | 'RECONNECTING' | 'CONNECTING';

export interface FeedStatus {
  symbol: string;
  asset_class?: string;
  mode: FeedMode;
  source: string;
  market_open: boolean;
  last_tick: number | null;
  last_price: number | null;
  age_seconds: number | null;
  latency_ms?: number | null;
  rejected_ticks?: number;
  message?: string;
  server_time: number;
}

export interface LiveCandle extends Candle {
  is_closed?: boolean;
}

/** A live coin row from the backend (CoinGecko-backed). */
export interface CryptoMarketCoin {
  id: string;
  name: string;
  symbol: string;
  ticker: string;
  trade_symbol: string;
  price: number | null;
  market_cap: number | null;
  rank: number | null;
  change_7d: number | null;
  change_30d: number | null;
  image?: string;
  as_of: number;
}
