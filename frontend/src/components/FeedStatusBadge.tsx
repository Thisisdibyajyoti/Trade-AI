import React, { useEffect, useState } from 'react';
import type { FeedMode, FeedStatus } from '../types';

const MODE_STYLE: Record<FeedMode, { bg: string; fg: string; dot: string; label: string }> = {
  LIVE: { bg: 'rgba(34,197,94,0.16)', fg: '#4ADE80', dot: '#22C55E', label: 'LIVE' },
  DELAYED: { bg: 'rgba(245,158,11,0.16)', fg: '#FBBF24', dot: '#F59E0B', label: 'DELAYED ~15m' },
  CLOSED: { bg: 'rgba(148,163,184,0.16)', fg: '#94A3B8', dot: '#64748B', label: 'MARKET CLOSED' },
  STALE: { bg: 'rgba(239,68,68,0.16)', fg: '#F87171', dot: '#EF4444', label: 'STALE' },
  RECONNECTING: { bg: 'rgba(239,68,68,0.16)', fg: '#F87171', dot: '#EF4444', label: 'RECONNECTING' },
  CONNECTING: { bg: 'rgba(148,163,184,0.16)', fg: '#94A3B8', dot: '#64748B', label: 'CONNECTING' },
};

function humanAge(seconds: number | null | undefined): string {
  if (seconds == null) return '';
  if (seconds < 60) return `${Math.round(seconds)}s ago`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
  return `${Math.round(seconds / 3600)}h ago`;
}

interface Props {
  status: FeedStatus | null;
  /** Live "seconds since last tick" measured on the client, if available. */
  clientAge?: number | null;
  showSource?: boolean;
  compact?: boolean;
}

/**
 * Honest freshness badge. Shows the real feed mode plus when the price last
 * updated, so nothing on screen is presented as more live than it really is.
 */
export const FeedStatusBadge: React.FC<Props> = ({ status, clientAge, showSource, compact }) => {
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => window.clearInterval(id);
  }, []);

  const mode: FeedMode = status?.mode || 'CONNECTING';
  const style = MODE_STYLE[mode] || MODE_STYLE.CONNECTING;
  const serverAge =
    status?.last_tick != null ? Math.max(0, now - status.last_tick) : status?.age_seconds ?? null;
  const age = clientAge != null ? clientAge : serverAge;
  const ageText = humanAge(age);

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        background: style.bg,
        color: style.fg,
        borderRadius: 999,
        padding: compact ? '2px 8px' : '3px 10px',
        fontSize: compact ? 10 : 11,
        fontWeight: 800,
        letterSpacing: '0.04em',
        whiteSpace: 'nowrap',
      }}
      title={status?.message || ''}
    >
      <span
        style={{
          width: 7,
          height: 7,
          borderRadius: 99,
          background: style.dot,
          boxShadow: mode === 'LIVE' ? `0 0 8px ${style.dot}` : 'none',
          animation: mode === 'LIVE' ? 'pulse 1.6s ease-in-out infinite' : 'none',
        }}
      />
      {style.label}
      {ageText && <span style={{ opacity: 0.75, fontWeight: 600 }}>· {ageText}</span>}
      {showSource && status?.source && (
        <span style={{ opacity: 0.7, fontWeight: 600 }}>· {status.source}</span>
      )}
    </span>
  );
};
