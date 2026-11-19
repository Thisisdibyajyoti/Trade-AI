import React, { useState, useEffect } from 'react';
import { StyleSheet, Text, View, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';

export default function MobileApp() {
  const [symbol, setSymbol] = useState('BTC/USDT');
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const fetchAnalysis = async (ticker: string) => {
    setLoading(true);
    try {
      const res = await fetch('http://localhost:8000/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol: ticker, timeframe: '1d' }),
      });
      const json = await res.json();
      setData(json);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalysis(symbol);
  }, [symbol]);

  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>TradeAI Mobile</Text>
        <Text style={styles.subtitle}>Data-Driven AI Trading Analysis</Text>
      </View>

      <View style={styles.pickerRow}>
        {['BTC/USDT', 'ETH/USDT', 'RELIANCE', 'AAPL'].map((s) => (
          <TouchableOpacity
            key={s}
            style={[styles.btn, symbol === s && styles.btnActive]}
            onPress={() => setSymbol(s)}
          >
            <Text style={[styles.btnText, symbol === s && styles.btnTextActive]}>{s}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {loading ? (
        <ActivityIndicator size="large" color="#10b981" style={{ marginTop: 40 }} />
      ) : data ? (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>{data.symbol} — ${data.current_price}</Text>
          <View style={styles.probRow}>
            <Text style={{ color: '#10b981', fontWeight: 'bold' }}>UP: {data.probabilities?.UP}%</Text>
            <Text style={{ color: '#ef4444', fontWeight: 'bold' }}>DOWN: {data.probabilities?.DOWN}%</Text>
            <Text style={{ color: '#3b82f6', fontWeight: 'bold' }}>SIDEWAYS: {data.probabilities?.SIDEWAYS}%</Text>
          </View>
          <Text style={styles.regime}>Regime: {data.market_regime?.regime}</Text>
          <Text style={styles.acc}>Out-of-Sample Accuracy: {data.backtest?.model_directional_accuracy}%</Text>
        </View>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#090d16', padding: 16 },
  header: { marginTop: 40, marginBottom: 20 },
  title: { fontSize: 24, fontWeight: 'bold', color: '#fff' },
  subtitle: { fontSize: 12, color: '#94a3b8' },
  pickerRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 20 },
  btn: { padding: 10, borderRadius: 8, backgroundColor: '#1e293b' },
  btnActive: { backgroundColor: '#10b981' },
  btnText: { color: '#94a3b8', fontSize: 12 },
  btnTextActive: { color: '#fff', fontWeight: 'bold' },
  card: { backgroundColor: '#0f172a', padding: 16, borderRadius: 12, borderHeight: 1, borderColor: '#334155' },
  cardTitle: { color: '#fff', fontSize: 18, fontWeight: 'bold' },
  probRow: { flexDirection: 'row', justifySpace: 'between', marginVertical: 12 },
  regime: { color: '#38bdf8', marginTop: 8 },
  acc: { color: '#a7f3d0', marginTop: 4 },
});
