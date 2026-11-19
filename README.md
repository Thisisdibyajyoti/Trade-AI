# TradeAI — Data-Driven AI Trading Analysis Application

**TradeAI** (TradeLens AI) is a real, quantitative, data-driven financial analysis and prediction system built with **FastAPI, PyTorch, XGBoost, Scikit-Learn, React, TypeScript, Vite, and TradingView Lightweight Charts**.

> ⚠️ **CORE MANDATE**: **NEVER use random, hardcoded, fabricated, placeholder, or manually invented market predictions.** Every prediction, probability, price interval, and historical similarity score shown in TradeAI is computed dynamically from real historical and current market data using verified mathematical and machine learning models.

---

## 🌟 Key Features

1. **Asset Identification & Verification**
   - Supports Indian Equities & Indices (`RELIANCE`, `TCS`, `NIFTY 50`, `BANK NIFTY`), Crypto (`BTC/USDT`, `ETH/USDT`), and US Stocks (`AAPL`, `TSLA`, `NVDA`, `MSFT`, `SPY`).
   - If an asset cannot be identified, the system strictly pauses and displays: `"Unable to reliably identify the trading instrument. Please select the asset manually."`

2. **10-Year Real Historical Data Fetcher**
   - Fetches up to 10 years of historical OHLCV data using legitimate financial data feeds (`yfinance`, Binance public feeds).
   - Accurately reports dataset span (e.g. `7.8 years available`) and total candle count. Never pretends 10 years were analyzed if only 2 years are available.

3. **Data Quality Engine**
   - Audits missing candles, duplicate timestamps, invalid OHLC logic ($High < Low$, $High < Open$), extreme spikes, and zero volume.
   - Generates transparent Data Quality Audit summaries.

4. **Feature Engineering & Anti-Data Leakage**
   - Computes 20+ features: Returns, Log returns, Rolling Volatility, ATR(14), SMA(20,50,200), EMA(9,21), RSI(14), MACD, Bollinger Bands, VWAP, Stochastic Oscillator (%K,%D), ADX(14), CCI(20), RVOL, Breakout/Breakdown signals, Trend Strength.
   - Uses strict past-only indexing (`shift(1)`) to ensure zero future data leakage during training and validation.

5. **Multi-Model Machine Learning Ensemble**
   - **Model A**: XGBoost / Gradient Boosting for structured feature matrices.
   - **Model B**: PyTorch LSTM sequential deep neural network for sliding sequence windows.
   - **Model C**: Temporal Ridge Feature Network.
   - **Model D**: Statistical Baseline (Parametric return distribution + Random Walk drift).

6. **Out-of-Sample Walk-Forward Backtester**
   - Performs expanding/rolling walk-forward out-of-sample backtesting.
   - Calculates Directional Accuracy (%), Precision, Recall, F1 Score, Sharpe Ratio, Profit Factor, Max Drawdown (%).
   - Explicitly compares complex ML models against the Statistical Baseline benchmark.

7. **Probabilities & Prediction Price Intervals**
   - Calibrated direction probabilities (`UP %`, `DOWN %`, `SIDEWAYS %`).
   - 50%, 80%, and 95% Price Prediction Intervals ($Price_{latest} \pm z \cdot \sigma_{residual}$).
   - Multi-horizon forecasts (`5M`, `15M`, `30M`, `1H`, `4H`, `1D`, `5D`).

8. **Market Regime Detection & Historical Similarity Engine**
   - Classifies current market regime (e.g., *High-volatility Uptrend*, *Sideways Consolidation*).
   - Uses K-Nearest Neighbors (k-NN) vector distance search to find statistically similar historical market conditions (e.g., `438 matches found`) and tracks historical outcome distributions (Positive, Negative, Neutral).

9. **OpenAI Reasoning Layer**
   - Integrates with OpenAI API (`gpt-4o-mini`) to provide natural language market explanations strictly based on verified quantitative model outputs.
   - Forbidden from altering numerical predictions or probabilities.

10. **Transparent Desktop Overlay UI**
    - Floating translucent window view for desktop trading layout integration (`Tauri` ready).

10b. **Target Scanner (Run / Stop)**
    - Header **Run Target** / **Stop Target** control.
    - Shows a movable translucent crosshair over a Google-style crypto search surface.
    - Hover the target over a crypto name (Bitcoin, Ethereum, etc.) to load live **potential growth** from `/api/quick-growth`.

11. **Paper Trading & Feedback Engine**
    - Logs live paper trades, evaluates outcome upon price updates, and tracks empirical win rate, profit factor, and prediction error over time.

---

## 🛠️ Technology Stack

- **Backend**: Python 3.10+, FastAPI, Uvicorn, PyTorch, XGBoost, Scikit-Learn, Pandas, NumPy, SciPy, YFinance, WebSockets, OpenAI API.
- **Frontend**: React 19, TypeScript, Vite, Vanilla CSS glassmorphism styling, TradingView Lightweight Charts, Lucide React icons.
- **Desktop**: Tauri (Rust + Webview2 translucent overlay).
- **Mobile**: React Native entry setup (`mobile/App.tsx`).

---

## 📁 Project Architecture

```
trade-lens/ (Tradingapp/)
├── backend/
│   ├── api/             # FastAPI main app & REST/WS endpoints
│   ├── market_data/     # Symbol resolver & 10-Yr data fetcher
│   ├── preprocessing/   # Data Quality Engine & Audit cleaner
│   ├── features/        # Past-only Feature Engineering
│   ├── models/          # XGBoost, PyTorch LSTM, Temporal, Baseline
│   ├── backtesting/     # Out-of-sample Walk-Forward Backtester
│   ├── ensemble/        # Dynamic ensemble combiner
│   ├── prediction/      # Probability calibrator & Price intervals
│   ├── similarity/      # Regime Classifier & k-NN Similarity Engine
│   ├── risk/            # Paper Trading feedback engine
│   └── services/        # OpenAI reasoning & Screen analysis services
├── frontend/            # Vite + React + TypeScript Dashboard
│   ├── src/
│   │   ├── components/  # Chart, Watchlist, Prediction, Backtest, Overlay, Modals
│   │   ├── types.ts     # TypeScript interfaces
│   │   └── App.tsx      # Master dashboard
├── desktop/             # Tauri desktop overlay configuration
├── mobile/              # React Native mobile application structure
├── training/            # Offline pipeline scripts & dataset experimentation
└── docs/                # Architectural diagrams & specifications
```

---

## 🚀 How to Run the Application

### 1. Run the Python FastAPI Backend

Open a terminal in `d:\Projects\Tradingapp`:

```bash
# Start FastAPI backend server on port 8000
python -m uvicorn backend.api.main:app --reload --port 8000
```

The backend API will be live at `http://localhost:8000`. You can inspect the API docs at `http://localhost:8000/docs`.

### 2. Run the React Frontend Dashboard

Open a second terminal in `d:\Projects\Tradingapp\frontend`:

```bash
# Start Vite development server
npm run dev
```

Open your browser to `http://localhost:5173` to view the **TradeAI** dashboard.

### 3. Run everything with npm (from repo root)

```bash
npm run install:all
npm run dev
```

### 4. Deploy on Vercel

```bash
npm run build
vercel
```

`vercel.json` builds the Vite frontend and routes `/api/*` to the Python serverless function.

**Target Scanner:** click **Run Target** → drag the translucent reticle onto a crypto name in the search results → growth popup appears. Click **Stop Target** (or **Stop Scanner**) to exit.

---

## 📋 Build Order Summary

- [x] **PHASE 1**: Market-data acquisition
- [x] **PHASE 2**: 10-year historical data pipeline
- [x] **PHASE 3**: Data cleaning and quality audit
- [x] **PHASE 4**: Leak-free feature engineering
- [x] **PHASE 5**: Baseline statistical model (Model D)
- [x] **PHASE 6**: XGBoost model (Model A)
- [x] **PHASE 7**: PyTorch LSTM model (Model B)
- [x] **PHASE 8**: Walk-forward out-of-sample validation
- [x] **PHASE 9**: Dynamic ensemble model
- [x] **PHASE 10**: Probability calibration
- [x] **PHASE 11**: 50%, 80%, 95% prediction price intervals
- [x] **PHASE 12**: Market regime & historical similarity engine
- [x] **PHASE 13**: Live prediction API
- [x] **PHASE 14**: OpenAI reasoning layer
- [x] **PHASE 15**: TradingView Lightweight chart integration
- [x] **PHASE 16**: Translucent desktop overlay
- [x] **PHASE 17**: Paper trading evaluator feedback loop
- [x] **PHASE 18**: Performance monitoring & transparency cards
- [x] **PHASE 19**: Mobile application structure & setup
