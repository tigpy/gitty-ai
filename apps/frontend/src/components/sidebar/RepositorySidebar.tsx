import React, { useState } from 'react';
import type { Repository, GraphNode } from '../../types';
import { 
  Folder, 
  Trash2, 
  Search, 
  ShieldAlert, 
  Activity, 
  GitBranch, 
  Layers,
  Terminal,
  Compass
} from 'lucide-react';

interface SidebarProps {
  selectedRepo: Repository | null;
  onSelectRepo: (repo: Repository | null) => void;
  nodes: GraphNode[];
  onSelectNode: (node: GraphNode) => void;
  overlays: {
    security: boolean;
    deadCode: boolean;
    smells: boolean;
    callGraph: boolean;
  };
  onToggleOverlay: (key: 'security' | 'deadCode' | 'smells' | 'callGraph') => void;
  repos: Repository[];
  setRepos: React.Dispatch<React.SetStateAction<Repository[]>>;
  loadingRepos: boolean;
  analyzing: boolean;
  onStartAnalyze: (url: string) => void;
  onDeleteRepo?: (repoId: string, repoName: string) => void;
}

export const RepositorySidebar: React.FC<SidebarProps> = ({
  selectedRepo,
  onSelectRepo,
  nodes,
  onSelectNode,
  overlays,
  onToggleOverlay,
  repos,
  loadingRepos,
  analyzing,
  onStartAnalyze,
  onDeleteRepo,
}) => {
  const [urlInput, setUrlInput] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  const handleAnalyzeSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!urlInput.trim() || analyzing) return;
    onStartAnalyze(urlInput.trim());
    setUrlInput('');
  };

  const files = nodes.filter(n => n.node_type === 'FILE');
  const filteredFiles = files.filter(f => 
    f.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (f.file_path && f.file_path.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  return (
    <aside 
      className="console-panel"
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        userSelect: 'none',
        overflow: 'hidden'
      }}
    >
      {/* Panel Header */}
      <div style={{
        padding: '12px 14px',
        borderBottom: '1px solid var(--hairline)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: 'var(--bg-raised)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Layers size={14} style={{ color: 'var(--accent-amber)' }} />
          <span className="tech-header">EXPLORER & INDEX</span>
        </div>
        <span className="tech-label" style={{ color: 'var(--accent-amber-bright)' }}>
          {repos.length} REPOS
        </span>
      </div>

      {/* Ingest Repository Command Section */}
      <div style={{
        padding: '12px 14px',
        borderBottom: '1px solid var(--hairline)',
        background: 'var(--bg-panel)'
      }}>
        <div className="tech-label" style={{ marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '5px' }}>
          <Terminal size={11} style={{ color: 'var(--accent-amber)' }} />
          <span>INGEST TARGET REPO</span>
        </div>
        <form onSubmit={handleAnalyzeSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <input 
            type="text" 
            placeholder="https://github.com/owner/repo"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            disabled={analyzing}
            className="console-input"
            style={{ width: '100%' }}
          />
          <button
            type="submit"
            disabled={analyzing || !urlInput.trim()}
            className="console-btn console-btn-primary"
            style={{
              justifyContent: 'center',
              width: '100%',
              opacity: analyzing || !urlInput.trim() ? 0.6 : 1,
              cursor: analyzing || !urlInput.trim() ? 'not-allowed' : 'pointer'
            }}
          >
            {analyzing ? 'ANALYZING GRAPH...' : 'INGEST & ANALYZE'}
          </button>
        </form>
      </div>

      {/* Repositories Selection List */}
      <div style={{
        padding: '10px 14px',
        borderBottom: '1px solid var(--hairline)',
        maxHeight: '140px',
        overflowY: 'auto',
        background: 'var(--bg-panel)'
      }}>
        <div className="tech-label" style={{ marginBottom: '6px', display: 'flex', justifyContent: 'space-between' }}>
          <span>AVAILABLE TARGETS</span>
          <span className="mono-num">{repos.length}</span>
        </div>

        {loadingRepos ? (
          <div style={{ color: 'var(--ink-muted)', fontSize: '11px', fontFamily: 'var(--font-mono)', padding: '6px 0' }}>
            SCANNING REPOSITORIES...
          </div>
        ) : repos.length === 0 ? (
          <div style={{ color: 'var(--ink-muted)', fontSize: '11px', fontFamily: 'var(--font-mono)', padding: '6px 0' }}>
            NO REPOSITORIES IN INDEX
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {repos.map((repo, idx) => {
              const isSelected = selectedRepo?.id === repo.id;
              const indexStr = String(idx + 1).padStart(2, '0');
              return (
                <div
                  key={repo.id}
                  onClick={() => onSelectRepo(repo)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '5px 8px',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    background: isSelected ? 'var(--bg-active)' : 'transparent',
                    border: '1px solid',
                    borderColor: isSelected ? 'var(--accent-amber)' : 'transparent',
                    color: isSelected ? 'var(--accent-amber-bright)' : 'var(--ink-primary)',
                    fontFamily: 'var(--font-mono)',
                    fontSize: '11px',
                    transition: 'all 0.15s ease'
                  }}
                  onMouseEnter={(e) => {
                    if (!isSelected) {
                      e.currentTarget.style.background = 'var(--bg-hover)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected) {
                      e.currentTarget.style.background = 'transparent';
                    }
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '7px', overflow: 'hidden' }}>
                    <span style={{ color: 'var(--ink-muted)', fontSize: '10px' }}>{indexStr}</span>
                    <GitBranch size={12} style={{ color: isSelected ? 'var(--accent-amber)' : 'var(--ink-muted)', flexShrink: 0 }} />
                    <span style={{ 
                      overflow: 'hidden', 
                      textOverflow: 'ellipsis', 
                      whiteSpace: 'nowrap',
                      fontWeight: isSelected ? 600 : 400
                    }}>
                      {repo.name}
                    </span>
                  </div>

                  {onDeleteRepo && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteRepo(repo.id, repo.name);
                      }}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: 'var(--ink-muted)',
                        cursor: 'pointer',
                        padding: '2px',
                        display: 'flex',
                        alignItems: 'center'
                      }}
                      title="Purge repository from index"
                    >
                      <Trash2 size={12} />
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Technical HUD Overlays Toggles */}
      <div style={{
        padding: '10px 14px',
        borderBottom: '1px solid var(--hairline)',
        background: 'var(--bg-panel)'
      }}>
        <div className="tech-label" style={{ marginBottom: '8px', display: 'flex', justifyContent: 'space-between' }}>
          <span>HUD GRAPH OVERLAYS</span>
          <span>FILTER</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
          <button
            onClick={() => onToggleOverlay('security')}
            className={`console-btn ${overlays.security ? 'active' : ''}`}
            style={{ padding: '5px 6px', fontSize: '10px', justifyContent: 'center' }}
          >
            <ShieldAlert size={12} style={{ color: overlays.security ? 'var(--status-red)' : 'inherit' }} />
            SECURITY
          </button>

          <button
            onClick={() => onToggleOverlay('deadCode')}
            className={`console-btn ${overlays.deadCode ? 'active' : ''}`}
            style={{ padding: '5px 6px', fontSize: '10px', justifyContent: 'center' }}
          >
            <Trash2 size={12} style={{ color: overlays.deadCode ? 'var(--ink-muted)' : 'inherit' }} />
            DEAD CODE
          </button>

          <button
            onClick={() => onToggleOverlay('smells')}
            className={`console-btn ${overlays.smells ? 'active' : ''}`}
            style={{ padding: '5px 6px', fontSize: '10px', justifyContent: 'center' }}
          >
            <Activity size={12} style={{ color: overlays.smells ? 'var(--accent-orange)' : 'inherit' }} />
            ARCH SMELLS
          </button>

          <button
            onClick={() => onToggleOverlay('callGraph')}
            className={`console-btn ${overlays.callGraph ? 'active' : ''}`}
            style={{ padding: '5px 6px', fontSize: '10px', justifyContent: 'center' }}
          >
            <Compass size={12} style={{ color: overlays.callGraph ? 'var(--status-green)' : 'inherit' }} />
            CALL PATHS
          </button>
        </div>
      </div>

      {/* File Search & Directory Navigator */}
      <div style={{ padding: '10px 14px 6px 14px' }}>
        <div className="tech-label" style={{ marginBottom: '6px', display: 'flex', justifyContent: 'space-between' }}>
          <span>SOURCE ARTIFACTS</span>
          <span className="mono-num">{filteredFiles.length} / {files.length}</span>
        </div>
        <div style={{ position: 'relative' }}>
          <Search size={13} style={{ position: 'absolute', left: '8px', top: '7px', color: 'var(--ink-muted)' }} />
          <input 
            type="text" 
            placeholder="Search source files..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="console-input"
            style={{ width: '100%', paddingLeft: '26px' }}
          />
        </div>
      </div>

      {/* Files List */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '4px 14px 10px 14px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
          {filteredFiles.map(file => (
            <div
              key={file.id}
              onClick={() => onSelectNode(file)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '4px 6px',
                borderRadius: '4px',
                cursor: 'pointer',
                fontFamily: 'var(--font-mono)',
                fontSize: '11px',
                color: file.dead_code ? 'var(--ink-muted)' : 'var(--ink-primary)',
                transition: 'background 0.1s ease'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--bg-hover)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent';
              }}
            >
              <Folder size={12} style={{ color: 'var(--ink-secondary)', flexShrink: 0 }} />
              <span style={{
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                flex: 1
              }}>
                {file.label}
              </span>

              {file.security_score !== undefined && file.security_score !== null && file.security_score < 100 && (
                <span 
                  className="badge badge-critical" 
                  style={{ fontSize: '9px', padding: '0 4px', lineHeight: '14px' }}
                >
                  SEC {file.security_score}
                </span>
              )}
            </div>
          ))}

          {filteredFiles.length === 0 && (
            <div style={{
              color: 'var(--ink-muted)',
              fontSize: '11px',
              fontFamily: 'var(--font-mono)',
              textAlign: 'center',
              padding: '16px 0'
            }}>
              NO MATCHING ARTIFACTS
            </div>
          )}
        </div>
      </div>

      {/* Visual Legend */}
      <div style={{
        padding: '10px 14px',
        borderTop: '1px solid var(--hairline)',
        background: 'var(--bg-panel)',
        fontFamily: 'var(--font-mono)',
        fontSize: '10px',
        color: 'var(--ink-muted)'
      }}>
        <div className="tech-label" style={{ marginBottom: '6px' }}>GRAPH MATRIX LEGEND</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: '#4f46e5' }} />
            <span>REPOSITORY</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: '#2563eb' }} />
            <span>FILE</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: '#0891b2' }} />
            <span>CLASS</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: '#94a3b8' }} />
            <span>FUNCTION</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: 'var(--status-red)' }} />
            <span>VULNERABILITY</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: '7px', height: '7px', border: '1px dashed var(--ink-muted)' }} />
            <span>DEAD CODE</span>
          </div>
        </div>
      </div>
    </aside>
  );
};
