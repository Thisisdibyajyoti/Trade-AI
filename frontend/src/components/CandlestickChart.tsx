import React, { useEffect, useRef } from 'react';
import { createChart, ColorType, CandlestickSeries } from 'lightweight-charts';
import type { IChartApi, ISeriesApi, CandlestickData } from 'lightweight-charts';
import type { Candle } from '../types';

interface ChartProps {
  candles: Candle[];
  symbol: string;
}

export const CandlestickChart: React.FC<ChartProps> = ({ candles, symbol }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);

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
      crosshair: {
        mode: 1,
      },
      rightPriceScale: {
        borderColor: 'rgba(255, 255, 255, 0.08)',
      },
      timeScale: {
        borderColor: 'rgba(255, 255, 255, 0.08)',
        timeVisible: true,
      },
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
    };
  }, []);

  useEffect(() => {
    if (candlestickSeriesRef.current && candles.length > 0) {
      const formattedData: CandlestickData[] = candles.map((c) => ({
        time: c.time as any,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }));
      candlestickSeriesRef.current.setData(formattedData);
      chartRef.current?.timeScale().fitContent();
    }
  }, [candles]);

  return (
    <div className="w-full relative rounded-2xl overflow-hidden" style={{ height: 360, background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
      <div className="absolute top-3 left-4 z-10 flex items-center gap-2" style={{ background: 'rgba(18,18,22,0.85)', padding: '0.35rem 0.75rem', borderRadius: '0.75rem', border: '1px solid rgba(255,255,255,0.07)' }}>
        <span className="font-bold text-slate-200 text-xs">{symbol}</span>
        <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full" style={{ background: 'linear-gradient(90deg,#D946EF,#EC4899)', color: '#09090B' }}>LIVE</span>
      </div>
      <div ref={chartContainerRef} className="w-full h-full" />
    </div>
  );
};
