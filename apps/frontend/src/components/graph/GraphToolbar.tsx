import React from 'react';
import { 
  ZoomIn, 
  ZoomOut, 
  RotateCcw, 
  Activity,
  HelpCircle
} from 'lucide-react';

interface ToolbarProps {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
  nodesCount: number;
  edgesCount: number;
}

export const GraphToolbar: React.FC<ToolbarProps> = ({
  onZoomIn,
  onZoomOut,
  onReset,
  nodesCount,
  edgesCount,
}) => {
  return (
    <div style={{
      position: 'absolute',
      bottom: '20px',
      left: '20px',
      display: 'flex',
      alignItems: 'center',
      gap: '12px',
      zIndex: 10
    }}>
      {/* Controls panel */}
      <div className="glass-panel" style={{ display: 'flex', padding: '6px', gap: '4px', borderRadius: '8px' }}>
        <button 
          onClick={onZoomIn}
          className="glass-btn"
          style={{ padding: '6px', borderRadius: '6px' }}
          title="Zoom In"
        >
          <ZoomIn size={14} />
        </button>
        <button 
          onClick={onZoomOut}
          className="glass-btn"
          style={{ padding: '6px', borderRadius: '6px' }}
          title="Zoom Out"
        >
          <ZoomOut size={14} />
        </button>
        <button 
          onClick={onReset}
          className="glass-btn"
          style={{ padding: '6px', borderRadius: '6px' }}
          title="Reset View"
        >
          <RotateCcw size={14} />
        </button>
      </div>

      {/* Graph info badge */}
      <div className="glass-panel" style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: '8px', 
        padding: '6px 12px', 
        fontSize: '0.75rem', 
        borderRadius: '8px',
        color: 'rgba(255,255,255,0.6)',
        fontWeight: 500
      }}>
        <Activity size={12} style={{ color: '#10b981' }} />
        <span>Nodes: <strong style={{ color: '#ffffff' }}>{nodesCount}</strong></span>
        <span style={{ color: 'rgba(255,255,255,0.15)' }}>|</span>
        <span>Edges: <strong style={{ color: '#ffffff' }}>{edgesCount}</strong></span>
      </div>

      {/* Guide tooltip */}
      <div className="glass-panel" style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: '6px', 
        padding: '6px 12px', 
        fontSize: '0.72rem', 
        borderRadius: '8px',
        color: 'rgba(255,255,255,0.4)',
        fontWeight: 500
      }}>
        <HelpCircle size={11} />
        <span>Double-click File/Class to expand structure</span>
      </div>
    </div>
  );
};
