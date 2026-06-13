import { useState, useCallback, useMemo, useEffect } from 'react';
import useGraphData from './hooks/useGraphData';
import Sidebar from './components/Sidebar';
import GraphCanvas from './components/GraphCanvas';
import ChatPanel from './components/ChatPanel';
import NodeDetail from './components/NodeDetail';
import ResizeHandle from './components/ResizeHandle';
import './App.css';

function getUpidFromUrl() {
  // Expects URL like /person/2349202
  const match = window.location.pathname.match(/\/person\/([^/]+)/);
  return match ? match[1] : null;
}

function App() {
  const upid = useMemo(() => getUpidFromUrl(), []);
  const { graphData, replaceGraphData, mergeGraphData } = useGraphData();
  const [selectedNode, setSelectedNode] = useState(null);
  const [sidebarWidth, setSidebarWidth] = useState(280);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [chatWidth, setChatWidth] = useState(320);
  const [chatCollapsed, setChatCollapsed] = useState(false);
  const [graphSummary, setGraphSummary] = useState('');
  const [theme, setTheme] = useState('dark');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);
  const [filters, setFilters] = useState({
    nodeTypes: [],
    relTypes: [],
    dateFrom: '',
    dateTo: '',
  });

  const handleSidebarResize = useCallback((delta) => {
    setSidebarWidth((w) => Math.min(Math.max(w + delta, 180), 500));
  }, []);

  const handleChatResize = useCallback((delta) => {
    setChatWidth((w) => Math.min(Math.max(w + delta, 200), 600));
  }, []);

  return (
    <div className="app-container">
      {!sidebarCollapsed && (
        <>
          <Sidebar
            upid={upid}
            replaceGraphData={replaceGraphData}
            mergeGraphData={mergeGraphData}
            filters={filters}
            onFilterChange={setFilters}
            onSummary={setGraphSummary}
            graphSummary={graphSummary}
            style={{ width: sidebarWidth }}
          />
          <ResizeHandle onResize={handleSidebarResize} side="left" />
        </>
      )}
      <button
        onClick={() => setSidebarCollapsed((c) => !c)}
        style={{
          position: 'absolute',
          top: '8px',
          left: sidebarCollapsed ? '8px' : sidebarWidth + 12,
          zIndex: 20,
          background: '#607D8B',
          border: 'none',
          borderRadius: '4px',
          color: '#fff',
          cursor: 'pointer',
          fontSize: '14px',
          padding: '4px 8px',
          transition: 'left 0.15s ease',
        }}
        title={sidebarCollapsed ? 'Show sidebar' : 'Hide sidebar'}
      >
        {sidebarCollapsed ? '\u25B6' : '\u25C0'}
      </button>
      <button
        onClick={() => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))}
        style={{
          position: 'absolute',
          top: '8px',
          left: sidebarCollapsed ? '40px' : sidebarWidth + 44,
          zIndex: 20,
          background: '#607D8B',
          border: 'none',
          borderRadius: '4px',
          color: '#fff',
          cursor: 'pointer',
          fontSize: '14px',
          padding: '4px 8px',
          transition: 'left 0.15s ease',
        }}
        title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      >
        {theme === 'dark' ? '\u2600' : '\u263E'}
      </button>
      <div className="graph-area">
        <GraphCanvas
          graphData={graphData}
          mergeGraphData={mergeGraphData}
          selectedNode={selectedNode}
          onNodeClick={setSelectedNode}
          theme={theme}
        />
        <NodeDetail
          node={selectedNode}
          onClose={() => setSelectedNode(null)}
        />
        {graphSummary && (
          <div className="graph-summary">
            <button
              onClick={() => setGraphSummary('')}
              style={{
                position: 'absolute',
                top: '4px',
                right: '8px',
                background: 'none',
                border: 'none',
                color: 'var(--text-dim)',
                cursor: 'pointer',
                fontSize: '14px',
              }}
              title="Dismiss"
            >
              {'\u2715'}
            </button>
            <div>
              {graphSummary.split('\n').map((line, i) => {
                const isBullet = line.trimStart().startsWith('•') || line.trimStart().startsWith('-');
                return (
                  <div key={i} style={isBullet ? { marginLeft: '16px', textIndent: '-12px', paddingLeft: '12px' } : { marginTop: i > 0 ? '6px' : 0 }}>
                    {line}
                  </div>
                );
              })}
            </div>
          </div>
        )}
        {upid && (
          <div className="graph-upid">
            UPID: {upid}
          </div>
        )}
        <div className="graph-stats">
          {graphData.nodes.length} nodes, {graphData.links.length} relationships
        </div>
      </div>
      <button
        onClick={() => setChatCollapsed((c) => !c)}
        style={{
          position: 'absolute',
          top: '8px',
          right: chatCollapsed ? '8px' : chatWidth + 12,
          zIndex: 20,
          background: '#607D8B',
          border: 'none',
          borderRadius: '4px',
          color: '#fff',
          cursor: 'pointer',
          fontSize: '14px',
          padding: '4px 8px',
          transition: 'right 0.15s ease',
        }}
        title={chatCollapsed ? 'Show chat' : 'Hide chat'}
      >
        {chatCollapsed ? '\u25C0' : '\u25B6'}
      </button>
      {!chatCollapsed && (
        <>
          <ResizeHandle onResize={handleChatResize} side="right" />
          <ChatPanel upid={upid} mergeGraphData={mergeGraphData} replaceGraphData={replaceGraphData} style={{ width: chatWidth }} />
        </>
      )}
    </div>
  );
}

export default App;
