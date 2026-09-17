import React from 'react';
import type { GraphNode, NodeDetails, GraphEdge } from '../../types';
import { 
  FileCode, 
  ShieldAlert, 
  X, 
  MessageSquare, 
  Copy, 
  Check, 
  CornerDownRight
} from 'lucide-react';

interface NodeInspectorProps {
  node: GraphNode;
  details: NodeDetails | null;
  edges: GraphEdge[];
  onClose: () => void;
  onTriggerCallGraph: () => void;
  onAskAboutNode?: (nodeLabel: string) => void;
}

export const NodeInspector: React.FC<NodeInspectorProps> = ({
  node,
  details,
  edges,
  onClose,
  onTriggerCallGraph,
  onAskAboutNode,
}) => {
  const [copied, setCopied] = React.useState(false);

  // Count incoming & outgoing connections
  const incomingCount = edges.filter(e => e.target === node.id).length;
  const outgoingCount = edges.filter(e => e.source === node.id).length;

  const handleCopyPath = () => {
    if (node.file_path) {
      navigator.clipboard.writeText(node.file_path);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div 
      className="console-panel console-panel-raised"
      style={{
        position: 'absolute',
        top: '16px',
        left: '16px',
        width: '340px',
        maxHeight: 'calc(100% - 32px)',
        overflowY: 'auto',
        padding: '14px',
        zIndex: 20,
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5)',
        backdropFilter: 'blur(8px)',
        border: '1px solid var(--hairline)'
      }}
    >
      {/* Top Header Bar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingBottom: '10px',
        borderBottom: '1px solid var(--hairline)',
        marginBottom: '12px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', overflow: 'hidden' }}>
          <FileCode size={15} style={{ color: 'var(--accent-amber)', flexShrink: 0 }} />
          <div style={{ overflow: 'hidden' }}>
            <div className="tech-label">INSPECTOR HUD</div>
            <h3 style={{
              margin: 0,
              fontSize: '13px',
              fontFamily: 'var(--font-mono)',
              fontWeight: 600,
              color: 'var(--ink-primary)',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis'
            }}>
              {node.label}
            </h3>
          </div>
        </div>

        <button
          onClick={onClose}
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--ink-muted)',
            cursor: 'pointer',
            padding: '4px',
            borderRadius: '4px',
            display: 'flex',
            alignItems: 'center'
          }}
          title="Close Inspector"
        >
          <X size={15} />
        </button>
      </div>

      {/* Node Metadata Section */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {/* Type & Severity Badges */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
          <span 
            className="badge"
            style={{
              background: 'rgba(240, 164, 34, 0.12)',
              color: 'var(--accent-amber-bright)',
              borderColor: 'rgba(240, 164, 34, 0.3)'
            }}
          >
            {node.node_type}
          </span>

          {details?.dead_code && (
            <span className="badge badge-dead">DEAD CODE</span>
          )}

          {details?.architecture_smell && (
            <span className="badge badge-smell">ARCH SMELL</span>
          )}

          {node.security_score !== undefined && node.security_score !== null && (
            <span className={`badge ${node.security_score < 70 ? 'badge-critical' : 'badge-info'}`}>
              SEC: {node.security_score}/100
            </span>
          )}
        </div>

        {/* File Path & Line Numbers */}
        {node.file_path && (
          <div style={{
            background: 'var(--bg-ground)',
            border: '1px solid var(--hairline)',
            borderRadius: '4px',
            padding: '6px 8px',
            fontSize: '11px',
            fontFamily: 'var(--font-mono)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '3px' }}>
              <span className="tech-label">FILE PATH</span>
              <button
                onClick={handleCopyPath}
                style={{
                  background: 'none',
                  border: 'none',
                  color: copied ? 'var(--status-green)' : 'var(--ink-muted)',
                  cursor: 'pointer',
                  padding: '1px 4px',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '3px',
                  fontSize: '10px'
                }}
                title="Copy relative path"
              >
                {copied ? <Check size={10} /> : <Copy size={10} />}
                {copied ? 'COPIED' : 'COPY'}
              </button>
            </div>
            <div style={{
              color: 'var(--ink-primary)',
              wordBreak: 'break-all',
              lineHeight: 1.4
            }}>
              {node.file_path}
            </div>
          </div>
        )}

        {/* Lines Range & Connection Metrics */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '6px',
          fontFamily: 'var(--font-mono)',
          fontSize: '11px'
        }}>
          <div style={{
            background: 'var(--bg-ground)',
            border: '1px solid var(--hairline)',
            padding: '6px 8px',
            borderRadius: '4px'
          }}>
            <div className="tech-label">LINE SPAN</div>
            <div style={{ color: 'var(--ink-primary)', marginTop: '2px' }}>
              {details?.start_line !== undefined && details?.end_line !== undefined
                ? `L${details.start_line} - L${details.end_line}`
                : 'GLOBAL'}
            </div>
          </div>

          <div style={{
            background: 'var(--bg-ground)',
            border: '1px solid var(--hairline)',
            padding: '6px 8px',
            borderRadius: '4px'
          }}>
            <div className="tech-label">CONNECTIONS</div>
            <div style={{ color: 'var(--ink-primary)', marginTop: '2px' }}>
              ↑ {outgoingCount} | ↓ {incomingCount}
            </div>
          </div>
        </div>

        {/* Security Findings List */}
        {details?.security_findings && details.security_findings.length > 0 && (
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '6px',
            marginTop: '4px'
          }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              color: 'var(--status-red)',
              fontFamily: 'var(--font-mono)',
              fontSize: '10.5px',
              fontWeight: 600,
              letterSpacing: '0.06em'
            }}>
              <ShieldAlert size={13} />
              SECURITY FINDINGS ({details.security_findings.length})
            </div>

            {details.security_findings.map((fnd) => (
              <div
                key={fnd.id}
                style={{
                  background: 'rgba(239, 68, 68, 0.06)',
                  border: '1px solid rgba(239, 68, 68, 0.25)',
                  borderRadius: '4px',
                  padding: '7px 9px',
                  fontSize: '11px',
                  fontFamily: 'var(--font-mono)'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '3px' }}>
                  <span className={`badge badge-${fnd.severity.toLowerCase()}`}>
                    {fnd.severity}
                  </span>
                  <span style={{ color: 'var(--ink-muted)', fontSize: '10px' }}>
                    Line: {fnd.line_number}
                  </span>
                </div>
                <div style={{ color: 'var(--ink-primary)', fontSize: '11px', lineHeight: 1.35 }}>
                  {fnd.description}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Technical Actions */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '6px' }}>
          {node.node_type === 'FUNCTION' && (
            <button
              onClick={onTriggerCallGraph}
              className="console-btn"
              style={{ justifyContent: 'center', width: '100%' }}
            >
              <CornerDownRight size={12} style={{ color: 'var(--status-green)' }} />
              EXPLORE CALL GRAPH
            </button>
          )}

          {onAskAboutNode && (
            <button
              onClick={() => onAskAboutNode(node.label)}
              className="console-btn console-btn-primary"
              style={{ justifyContent: 'center', width: '100%' }}
            >
              <MessageSquare size={12} />
              QUERY GITTY ABOUT NODE
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
