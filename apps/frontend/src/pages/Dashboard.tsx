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
import { Activity, AlertTriangle } from 'lucide-react';

export const Dashboard: React.FC = () => {
  const [selectedRepo, setSelectedRepo] = useState<Repository | null>(null);
  const [repos, setRepos] = useState<Repository[]>([]);
  const [loadingRepos, setLoadingRepos] = useState(true);
  
  // Navigation tabs
  const [activeTab, setActiveTab] = useState<NavTab>('GRAPH');

  // Active Analysis State
  const [analyzing, setAnalyzing] = useState(false);
  const [progressLogs, setProgressLogs] = useState<string[]>([]);
  const [analyzingRepoName, setAnalyzingRepoName] = useState('');
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  // Graph rendering lists
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  
  // Highlights & Details panel
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [nodeDetails, setNodeDetails] = useState<NodeDetails | null>(null);
  const [highlightedNodeId, setHighlightedNodeId] = useState<string | null>(null);
  const [loadingGraph, setLoadingGraph] = useState(false);
  const [currentZoom, setCurrentZoom] = useState(1);
  const [hasInteracted, setHasInteracted] = useState(false);
  const graphCanvasRef = useRef<GraphCanvasRef | null>(null);

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
      return;
    }
    
    setLoadingGraph(true);
    setSelectedNode(null);
    setNodeDetails(null);
    setHighlightedNodeId(null);
    setHasInteracted(false);

    api.getRepositoryGraph(selectedRepo.id)
      .then((data) => {
        setNodes(data.nodes);
        setEdges(data.edges);
      })
      .catch(console.error)
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
    setAnalysisError(null);
    setProgressLogs(['Queuing analysis pipeline task...']);

    if (selectedRepo && selectedRepo.name === cleanRepoName) {
      setSelectedRepo(null);
    }

    try {
      const res = await api.analyzeRepository(url);
      const repoId = res.repository_id;
      
      setProgressLogs(prev => [...prev, 'Pipeline task queued. Stream connecting...']);

      const eventSource = new EventSource(api.getProgressUrl(repoId));
      
      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setProgressLogs(prev => [...prev, data.message]);

          if (data.status === 'completed') {
            eventSource.close();
            setAnalyzing(false);
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
          } else if (data.status === 'failed') {
            eventSource.close();
            setAnalyzing(false);
            setAnalysisError(data.message || 'Analysis failed');
          }
        } catch (e) {
          console.error('Failed to parse SSE event data:', e);
          eventSource.close();
          setAnalyzing(false);
          setAnalysisError('Failed to parse analysis stream');
          setProgressLogs(prev => [...prev, 'Failed to parse stream data']);
        }
      };

      eventSource.onerror = () => {
        eventSource.close();
        setAnalyzing(false);
        setAnalysisError('Event stream disconnected');
        setProgressLogs(prev => [...prev, 'Error: Telemetry stream disconnected']);
      };

    } catch (err: any) {
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
          {(analyzing || analysisError) ? (
            /* Analysis Pipeline Overlay */
            <div style={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              width: '90%',
              maxWidth: '520px',
              background: 'var(--bg-panel)',
              border: '1px solid var(--hairline)',
              borderRadius: '8px',
              padding: '24px',
              boxShadow: '0 16px 48px rgba(0, 0, 0, 0.8)',
              zIndex: 30,
              display: 'flex',
              flexDirection: 'column',
              gap: '16px'
            }}>
              <div style={{ borderBottom: '1px solid var(--hairline)', paddingBottom: '12px' }}>
                <div className="tech-label" style={{ marginBottom: '4px' }}>
                  {analysisError ? 'ANALYSIS PIPELINE FAILURE' : 'REPOSITORY ANALYSIS IN PROGRESS'}
                </div>
                <h2 style={{
                  margin: 0,
                  fontSize: '15px',
                  fontFamily: 'var(--font-mono)',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  color: analysisError ? 'var(--status-red)' : 'var(--ink-primary)'
                }}>
                  {analysisError ? (
                    <AlertTriangle size={16} style={{ color: 'var(--status-red)' }} />
                  ) : (
                    <span 
                      style={{
                        width: '14px',
                        height: '14px',
                        border: '2px solid var(--accent-amber)',
                        borderTopColor: 'transparent',
                        borderRadius: '50%',
                        display: 'inline-block',
                        animation: 'spin 0.8s linear infinite'
                      }}
                    />
                  )}
                  {analysisError ? 'Analysis Pipeline Halted' : `Indexing: ${analyzingRepoName}`}
                </h2>
                <p style={{ margin: '6px 0 0 0', fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--ink-muted)' }}>
                  {analysisError ? analysisError : 'Parsing symbols, ast call relationships, and security heuristics...'}
                </p>
              </div>

              <div style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
                fontFamily: 'var(--font-mono)',
                fontSize: '11px',
                maxHeight: '220px',
                overflowY: 'auto',
                background: 'var(--bg-ground)',
                border: '1px solid var(--hairline)',
                padding: '10px 12px',
                borderRadius: '6px'
              }}>
                {progressLogs.map((log, idx) => {
                  const isCheck = log.startsWith('✓');
                  const isFailed = log.toLowerCase().includes('failed') || log.startsWith('Error');
                  return (
                    <div 
                      key={idx}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        color: isFailed ? 'var(--status-red)' : (isCheck ? 'var(--status-green)' : 'var(--ink-secondary)')
                      }}
                    >
                      <span>{isCheck ? '✓' : isFailed ? '✗' : '›'}</span>
                      <span>{isCheck ? log.substring(2) : log}</span>
                    </div>
                  );
                })}
              </div>

              {analysisError && (
                <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: '6px' }}>
                  <button
                    onClick={() => {
                      setAnalysisError(null);
                    }}
                    className="console-btn"
                    style={{ borderColor: 'var(--status-red)', color: 'var(--status-red)' }}
                  >
                    DISMISS ERROR
                  </button>
                </div>
              )}
            </div>
          ) : loadingGraph ? (
            /* Visual Graph Loading State */
            <div style={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              fontFamily: 'var(--font-mono)',
              fontSize: '12px',
              color: 'var(--ink-muted)'
            }}>
              <Activity size={16} style={{ color: 'var(--accent-amber)', animation: 'spin 1.5s linear infinite' }} />
              <span>COMPUTING GRAPH MATRIX VIEWPORT...</span>
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
