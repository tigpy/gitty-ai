import React, { useState, useEffect, useRef } from 'react';
import { TopNav, type NavTab } from '../components/nav/TopNav';
import { RepositorySidebar } from '../components/sidebar/RepositorySidebar';
import { GraphCanvas, type GraphCanvasRef } from '../components/graph/GraphCanvas';
import { GraphToolbar } from '../components/graph/GraphToolbar';
import { NodeInspector } from '../components/graph/NodeInspector';
import { ChatPanel } from '../components/chat/ChatPanel';
import { TelemetryBar } from '../components/common/TelemetryBar';
import { api } from '../services/api';
import type { Repository, GraphNode, GraphEdge, NodeDetails } from '../types';
import { Activity, AlertTriangle, CheckCircle, XCircle, Clock } from 'lucide-react';

// Maps raw SSE message fragments to human-readable stage labels
function deriveStage(msg: string): string {
  const m = msg.toLowerCase();
  if (m.includes('queuing') || m.includes('queued') || m.includes('pipeline task queued') || m.includes('connecting')) return 'Queued';
  if (m.includes('cloning') || m.includes('scanning') || m.includes('scan')) return 'Cloning repository';
  if (m.includes('parsing') || m.includes('parsed') || m.includes('code module')) return 'Parsing source files';
  if (m.includes('building graph') || m.includes('built') || m.includes('generated') || m.includes('nodes')) return 'Building knowledge graph';
  if (m.includes('dead code')) return 'Dead code analysis';
  if (m.includes('security') || m.includes('vulnerability') || m.includes('osv')) return 'Security scanning';
  if (m.includes('vector') || m.includes('embedding') || m.includes('index')) return 'Building vector index';
  if (m.includes('completed') || m.includes('complete')) return 'Completed';
  if (m.includes('failed') || m.includes('error')) return 'Failed';
  return '';
}

const ORDERED_STAGES = [
  'Queued',
  'Cloning repository',
  'Parsing source files',
  'Building knowledge graph',
  'Dead code analysis',
  'Security scanning',
  'Building vector index',
  'Completed',
];

function useElapsedTimer(running: boolean) {
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef<number | null>(null);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (running) {
      startRef.current = Date.now();
      setElapsed(0);
      const tick = () => {
        setElapsed(Math.floor((Date.now() - startRef.current!) / 1000));
        rafRef.current = requestAnimationFrame(tick);
      };
      rafRef.current = requestAnimationFrame(tick);
    } else {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    }
    return () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, [running]);

  return elapsed;
}

export const Dashboard: React.FC = () => {
  const [selectedRepo, setSelectedRepo] = useState<Repository | null>(null);
  const [repos, setRepos] = useState<Repository[]>([]);
  const [loadingRepos, setLoadingRepos] = useState(true);
  
  // Navigation tabs
  const [activeTab, setActiveTab] = useState<NavTab>('GRAPH');

  // Active Analysis State
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisComplete, setAnalysisComplete] = useState(false);
  const [progressLogs, setProgressLogs] = useState<string[]>([]);
  const [currentStage, setCurrentStage] = useState<string>('Queued');
  const [completedStages, setCompletedStages] = useState<Set<string>>(new Set());
  const [analyzingRepoName, setAnalyzingRepoName] = useState('');
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const elapsed = useElapsedTimer(analyzing);

  // Graph rendering lists
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [graphError, setGraphError] = useState<string | null>(null);
  
  // Highlights & Details panel
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [nodeDetails, setNodeDetails] = useState<NodeDetails | null>(null);
  const [highlightedNodeId, setHighlightedNodeId] = useState<string | null>(null);
  const [loadingGraph, setLoadingGraph] = useState(false);
  const [currentZoom, setCurrentZoom] = useState(1);
  const [hasInteracted, setHasInteracted] = useState(false);
  const graphCanvasRef = useRef<GraphCanvasRef | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const pollTimerRef = useRef<number | null>(null);

  // Clean up timers & eventSource on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (pollTimerRef.current !== null) {
        window.clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, []);

  // Overlay Toggles
  const [overlays, setOverlays] = useState({
    security: true,
    deadCode: true,
    smells: true,
    callGraph: false
  });

  // Load repositories on mount
  useEffect(() => {
    setLoadingRepos(true);
    api.getRepositories()
      .then((data) => {
        setRepos(data);
        if (data.length > 0) {
          setSelectedRepo(prev => prev || data[0]);
        }
      })
      .catch(console.error)
      .finally(() => setLoadingRepos(false));
  }, []);

  // Load Graph Data on Repo change
  useEffect(() => {
    if (!selectedRepo) {
      setNodes([]);
      setEdges([]);
      setGraphError(null);
      return;
    }
    
    setLoadingGraph(true);
    setSelectedNode(null);
    setNodeDetails(null);
    setHighlightedNodeId(null);
    setHasInteracted(false);
    setGraphError(null);

    api.getRepositoryGraph(selectedRepo.id)
      .then((data) => {
        setNodes(data.nodes);
        setEdges(data.edges);
      })
      .catch((err) => {
        console.error(err);
        setGraphError(err?.message || 'Failed to load graph data. The backend may be unavailable.');
      })
      .finally(() => setLoadingGraph(false));
  }, [selectedRepo]);

  const handleTabSelect = (tab: NavTab) => {
    setActiveTab(tab);
    if (tab === 'SECURITY') {
      setOverlays(prev => ({ ...prev, security: true }));
    } else if (tab === 'ARCHITECTURE') {
      setOverlays(prev => ({ ...prev, smells: true, callGraph: true }));
    }
  };

  const onSelectRepo = (repo: Repository | null) => {
    setSelectedRepo(repo);
  };

  const handleDeleteRepo = async (repoId: string, name: string) => {
    if (confirm(`Purge repository ${name} from system index?`)) {
      try {
        await api.deleteRepository(repoId);
        const refreshed = await api.getRepositories();
        setRepos(refreshed);
        if (selectedRepo?.id === repoId) {
          setSelectedRepo(refreshed[0] || null);
        }
      } catch (err) {
        console.error('Delete repository failed:', err);
        alert('Failed to delete repository');
      }
    }
  };

  const handleStartAnalyze = async (url: string) => {
    // Prevent duplicate analysis requests
    if (analyzing) return;

    const rawName = url.replace(/\/$/, '').split('/').pop() || 'Repository';
    const cleanRepoName = rawName.replace('.git', '');
    
    setAnalyzingRepoName(cleanRepoName);
    setAnalyzing(true);
    setAnalysisComplete(false);
    setAnalysisError(null);
    setCurrentStage('Queued');
    setCompletedStages(new Set());
    setProgressLogs(['Queuing analysis pipeline task...']);

    if (selectedRepo && selectedRepo.name === cleanRepoName) {
      setSelectedRepo(null);
    }

    // Clean up any existing connection/poll before starting a new one
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (pollTimerRef.current !== null) {
      window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }

    const advanceStage = (msg: string) => {
      const stage = deriveStage(msg);
      if (!stage) return;
      setCurrentStage(stage);
      if (stage !== 'Completed' && stage !== 'Failed') {
        setCompletedStages(prev => {
          const next = new Set(prev);
          // Mark all stages before this one as completed
          const idx = ORDERED_STAGES.indexOf(stage);
          for (let i = 0; i < idx; i++) next.add(ORDERED_STAGES[i]);
          return next;
        });
      }
    };

    const finishAnalysisSuccess = (repoId: string) => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (pollTimerRef.current !== null) {
        window.clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
      setCurrentStage('Completed');
      setCompletedStages(new Set(ORDERED_STAGES.filter(s => s !== 'Completed' && s !== 'Failed')));
      setAnalyzing(false);
      setAnalysisComplete(true);
      setAnalysisError(null);
      api.getRepositories()
        .then((dataList) => {
          setRepos(dataList);
          const found = dataList.find(r => r.id === repoId);
          if (found) {
            setSelectedRepo(found);
          }
        })
        .catch(console.error);
    };

    const finishAnalysisFailure = (errorMessage: string) => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (pollTimerRef.current !== null) {
        window.clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
      setAnalyzing(false);
      setAnalysisError(errorMessage);
    };

    const startStatusPollingFallback = (repoId: string) => {
      if (pollTimerRef.current !== null) return;
      setProgressLogs(prev => [...prev, 'Telemetry stream interrupted. Switching to polling fallback...']);
      let attempts = 0;
      pollTimerRef.current = window.setInterval(async () => {
        attempts++;
        try {
          const statusRes = await api.getRepositoryStatus(repoId);
          if (statusRes.message) {
            setProgressLogs(prev => {
              if (prev[prev.length - 1] !== statusRes.message) {
                return [...prev, statusRes.message!];
              }
              return prev;
            });
            advanceStage(statusRes.message || '');
          }
          if (statusRes.status === 'completed') {
            finishAnalysisSuccess(repoId);
          } else if (statusRes.status === 'failed') {
            finishAnalysisFailure(statusRes.message || 'Analysis failed');
          } else if (attempts >= 120) {
            finishAnalysisFailure('Analysis polling timed out after 4 minutes');
          }
        } catch {
          if (attempts >= 120) {
            finishAnalysisFailure('Lost telemetry connection to analysis service');
          }
        }
      }, 2000);
    };

    try {
      const res = await api.analyzeRepository(url);
      const repoId = res.repository_id;
      
      setProgressLogs(prev => [...prev, 'Pipeline task queued. Stream connecting...']);

      const eventSource = new EventSource(api.getProgressUrl(repoId));
      eventSourceRef.current = eventSource;
      
      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.message) {
            setProgressLogs(prev => [...prev, data.message]);
            advanceStage(data.message);
          }

          if (data.status === 'completed') {
            finishAnalysisSuccess(repoId);
          } else if (data.status === 'failed') {
            finishAnalysisFailure(data.message || 'Analysis failed');
          }
        } catch (e) {
          console.error('Failed to parse SSE event data:', e);
          startStatusPollingFallback(repoId);
        }
      };

      eventSource.onerror = () => {
        if (eventSourceRef.current) {
          eventSourceRef.current.close();
          eventSourceRef.current = null;
        }
        startStatusPollingFallback(repoId);
      };

    } catch (err: any) {
      if (pollTimerRef.current !== null) {
        window.clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
      setAnalyzing(false);
      setAnalysisError(err.message || 'Failed to initialize analysis pipeline');
      setProgressLogs(prev => [...prev, `Error: ${err.message || 'Pipeline failed'}`]);
    }
  };

  const handleSelectNode = async (node: GraphNode | null) => {
    setSelectedNode(node);
    setHighlightedNodeId(null);
    if (!node || !selectedRepo) {
      setNodeDetails(null);
      return;
    }

    try {
      const details = await api.getNodeDetails(node.id, selectedRepo.id);
      setNodeDetails(details);
    } catch (err) {
      console.error(err);
    }
  };

  const handleExpandNode = async (node: GraphNode) => {
    if (!selectedRepo || (node.node_type !== 'FILE' && node.node_type !== 'CLASS')) return;

    try {
      const expansion = await api.expandNode(selectedRepo.id, node.id);
      if (expansion.nodes.length > 0) {
        setNodes((prev) => {
          const existingIds = new Set(prev.map(n => n.id));
          const uniqueNewNodes = expansion.nodes.filter(n => !existingIds.has(n.id));
          return [...prev, ...uniqueNewNodes];
        });
        setEdges((prev) => {
          const existingIds = new Set(prev.map(e => `${e.source}->${e.relationship}->${e.target}`));
          const uniqueNewEdges = expansion.edges.filter(e => !existingIds.has(`${e.source}->${e.relationship}->${e.target}`));
          return [...prev, ...uniqueNewEdges];
        });
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleTriggerCallGraph = async () => {
    if (!selectedNode || !selectedRepo) return;

    try {
      const callGraph = await api.traverseNode(selectedNode.id);
      if (callGraph.nodes.length > 0) {
        setNodes((prev) => {
          const existingIds = new Set(prev.map(n => n.id));
          const uniqueNewNodes = callGraph.nodes.filter(n => !existingIds.has(n.id));
          return [...prev, ...uniqueNewNodes];
        });
        setEdges((prev) => {
          const existingIds = new Set(prev.map(e => `${e.source}->${e.relationship}->${e.target}`));
          const uniqueNewEdges = callGraph.edges.filter(e => !existingIds.has(`${e.source}->${e.relationship}->${e.target}`));
          return [...prev, ...uniqueNewEdges];
        });
        setOverlays(prev => ({ ...prev, callGraph: true }));
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleToggleOverlay = (key: 'security' | 'deadCode' | 'smells' | 'callGraph') => {
    setOverlays(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const handleCitationClick = async (filePath: string, symbolName?: string) => {
    if (!selectedRepo) return;

    let found = nodes.find(n => n.file_path === filePath && (!symbolName || n.label === symbolName));
    
    if (!found) {
      const fileNode = nodes.find(n => n.node_type === 'FILE' && n.file_path === filePath);
      if (fileNode) {
        await handleExpandNode(fileNode);
        found = nodes.find(n => n.file_path === filePath && (!symbolName || n.label === symbolName));
      }
    }

    if (found) {
      setHighlightedNodeId(found.id);
      setSelectedNode(found);
      
      const details = await api.getNodeDetails(found.id, selectedRepo.id);
      setNodeDetails(details);
    }
  };

  const filesCount = nodes.filter(n => n.node_type === 'FILE').length;

  return (
    <div className="app-shell">
      {/* Top Technical Console Navigation */}
      <TopNav
        activeTab={activeTab}
        onSelectTab={handleTabSelect}
        selectedRepo={selectedRepo}
        systemStatus="ONLINE"
      />

      {/* Main Console Body: 3-Column Layout */}
      <main className="console-body">
        {/* Left Explorer & Index Column */}
        <RepositorySidebar
          selectedRepo={selectedRepo}
          onSelectRepo={onSelectRepo}
          nodes={nodes}
          onSelectNode={handleSelectNode}
          selectedNode={selectedNode}
          overlays={overlays}
          onToggleOverlay={handleToggleOverlay}
          repos={repos}
          setRepos={setRepos}
          loadingRepos={loadingRepos}
          analyzing={analyzing}
          onStartAnalyze={handleStartAnalyze}
          onDeleteRepo={handleDeleteRepo}
        />

        {/* Center Graph Workspace */}
        <section 
          className="console-panel"
          style={{
            position: 'relative',
            height: '100%',
            overflow: 'hidden',
            background: 'var(--bg-ground)'
          }}
        >
          {(analyzing || analysisComplete || analysisError) ? (
            /* ── Analysis Pipeline Overlay ────────────────────────────── */
            <div style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'rgba(11, 13, 16, 0.92)',
              backdropFilter: 'blur(4px)',
              zIndex: 30,
              padding: '16px',
            }}>
              <div style={{
                width: '100%',
                maxWidth: '520px',
                background: 'var(--bg-panel)',
                border: `1px solid ${analysisError ? 'rgba(239,68,68,0.4)' : analysisComplete ? 'rgba(61,220,151,0.4)' : 'var(--hairline)'}`,
                borderRadius: '10px',
                overflow: 'hidden',
                boxShadow: '0 24px 64px rgba(0,0,0,0.8)',
              }}>
                {/* Header */}
                <div style={{
                  padding: '14px 18px',
                  borderBottom: '1px solid var(--hairline)',
                  background: 'var(--bg-raised)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                }}>
                  {analysisError ? (
                    <XCircle size={16} style={{ color: 'var(--status-red)', flexShrink: 0 }} />
                  ) : analysisComplete ? (
                    <CheckCircle size={16} style={{ color: 'var(--status-green)', flexShrink: 0 }} />
                  ) : (
                    <span style={{
                      width: '14px', height: '14px', flexShrink: 0,
                      border: '2px solid var(--accent-amber)',
                      borderTopColor: 'transparent',
                      borderRadius: '50%',
                      display: 'inline-block',
                      animation: 'spin 0.8s linear infinite',
                    }} />
                  )}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontFamily: 'var(--font-mono)', fontSize: '13px', fontWeight: 600,
                      color: analysisError ? 'var(--status-red)' : analysisComplete ? 'var(--status-green)' : 'var(--ink-primary)',
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {analysisError ? 'Analysis failed' : analysisComplete ? `${analyzingRepoName} — indexed` : `Indexing: ${analyzingRepoName}`}
                    </div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--ink-muted)', marginTop: '2px' }}>
                      {analysisError
                        ? 'Pipeline halted — see error below'
                        : analysisComplete
                          ? 'Graph is ready to explore'
                          : `Stage: ${currentStage}`}
                    </div>
                  </div>
                  {/* Elapsed timer */}
                  <div style={{
                    display: 'flex', alignItems: 'center', gap: '5px',
                    fontFamily: 'var(--font-mono)', fontSize: '11px',
                    color: 'var(--ink-muted)', flexShrink: 0,
                  }}>
                    <Clock size={11} />
                    <span className="mono-num">{elapsed}s</span>
                  </div>
                </div>

                {/* Stage pipeline — only shown while running or completed */}
                {!analysisError && (
                  <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--hairline)' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      {ORDERED_STAGES.filter(s => s !== 'Failed').map((stage) => {
                        const done = completedStages.has(stage);
                        const active = currentStage === stage && !analysisComplete;
                        return (
                          <div key={stage} style={{
                            display: 'flex', alignItems: 'center', gap: '10px',
                            fontFamily: 'var(--font-mono)', fontSize: '11px',
                          }}>
                            {done || (analysisComplete && stage !== 'Completed') ? (
                              <CheckCircle size={12} style={{ color: 'var(--status-green)', flexShrink: 0 }} />
                            ) : active ? (
                              <span style={{
                                width: '12px', height: '12px', flexShrink: 0,
                                border: '2px solid var(--accent-amber)',
                                borderTopColor: 'transparent',
                                borderRadius: '50%',
                                display: 'inline-block',
                                animation: 'spin 0.8s linear infinite',
                              }} />
                            ) : stage === 'Completed' && analysisComplete ? (
                              <CheckCircle size={12} style={{ color: 'var(--status-green)', flexShrink: 0 }} />
                            ) : (
                              <span style={{
                                width: '12px', height: '12px', flexShrink: 0,
                                border: '1px solid var(--ink-faint)',
                                borderRadius: '50%',
                                display: 'inline-block',
                              }} />
                            )}
                            <span style={{
                              color: (done || (analysisComplete)) ? 'var(--ink-primary)' : active ? 'var(--accent-amber-bright)' : 'var(--ink-muted)',
                              fontWeight: active ? 600 : 400,
                            }}>
                              {stage}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Log stream */}
                <div style={{
                  maxHeight: '160px', overflowY: 'auto',
                  padding: '10px 14px',
                  background: 'var(--bg-ground)',
                  fontFamily: 'var(--font-mono)', fontSize: '10.5px',
                  display: 'flex', flexDirection: 'column', gap: '4px',
                  borderBottom: (analysisComplete || analysisError) ? '1px solid var(--hairline)' : undefined,
                }}>
                  {progressLogs.map((log, idx) => {
                    const isCheck = log.startsWith('✓');
                    const isFail = log.toLowerCase().includes('failed') || log.toLowerCase().startsWith('error');
                    return (
                      <div key={idx} style={{
                        display: 'flex', alignItems: 'baseline', gap: '7px',
                        color: isFail ? 'var(--status-red)' : isCheck ? 'var(--status-green)' : 'var(--ink-secondary)',
                      }}>
                        <span style={{ flexShrink: 0, width: '10px', textAlign: 'center' }}>
                          {isCheck ? '✓' : isFail ? '✗' : '›'}
                        </span>
                        <span>{isCheck ? log.slice(2) : log}</span>
                      </div>
                    );
                  })}
                </div>

                {/* Footer actions */}
                {(analysisComplete || analysisError) && (
                  <div style={{
                    padding: '10px 18px',
                    display: 'flex', justifyContent: 'flex-end', gap: '8px',
                  }}>
                    {analysisError && (
                      <button
                        onClick={() => { setAnalysisError(null); setAnalysisComplete(false); }}
                        className="console-btn"
                        style={{ borderColor: 'var(--status-red)', color: 'var(--status-red)' }}
                        aria-label="Dismiss error"
                      >
                        DISMISS
                      </button>
                    )}
                    {analysisComplete && (
                      <button
                        onClick={() => { setAnalysisComplete(false); }}
                        className="console-btn console-btn-primary"
                        aria-label="View graph"
                      >
                        VIEW GRAPH →
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          ) : loadingGraph ? (
            /* ── Graph loading state ──────────────────────────────────── */
            <div style={{
              position: 'absolute', inset: 0,
              display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center', gap: '12px',
            }}>
              <div style={{
                width: '32px', height: '32px',
                border: '2px solid var(--hairline)',
                borderTopColor: 'var(--accent-amber)',
                borderRadius: '50%',
                animation: 'spin 0.9s linear infinite',
              }} />
              <span style={{
                fontFamily: 'var(--font-mono)', fontSize: '11px',
                color: 'var(--ink-muted)', letterSpacing: '0.08em',
              }}>
                LOADING GRAPH DATA…
              </span>
            </div>
          ) : graphError ? (
            /* ── Graph error state ────────────────────────────────────── */
            <div style={{
              position: 'absolute', inset: 0,
              display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center', gap: '12px',
              padding: '24px',
            }}>
              <AlertTriangle size={32} style={{ color: 'var(--status-red)', opacity: 0.7 }} />
              <div style={{ textAlign: 'center' }}>
                <div style={{
                  fontFamily: 'var(--font-mono)', fontSize: '13px',
                  color: 'var(--ink-primary)', fontWeight: 600, marginBottom: '6px',
                }}>
                  Failed to load graph
                </div>
                <div style={{
                  fontFamily: 'var(--font-mono)', fontSize: '11px',
                  color: 'var(--ink-muted)', maxWidth: '360px', lineHeight: 1.5,
                }}>
                  {graphError}
                </div>
              </div>
              <button
                className="console-btn"
                onClick={() => {
                  if (selectedRepo) {
                    setGraphError(null);
                    setLoadingGraph(true);
                    api.getRepositoryGraph(selectedRepo.id)
                      .then(d => { setNodes(d.nodes); setEdges(d.edges); })
                      .catch(e => setGraphError(e?.message || 'Failed to load graph'))
                      .finally(() => setLoadingGraph(false));
                  }
                }}
                aria-label="Retry loading graph"
              >
                ↺ RETRY
              </button>
            </div>
          ) : !selectedRepo ? (
            /* ── No repo selected ─────────────────────────────────────── */
            <div style={{
              position: 'absolute', inset: 0,
              display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center', gap: '10px',
              color: 'var(--ink-muted)',
            }}>
              <Activity size={28} style={{ color: 'var(--ink-faint)' }} />
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', letterSpacing: '0.06em' }}>
                NO REPOSITORY SELECTED
              </div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--ink-faint)' }}>
                Select a repository from the sidebar or ingest a new one
              </div>
            </div>
          ) : nodes.length === 0 ? (
            /* ── Empty graph ──────────────────────────────────────────── */
            <div style={{
              position: 'absolute', inset: 0,
              display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center', gap: '10px',
              color: 'var(--ink-muted)',
            }}>
              <Activity size={28} style={{ color: 'var(--ink-faint)' }} />
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', letterSpacing: '0.06em' }}>
                GRAPH IS EMPTY
              </div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--ink-faint)' }}>
                {selectedRepo.name} has no indexed nodes yet
              </div>
            </div>
          ) : (
            /* Stable Finite Force-Directed Canvas */
            <GraphCanvas
              ref={graphCanvasRef}
              nodes={nodes}
              edges={edges}
              selectedNode={selectedNode}
              onSelectNode={handleSelectNode}
              onExpandNode={handleExpandNode}
              overlays={overlays}
              highlightedNodeId={highlightedNodeId}
              onZoomChange={setCurrentZoom}
              onInteraction={() => setHasInteracted(true)}
            />
          )}

          {/* Node Inspector HUD Overlay */}
          {selectedNode && (
            <NodeInspector
              node={selectedNode}
              details={nodeDetails}
              edges={edges}
              onClose={() => handleSelectNode(null)}
              onTriggerCallGraph={handleTriggerCallGraph}
            />
          )}

          {/* Bottom Viewport Toolbar */}
          <GraphToolbar
            onZoomIn={() => graphCanvasRef.current?.zoomIn()}
            onZoomOut={() => graphCanvasRef.current?.zoomOut()}
            onReset={() => graphCanvasRef.current?.resetView()}
            nodesCount={nodes.length}
            edgesCount={edges.length}
            status={loadingGraph ? 'COMPUTING' : (nodes.length > 0 ? 'STABLE' : 'READY')}
            hasInteracted={hasInteracted}
          />
        </section>

        {/* Right Assistant Column: GITTY CORE */}
        <ChatPanel
          selectedRepoId={selectedRepo?.id}
          selectedNode={selectedNode}
          onCitationClick={handleCitationClick}
          analyzing={analyzing}
        />
      </main>

      {/* Bottom Telemetry Status Strip */}
      <TelemetryBar
        nodesCount={nodes.length}
        edgesCount={edges.length}
        filesCount={filesCount}
        status={loadingGraph ? 'COMPUTING' : (nodes.length > 0 ? 'STABLE' : 'IDLE')}
        zoomLevel={currentZoom}
        repoName={selectedRepo?.name}
      />
    </div>
  );
};

export default Dashboard;
