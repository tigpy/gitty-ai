import React, { useEffect, useRef, useState, useMemo, useImperativeHandle, forwardRef, useCallback } from 'react';
import type { GraphNode, GraphEdge } from '../../types';

export interface GraphCanvasRef {
  zoomIn: () => void;
  zoomOut: () => void;
  resetView: () => void;
}

interface GraphCanvasProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNode: GraphNode | null;
  onSelectNode: (node: GraphNode | null) => void;
  onExpandNode: (node: GraphNode) => void;
  overlays: {
    security: boolean;
    deadCode: boolean;
    smells: boolean;
    callGraph: boolean;
  };
  highlightedNodeId?: string | null;
  onZoomChange?: (zoom: number) => void;
  onInteraction?: () => void;
}

interface SimNode extends GraphNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
  fx?: number;
  fy?: number;
}

const getNodeRadius = (type: string): number => {
  switch (type) {
    case 'REPOSITORY': return 25;
    case 'FILE': return 12;
    case 'CLASS': return 8;
    case 'FUNCTION': return 6;
    case 'IMPORT': return 5;
    case 'CALL': return 4;
    case 'SECURITY_FINDING': return 9;
    default: return 6;
  }
};

const getNodeColor = (type: string): string => {
  switch (type) {
    case 'REPOSITORY': return '#4f46e5'; // Deep Indigo
    case 'FILE': return '#2563eb';       // Blue
    case 'CLASS': return '#0891b2';      // Cyan
    case 'FUNCTION': return '#94a3b8';   // Technical Slate (replaces green to reserve green strictly for system state)
    case 'IMPORT': return '#8b5cf6';     // Purple
    case 'CALL': return '#f59e0b';       // Amber
    case 'SECURITY_FINDING': return '#dc2626'; // Red
    default: return '#6b7280';
  }
};

const computeFitView = (
  nodes: SimNode[],
  canvasWidth: number,
  canvasHeight: number,
  padding: number = 60
): { zoom: number; pan: { x: number; y: number } } => {
  if (nodes.length === 0 || canvasWidth <= 0 || canvasHeight <= 0) {
    return { zoom: 1, pan: { x: canvasWidth / 2, y: canvasHeight / 2 } };
  }

  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;

  for (const node of nodes) {
    const r = getNodeRadius(node.node_type) + 24;
    if (node.x - r < minX) minX = node.x - r;
    if (node.x + r > maxX) maxX = node.x + r;
    if (node.y - r < minY) minY = node.y - r;
    if (node.y + r > maxY) maxY = node.y + r;
  }

  const graphWidth = Math.max(maxX - minX, 100);
  const graphHeight = Math.max(maxY - minY, 100);
  const centerX = (minX + maxX) / 2;
  const centerY = (minY + maxY) / 2;

  const availWidth = Math.max(canvasWidth - padding * 2, 100);
  const availHeight = Math.max(canvasHeight - padding * 2, 100);

  const zoomX = availWidth / graphWidth;
  const zoomY = availHeight / graphHeight;
  const fitZoom = Math.max(0.15, Math.min(Math.min(zoomX, zoomY), 1.25));

  const panX = canvasWidth / 2 - fitZoom * centerX;
  const panY = canvasHeight / 2 - fitZoom * centerY;

  return { zoom: fitZoom, pan: { x: panX, y: panY } };
};

type SimStage = 'INITIALIZING' | 'WARMUP' | 'SETTLING' | 'STABLE';

const warmupSimulation = (nodes: SimNode[], edges: GraphEdge[], iterations: number = 90) => {
  if (nodes.length === 0) return;

  const kLink = 0.04;
  const dLink = 140;
  const kRepulsion = 1500;
  const kGravity = 0.012;
  const friction = 0.85;

  const nodeMap = new Map<string, SimNode>();
  for (let i = 0; i < nodes.length; i++) {
    nodeMap.set(nodes[i].id, nodes[i]);
  }

  let alpha = 1.0;
  const alphaDecay = Math.pow(0.15 / 1.0, 1 / iterations);

  for (let step = 0; step < iterations; step++) {
    alpha *= alphaDecay;

    // 1. Repulsion force between all node pairs
    for (let i = 0; i < nodes.length; i++) {
      const n1 = nodes[i];
      for (let j = i + 1; j < nodes.length; j++) {
        const n2 = nodes[j];
        const dx = n2.x - n1.x;
        const dy = n2.y - n1.y;
        const distSq = dx * dx + dy * dy + 0.1;
        const dist = Math.sqrt(distSq);

        if (dist < 400) {
          const force = (kRepulsion / distSq) * alpha;
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          n1.vx -= fx;
          n1.vy -= fy;
          n2.vx += fx;
          n2.vy += fy;
        }
      }
    }

    // 2. Link Spring forces
    for (let i = 0; i < edges.length; i++) {
      const edge = edges[i];
      const sNode = nodeMap.get(edge.source);
      const tNode = nodeMap.get(edge.target);
      if (sNode && tNode) {
        const dx = tNode.x - sNode.x;
        const dy = tNode.y - sNode.y;
        const dist = Math.sqrt(dx * dx + dy * dy) + 0.1;
        const displacement = dist - dLink;
        const force = displacement * kLink * alpha;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        sNode.vx += fx;
        sNode.vy += fy;
        tNode.vx -= fx;
        tNode.vy -= fy;
      }
    }

    // 3. Gravity towards (0, 0) and damping
    for (let i = 0; i < nodes.length; i++) {
      const node = nodes[i];
      node.vx += (0 - node.x) * kGravity * alpha;
      node.vy += (0 - node.y) * kGravity * alpha;
      node.x += node.vx;
      node.y += node.vy;
      node.vx *= friction;
      node.vy *= friction;
    }
  }

  // Zero out velocities after warmup
  for (let i = 0; i < nodes.length; i++) {
    nodes[i].vx = 0;
    nodes[i].vy = 0;
  }
};

export const GraphCanvas = forwardRef<GraphCanvasRef, GraphCanvasProps>(({
  nodes,
  edges,
  selectedNode,
  onSelectNode,
  onExpandNode,
  overlays,
  highlightedNodeId,
  onZoomChange,
  onInteraction,
}, ref) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const [simNodes, setSimNodes] = useState<SimNode[]>([]);
  const simNodesRef = useRef<SimNode[]>([]);
  simNodesRef.current = simNodes;

  const simStageRef = useRef<SimStage>('INITIALIZING');
  const alphaRef = useRef<number>(1.0);
  const nodeMapRef = useRef<Map<string, SimNode>>(new Map());

  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);

  // Deterministic node degree & importance ranking
  const { degreeMap, rankedNodes } = useMemo(() => {
    const degMap = new Map<string, number>();
    for (let i = 0; i < edges.length; i++) {
      const e = edges[i];
      degMap.set(e.source, (degMap.get(e.source) || 0) + 1);
      degMap.set(e.target, (degMap.get(e.target) || 0) + 1);
    }

    const getNodeScore = (n: SimNode) => {
      let score = 0;
      const deg = degMap.get(n.id) || 0;
      if (n.node_type === 'REPOSITORY') score += 10000;
      else if (n.node_type === 'FILE') score += 5000 + deg * 10;
      else if (n.node_type === 'CLASS') score += 2000 + deg * 10;
      else if (n.node_type === 'SECURITY_FINDING') score += 1500;
      else score += deg * 5;

      if (n.security_score !== null && n.security_score !== undefined && n.security_score < 100) {
        score += 800;
      }
      return score;
    };

    const ranked = [...simNodes].sort((a, b) => {
      const diff = getNodeScore(b) - getNodeScore(a);
      if (diff !== 0) return diff;
      return a.id.localeCompare(b.id);
    });

    return { degreeMap: degMap, rankedNodes: ranked };
  }, [simNodes, edges]);

  useEffect(() => {
    onZoomChange?.(zoom);
  }, [zoom, onZoomChange]);

  const hasUserInteractedRef = useRef(false);

  const isDraggingViewportRef = useRef(false);
  const dragStartRef = useRef({ x: 0, y: 0 });

  const draggedNodeRef = useRef<SimNode | null>(null);
  const lastClickRef = useRef<{ time: number; nodeId: string }>({ time: 0, nodeId: '' });

  const fitToGraph = useCallback((nodesToFit = simNodesRef.current) => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    const width = canvas?.width || container?.clientWidth || 0;
    const height = canvas?.height || container?.clientHeight || 0;

    if (nodesToFit.length === 0 || width <= 0 || height <= 0) return;

    const { zoom: fitZoom, pan: fitPan } = computeFitView(nodesToFit, width, height);
    setZoom(fitZoom);
    setPan(fitPan);
  }, []);

  useImperativeHandle(ref, () => ({
    zoomIn: () => {
      hasUserInteractedRef.current = true;
      const canvas = canvasRef.current;
      const cx = canvas ? canvas.width / 2 : window.innerWidth / 2;
      const cy = canvas ? canvas.height / 2 : window.innerHeight / 2;
      setZoom((prevZoom) => {
        const newZoom = Math.min(prevZoom * 1.25, 4);
        const scale = newZoom / prevZoom;
        setPan((prevPan) => ({
          x: cx - (cx - prevPan.x) * scale,
          y: cy - (cy - prevPan.y) * scale,
        }));
        return newZoom;
      });
    },
    zoomOut: () => {
      hasUserInteractedRef.current = true;
      const canvas = canvasRef.current;
      const cx = canvas ? canvas.width / 2 : window.innerWidth / 2;
      const cy = canvas ? canvas.height / 2 : window.innerHeight / 2;
      setZoom((prevZoom) => {
        const newZoom = Math.max(prevZoom / 1.25, 0.15);
        const scale = newZoom / prevZoom;
        setPan((prevPan) => ({
          x: cx - (cx - prevPan.x) * scale,
          y: cy - (cy - prevPan.y) * scale,
        }));
        return newZoom;
      });
    },
    resetView: () => {
      hasUserInteractedRef.current = false;
      fitToGraph(simNodesRef.current);
    }
  }), [fitToGraph]);

  // Sync incoming nodes, initialize coordinates at (0, 0), and auto-fit
  useEffect(() => {
    if (nodes.length === 0) {
      setSimNodes([]);
      simNodesRef.current = [];
      nodeMapRef.current.clear();
      simStageRef.current = 'STABLE';
      return;
    }

    const prevMap = new Map(simNodesRef.current.map((n) => [n.id, n]));
    const existingCount = nodes.filter((n) => prevMap.has(n.id)).length;
    const isNewGraph = existingCount < Math.min(nodes.length * 0.4, 4);

    let nextSimNodes: SimNode[];

    if (isNewGraph) {
      simStageRef.current = 'INITIALIZING';
      // Deterministic layout centered at world origin (0, 0)
      const goldenAngle = Math.PI * (3 - Math.sqrt(5));
      nextSimNodes = nodes.map((node, i) => {
        const r = 25 * Math.sqrt(i + 1);
        const theta = i * goldenAngle;
        return {
          ...node,
          x: Math.cos(theta) * r,
          y: Math.sin(theta) * r,
          vx: 0,
          vy: 0,
        };
      });

      simStageRef.current = 'WARMUP';
      // Synchronous physics warmup to converge positions immediately
      warmupSimulation(nextSimNodes, edges, 90);

      // Transition to SETTLING with small initial alpha for smooth visual convergence
      simStageRef.current = 'SETTLING';
      alphaRef.current = 0.2;

      hasUserInteractedRef.current = false;
      simNodesRef.current = nextSimNodes;
      nodeMapRef.current = new Map(nextSimNodes.map(n => [n.id, n]));
      setSimNodes(nextSimNodes);

      const canvas = canvasRef.current;
      const container = containerRef.current;
      const width = canvas?.width || container?.clientWidth || 0;
      const height = canvas?.height || container?.clientHeight || 0;

      if (width > 0 && height > 0) {
        const { zoom: fitZoom, pan: fitPan } = computeFitView(nextSimNodes, width, height);
        setZoom(fitZoom);
        setPan(fitPan);
      }
    } else {
      // Incremental addition (e.g. node expansion)
      nextSimNodes = nodes.map((node) => {
        const existing = prevMap.get(node.id);
        if (existing) {
          return { ...node, x: existing.x, y: existing.y, vx: 0, vy: 0 };
        }
        const angle = Math.random() * Math.PI * 2;
        const radius = 60 + Math.random() * 120;
        return {
          ...node,
          x: Math.cos(angle) * radius,
          y: Math.sin(angle) * radius,
          vx: 0,
          vy: 0,
        };
      });
      simNodesRef.current = nextSimNodes;
      nodeMapRef.current = new Map(nextSimNodes.map(n => [n.id, n]));
      setSimNodes(nextSimNodes);
      alphaRef.current = 0.25;
      simStageRef.current = 'SETTLING';
    }
  }, [nodes, edges]);

  // Simulation physics loop
  useEffect(() => {
    let animationId: number;

    const updatePhysics = () => {
      if (simNodes.length === 0) return;

      if (simStageRef.current === 'SETTLING') {
        const alpha = alphaRef.current;
        if (alpha > 0.005) {
          const kLink = 0.04;
          const dLink = 140;
          const kRepulsion = 1500;
          const kGravity = 0.01;
          const friction = 0.85;

          // 1. Repulsion force between all node pairs
          for (let i = 0; i < simNodes.length; i++) {
            const n1 = simNodes[i];
            for (let j = i + 1; j < simNodes.length; j++) {
              const n2 = simNodes[j];
              const dx = n2.x - n1.x;
              const dy = n2.y - n1.y;
              const distSq = dx * dx + dy * dy + 0.1;
              const dist = Math.sqrt(distSq);

              if (dist < 400) {
                const force = (kRepulsion / distSq) * alpha;
                const fx = (dx / dist) * force;
                const fy = (dy / dist) * force;

                n1.vx -= fx;
                n1.vy -= fy;
                n2.vx += fx;
                n2.vy += fy;
              }
            }
          }

          const nodeMap = nodeMapRef.current;

          // 2. Link Spring forces
          for (let i = 0; i < edges.length; i++) {
            const edge = edges[i];
            const sNode = nodeMap.get(edge.source);
            const tNode = nodeMap.get(edge.target);

            if (sNode && tNode) {
              const dx = tNode.x - sNode.x;
              const dy = tNode.y - sNode.y;
              const dist = Math.sqrt(dx * dx + dy * dy) + 0.1;

              const displacement = dist - dLink;
              const force = displacement * kLink * alpha;
              const fx = (dx / dist) * force;
              const fy = (dy / dist) * force;

              sNode.vx += fx;
              sNode.vy += fy;
              tNode.vx -= fx;
              tNode.vy -= fy;
            }
          }

          // 3. Gravity towards world origin (0, 0)
          for (let i = 0; i < simNodes.length; i++) {
            const node = simNodes[i];
            node.vx += (0 - node.x) * kGravity * alpha;
            node.vy += (0 - node.y) * kGravity * alpha;
          }

          // 4. Update coordinates & apply damping
          let maxV = 0;
          for (let i = 0; i < simNodes.length; i++) {
            const node = simNodes[i];
            if (node === draggedNodeRef.current) {
              node.vx = 0;
              node.vy = 0;
              continue;
            }
            node.x += node.vx;
            node.y += node.vy;
            node.vx *= friction;
            node.vy *= friction;
            const v = Math.abs(node.vx) + Math.abs(node.vy);
            if (v > maxV) maxV = v;
          }

          // Cool down alpha
          alphaRef.current *= 0.92;

          // Settling condition: transition to STABLE
          if (alphaRef.current <= 0.005 || maxV < 0.05) {
            simStageRef.current = 'STABLE';
            alphaRef.current = 0;
            for (let i = 0; i < simNodes.length; i++) {
              simNodes[i].vx = 0;
              simNodes[i].vy = 0;
            }
          }
        } else {
          simStageRef.current = 'STABLE';
          alphaRef.current = 0;
          for (let i = 0; i < simNodes.length; i++) {
            simNodes[i].vx = 0;
            simNodes[i].vy = 0;
          }
        }
      }

      // Render Graph on Canvas
      renderGraph();

      animationId = requestAnimationFrame(updatePhysics);
    };

    const renderGraph = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const nodeMap = nodeMapRef.current;

      // Clear Screen
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      ctx.save();
      // Apply panning and zoom transforms
      ctx.translate(pan.x, pan.y);
      ctx.scale(zoom, zoom);

      // Pre-compute connected nodes and edges for HUD highlighting
      const connectedNodeIds = new Set<string>();
      const connectedEdgeIndices = new Set<number>();
      if (selectedNode) {
        connectedNodeIds.add(selectedNode.id);
        edges.forEach((edge, idx) => {
          if (edge.source === selectedNode.id || edge.target === selectedNode.id) {
            connectedNodeIds.add(edge.source);
            connectedNodeIds.add(edge.target);
            connectedEdgeIndices.add(idx);
          }
        });
      }

      // Deterministic LOD Label Budget:
      // LOW ZOOM (< 0.35): max 24 labels (REPOSITORY, FILE, top CLASS nodes)
      // MEDIUM ZOOM (0.35 - 0.70): max 75 labels (REPOSITORY, FILE, CLASS, and active/high-degree FUNCTION)
      // HIGH ZOOM (>= 0.70): max 180 labels
      const visibleLabelIds = new Set<string>();
      if (selectedNode) {
        visibleLabelIds.add(selectedNode.id);
        connectedNodeIds.forEach(id => visibleLabelIds.add(id));
      }

      const maxLabelBudget = zoom < 0.35 ? 24 : zoom < 0.70 ? 75 : 180;
      for (let i = 0; i < rankedNodes.length && visibleLabelIds.size < maxLabelBudget; i++) {
        const node = rankedNodes[i];
        if (visibleLabelIds.has(node.id)) continue;

        const deg = degreeMap.get(node.id) || 0;
        if (zoom < 0.35) {
          // Low Zoom: System architecture overview
          if (node.node_type === 'REPOSITORY' || node.node_type === 'FILE' || (node.node_type === 'CLASS' && deg >= 4)) {
            visibleLabelIds.add(node.id);
          }
        } else if (zoom < 0.70) {
          // Medium Zoom: Structural symbols
          if (node.node_type === 'REPOSITORY' || node.node_type === 'FILE' || node.node_type === 'CLASS' || deg >= 2) {
            visibleLabelIds.add(node.id);
          }
        } else {
          // High Zoom: Full symbol fidelity
          visibleLabelIds.add(node.id);
        }
      }

      // Draw Edges
      edges.forEach((edge, idx) => {
        const sNode = nodeMap.get(edge.source);
        const tNode = nodeMap.get(edge.target);
        
        if (sNode && tNode) {
          const isConnectedToSelected = selectedNode && connectedEdgeIndices.has(idx);

          ctx.beginPath();
          ctx.moveTo(sNode.x, sNode.y);
          ctx.lineTo(tNode.x, tNode.y);
          
          if (overlays.callGraph && (edge.relationship === 'CALLS' || edge.relationship === 'BELONGS_TO')) {
            ctx.strokeStyle = 'rgba(61, 220, 151, 0.75)';
            ctx.lineWidth = 2.5;
          } else if (selectedNode) {
            if (isConnectedToSelected) {
              ctx.strokeStyle = 'rgba(240, 164, 34, 0.9)';
              ctx.lineWidth = 2.2;
            } else {
              ctx.strokeStyle = 'rgba(232, 235, 239, 0.025)';
              ctx.lineWidth = 0.5;
            }
          } else {
            // Subtle zoom-scaled edge intensity
            if (zoom < 0.35) {
              ctx.strokeStyle = 'rgba(232, 235, 239, 0.04)';
              ctx.lineWidth = 0.6;
            } else if (zoom < 0.70) {
              ctx.strokeStyle = 'rgba(232, 235, 239, 0.07)';
              ctx.lineWidth = 0.8;
            } else {
              ctx.strokeStyle = 'rgba(232, 235, 239, 0.11)';
              ctx.lineWidth = 1;
            }
          }
          ctx.stroke();

          // Dependency arrow rendering
          // Show arrows when selected, or at medium/high zoom when no node is selected
          const showArrow = isConnectedToSelected || overlays.callGraph || (!selectedNode && zoom >= 0.40);
          if (showArrow) {
            const angle = Math.atan2(tNode.y - sNode.y, tNode.x - sNode.x);
            const arrowLength = 5;
            const arrowOffset = 20;
            const arrowX = tNode.x - Math.cos(angle) * arrowOffset;
            const arrowY = tNode.y - Math.sin(angle) * arrowOffset;
            
            ctx.beginPath();
            ctx.moveTo(arrowX, arrowY);
            ctx.lineTo(arrowX - arrowLength * Math.cos(angle - Math.PI / 6), arrowY - arrowLength * Math.sin(angle - Math.PI / 6));
            ctx.lineTo(arrowX - arrowLength * Math.cos(angle + Math.PI / 6), arrowY - arrowLength * Math.sin(angle + Math.PI / 6));
            ctx.fillStyle = overlays.callGraph 
              ? 'rgba(61, 220, 151, 0.75)' 
              : isConnectedToSelected 
                ? 'rgba(240, 164, 34, 0.9)' 
                : 'rgba(232, 235, 239, 0.12)';
            ctx.fill();
          }
        }
      });

      // Draw Nodes
      simNodes.forEach((node) => {
        const baseRadius = getNodeRadius(node.node_type);
        const deg = degreeMap.get(node.id) || 0;
        // Subtle prominence for architectural hub nodes (+0 to +3.5px max)
        const degreeBonus = Math.min(Math.sqrt(deg) * 0.5, 3.5);
        const radius = baseRadius + degreeBonus;
        const color = getNodeColor(node.node_type);

        const isSelected = selectedNode && selectedNode.id === node.id;
        const isHighlighted = highlightedNodeId && highlightedNodeId === node.id;
        const isConnectedNeighbor = selectedNode && connectedNodeIds.has(node.id);

        ctx.save();

        // Subtle dimming of unconnected nodes when a target is focused
        if (selectedNode && !isConnectedNeighbor) {
          ctx.globalAlpha = 0.30;
        }

        ctx.beginPath();
        ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);

        // Security Overlay Pulsing red concentric rings
        if (overlays.security && node.security_score !== undefined && node.security_score !== null && node.security_score < 100) {
          const pulse = (1 + Math.sin(Date.now() / 200)) * 4 + 2;
          ctx.shadowColor = '#ef4444';
          ctx.shadowBlur = 12 + pulse;
          ctx.strokeStyle = '#f87171';
          ctx.lineWidth = 2;
          ctx.stroke();
        }

        // Selected Node Highlight (Amber Glow)
        if (isSelected || isHighlighted) {
          ctx.shadowColor = '#F0A422';
          ctx.shadowBlur = 18;
          ctx.strokeStyle = '#FFB400';
          ctx.lineWidth = 3;
          ctx.stroke();
        } else if (isConnectedNeighbor) {
          ctx.strokeStyle = 'rgba(240, 164, 34, 0.6)';
          ctx.lineWidth = 1.5;
          ctx.stroke();
        }

        // Dead Code overlay desaturated + dashed outline
        const isDeadCodeNode = overlays.deadCode && node.dead_code;
        if (isDeadCodeNode) {
          ctx.fillStyle = '#1D232D';
          ctx.strokeStyle = '#6B7481';
          ctx.setLineDash([4, 4]);
          ctx.lineWidth = 1.5;
          ctx.stroke();
        } else {
          ctx.fillStyle = color;
        }

        // Architecture Smells orange highlight border
        if (overlays.smells && node.architecture_smell) {
          ctx.strokeStyle = '#FF8A00';
          ctx.lineWidth = 3;
          ctx.stroke();
        }

        ctx.fill();
        ctx.restore();

        // Draw Node Text Labels strictly based on deterministic LOD budget
        if (visibleLabelIds.has(node.id)) {
          ctx.save();
          if (selectedNode && !isConnectedNeighbor) {
            ctx.globalAlpha = 0.35;
          }
          ctx.font = isSelected ? "bold 11px 'JetBrains Mono', monospace" : "10px 'JetBrains Mono', monospace";
          ctx.fillStyle = isSelected ? '#FFB400' : isConnectedNeighbor ? '#E8EBEF' : 'rgba(232, 235, 239, 0.75)';
          ctx.textAlign = 'center';
          ctx.fillText(node.label, node.x, node.y + radius + 13);
          
          if (node.node_type === 'FILE' && node.security_score !== null && overlays.security) {
            ctx.font = "bold 9px 'JetBrains Mono', monospace";
            ctx.fillStyle = '#ef4444';
            ctx.fillText(`Score: ${node.security_score}`, node.x, node.y - radius - 6);
          }
          ctx.restore();
        }
      });

      ctx.restore();
    };

    updatePhysics();

    return () => cancelAnimationFrame(animationId);
  }, [simNodes, edges, selectedNode, pan, zoom, overlays, highlightedNodeId, degreeMap, rankedNodes]);

  // Adjust canvas size to container and maintain centered view on resize
  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;

    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width <= 0 || height <= 0) continue;

        const oldWidth = canvas.width;
        const oldHeight = canvas.height;

        canvas.width = width;
        canvas.height = height;

        if (oldWidth <= 0 || oldHeight <= 0 || !hasUserInteractedRef.current) {
          if (simNodesRef.current.length > 0) {
            const { zoom: fitZoom, pan: fitPan } = computeFitView(simNodesRef.current, width, height);
            setZoom(fitZoom);
            setPan(fitPan);
          } else {
            setPan({ x: width / 2, y: height / 2 });
          }
        } else {
          setPan((prev) => ({
            x: prev.x + (width - oldWidth) / 2,
            y: prev.y + (height - oldHeight) / 2,
          }));
        }
      }
    });

    ro.observe(container);
    return () => ro.disconnect();
  }, []);

  // Interaction handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    // Convert screen coordinates to canvas space coordinates
    const canvasX = (x - pan.x) / zoom;
    const canvasY = (y - pan.y) / zoom;

    // Check if clicked a node
    let clickedNode: SimNode | null = null;
    for (let node of simNodes) {
      const radius = getNodeRadius(node.node_type);
      const dist = Math.sqrt((node.x - canvasX) ** 2 + (node.y - canvasY) ** 2);
      if (dist <= radius) {
        clickedNode = node;
        break;
      }
    }

    if (clickedNode) {
      hasUserInteractedRef.current = true;
      onInteraction?.();
      draggedNodeRef.current = clickedNode;
      onSelectNode(clickedNode);

      // Double click detection
      const now = Date.now();
      if (now - lastClickRef.current.time < 300 && lastClickRef.current.nodeId === clickedNode.id) {
        onExpandNode(clickedNode);
      }
      lastClickRef.current = { time: now, nodeId: clickedNode.id };
    } else {
      hasUserInteractedRef.current = true;
      onInteraction?.();
      isDraggingViewportRef.current = true;
      dragStartRef.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    if (draggedNodeRef.current) {
      hasUserInteractedRef.current = true;
      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      // Convert coordinates
      draggedNodeRef.current.x = (x - pan.x) / zoom;
      draggedNodeRef.current.y = (y - pan.y) / zoom;
    } else if (isDraggingViewportRef.current) {
      hasUserInteractedRef.current = true;
      setPan({
        x: e.clientX - dragStartRef.current.x,
        y: e.clientY - dragStartRef.current.y,
      });
    }
  };

  const handleMouseUp = () => {
    draggedNodeRef.current = null;
    isDraggingViewportRef.current = false;
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const canvas = canvasRef.current;
    if (!canvas) return;
    hasUserInteractedRef.current = true;
    onInteraction?.();

    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
    const newZoom = Math.max(0.15, Math.min(zoom * factor, 4));
    const scale = newZoom / zoom;

    setPan((prev) => ({
      x: mouseX - (mouseX - prev.x) * scale,
      y: mouseY - (mouseY - prev.y) * scale,
    }));
    setZoom(newZoom);
  };

  return (
    <div
      ref={containerRef}
      style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden' }}
    >
      <canvas
        ref={canvasRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
        style={{
          cursor: draggedNodeRef.current ? 'grabbing' : isDraggingViewportRef.current ? 'move' : 'default',
          display: 'block',
        }}
      />
    </div>
  );
});
