import { useState } from 'react';
import api from '../api';

export default function SearchBar({ upid, replaceGraphData }) {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    try {
      const params = new URLSearchParams({ q: query.trim() });
      if (upid) params.set('upid', upid);
      const res = await api.get(`/graph/search?${params.toString()}`);
      replaceGraphData(res.data);
    } catch (err) {
      console.error('Search error:', err);
    }
    setLoading(false);
  };

  return (
    <form onSubmit={handleSearch} style={{ marginBottom: '16px' }}>
      <label style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px', display: 'block' }}>
        Search Person
      </label>
      <div style={{ display: 'flex', gap: '4px' }}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Person ID or name..."
          style={{
            flex: 1,
            padding: '6px 8px',
            background: 'var(--bg-input)',
            border: '1px solid var(--border-light)',
            borderRadius: '4px',
            color: 'var(--text-primary)',
            fontSize: '13px',
          }}
        />
        <button
          type="submit"
          disabled={loading}
          style={{
            padding: '6px 12px',
            background: '#4CAF50',
            border: 'none',
            borderRadius: '4px',
            color: '#fff',
            cursor: 'pointer',
            fontSize: '13px',
          }}
        >
          {loading ? '...' : 'Go'}
        </button>
      </div>
    </form>
  );
}
