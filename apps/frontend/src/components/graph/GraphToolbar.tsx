import React from 'react';
import { 
  ZoomIn, 
  ZoomOut, 
  RotateCcw, 
  Activity,
  Compass
} from 'lucide-react';

interface ToolbarProps {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
  nodesCount: number;
  edgesCount: number;
  status?: string;
}

export const GraphToolbar: React.FC<ToolbarProps> = ({
  onZoomIn,
  onZoomOut,
  onReset,
  nodesCount,
  edgesCount,
  status = 'STABLE'
}) => {
  return (
    <div style={{
      position: 'absolute',
      bottom: '16px',
      left: '16px',
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      zIndex: 15,
      userSelect: 'none'
    }}>
      {/* Zoom / Viewport Buttons */}
      <div 
        className="console-panel"
        style={{ 
          display: 'flex', 
          padding: '3px', 
          gap: '3px',
          background: 'rgba(18, 22, 28, 0.85)',
          backdropFilter: 'blur(6px)'
        }}
      >
        <button 
          onClick={onZoomIn}
          className="console-btn"
          style={{ padding: '5px 7px' }}
          title="Zoom In"
        >
          <ZoomIn size={13} />
        </button>
        <button 
          onClick={onZoomOut}
          className="console-btn"
          style={{ padding: '5px 7px' }}
          title="Zoom Out"
        >
          <ZoomOut size={13} />
        </button>
        <button 
          onClick={onReset}
          className="console-btn"
          style={{ padding: '5px 9px', gap: '5px' }}
          title="Reset & Center View"
        >
          <RotateCcw size={12} />
          <span>RESET</span>
        </button>
      </div>

      {/* Nodes and Edges Metric Badge */}
      <div 
        className="console-panel"
        style={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: '10px', 
          padding: '6px 12px', 
          fontSize: '11px',
          fontFamily: 'var(--font-mono)',
          color: 'var(--ink-secondary)',
          background: 'rgba(18, 22, 28, 0.85)',
          backdropFilter: 'blur(6px)'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <Activity size={12} style={{ color: 'var(--status-green)' }} />
          <span style={{ color: 'var(--ink-muted)' }}>NODES:</span>
          <span className="mono-num" style={{ color: 'var(--ink-primary)', fontWeight: 600 }}>{nodesCount}</span>
        </div>

        <span style={{ color: 'var(--hairline)' }}>|</span>

        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <span style={{ color: 'var(--ink-muted)' }}>EDGES:</span>
          <span className="mono-num" style={{ color: 'var(--ink-primary)', fontWeight: 600 }}>{edgesCount}</span>
        </div>

        <span style={{ color: 'var(--hairline)' }}>|</span>

        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <span className="status-dot status-dot-green" />
          <span style={{ color: 'var(--status-green)', fontSize: '10px', fontWeight: 600 }}>{status}</span>
        </div>
      </div>

      {/* Quick interaction hint */}
      <div 
        className="console-panel"
        style={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: '6px', 
          padding: '6px 10px', 
          fontSize: '10.5px',
          fontFamily: 'var(--font-mono)',
          color: 'var(--ink-muted)',
          background: 'rgba(18, 22, 28, 0.85)',
          backdropFilter: 'blur(6px)'
        }}
      >
        <Compass size={12} style={{ color: 'var(--accent-amber)' }} />
        <span>DBL-CLICK FILE/CLASS TO EXPAND</span>
      </div>
    </div>
  );
};
