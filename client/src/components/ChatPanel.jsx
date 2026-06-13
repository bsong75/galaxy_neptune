import { useState, useRef, useEffect } from 'react';
import api from '../api';

export default function ChatPanel({ mergeGraphData, replaceGraphData, style }) {
  const [tab, setTab] = useState('chat');
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  // Cypher tab state
  const [cypher, setCypher] = useState('');
  const [cypherLoading, setCypherLoading] = useState(false);
  const [cypherResult, setCypherResult] = useState(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMsg = input.trim();
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', text: userMsg }]);
    setLoading(true);

    try {
      const res = await api.post('/chat', { message: userMsg });
      const { cypher, data, answer } = res.data;

      setMessages((prev) => [...prev, {
        role: 'assistant',
        text: answer,
        cypher,
      }]);

      if (data && (data.nodes?.length > 0 || data.links?.length > 0)) {
        mergeGraphData(data);
      }
    } catch (err) {
      setMessages((prev) => [...prev, {
        role: 'assistant',
        text: `Error: ${err.response?.data?.error || err.message}`,
      }]);
    }
    setLoading(false);
  };

  const handleCypherRun = async (e) => {
    e.preventDefault();
    if (!cypher.trim() || cypherLoading) return;

    setCypherLoading(true);
    setCypherResult(null);

    try {
      const res = await api.post('/graph/cypher', { cypher: cypher.trim() });
      if (res.data.error) {
        setCypherResult({ error: res.data.error });
      } else {
        const nodeCount = res.data.nodes?.length || 0;
        const linkCount = res.data.links?.length || 0;
        setCypherResult({ success: `Found ${nodeCount} nodes, ${linkCount} relationships` });
        if (nodeCount > 0 || linkCount > 0) {
          replaceGraphData(res.data);
        }
      }
    } catch (err) {
      setCypherResult({ error: err.response?.data?.error || err.message });
    }
    setCypherLoading(false);
  };

  const tabStyle = (active) => ({
    flex: 1,
    padding: '8px',
    background: active ? 'var(--bg-panel)' : 'transparent',
    border: 'none',
    borderBottom: active ? '2px solid #4CAF50' : '2px solid transparent',
    color: active ? 'var(--text-primary)' : 'var(--text-dim)',
    cursor: 'pointer',
    fontSize: '13px',
    fontWeight: active ? 'bold' : 'normal',
  });

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      background: 'var(--bg-sidebar)',
      borderLeft: '1px solid var(--border-color)',
      flexShrink: 0,
      ...style,
    }}>
      {/* Tab bar */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border-color)' }}>
        <button style={tabStyle(tab === 'chat')} onClick={() => setTab('chat')}>
          Chat (AI)
        </button>
        <button style={tabStyle(tab === 'cypher')} onClick={() => setTab('cypher')}>
          Cypher
        </button>
      </div>

      {/* Chat tab */}
      {tab === 'chat' && (
        <>
          <div style={{ flex: 1, overflowY: 'auto', padding: '12px' }}>
            {messages.map((msg, i) => (
              <div
                key={i}
                style={{
                  marginBottom: '12px',
                  textAlign: msg.role === 'user' ? 'right' : 'left',
                }}
              >
                <div style={{
                  display: 'inline-block',
                  padding: '8px 12px',
                  borderRadius: '8px',
                  background: msg.role === 'user' ? '#4CAF50' : 'var(--bg-panel)',
                  color: msg.role === 'user' ? '#fff' : 'var(--text-primary)',
                  fontSize: '13px',
                  maxWidth: '90%',
                  textAlign: 'left',
                }}>
                  {msg.text}
                </div>
                {msg.cypher && (
                  <details style={{ marginTop: '4px', fontSize: '11px', color: 'var(--text-dim)' }}>
                    <summary style={{ cursor: 'pointer' }}>Cypher</summary>
                    <pre style={{
                      background: 'var(--code-bg)',
                      padding: '8px',
                      borderRadius: '4px',
                      overflowX: 'auto',
                      fontSize: '11px',
                      color: 'var(--code-text)',
                      marginTop: '4px',
                    }}>
                      {msg.cypher}
                    </pre>
                  </details>
                )}
              </div>
            ))}
            {loading && (
              <div style={{ color: 'var(--text-dim)', fontSize: '12px' }}>Thinking...</div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <form onSubmit={handleSend} style={{ display: 'flex', padding: '8px', borderTop: '1px solid var(--border-color)' }}>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about the graph..."
              style={{
                flex: 1,
                padding: '8px',
                background: 'var(--bg-input)',
                border: '1px solid var(--border-light)',
                borderRadius: '4px 0 0 4px',
                color: 'var(--text-primary)',
                fontSize: '13px',
              }}
            />
            <button
              type="submit"
              disabled={loading}
              style={{
                padding: '8px 16px',
                background: '#4CAF50',
                border: 'none',
                borderRadius: '0 4px 4px 0',
                color: '#fff',
                cursor: 'pointer',
                fontSize: '13px',
              }}
            >
              Send
            </button>
          </form>
        </>
      )}

      {/* Cypher tab */}
      {tab === 'cypher' && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '12px' }}>
          <label style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '6px' }}>
            Enter Cypher query (read-only)
          </label>
          <textarea
            value={cypher}
            onChange={(e) => setCypher(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                if (e.ctrlKey || e.shiftKey || e.metaKey) {
                  e.preventDefault();
                  const textarea = e.target;
                  const start = textarea.selectionStart;
                  const end = textarea.selectionEnd;
                  const before = cypher.substring(0, start);
                  const after = cypher.substring(end);
                  setCypher(before + '\n' + after);
                  requestAnimationFrame(() => {
                    textarea.selectionStart = textarea.selectionEnd = start + 1;
                  });
                } else {
                  e.preventDefault();
                  handleCypherRun(e);
                }
              }
            }}
            placeholder={"MATCH (n:Person)-[r]-(m)\nRETURN n, r, m\nLIMIT 50"}
            spellCheck={false}
            style={{
              flex: 1,
              padding: '10px',
              background: 'var(--code-bg)',
              border: '1px solid var(--border-light)',
              borderRadius: '4px',
              color: 'var(--code-text)',
              fontSize: '12px',
              fontFamily: 'monospace',
              resize: 'none',
              minHeight: '120px',
            }}
          />
          <button
            onClick={handleCypherRun}
            disabled={cypherLoading}
            style={{
              marginTop: '8px',
              padding: '8px',
              background: '#FF9800',
              border: 'none',
              borderRadius: '4px',
              color: '#fff',
              cursor: 'pointer',
              fontSize: '13px',
            }}
          >
            {cypherLoading ? 'Running...' : 'Run Query'}
          </button>
          {cypherResult && (
            <div style={{
              marginTop: '8px',
              padding: '8px',
              background: 'var(--bg-panel)',
              borderRadius: '4px',
              fontSize: '12px',
              color: cypherResult.error ? '#ff6b6b' : '#8f8',
            }}>
              {cypherResult.error || cypherResult.success}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
