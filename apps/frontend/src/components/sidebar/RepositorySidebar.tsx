import React, { useState, useMemo } from 'react';
import type { Repository, GraphNode } from '../../types';
import { 
  Folder, 
  FileCode, 
  Trash2, 
  Search, 
  ShieldAlert, 
  Activity, 
  Compass, 
  Terminal, 
  Layers,
  ChevronDown,
  ChevronRight
} from 'lucide-react';

interface SidebarProps {
  selectedRepo: Repository | null;
  onSelectRepo: (repo: Repository | null) => void;
  nodes: GraphNode[];
  onSelectNode: (node: GraphNode) => void;
  selectedNode?: GraphNode | null;
  overlays: {
    security: boolean;
    deadCode: boolean;
    smells: boolean;
    callGraph: boolean;
  };
  onToggleOverlay: (key: 'security' | 'deadCode' | 'smells' | 'callGraph') => void;
  repos: Repository[];
  setRepos?: React.Dispatch<React.SetStateAction<Repository[]>>;
  loadingRepos: boolean;
  analyzing: boolean;
  onStartAnalyze: (url: string) => void;
  onDeleteRepo?: (repoId: string, repoName: string) => void;
}

interface FileTreeNode {
  name: string;
  fullPath: string;
  isDirectory: boolean;
  fileNode?: GraphNode;
  children: FileTreeNode[];
}

function buildFileTree(files: GraphNode[]): FileTreeNode[] {
  const root: { [key: string]: any } = {};

  for (const f of files) {
    const rawPath = (f.file_path || f.label).replace(/\\/g, '/');
    const parts = rawPath.split('/').filter(Boolean);

    let current = root;
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      const isFile = i === parts.length - 1;
      const fullPath = parts.slice(0, i + 1).join('/');

      if (!current[part]) {
        current[part] = {
          name: part,
          fullPath,
          isDirectory: !isFile,
          fileNode: isFile ? f : undefined,
          children: {}
        };
      } else if (isFile) {
        current[part].fileNode = f;
        current[part].isDirectory = false;
      }
      current = current[part].children;
    }
  }

  function convertToArray(obj: { [key: string]: any }): FileTreeNode[] {
    const arr = Object.values(obj).map(item => ({
      name: item.name,
      fullPath: item.fullPath,
      isDirectory: item.isDirectory,
      fileNode: item.fileNode,
      children: convertToArray(item.children)
    }));

    arr.sort((a, b) => {
      if (a.isDirectory && !b.isDirectory) return -1;
      if (!a.isDirectory && b.isDirectory) return 1;
      return a.name.localeCompare(b.name);
    });

    return arr;
  }

  return convertToArray(root);
}

export const RepositorySidebar: React.FC<SidebarProps> = ({
  selectedRepo,
  onSelectRepo,
  nodes,
  onSelectNode,
  selectedNode,
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
  const [collapsedDirs, setCollapsedDirs] = useState<Record<string, boolean>>({});

  const handleAnalyzeSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!urlInput.trim() || analyzing) return;
    onStartAnalyze(urlInput.trim());
    setUrlInput('');
  };

  const toggleDirectory = (dirPath: string) => {
    setCollapsedDirs(prev => ({
      ...prev,
      [dirPath]: !prev[dirPath]
    }));
  };

  // Filter file nodes
  const files = useMemo(() => nodes.filter(n => n.node_type === 'FILE'), [nodes]);

  const filteredFiles = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return files;
    return files.filter(f => 
      f.label.toLowerCase().includes(query) ||
      (f.file_path && f.file_path.toLowerCase().includes(query))
    );
  }, [files, searchQuery]);

  const fileTree = useMemo(() => buildFileTree(filteredFiles), [filteredFiles]);

  const renderTreeNode = (node: FileTreeNode, level: number = 0) => {
    if (node.isDirectory) {
      const isCollapsed = collapsedDirs[node.fullPath];
      return (
        <div key={node.fullPath} style={{ display: 'flex', flexDirection: 'column' }}>
          <div
            onClick={() => toggleDirectory(node.fullPath)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              padding: '2px 4px',
              paddingLeft: `${level * 10 + 4}px`,
              cursor: 'pointer',
              fontSize: '11px',
              fontFamily: 'var(--font-mono)',
              color: 'var(--ink-secondary)',
              userSelect: 'none',
              borderRadius: '3px',
              transition: 'background 0.1s ease',
              height: '24px'
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg-hover)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
          >
            {isCollapsed ? (
              <ChevronRight size={11} style={{ color: 'var(--ink-muted)', flexShrink: 0 }} />
            ) : (
              <ChevronDown size={11} style={{ color: 'var(--ink-muted)', flexShrink: 0 }} />
            )}
            <Folder size={11} style={{ color: 'var(--ink-muted)', flexShrink: 0 }} />
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {node.name}
            </span>
          </div>
          {!isCollapsed && (
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {node.children.map(child => renderTreeNode(child, level + 1))}
            </div>
          )}
        </div>
      );
    }

    const isSelected = selectedNode && node.fileNode && selectedNode.id === node.fileNode.id;
    const isDead = node.fileNode?.dead_code;
    const hasSecurityFinding = node.fileNode?.security_score !== undefined && node.fileNode.security_score !== null && node.fileNode.security_score < 100;

    return (
      <div
        key={node.fullPath}
        onClick={() => node.fileNode && onSelectNode(node.fileNode)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '5px',
          padding: '2px 4px',
          paddingLeft: `${level * 10 + 16}px`,
          cursor: 'pointer',
          fontSize: '11px',
          fontFamily: 'var(--font-mono)',
          color: isSelected ? 'var(--accent-amber-bright)' : isDead ? 'var(--ink-muted)' : 'var(--ink-primary)',
          background: isSelected ? 'rgba(240, 164, 34, 0.08)' : 'transparent',
          borderLeft: isSelected ? '2px solid var(--accent-amber)' : '2px solid transparent',
          borderRadius: '0 3px 3px 0',
          transition: 'background 0.1s ease',
          height: '24px'
        }}
        onMouseEnter={(e) => {
          if (!isSelected) e.currentTarget.style.background = 'var(--bg-hover)';
        }}
        onMouseLeave={(e) => {
          if (!isSelected) e.currentTarget.style.background = 'transparent';
        }}
      >
        <FileCode size={11} style={{ color: isSelected ? 'var(--accent-amber)' : 'var(--ink-secondary)', flexShrink: 0 }} />
        <span style={{
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          flex: 1,
          fontWeight: isSelected ? 600 : 400
        }}>
          {node.name}
        </span>

        {hasSecurityFinding && (
          <span 
            className="badge badge-critical" 
            style={{ fontSize: '8.5px', padding: '0 3px', lineHeight: '13px', marginLeft: 'auto', flexShrink: 0 }}
          >
            SEC {node.fileNode!.security_score}
          </span>
        )}
      </div>
    );
  };

  return (
    <aside 
      className="console-panel"
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        userSelect: 'none',
        overflow: 'hidden',
        background: 'var(--bg-panel)'
      }}
    >
      {/* 1. Header (Compact 40px) */}
      <div style={{
        height: '40px',
        padding: '0 12px',
        borderBottom: '1px solid var(--hairline)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: 'var(--bg-raised)',
        flexShrink: 0
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
          <Layers size={13} style={{ color: 'var(--accent-amber)' }} />
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '11px',
            fontWeight: 600,
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            color: 'var(--ink-primary)'
          }}>
            EXPLORER / INDEX
          </span>
        </div>
        <span 
          className="mono-num" 
          style={{ 
            color: 'var(--accent-amber-bright)', 
            fontWeight: 600, 
            fontSize: '11px' 
          }}
        >
          {String(repos.length).padStart(2, '0')}
        </span>
      </div>

      {/* 2. Ingest Target Repo (Compact 32px inputs) */}
      <div style={{
        padding: '8px 12px',
        borderBottom: '1px solid var(--hairline)',
        background: 'var(--bg-panel)',
        flexShrink: 0
      }}>
        <div className="tech-label" style={{ marginBottom: '5px', display: 'flex', alignItems: 'center', gap: '5px' }}>
          <Terminal size={10} style={{ color: 'var(--accent-amber)' }} />
          <span>TARGET REPOSITORY</span>
        </div>
        <form onSubmit={handleAnalyzeSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
          <input 
            type="text" 
            placeholder="github.com/owner/repo"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            disabled={analyzing}
            className="console-input"
            style={{ width: '100%', height: '32px', fontSize: '11px' }}
          />
          <button
            type="submit"
            disabled={analyzing || !urlInput.trim()}
            className="console-btn console-btn-primary"
            style={{
              justifyContent: 'center',
              width: '100%',
              height: '32px',
              fontSize: '10.5px',
              opacity: analyzing || !urlInput.trim() ? 0.6 : 1,
              cursor: analyzing || !urlInput.trim() ? 'not-allowed' : 'pointer'
            }}
          >
            {analyzing ? 'ANALYZING GRAPH...' : '+ INGEST & ANALYZE'}
          </button>
        </form>
      </div>

      {/* 3. Target Repositories List (Compact Rows, 32px height) */}
      <div style={{
        padding: '8px 12px',
        borderBottom: '1px solid var(--hairline)',
        maxHeight: '124px',
        overflowY: 'auto',
        background: 'var(--bg-panel)',
        flexShrink: 0
      }}>
        <div className="tech-label" style={{ marginBottom: '5px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>TARGETS</span>
          <span className="mono-num" style={{ color: 'var(--accent-amber-bright)' }}>
            {String(repos.length).padStart(2, '0')}
          </span>
        </div>

        {loadingRepos ? (
          <div style={{ color: 'var(--ink-muted)', fontSize: '10.5px', fontFamily: 'var(--font-mono)', padding: '4px 0' }}>
            SCANNING TARGETS...
          </div>
        ) : repos.length === 0 ? (
          <div style={{ color: 'var(--ink-muted)', fontSize: '10.5px', fontFamily: 'var(--font-mono)', padding: '4px 0' }}>
            NO TARGETS CONFIGURED
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
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
                    padding: '4px 7px',
                    height: '32px',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    background: isSelected ? 'rgba(240, 164, 34, 0.08)' : 'transparent',
                    border: '1px solid',
                    borderColor: isSelected ? 'var(--accent-amber)' : 'transparent',
                    borderLeft: isSelected ? '2px solid var(--accent-amber)' : '1px solid transparent',
                    color: isSelected ? 'var(--accent-amber-bright)' : 'var(--ink-primary)',
                    fontFamily: 'var(--font-mono)',
                    fontSize: '11px',
                    transition: 'all 0.12s ease'
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
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', overflow: 'hidden', flex: 1 }}>
                    <span style={{ color: isSelected ? 'var(--accent-amber)' : 'var(--ink-muted)', fontSize: '10px' }}>{indexStr}</span>
                    <span style={{ color: isSelected ? 'var(--accent-amber)' : 'var(--ink-muted)', fontSize: '11px' }}>◈</span>
                    <span style={{ 
                      overflow: 'hidden', 
                      textOverflow: 'ellipsis', 
                      whiteSpace: 'nowrap',
                      fontWeight: isSelected ? 600 : 400
                    }}>
                      {repo.name}
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
                    {isSelected && (
                      <span style={{
                        fontSize: '9px',
                        fontFamily: 'var(--font-mono)',
                        color: 'var(--accent-amber)',
                        letterSpacing: '0.06em',
                        fontWeight: 600
                      }}>
                        ACTIVE
                      </span>
                    )}

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
                          alignItems: 'center',
                          borderRadius: '3px'
                        }}
                        title="Purge repository from index"
                      >
                        <Trash2 size={11} />
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 4. HUD Graph Overlays (Compact 2x2 Matrix) */}
      <div style={{
        padding: '8px 12px',
        borderBottom: '1px solid var(--hairline)',
        background: 'var(--bg-panel)',
        flexShrink: 0
      }}>
        <div className="tech-label" style={{ marginBottom: '6px' }}>
          <span>HUD GRAPH OVERLAYS</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '5px' }}>
          <button
            onClick={() => onToggleOverlay('security')}
            className={`console-btn ${overlays.security ? 'active' : ''}`}
            style={{
              padding: '4px 6px',
              height: '30px',
              fontSize: '9.5px',
              justifyContent: 'center',
              borderColor: overlays.security ? 'rgba(239, 68, 68, 0.5)' : undefined,
              color: overlays.security ? 'var(--status-red)' : undefined,
              background: overlays.security ? 'rgba(239, 68, 68, 0.1)' : undefined
            }}
          >
            <ShieldAlert size={11} style={{ color: overlays.security ? 'var(--status-red)' : 'inherit' }} />
            SECURITY
          </button>

          <button
            onClick={() => onToggleOverlay('deadCode')}
            className={`console-btn ${overlays.deadCode ? 'active' : ''}`}
            style={{ padding: '4px 6px', height: '30px', fontSize: '9.5px', justifyContent: 'center' }}
          >
            <Trash2 size={11} style={{ color: overlays.deadCode ? 'var(--accent-amber-bright)' : 'inherit' }} />
            DEAD CODE
          </button>

          <button
            onClick={() => onToggleOverlay('smells')}
            className={`console-btn ${overlays.smells ? 'active' : ''}`}
            style={{ padding: '4px 6px', height: '30px', fontSize: '9.5px', justifyContent: 'center' }}
          >
            <Activity size={11} style={{ color: overlays.smells ? 'var(--accent-orange)' : 'inherit' }} />
            ARCH SMELLS
          </button>

          <button
            onClick={() => onToggleOverlay('callGraph')}
            className={`console-btn ${overlays.callGraph ? 'active' : ''}`}
            style={{ padding: '4px 6px', height: '30px', fontSize: '9.5px', justifyContent: 'center' }}
          >
            <Compass size={11} style={{ color: overlays.callGraph ? 'var(--accent-amber-bright)' : 'inherit' }} />
            CALL PATHS
          </button>
        </div>
      </div>

      {/* 5. Source Artifact Explorer (Primary Scrollable Region) */}
      <div style={{
        padding: '8px 12px 5px 12px',
        borderBottom: '1px solid var(--hairline-subtle, rgba(232,235,239,0.06))',
        flexShrink: 0
      }}>
        <div className="tech-label" style={{ marginBottom: '5px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>SOURCE ARTIFACTS</span>
          <span className="mono-num" style={{ color: 'var(--accent-amber-bright)' }}>
            {filteredFiles.length} / {files.length}
          </span>
        </div>
        <div style={{ position: 'relative' }}>
          <Search size={12} style={{ position: 'absolute', left: '7px', top: '9px', color: 'var(--ink-muted)' }} />
          <input 
            type="text" 
            placeholder="Search source files..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="console-input"
            style={{ width: '100%', height: '28px', paddingLeft: '24px', fontSize: '11px' }}
          />
        </div>
      </div>

      {/* Hierarchical Source Tree (Absorbs remaining vertical overflow) */}
      <div style={{
        flex: 1,
        minHeight: 0,
        overflowY: 'auto',
        padding: '4px 8px 8px 8px',
        background: 'var(--bg-ground)'
      }}>
        {fileTree.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1px' }}>
            {fileTree.map(node => renderTreeNode(node, 0))}
          </div>
        ) : (
          <div style={{
            color: 'var(--ink-muted)',
            fontSize: '10.5px',
            fontFamily: 'var(--font-mono)',
            textAlign: 'center',
            padding: '20px 0'
          }}>
            NO MATCHING ARTIFACTS
          </div>
        )}
      </div>

      {/* 6. Compact Fixed Visual Legend (Height ~64px) */}
      <div style={{
        height: '64px',
        padding: '6px 12px',
        borderTop: '1px solid var(--hairline)',
        background: 'var(--bg-panel)',
        fontFamily: 'var(--font-mono)',
        fontSize: '9.5px',
        color: 'var(--ink-muted)',
        flexShrink: 0,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center'
      }}>
        <div className="tech-label" style={{ marginBottom: '4px', fontSize: '9px' }}>GRAPH MATRIX LEGEND</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '4px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#4F46E5', flexShrink: 0 }} />
            <span>REPO</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#2563EB', flexShrink: 0 }} />
            <span>FILE</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#0891B2', flexShrink: 0 }} />
            <span>CLASS</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#94A3B8', flexShrink: 0 }} />
            <span>FUNC</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--status-red)', flexShrink: 0 }} />
            <span>VULN</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '6px', height: '6px', border: '1px dashed var(--ink-muted)', display: 'inline-block', flexShrink: 0 }} />
            <span>DEAD</span>
          </div>
        </div>
      </div>
    </aside>
  );
};
