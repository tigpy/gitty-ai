import React, { useState, useEffect } from 'react';
import { RepositorySidebar } from '../components/sidebar/RepositorySidebar';
import { GraphCanvas } from '../components/graph/GraphCanvas';
import { GraphToolbar } from '../components/graph/GraphToolbar';
import { ChatPanel } from '../components/chat/ChatPanel';
import { api } from '../services/api';
import type { Repository, GraphNode, GraphEdge, NodeDetails } from '../types';
import { 
  FileText, 
  ShieldAlert, 
  X,
  Plus
} from 'lucide-react';

export const Dashboard: React.FC = () => {
  const [selectedRepo, setSelectedRepo] = useState<Repository | null>(null);
  const [repos, setRepos] = useState<Repository[]>([]);
  const [loadingRepos, setLoadingRepos] = useState(true);
  
  // Active Analysis State
  const [analyzing, setAnalyzing] = useState(false);
  const [progressLogs, setProgressLogs] = useState<string[]>([]);
  const [analyzingRepoName, setAnalyzingRepoName] = useState('');

  // Graph rendering lists
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  
  // Highlights & Details panel
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [nodeDetails, setNodeDetails] = useState<NodeDetails | null>(null);
  const [highlightedNodeId, setHighlightedNodeId] = useState<string | null>(null);
  const [loadingGraph, setLoadingGraph] = useState(false);

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
        if (data.length > 0 && !selectedRepo) {
          setSelectedRepo(data[0]);
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

    api.getRepositoryGraph(selectedRepo.id)
      .then((data) => {
        setNodes(data.nodes);
        setEdges(data.edges);
      })
      .catch(console.error)
      .finally(() => setLoadingGraph(false));
  }, [selectedRepo]);

  const handleStartAnalyze = async (url: string) => {
    const rawName = url.replace(/\/$/, '').split('/').pop() || 'Repository';
    const cleanRepoName = rawName.replace('.git', '');
    
    setAnalyzingRepoName(cleanRepoName);
    setAnalyzing(true);
    setProgressLogs(['Queueing analysis task...']);

    // Clear stale state if we are re-indexing the currently selected repository
    if (selectedRepo && selectedRepo.name === cleanRepoName) {
      setSelectedRepo(null);
    }

    try {
      const res = await api.analyzeRepository(url);
      const repoId = res.repository_id;
      
      setProgressLogs(prev => [...prev, 'Analysis task queued successfully. Connecting live stream...']);

      // Setup Server-Sent Events (SSE)
      const eventSource = new EventSource(`http://localhost:8000/api/v1/repositories/${repoId}/progress`);
      
      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setProgressLogs(prev => [...prev, data.message]);

          if (data.status === 'completed') {
            eventSource.close();
            setAnalyzing(false);
            
            // Reload repositories and select the new one
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
          }
        } catch (e) {
          eventSource.close();
          setAnalyzing(false);
          setProgressLogs(prev => [...prev, 'Failed to parse live log data']);
        }
      };

      eventSource.onerror = () => {
        eventSource.close();
        setAnalyzing(false);
        setProgressLogs(prev => [...prev, 'Error: Event stream disconnected']);
      };

    } catch (err: any) {
      setAnalyzing(false);
      alert(err.message || 'Failed to start analysis');
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

  // Traversal Call graph overlay loader
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

  return (
    <div className="app-container">
      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        @keyframes pulse {
          0%, 100% { opacity: 0.3; }
          50% { opacity: 1; }
        }
      `}</style>

      {/* Sidebar selection */}
      <RepositorySidebar
        selectedRepo={selectedRepo}
        onSelectRepo={setSelectedRepo}
        nodes={nodes}
        onSelectNode={handleSelectNode}
        overlays={overlays}
        onToggleOverlay={handleToggleOverlay}
        repos={repos}
        setRepos={setRepos}
        loadingRepos={loadingRepos}
        analyzing={analyzing}
        onStartAnalyze={handleStartAnalyze}
      />

      {/* Main Graph Canvas Area */}
      <div className="glass-panel" style={{ position: 'relative', height: '100%', overflow: 'hidden' }}>
        {analyzing ? (
          <div style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            width: '85%',
            maxWidth: '500px',
            background: 'rgba(10, 11, 18, 0.95)',
            border: '1px solid rgba(129, 140, 248, 0.25)',
            borderRadius: '16px',
            padding: '30px',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.6)',
            color: '#ffffff',
            display: 'flex',
            flexDirection: 'column',
            gap: '20px'
          }}>
            <div style={{ borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '15px' }}>
              <h2 style={{ margin: 0, fontSize: '1.25rem', fontFamily: 'Outfit', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ 
                  width: '18px', 
                  height: '18px', 
                  border: '2px solid #818cf8', 
                  borderTopColor: 'transparent', 
                  borderRadius: '50%', 
                  display: 'inline-block', 
                  animation: 'spin 1s linear infinite' 
                }} />
                Analyzing {analyzingRepoName}...
              </h2>
              <p style={{ margin: '6px 0 0 0', fontSize: '0.8rem', color: 'rgba(255,255,255,0.45)' }}>
                Please wait while Gitty parses and indexes the codebase.
              </p>
            </div>
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '10px',
              fontFamily: 'monospace',
              fontSize: '0.85rem',
              maxHeight: '260px',
              overflowY: 'auto',
              paddingRight: '6px'
            }}>
              {progressLogs.map((log, idx) => {
                const isCheck = log.startsWith('✓');
                const isFailed = log.toLowerCase().includes('failed') || log.startsWith('Error');
                return (
                  <div key={idx} style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: '8px',
                    color: isFailed ? '#ef4444' : (isCheck ? '#34d399' : 'rgba(255,255,255,0.85)')
                  }}>
                    {isCheck ? (
                      <span style={{ color: '#34d399', fontWeight: 'bold' }}>✓</span>
                    ) : (
                      isFailed ? (
                        <span style={{ color: '#ef4444', fontWeight: 'bold' }}>✗</span>
                      ) : (
                        <span style={{ 
                          width: '5px', 
                          height: '5px', 
                          borderRadius: '50%', 
                          background: '#818cf8', 
                          display: 'inline-block',
                          animation: 'pulse 1.5s infinite'
                        }} />
                      )
                    )}
                    <span>{isCheck ? log.substring(2) : log}</span>
                  </div>
                );
              })}
            </div>
          </div>
        ) : loadingGraph ? (
          <div style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            fontSize: '1rem',
            color: 'rgba(255,255,255,0.6)'
          }}>
            Loading visual graph...
          </div>
        ) : (
          <GraphCanvas
            nodes={nodes}
            edges={edges}
            selectedNode={selectedNode}
            onSelectNode={handleSelectNode}
            onExpandNode={handleExpandNode}
            overlays={overlays}
            highlightedNodeId={highlightedNodeId}
          />
        )}

        <GraphToolbar
          onZoomIn={() => {}}
          onZoomOut={() => {}}
          onReset={() => {}}
          nodesCount={nodes.length}
          edgesCount={edges.length}
        />

        {/* Node Details Overlay Panel Card */}
        {nodeDetails && (
          <div className="glass-panel" style={{
            position: 'absolute',
            top: '20px',
            left: '20px',
            width: '320px',
            maxHeight: '350px',
            overflowY: 'auto',
            padding: '16px',
            zIndex: 10,
            background: 'rgba(11, 12, 16, 0.85)',
            border: '1px solid rgba(255, 255, 255, 0.1)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
              <FileText size={16} style={{ color: '#818cf8' }} />
              <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600, fontFamily: 'Outfit' }}>{nodeDetails.name}</h3>
              <button 
                onClick={() => handleSelectNode(null)} 
                style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'rgba(255,255,255,0.4)', cursor: 'pointer', padding: 0 }}
              >
                <X size={14} />
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.8rem', color: 'rgba(255,255,255,0.7)' }}>
              <div>Type: <strong style={{ color: '#ffffff' }}>{nodeDetails.type}</strong></div>
              {nodeDetails.file_path && (
                <div style={{ wordBreak: 'break-all' }}>Path: <strong style={{ color: '#ffffff' }}>{nodeDetails.file_path}</strong></div>
              )}
              {nodeDetails.start_line !== undefined && (
                <div>Lines: <strong style={{ color: '#ffffff' }}>{nodeDetails.start_line}-{nodeDetails.end_line}</strong></div>
              )}

              {/* Status Indicator Badges */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '6px' }}>
                {nodeDetails.dead_code && (
                  <span className="badge badge-dead">Dead Code</span>
                )}
                {nodeDetails.architecture_smell && (
                  <span className="badge badge-smell">Architecture Smell</span>
                )}
              </div>

              {/* Security Vulnerabilities */}
              {nodeDetails.security_findings.length > 0 && (
                <div style={{ marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <span style={{ fontSize: '0.72rem', color: '#ef4444', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <ShieldAlert size={12} /> SECURITY ISSUES DETECTED
                  </span>
                  {nodeDetails.security_findings.map((fnd) => (
                    <div 
                      key={fnd.id} 
                      style={{ 
                        background: 'rgba(239, 68, 68, 0.05)', 
                        border: '1px solid rgba(239, 68, 68, 0.2)', 
                        borderRadius: '6px', 
                        padding: '6px 8px',
                        fontSize: '0.75rem',
                        lineHeight: '1.3'
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
                        <span className={`badge badge-${fnd.severity.toLowerCase()}`} style={{ fontSize: '0.6rem', padding: '1px 3px' }}>{fnd.severity}</span>
                        <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.7rem' }}>Line: {fnd.line_number}</span>
                      </div>
                      <div style={{ color: 'rgba(255,255,255,0.8)' }}>{fnd.description}</div>
                    </div>
                  ))}
                </div>
              )}

              {/* Call graph traversal action */}
              {nodeDetails.type === 'FUNCTION' && (
                <button 
                  onClick={handleTriggerCallGraph}
                  className="glass-btn"
                  style={{ marginTop: '10px', fontSize: '0.75rem', padding: '6px 12px', justifyContent: 'center' }}
                >
                  <Plus size={12} /> Highlight Call Graph
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Right Assistant Panel */}
      <ChatPanel
        selectedRepoId={selectedRepo?.id}
        selectedNode={selectedNode}
        onCitationClick={handleCitationClick}
      />
    </div>
  );
};
export default Dashboard;
