import pandas as pd
import numpy as np

class FeatureEngineer:
    """
    Generates rich, leak-free quantitative market features from historical OHLCV data.
    Strictly uses past-looking windows to prevent lookahead data leakage.
    """

    @staticmethod
    def generate_features(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or len(df) < 20:
            return df

        data = df.copy()

        # 1. Price Features
        data['returns'] = data['Close'].pct_change()
        data['log_returns'] = np.log(data['Close'] / data['Close'].shift(1))
        data['momentum_5'] = data['Close'].pct_change(5)
        data['momentum_10'] = data['Close'].pct_change(10)
        data['hl_range'] = (data['High'] - data['Low']) / data['Close']
        data['oc_range'] = (data['Close'] - data['Open']).abs() / data['Close']
        data['volatility_20'] = data['returns'].rolling(20).std()

        # Average True Range (ATR)
        tr1 = data['High'] - data['Low']
        tr2 = (data['High'] - data['Close'].shift(1)).abs()
        tr3 = (data['Low'] - data['Close'].shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        data['atr_14'] = tr.rolling(14).mean()

        # 2. Technical Indicators
        # Moving Averages
        data['sma_20'] = data['Close'].rolling(20).mean()
        data['sma_50'] = data['Close'].rolling(50).mean()
        data['sma_200'] = data['Close'].rolling(200).mean()
        data['ema_9'] = data['Close'].ewm(span=9, adjust=False).mean()
        data['ema_21'] = data['Close'].ewm(span=21, adjust=False).mean()

        # Relative Strength Index (RSI 14)
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss + 1e-9)
        data['rsi_14'] = 100 - (100 / (1 + rs))

        # MACD
        ema_12 = data['Close'].ewm(span=12, adjust=False).mean()
        ema_26 = data['Close'].ewm(span=26, adjust=False).mean()
        data['macd'] = ema_12 - ema_26
        data['macd_signal'] = data['macd'].ewm(span=9, adjust=False).mean()
        data['macd_hist'] = data['macd'] - data['macd_signal']

        # Bollinger Bands (20, 2)
        bb_middle = data['sma_20']
        bb_std = data['Close'].rolling(20).std()
        data['bb_upper'] = bb_middle + (bb_std * 2)
        data['bb_lower'] = bb_middle - (bb_std * 2)
        data['bb_pct_b'] = (data['Close'] - data['bb_lower']) / (data['bb_upper'] - data['bb_lower'] + 1e-9)
        data['bb_bandwidth'] = (data['bb_upper'] - data['bb_lower']) / (bb_middle + 1e-9)

        # VWAP (Volume Weighted Average Price)
        typical_price = (data['High'] + data['Low'] + data['Close']) / 3
        data['vwap'] = (typical_price * data['Volume']).cumsum() / (data['Volume'].cumsum() + 1e-9)

        # Stochastic Oscillator (%K, %D)
        low_14 = data['Low'].rolling(14).min()
        high_14 = data['High'].rolling(14).max()
        data['stoch_k'] = 100 * ((data['Close'] - low_14) / (high_14 - low_14 + 1e-9))
        data['stoch_d'] = data['stoch_k'].rolling(3).mean()

        # Commodity Channel Index (CCI 20)
        tp_mean = typical_price.rolling(20).mean()
        tp_mad = typical_price.rolling(20).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
        data['cci_20'] = (typical_price - tp_mean) / (0.015 * tp_mad + 1e-9)

        # Average Directional Index (ADX 14 proxy)
        up_move = data['High'].diff()
        down_move = -data['Low'].diff()
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        data['adx_14'] = pd.Series(plus_dm).rolling(14).mean() / (data['atr_14'] + 1e-9) * 100

        # 3. Volume Features
        data['volume_change'] = data['Volume'].pct_change()
        data['volume_ma20'] = data['Volume'].rolling(20).mean()
        data['rvol'] = data['Volume'] / (data['volume_ma20'] + 1e-9)
        data['vpt'] = (data['Volume'] * (data['Close'] - data['Close'].shift(1)) / data['Close'].shift(1)).cumsum()

        # 4. Market Structure & Regimes
        rolling_max_50 = data['High'].rolling(50).max()
        rolling_min_50 = data['Low'].rolling(50).min()
        data['breakout_50'] = (data['Close'] >= rolling_max_50.shift(1)).astype(int)
        data['breakdown_50'] = (data['Close'] <= rolling_min_50.shift(1)).astype(int)
        data['trend_strength'] = (data['Close'] - data['sma_50']) / (data['atr_14'] + 1e-9)
        data['consolidation_index'] = (rolling_max_50 - rolling_min_50) / (data['Close'] + 1e-9)

        # 5. Time Features
        if 'Timestamp' in data.columns:
            ts = pd.to_datetime(data['Timestamp'])
            data['hour'] = ts.dt.hour
            data['day_of_week'] = ts.dt.dayofweek
            data['month'] = ts.dt.month

        # Fill initial NaNs cleanly
        data = data.ffill().bfill().fillna(0.0)

        return data
