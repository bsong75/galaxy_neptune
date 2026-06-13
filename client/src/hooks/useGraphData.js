import { useState, useCallback } from 'react';

export default function useGraphData() {
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });

  const replaceGraphData = useCallback((data) => {
    setGraphData(data);
  }, []);

  const mergeGraphData = useCallback((newData) => {
    setGraphData((prev) => {
      const nodeMap = {};
      // Keep existing nodes (they have x, y, fx, fy from the simulation)
      prev.nodes.forEach((n) => { nodeMap[n.id] = n; });
      // Only add truly new nodes from the API response
      newData.nodes.forEach((n) => {
        if (!nodeMap[n.id]) {
          nodeMap[n.id] = n;
        }
      });

      const linkSet = new Set();
      const links = [];

      const addLink = (link) => {
        const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
        const targetId = typeof link.target === 'object' ? link.target.id : link.target;
        const key = `${sourceId}-${link.type}-${targetId}`;
        if (!linkSet.has(key)) {
          linkSet.add(key);
          links.push({ source: sourceId, target: targetId, type: link.type });
        }
      };

      prev.links.forEach(addLink);
      newData.links.forEach(addLink);

      return { nodes: Object.values(nodeMap), links };
    });
  }, []);

  const clearGraphData = useCallback(() => {
    setGraphData({ nodes: [], links: [] });
  }, []);

  return { graphData, replaceGraphData, mergeGraphData, clearGraphData };
}
