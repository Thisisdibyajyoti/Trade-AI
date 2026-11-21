import React, { useEffect, useRef } from 'react';
import { createChart, ColorType, CandlestickSeries } from 'lightweight-charts';
import type { IChartApi, ISeriesApi, CandlestickData, UTCTimestamp } from 'lightweight-charts';
import type { FeedStatus, LiveCandle } from '../types';
import { FeedStatusBadge } from './FeedStatusBadge';

interface ChartProps {
  candles: LiveCandle[];
  forming: LiveCandle | null;
  symbol: string;
  feedStatus: FeedStatus | null;
}

const toBar = (c: LiveCandle): CandlestickData => ({
  time: c.time as UTCTimestamp,
  open: c.open,
  high: c.high,
  low: c.low,
  close: c.close,
});

export const CandlestickChart: React.FC<ChartProps> = ({ candles, forming, symbol, feedStatus }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const lastCandlesRef = useRef<LiveCandle[] | null>(null);
  const didFitRef = useRef(false);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#8E8E98',
        fontFamily: "'Plus Jakarta Sans', Inter, system-ui, sans-serif",
      },
      grid: {
        vertLines: { color: 'rgba(255, 255, 255, 0.04)' },
        horzLines: { color: 'rgba(255, 255, 255, 0.04)' },
      },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: 'rgba(255, 255, 255, 0.08)' },
      timeScale: { borderColor: 'rgba(255, 255, 255, 0.08)', timeVisible: true, secondsVisible: false },
      width: chartContainerRef.current.clientWidth,
      height: 360,
    });

    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#D946EF',
      downColor: '#EC4899',
      borderVisible: false,
      wickUpColor: '#E879F9',
      wickDownColor: '#F472B6',
    });

    chartRef.current = chart;
    candlestickSeriesRef.current = candlestickSeries;

    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
      chartRef.current = null;
      candlestickSeriesRef.current = null;
    };
  }, []);

  // Rebuild the closed series when the symbol changes.
  useEffect(() => {
    didFitRef.current = false;
    lastCandlesRef.current = null;
  }, [symbol]);

  // Apply closed candles (full set) + the live forming candle (incremental).
  useEffect(() => {
    const series = candlestickSeriesRef.current;
    if (!series || candles.length === 0) return;

    if (lastCandlesRef.current !== candles) {
      series.setData(candles.map(toBar));
      lastCandlesRef.current = candles;
      if (!didFitRef.current) {
        chartRef.current?.timeScale().fitContent();
        didFitRef.current = true;
      }
    }

    if (forming && forming.time > 0) {
      series.update(toBar(forming));
    }
  }, [candles, forming]);

  return (
    <div
      className="w-full relative rounded-2xl overflow-hidden"
      style={{ height: 360, background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}
    >
      <div
        className="absolute top-3 left-4 z-10 flex items-center gap-2"
        style={{ background: 'rgba(18,18,22,0.85)', padding: '0.35rem 0.75rem', borderRadius: '0.75rem', border: '1px solid rgba(255,255,255,0.07)' }}
      >
        <span className="font-bold text-slate-200 text-xs">{symbol}</span>
        <FeedStatusBadge status={feedStatus} />
      </div>
      <div ref={chartContainerRef} className="w-full h-full" />
    </div>
  );
};
