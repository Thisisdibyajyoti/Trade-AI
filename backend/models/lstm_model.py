import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import pandas as pd
import logging

logger = logging.getLogger("lstm_model")

class PyTorchLSTMNet(nn.Module):
    def __init__(self, input_size: int, hidden_size: int = 32, num_classes: int = 3):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers=1, batch_first=True)
        self.fc = nn.Linear(hidden_size, num_classes)
        self.softmax = nn.Softmax(dim=1)

    def forward(self, x):
        out, _ = self.lstm(x)
        out = out[:, -1, :] # Take last sequence step
        logits = self.fc(out)
        return self.softmax(logits)

class LSTMModel:
    """
    Model B: PyTorch LSTM for sequential time-series patterns.
    Trained on sliding windows of past feature sequences.
    """

    def __init__(self, seq_len: int = 10):
        self.seq_len = seq_len
        self.model = None
        self.trained = False
        self.feature_cols = []
        self.mean = None
        self.std = None

    def fit(self, df: pd.DataFrame, feature_cols: list, horizon_candles: int = 1):
        target_df = df.copy()
        future_return = target_df['Close'].shift(-horizon_candles) / target_df['Close'] - 1.0
        threshold = 0.25 * target_df['returns'].rolling(20).std().shift(-horizon_candles).fillna(0.005)
        
        target_df['target'] = 1 # SIDEWAYS
        target_df.loc[future_return > threshold, 'target'] = 2 # UP
        target_df.loc[future_return < -threshold, 'target'] = 0 # DOWN
        
        df_clean = target_df.dropna(subset=feature_cols + ['target'])
        if len(df_clean) < self.seq_len + 30:
            return False

        self.feature_cols = feature_cols
        X_raw = df_clean[feature_cols].values
        y_raw = df_clean['target'].values
        
        # Standardize features
        self.mean = np.mean(X_raw, axis=0)
        self.std = np.std(X_raw, axis=0) + 1e-6
        X_norm = (X_raw - self.mean) / self.std

        X_seq, y_seq = [], []
        for i in range(len(X_norm) - self.seq_len - horizon_candles):
            X_seq.append(X_norm[i : i + self.seq_len])
            y_seq.append(y_raw[i + self.seq_len])

        if len(X_seq) < 20:
            return False

        X_tensor = torch.tensor(np.array(X_seq), dtype=torch.float32)
        y_tensor = torch.tensor(np.array(y_seq), dtype=torch.long)

        self.model = PyTorchLSTMNet(input_size=len(feature_cols))
        criterion = nn.CrossEntropyLoss()
        optimizer = optim.Adam(self.model.parameters(), lr=0.01)

        self.model.train()
        for epoch in range(15): # Fast online epoch count
            optimizer.zero_grad()
            outputs = self.model(X_tensor)
            loss = criterion(outputs, y_tensor)
            loss.backward()
            optimizer.step()

        self.trained = True
        logger.info("PyTorch LSTM model trained successfully")
        return True

    def predict_proba(self, df: pd.DataFrame) -> dict:
        if not self.trained or self.model is None or len(df) < self.seq_len:
            return {"UP": 0.333, "DOWN": 0.333, "SIDEWAYS": 0.334}

        X_raw = df[self.feature_cols].iloc[-self.seq_len:].values
        X_norm = (X_raw - self.mean) / self.std
        X_tensor = torch.tensor(np.array([X_norm]), dtype=torch.float32)

        self.model.eval()
        with torch.no_grad():
            probs = self.model(X_tensor).numpy()[0]

        return {
            "DOWN": float(round(probs[0], 4)),
            "SIDEWAYS": float(round(probs[1], 4)),
            "UP": float(round(probs[2], 4))
        }
