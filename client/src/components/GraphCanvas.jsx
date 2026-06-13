import { useRef, useCallback, useMemo, useEffect, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { NODE_LABELS, NODE_ICONS, NODE_DISPLAY_PROPERTY } from '../constants';
import api from '../api';

function getCssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export default function GraphCanvas({ graphData, mergeGraphData, selectedNode, onNodeClick, theme }) {
  const fgRef = useRef();
  const containerRef = useRef();
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

  // Track container size so the canvas fits between sidebar and chat panel
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const observer = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setDimensions({ width, height });
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  const handleNodeDragEnd = useCallback((node) => {
    // Pin the node in place after dragging
    node.fx = node.x;
    node.fy = node.y;
  }, []);

  const handleNodeClick = useCallback((node) => {
    onNodeClick(node);
  }, [onNodeClick]);

  const paintNode = useCallback((node, ctx, globalScale) => {
    const icon = NODE_ICONS[node.label];
    const label = NODE_LABELS[node.label] || '?';
    const displayProp = NODE_DISPLAY_PROPERTY[node.label];
    const displayVal = node.properties?.[displayProp] || '';
    const fontSize = 12 / globalScale;
    const nodeSize = node.val || 6;
    const textColor = getCssVar('--text-primary') || '#fff';
    const subTextColor = getCssVar('--text-secondary') || '#ddd';

    // Draw circle background
    ctx.beginPath();
    ctx.arc(node.x, node.y, nodeSize, 0, 2 * Math.PI);
    ctx.fillStyle = node.color || '#999';
    ctx.fill();

    // Highlight selected node
    if (selectedNode && selectedNode.id === node.id) {
      ctx.strokeStyle = textColor;
      ctx.lineWidth = 2 / globalScale;
      ctx.stroke();
    }

    // Draw icon or label abbreviation inside
    if (icon) {
      const iconSize = nodeSize * 1.4;
      ctx.font = `${iconSize}px Sans-Serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(icon, node.x, node.y);
    } else {
      ctx.font = `bold ${fontSize}px Sans-Serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = textColor;
      ctx.fillText(label, node.x, node.y);
    }

    // Draw display value below
    if (displayVal) {
      ctx.font = `${fontSize * 0.8}px Sans-Serif`;
      ctx.fillStyle = subTextColor;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(displayVal, node.x, node.y + nodeSize + fontSize);
    }
  }, [selectedNode, theme]);

  const paintLink = useCallback((link, ctx, globalScale) => {
    const fontSize = 8 / globalScale;
    const start = link.source;
    const end = link.target;

    if (typeof start !== 'object' || typeof end !== 'object') return;

    const linkColor = getCssVar('--link-color') || 'rgba(255,255,255,0.2)';
    const labelColor = getCssVar('--link-label') || 'rgba(255,255,255,0.4)';

    // Draw line
    ctx.beginPath();
    ctx.moveTo(start.x, start.y);
    ctx.lineTo(end.x, end.y);
    ctx.strokeStyle = linkColor;
    ctx.lineWidth = 0.5 / globalScale;
    ctx.stroke();

    // Draw relationship type at midpoint
    const midX = (start.x + end.x) / 2;
    const midY = (start.y + end.y) / 2;
    ctx.font = `${fontSize}px Sans-Serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = labelColor;
    ctx.fillText(link.type, midX, midY);
  }, [theme]);

  // Center the graph when data changes
  useEffect(() => {
    if (fgRef.current && graphData.nodes.length > 0) {
      setTimeout(() => {
        fgRef.current.zoomToFit(400, 60);
      }, 500);
    }
  }, [graphData]);

  const canvasBg = theme === 'light' ? '#e0e4eb' : '#1a1a2e';

  return (
    <div ref={containerRef} style={{ flex: 1, background: 'var(--bg-canvas)', position: 'relative', overflow: 'hidden' }}>
      <ForceGraph2D
        ref={fgRef}
        graphData={graphData}
        width={dimensions.width}
        height={dimensions.height}
        nodeCanvasObject={paintNode}
        linkCanvasObject={paintLink}
        onNodeClick={handleNodeClick}
        onNodeDragEnd={handleNodeDragEnd}
        nodeId="id"
        linkSource="source"
        linkTarget="target"
        backgroundColor={canvasBg}
        nodeRelSize={6}
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.3}
      />
    </div>
  );
}
