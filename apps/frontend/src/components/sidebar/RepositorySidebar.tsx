import React, { useState } from 'react';
import { api } from '../../services/api';
import type { Repository, GraphNode } from '../../types';
import { 
  Folder, 
  ShieldAlert, 
  Trash2, 
  GitFork, 
  Search, 
  Info,
  TrendingDown
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
}

export const RepositorySidebar: React.FC<SidebarProps> = ({
  selectedRepo,
  onSelectRepo,
  nodes,
  onSelectNode,
  overlays,
  onToggleOverlay,
  repos,
  setRepos,
  loadingRepos,
  analyzing,
  onStartAnalyze,
}) => {
  const [urlInput, setUrlInput] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  const handleAnalyzeClick = () => {
    if (!urlInput.trim()) return;
    onStartAnalyze(urlInput.trim());
    setUrlInput('');
  };

  const handleDelete = async (repoId: string, name: string) => {
    if (confirm(`Are you sure you want to delete ${name}?`)) {
      try {
        await api.deleteRepository(repoId);
        const refreshed = await api.getRepositories();
        setRepos(refreshed);
        if (selectedRepo?.id === repoId) {
          if (refreshed.length > 0) {
            onSelectRepo(refreshed[0]);
          } else {
            onSelectRepo(null);
          }
        }
      } catch (err) {
        alert('Failed to delete repository');
      }
    }
  };

  const files = nodes.filter(n => n.node_type === 'FILE');
  const filteredFiles = files.filter(f => 
    f.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (f.file_path && f.file_path.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  return (
    <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Brand Header */}
      <div style={{ padding: '20px 16px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <h1 style={{ 
          margin: 0, 
          fontFamily: 'Outfit', 
          fontSize: '1.5rem', 
          fontWeight: 800, 
          background: 'linear-gradient(90deg, #818cf8 0%, #c084fc 100%)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <GitFork style={{ color: '#818cf8' }} /> Gitty AI
        </h1>
        <span style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.4)', fontWeight: 500 }}>REPOSITORY INTELLIGENCE v10.0</span>
      </div>

      {/* Analyze Repository Section */}
      <div style={{ padding: '16px 12px 12px 12px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <label style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.4)', fontWeight: 600, display: 'block', marginBottom: '8px', textTransform: 'uppercase' }}>Analyze Repository</label>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <input 
            type="text" 
            placeholder="https://github.com/owner/repo"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            disabled={analyzing}
            className="glass-input"
            style={{ width: '100%', fontSize: '0.85rem' }}
          />
          <button
            onClick={handleAnalyzeClick}
            disabled={analyzing || !urlInput.trim()}
            className="glass-btn active"
            style={{ 
              width: '100%', 
              justifyContent: 'center', 
              fontSize: '0.85rem', 
              padding: '8px',
              background: 'linear-gradient(90deg, #818cf8 0%, #c084fc 100%)',
              border: 'none',
              color: '#ffffff',
              cursor: analyzing || !urlInput.trim() ? 'not-allowed' : 'pointer',
              opacity: analyzing || !urlInput.trim() ? 0.6 : 1
            }}
          >
            {analyzing ? 'Analyzing...' : 'Analyze'}
          </button>
        </div>
      </div>

      {/* Repositories List Section */}
      <div style={{ padding: '16px 12px 8px 12px', borderBottom: '1px solid rgba(255,255,255,0.06)', maxHeight: '160px', overflowY: 'auto' }}>
        <label style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.4)', fontWeight: 600, display: 'block', marginBottom: '8px', textTransform: 'uppercase' }}>Repositories</label>
        {loadingRepos ? (
          <div style={{ color: 'rgba(255,255,255,0.5)', fontSize: '0.8rem' }}>Loading repositories...</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {repos.map(r => (
              <div 
                key={r.id}
                onClick={() => onSelectRepo(r)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '6px 8px',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  background: selectedRepo?.id === r.id ? 'rgba(129, 140, 248, 0.15)' : 'rgba(255,255,255,0.02)',
                  border: selectedRepo?.id === r.id ? '1px solid rgba(129, 140, 248, 0.3)' : '1px solid transparent',
                  color: selectedRepo?.id === r.id ? '#ffffff' : 'rgba(255,255,255,0.7)',
                  transition: 'all 0.15s ease'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', overflow: 'hidden' }}>
                  <span style={{ 
                    width: '6px', 
                    height: '6px', 
                    borderRadius: '50%', 
                    background: selectedRepo?.id === r.id ? '#818cf8' : 'rgba(255,255,255,0.4)', 
                    display: 'inline-block',
                    flexShrink: 0
                  }} />
                  <span style={{ fontSize: '0.8rem', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>{r.name}</span>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(r.id, r.name);
                  }}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'rgba(239, 68, 68, 0.6)',
                    cursor: 'pointer',
                    padding: '2px',
                    display: 'flex',
                    alignItems: 'center'
                  }}
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
            {repos.length === 0 && (
              <div style={{ color: 'rgba(255,255,255,0.3)', fontSize: '0.75rem', textAlign: 'center' }}>No repositories found</div>
            )}
          </div>
        )}
      </div>

      {/* Overlay Toggles */}
      <div style={{ padding: '12px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <label style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.4)', fontWeight: 600, display: 'block', marginBottom: '8px', textTransform: 'uppercase' }}>Graph Overlays</label>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
          <button 
            className={`glass-btn ${overlays.security ? 'active' : ''}`}
            onClick={() => onToggleOverlay('security')}
            style={{ fontSize: '0.75rem', padding: '6px 8px', justifyContent: 'center' }}
          >
            <ShieldAlert size={14} /> Security
          </button>
          <button 
            className={`glass-btn ${overlays.deadCode ? 'active' : ''}`}
            onClick={() => onToggleOverlay('deadCode')}
            style={{ fontSize: '0.75rem', padding: '6px 8px', justifyContent: 'center' }}
          >
            <Trash2 size={14} /> Dead Code
          </button>
          <button 
            className={`glass-btn ${overlays.smells ? 'active' : ''}`}
            onClick={() => onToggleOverlay('smells')}
            style={{ fontSize: '0.75rem', padding: '6px 8px', justifyContent: 'center', gridColumn: 'span 2' }}
          >
            <TrendingDown size={14} /> Architecture Smells
          </button>
        </div>
      </div>

      {/* File Search */}
      <div style={{ padding: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <div style={{ position: 'relative' }}>
          <Search size={14} style={{ position: 'absolute', left: '10px', top: '11px', color: 'rgba(255,255,255,0.4)' }} />
          <input 
            type="text" 
            placeholder="Search files..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="glass-input"
            style={{ width: '100%', paddingLeft: '30px', fontSize: '0.85rem' }}
          />
        </div>
      </div>

      {/* Files List */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '0 12px 12px 12px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {filteredFiles.map(f => (
            <div 
              key={f.id}
              onClick={() => onSelectNode(f)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 8px',
                borderRadius: '6px',
                cursor: 'pointer',
                background: 'rgba(255,255,255,0.01)',
                border: '1px solid transparent',
                transition: 'all 0.15s ease'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(255,255,255,0.04)';
                e.currentTarget.style.borderColor = 'rgba(255,255,255,0.05)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(255,255,255,0.01)';
                e.currentTarget.style.borderColor = 'transparent';
              }}
            >
              <Folder size={14} style={{ color: '#60a5fa', flexShrink: 0 }} />
              <span style={{ 
                fontSize: '0.85rem', 
                whiteSpace: 'nowrap', 
                overflow: 'hidden', 
                textOverflow: 'ellipsis',
                color: f.dead_code ? 'rgba(255,255,255,0.3)' : 'rgba(255,255,255,0.85)'
              }}>
                {f.label}
              </span>
              {f.security_score !== undefined && f.security_score !== null && f.security_score < 100 && (
                <span 
                  className="badge badge-critical" 
                  style={{ marginLeft: 'auto', fontSize: '0.65rem', padding: '1px 4px' }}
                >
                  {f.security_score}
                </span>
              )}
            </div>
          ))}
          {filteredFiles.length === 0 && (
            <div style={{ color: 'rgba(255,255,255,0.3)', fontSize: '0.85rem', textAlign: 'center', marginTop: '20px' }}>
              No files found
            </div>
          )}
        </div>
      </div>

      {/* Visual Legend */}
      <div style={{ 
        padding: '12px', 
        borderTop: '1px solid rgba(255,255,255,0.06)', 
        background: 'rgba(255,255,255,0.01)',
        fontSize: '0.75rem',
        color: 'rgba(255,255,255,0.5)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '8px', fontWeight: 600 }}>
          <Info size={12} /> Visual Legend
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#6366f1', display: 'inline-block' }} /> Repo
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#3b82f6', display: 'inline-block' }} /> File
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#06b6d4', display: 'inline-block' }} /> Class
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10b981', display: 'inline-block' }} /> Function
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#ef4444', display: 'inline-block' }} /> Risk
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '2px', border: '1px dashed #9ca3af', display: 'inline-block' }} /> Dead Code
          </div>
        </div>
      </div>
    </div>
  );
};
