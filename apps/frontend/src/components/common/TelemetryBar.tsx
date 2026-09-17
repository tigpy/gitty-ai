import React from 'react';
import { Activity, Database, Cpu, Radio } from 'lucide-react';

interface TelemetryBarProps {
  nodesCount: number;
  edgesCount: number;
  filesCount: number;
  status?: string;
  zoomLevel?: number;
  repoName?: string;
}

export const TelemetryBar: React.FC<TelemetryBarProps> = ({
  nodesCount,
  edgesCount,
  filesCount,
  status = 'STABLE',
  zoomLevel = 1,
  repoName
}) => {
  return (
    <footer style={{
      height: '28px',
      background: 'var(--bg-panel)',
      borderTop: '1px solid var(--hairline)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 16px',
      fontFamily: 'var(--font-mono)',
      fontSize: '10.5px',
      color: 'var(--ink-secondary)',
      userSelect: 'none',
      zIndex: 50,
      flexShrink: 0
    }}>
      {/* Left: Core Graph Telemetry */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Radio size={11} style={{ color: 'var(--accent-amber)' }} />
          <span style={{ color: 'var(--ink-muted)' }}>HUD:</span>
          <span style={{ color: 'var(--ink-primary)', fontWeight: 600 }}>TELEMETRY ACTIVE</span>
        </div>

        <span style={{ color: 'var(--hairline)' }}>|</span>

        <div>
          <span style={{ color: 'var(--ink-muted)' }}>NODES: </span>
          <span className="mono-num" style={{ color: 'var(--accent-amber-bright)', fontWeight: 600 }}>{nodesCount}</span>
        </div>

        <div>
          <span style={{ color: 'var(--ink-muted)' }}>RELATIONSHIPS: </span>
          <span className="mono-num" style={{ color: 'var(--accent-amber-bright)', fontWeight: 600 }}>{edgesCount}</span>
        </div>

        <div>
          <span style={{ color: 'var(--ink-muted)' }}>SOURCE FILES: </span>
          <span className="mono-num" style={{ color: 'var(--ink-primary)' }}>{filesCount}</span>
        </div>
      </div>

      {/* Center: Viewport & System Stability */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        {repoName && (
          <div>
            <span style={{ color: 'var(--ink-muted)' }}>TARGET: </span>
            <span style={{ color: 'var(--ink-primary)' }}>{repoName}</span>
          </div>
        )}

        <div>
          <span style={{ color: 'var(--ink-muted)' }}>SCALE: </span>
          <span className="mono-num" style={{ color: 'var(--ink-primary)' }}>{Math.round(zoomLevel * 100)}%</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {nodesCount > 0 && status === 'STABLE' ? (
            <>
              <Activity size={11} style={{ color: 'var(--status-green)' }} />
              <span style={{ color: 'var(--ink-muted)' }}>SIMULATION: </span>
              <span style={{ color: 'var(--status-green)', fontWeight: 600 }}>STABLE</span>
            </>
          ) : (
            <>
              <Activity size={11} style={{ color: 'var(--ink-muted)' }} />
              <span style={{ color: 'var(--ink-muted)' }}>SIMULATION: </span>
              <span style={{ color: 'var(--ink-muted)', fontWeight: 500 }}>{status}</span>
            </>
          )}
        </div>
      </div>

      {/* Right: Engine Stack & Database Status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <Cpu size={11} style={{ color: 'var(--ink-muted)' }} />
          <span style={{ color: 'var(--ink-muted)' }}>ENGINE: </span>
          <span>FASTAPI + CELERY</span>
        </div>

        <span style={{ color: 'var(--hairline)' }}>|</span>

        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <Database size={11} style={{ color: 'var(--ink-muted)' }} />
          <span style={{ color: 'var(--ink-muted)' }}>VECTOR DB: </span>
          <span>QDRANT</span>
        </div>
      </div>
    </footer>
  );
};
