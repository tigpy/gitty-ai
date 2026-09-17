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
  hasInteracted?: boolean;
}

export const GraphToolbar: React.FC<ToolbarProps> = ({
  onZoomIn,
  onZoomOut,
  onReset,
  nodesCount,
  edgesCount,
  status = 'STABLE',
  hasInteracted = false
}) => {
  return (
    <div style={{
      position: 'absolute',
      bottom: '14px',
      left: '14px',
      display: 'flex',
      alignItems: 'center',
      gap: '6px',
      zIndex: 15,
      userSelect: 'none'
    }}>
      {/* Zoom / Viewport Buttons */}
      <div 
        className="console-panel"
        style={{ 
          display: 'flex', 
          padding: '2px', 
          gap: '2px',
          background: 'rgba(18, 22, 28, 0.9)',
          backdropFilter: 'blur(8px)'
        }}
      >
        <button 
          onClick={onZoomIn}
          className="console-btn"
          style={{ padding: '4px 6px' }}
          title="Zoom In"
        >
          <ZoomIn size={12} />
        </button>
        <button 
          onClick={onZoomOut}
          className="console-btn"
          style={{ padding: '4px 6px' }}
          title="Zoom Out"
        >
          <ZoomOut size={12} />
        </button>
        <button 
          onClick={onReset}
          className="console-btn"
          style={{ padding: '4px 8px', gap: '4px', fontSize: '10px' }}
          title="Reset & Center View"
        >
          <RotateCcw size={11} />
          <span>RESET</span>
        </button>
      </div>

      {/* Nodes and Edges Metric Badge */}
      <div 
        className="console-panel"
        style={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: '8px', 
          padding: '4px 10px', 
          fontSize: '10px',
          fontFamily: 'var(--font-mono)',
          color: 'var(--ink-secondary)',
          background: 'rgba(18, 22, 28, 0.9)',
          backdropFilter: 'blur(8px)'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <Activity size={11} style={{ color: status === 'STABLE' ? 'var(--status-green)' : 'var(--ink-muted)' }} />
          <span style={{ color: 'var(--ink-muted)' }}>NODES:</span>
          <span className="mono-num" style={{ color: 'var(--ink-primary)', fontWeight: 600 }}>{nodesCount}</span>
        </div>

        <span style={{ color: 'var(--hairline)' }}>|</span>

        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <span style={{ color: 'var(--ink-muted)' }}>EDGES:</span>
          <span className="mono-num" style={{ color: 'var(--ink-primary)', fontWeight: 600 }}>{edgesCount}</span>
        </div>

        <span style={{ color: 'var(--hairline)' }}>|</span>

        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          {status === 'STABLE' && nodesCount > 0 ? (
            <>
              <span className="status-dot status-dot-green" />
              <span style={{ color: 'var(--status-green)', fontSize: '9.5px', fontWeight: 600 }}>STABLE</span>
            </>
          ) : (
            <span style={{ color: 'var(--ink-muted)', fontSize: '9.5px', fontWeight: 500 }}>{status}</span>
          )}
        </div>
      </div>

      {/* Quick interaction hint (collapses after user interacts to prevent obstruction) */}
      {!hasInteracted ? (
        <div 
          className="console-panel"
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '5px', 
            padding: '4px 8px', 
            fontSize: '9.5px',
            fontFamily: 'var(--font-mono)',
            color: 'var(--ink-muted)',
            background: 'rgba(18, 22, 28, 0.9)',
            backdropFilter: 'blur(8px)'
          }}
        >
          <Compass size={11} style={{ color: 'var(--accent-amber)' }} />
          <span>DBL-CLICK FILE/CLASS TO EXPAND</span>
        </div>
      ) : (
        <div 
          className="console-panel"
          title="Tip: Double-click File or Class node to expand AST structure"
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            padding: '4px 6px', 
            background: 'rgba(18, 22, 28, 0.7)',
            backdropFilter: 'blur(8px)',
            cursor: 'help'
          }}
        >
          <Compass size={11} style={{ color: 'var(--ink-muted)' }} />
        </div>
      )}
    </div>
  );
};
