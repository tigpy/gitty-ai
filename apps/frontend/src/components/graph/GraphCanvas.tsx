import React, { useEffect, useRef, useState } from 'react';
import type { GraphNode, GraphEdge } from '../../types';

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
}

interface SimNode extends GraphNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
  fx?: number;
  fy?: number;
}

export const GraphCanvas: React.FC<GraphCanvasProps> = ({
  nodes,
  edges,
  selectedNode,
  onSelectNode,
  onExpandNode,
  overlays,
  highlightedNodeId,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  
  // Transform nodes to include simulation coordinates
  const [simNodes, setSimNodes] = useState<SimNode[]>([]);
  
  // Viewport states for zoom & pan
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const isDraggingViewportRef = useRef(false);
  const dragStartRef = useRef({ x: 0, y: 0 });
  
  // Node dragging states
  const draggedNodeRef = useRef<SimNode | null>(null);
  
  // Double click timer
  const lastClickRef = useRef<{ time: number; nodeId: string }>({ time: 0, nodeId: '' });

  // Sync incoming nodes with coordinates
  useEffect(() => {
    setSimNodes((prev) => {
      const prevMap = new Map(prev.map(n => [n.id, n]));
      return nodes.map((node) => {
        const existing = prevMap.get(node.id);
        const angle = Math.random() * Math.PI * 2;
        const radius = 100 + Math.random() * 200;
        return {
          ...node,
          x: existing ? existing.x : window.innerWidth / 2 + Math.cos(angle) * radius,
          y: existing ? existing.y : window.innerHeight / 2 + Math.sin(angle) * radius,
          vx: existing ? existing.vx : 0,
          vy: existing ? existing.vy : 0
        };
      });
    });
  }, [nodes]);

  // Center the graph initially
  useEffect(() => {
    if (simNodes.length > 0 && pan.x === 0 && pan.y === 0 && canvasRef.current) {
      const canvas = canvasRef.current;
      setPan({ x: canvas.width / 2, y: canvas.height / 2 });
    }
  }, [simNodes]);

  // Simulation physics loop
  useEffect(() => {
    let animationId: number;
    
    const updatePhysics = () => {
      if (simNodes.length === 0) return;

      const kLink = 0.04; // Spring strength
      const dLink = 140;  // Target link distance
      const kRepulsion = 1500; // Coulomb repulsion strength
      const kGravity = 0.01;  // Pull towards center
      const friction = 0.85;  // Velocity damping

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
            // Coulomb's repulsion
            const force = kRepulsion / distSq;
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
      edges.forEach((edge) => {
        const sNode = simNodes.find(n => n.id === edge.source);
        const tNode = simNodes.find(n => n.id === edge.target);
        
        if (sNode && tNode) {
          const dx = tNode.x - sNode.x;
          const dy = tNode.y - sNode.y;
          const dist = Math.sqrt(dx * dx + dy * dy) + 0.1;
          
          // Spring Hooke's Law
          const displacement = dist - dLink;
          const force = displacement * kLink;
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          
          sNode.vx += fx;
          sNode.vy += fy;
          tNode.vx -= fx;
          tNode.vy -= fy;
        }
      });

      // 3. Apply gravity towards viewport center
      if (canvasRef.current) {
        const cx = window.innerWidth / 2;
        const cy = window.innerHeight / 2;
        simNodes.forEach((node) => {
          node.vx += (cx - node.x) * kGravity;
          node.vy += (cy - node.y) * kGravity;
        });
      }

      // 4. Update coordinates & apply damping
      simNodes.forEach((node) => {
        if (node === draggedNodeRef.current) {
          node.vx = 0;
          node.vy = 0;
          return;
        }
        node.x += node.vx;
        node.y += node.vy;
        node.vx *= friction;
        node.vy *= friction;
      });

      // Render Graph on Canvas
      renderGraph();

      animationId = requestAnimationFrame(updatePhysics);
    };

    const renderGraph = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      // Clear Screen
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      ctx.save();
      // Apply panning and zoom transforms
      ctx.translate(pan.x, pan.y);
      ctx.scale(zoom, zoom);

      // Draw Edges
      edges.forEach((edge) => {
        const sNode = simNodes.find(n => n.id === edge.source);
        const tNode = simNodes.find(n => n.id === edge.target);
        
        if (sNode && tNode) {
          ctx.beginPath();
          ctx.moveTo(sNode.x, sNode.y);
          ctx.lineTo(tNode.x, tNode.y);
          
          // Call Graph Overlay highlights CALLS paths in green
          if (overlays.callGraph && (edge.relationship === 'CALLS' || edge.relationship === 'BELONGS_TO')) {
            ctx.strokeStyle = 'rgba(16, 185, 129, 0.7)';
            ctx.lineWidth = 2.5;
          } else {
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
            ctx.lineWidth = 1;
          }
          ctx.stroke();

          // Draw dependency direction indicator arrow
          const angle = Math.atan2(tNode.y - sNode.y, tNode.x - sNode.x);
          const arrowLength = 6;
          const arrowOffset = 22; // Draw arrow near node border
          const arrowX = tNode.x - Math.cos(angle) * arrowOffset;
          const arrowY = tNode.y - Math.sin(angle) * arrowOffset;
          
          ctx.beginPath();
          ctx.moveTo(arrowX, arrowY);
          ctx.lineTo(arrowX - arrowLength * Math.cos(angle - Math.PI / 6), arrowY - arrowLength * Math.sin(angle - Math.PI / 6));
          ctx.lineTo(arrowX - arrowLength * Math.cos(angle + Math.PI / 6), arrowY - arrowLength * Math.sin(angle + Math.PI / 6));
          ctx.fillStyle = overlays.callGraph ? 'rgba(16, 185, 129, 0.7)' : 'rgba(255, 255, 255, 0.12)';
          ctx.fill();
        }
      });

      // Draw Nodes
      simNodes.forEach((node) => {
        const radius = getNodeRadius(node.node_type);
        const color = getNodeColor(node.node_type);

        ctx.save();
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

        // Selected Node Highlight
        const isSelected = selectedNode && selectedNode.id === node.id;
        const isHighlighted = highlightedNodeId && highlightedNodeId === node.id;
        if (isSelected || isHighlighted) {
          ctx.shadowColor = '#818cf8';
          ctx.shadowBlur = 18;
          ctx.strokeStyle = '#a5b4fc';
          ctx.lineWidth = 3;
          ctx.stroke();
        }

        // Dead Code overlay desaturated + dashed outline
        const isDeadCodeNode = overlays.deadCode && node.dead_code;
        if (isDeadCodeNode) {
          ctx.fillStyle = '#1f2937';
          ctx.strokeStyle = '#6b7280';
          ctx.setLineDash([4, 4]);
          ctx.lineWidth = 1.5;
          ctx.stroke();
        } else {
          ctx.fillStyle = color;
        }

        // Architecture Smells orange highlight border
        if (overlays.smells && node.architecture_smell) {
          ctx.strokeStyle = '#f97316';
          ctx.lineWidth = 3.5;
          ctx.stroke();
        }

        ctx.fill();
        ctx.restore();

        // Draw Node Text Labels
        if (zoom > 0.45) {
          ctx.font = isSelected ? 'bold 11px Inter' : '10px Inter';
          ctx.fillStyle = isSelected ? '#ffffff' : 'rgba(255, 255, 255, 0.7)';
          ctx.textAlign = 'center';
          ctx.fillText(node.label, node.x, node.y + radius + 14);
          
          if (node.node_type === 'FILE' && node.security_score !== null && overlays.security) {
            ctx.font = 'bold 9px Inter';
            ctx.fillStyle = '#ef4444';
            ctx.fillText(`Score: ${node.security_score}`, node.x, node.y - radius - 6);
          }
        }
      });

      ctx.restore();
    };

    updatePhysics();

    return () => cancelAnimationFrame(animationId);
  }, [simNodes, edges, selectedNode, pan, zoom, overlays, highlightedNodeId]);

  // Adjust canvas size to window size
  useEffect(() => {
    const handleResize = () => {
      const canvas = canvasRef.current;
      if (canvas) {
        canvas.width = canvas.parentElement?.clientWidth || window.innerWidth;
        canvas.height = canvas.parentElement?.clientHeight || window.innerHeight;
      }
    };
    window.addEventListener('resize', handleResize);
    handleResize();
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const getNodeRadius = (type: string) => {
    switch (type) {
      case 'REPOSITORY': return 25;
      case 'FILE': return 12;
      case 'CLASS': return 8;
      case 'FUNCTION': return 6;
      default: return 7;
    }
  };

  const getNodeColor = (type: string) => {
    switch (type) {
      case 'REPOSITORY': return '#4f46e5'; // Deep Indigo
      case 'FILE': return '#2563eb';       // Blue
      case 'CLASS': return '#0891b2';      // Cyan
      case 'FUNCTION': return '#059669';   // Green
      case 'SECURITY_FINDING': return '#dc2626'; // Red
      default: return '#6b7280';
    }
  };

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
      draggedNodeRef.current = clickedNode;
      onSelectNode(clickedNode);
      
      // Double click detection
      const now = Date.now();
      if (now - lastClickRef.current.time < 300 && lastClickRef.current.nodeId === clickedNode.id) {
        onExpandNode(clickedNode);
      }
      lastClickRef.current = { time: now, nodeId: clickedNode.id };
    } else {
      isDraggingViewportRef.current = true;
      dragStartRef.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    if (draggedNodeRef.current) {
      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      
      // Convert coordinates
      draggedNodeRef.current.x = (x - pan.x) / zoom;
      draggedNodeRef.current.y = (y - pan.y) / zoom;
    } else if (isDraggingViewportRef.current) {
      setPan({
        x: e.clientX - dragStartRef.current.x,
        y: e.clientY - dragStartRef.current.y
      });
    }
  };

  const handleMouseUp = () => {
    draggedNodeRef.current = null;
    isDraggingViewportRef.current = false;
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const zoomFactor = 1.1;
    let newZoom = zoom;
    if (e.deltaY < 0) {
      newZoom *= zoomFactor;
    } else {
      newZoom /= zoomFactor;
    }
    
    // Clamp zoom levels
    setZoom(Math.max(0.15, Math.min(newZoom, 4)));
  };

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden' }}>
      <canvas 
        ref={canvasRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
        style={{ cursor: draggedNodeRef.current ? 'grabbing' : isDraggingViewportRef.current ? 'move' : 'default', display: 'block' }}
      />
    </div>
  );
};
