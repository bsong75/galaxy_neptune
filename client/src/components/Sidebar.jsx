import { useState, useEffect, useRef } from 'react';
import SearchBar from './SearchBar';
import FilterPanel from './FilterPanel';
import DateFilter from './DateFilter';
import api from '../api';

const DEROG_TYPES = [
  { key: 'seacat', label: 'SEACATS', nodeLabel: 'Seacat', relType: 'HAS_SEACAT', color: '#E91E63' },
  { key: 'visa', label: 'Visa', nodeLabel: 'Visa', relType: 'HAS_VISA', color: '#FF9800' },
  { key: 'secondary', label: 'Secondary', nodeLabel: 'Secondary', relType: 'HAS_SECONDARY', color: '#607D8B' },
];

// Get link source/target ID — handles both string IDs and object refs (react-force-graph mutates links)
function linkSrc(link) { return typeof link.source === 'object' ? link.source.id : link.source; }
function linkTgt(link) { return typeof link.target === 'object' ? link.target.id : link.target; }

function filterGraphData(rawData, derogFilters) {
  if (!rawData || !rawData.nodes) return { nodes: [], links: [] };

  const { seacat, visa, secondary, derogOnly } = derogFilters;

  // Map derog node labels to their checked state
  const derogVisible = {
    Seacat: seacat,
    Visa: visa,
    Secondary: secondary,
  };

  // Step 1: Remove unchecked derog nodes
  const hiddenNodeIds = new Set();
  for (const node of rawData.nodes) {
    if (node.label in derogVisible && !derogVisible[node.label]) {
      hiddenNodeIds.add(node.id);
    }
  }

  // Step 2: If derogOnly, hide AssociatedPersons with no CHECKED derog connections
  if (derogOnly) {
    // Only count derog types whose checkbox is checked
    const activeDerogRels = new Set();
    if (seacat) activeDerogRels.add('HAS_SEACAT');
    if (visa) activeDerogRels.add('HAS_VISA');
    if (secondary) activeDerogRels.add('HAS_SECONDARY');

    const personsWithDerog = new Set();
    for (const link of rawData.links) {
      if (activeDerogRels.has(link.type)) {
        personsWithDerog.add(linkSrc(link));
      }
    }

    // Keep parent bridges: if a person is the SOURCE of a CO_TRAVELER to a flagged person,
    // they must stay visible to maintain the connection path from MainPassenger
    const bridgePersons = new Set();
    for (const link of rawData.links) {
      if (link.type === 'CO_TRAVELER' && personsWithDerog.has(linkTgt(link))) {
        bridgePersons.add(linkSrc(link));
      }
    }

    for (const node of rawData.nodes) {
      if (node.label === 'AssociatedPerson' && !personsWithDerog.has(node.id) && !bridgePersons.has(node.id)) {
        hiddenNodeIds.add(node.id);
      }
    }
  }

  // Step 3: Final filter — remove hidden nodes and their links
  const filteredNodes = rawData.nodes.filter((n) => !hiddenNodeIds.has(n.id));
  const filteredLinks = rawData.links.filter(
    (link) => !hiddenNodeIds.has(linkSrc(link)) && !hiddenNodeIds.has(linkTgt(link))
  );

  return { nodes: filteredNodes, links: filteredLinks };
}

export default function Sidebar({ upid, replaceGraphData, mergeGraphData, filters, onFilterChange, onSummary, graphSummary, style }) {
  const [limit, setLimit] = useState(500);
  const [currentLevel, setCurrentLevel] = useState(null);
  const [hasSummary, setHasSummary] = useState(false);
  const [summaryVisible, setSummaryVisible] = useState(false);
  const [derogFilters, setDerogFilters] = useState({
    seacat: true,
    visa: false,
    secondary: false,
    derogOnly: true,
  });
  const autoLoaded = useRef(false);
  const lastSummary = useRef('');
  const rawGraphData = useRef(null);

  // Sync summaryVisible when the overlay is dismissed via the X button in App
  useEffect(() => {
    setSummaryVisible(!!graphSummary);
  }, [graphSummary]);

  const upidParam = upid ? `upid=${encodeURIComponent(upid)}` : '';

  const fetchSummary = async (graphData) => {
    if (!onSummary) return;
    try {
      const res = await api.post('/graph/summarize', graphData);
      const summary = res.data.summary || '';
      lastSummary.current = summary;
      setHasSummary(!!summary);
      setSummaryVisible(!!summary);
      onSummary(summary);
    } catch (err) {
      console.error('Summary error:', err);
    }
  };

  const handleToggleSummary = () => {
    if (!onSummary || !lastSummary.current) return;
    if (summaryVisible) {
      onSummary('');
      setSummaryVisible(false);
    } else {
      onSummary(lastSummary.current);
      setSummaryVisible(true);
    }
  };

  const applyDerogFilters = (data, filtersOverride) => {
    const f = filtersOverride || derogFilters;
    const filtered = filterGraphData(data, f);
    replaceGraphData(filtered);
  };

  // Level 1: People + derog (frontend filters handle flagged-only view)
  const handleLoadFlagged = async () => {
    try {
      const res = await api.get(`/graph/people?${upidParam}`);
      rawGraphData.current = JSON.parse(JSON.stringify(res.data));
      applyDerogFilters(rawGraphData.current);
      setCurrentLevel(1);
      fetchSummary(res.data);
    } catch (err) {
      console.error('Load flagged error:', err);
    }
  };

  // Level 2: All people
  const handleLoadPeople = async () => {
    try {
      const res = await api.get(`/graph/people?${upidParam}`);
      rawGraphData.current = JSON.parse(JSON.stringify(res.data));
      applyDerogFilters(rawGraphData.current);
      setCurrentLevel(2);
    } catch (err) {
      console.error('Load people error:', err);
    }
  };

  // Level 3: Show all details
  const handleShowAll = async () => {
    try {
      const res = await api.get(`/graph/details?${upidParam}`);
      rawGraphData.current = JSON.parse(JSON.stringify(res.data));
      applyDerogFilters(rawGraphData.current);
      setCurrentLevel(3);
    } catch (err) {
      console.error('Details error:', err);
    }
  };

  const handleDerogFilterChange = (key) => {
    const updated = { ...derogFilters, [key]: !derogFilters[key] };
    setDerogFilters(updated);
  };

  const handleApplyDerogFilters = () => {
    if (rawGraphData.current) {
      applyDerogFilters(rawGraphData.current);
    }
  };

  const handleApplyFilters = async () => {
    try {
      const params = new URLSearchParams();
      if (upid) params.set('upid', upid);
      if (filters.nodeTypes?.length) params.set('nodeTypes', filters.nodeTypes.join(','));
      if (filters.relTypes?.length) params.set('relTypes', filters.relTypes.join(','));
      if (filters.dateFrom) params.set('dateFrom', filters.dateFrom);
      if (filters.dateTo) params.set('dateTo', filters.dateTo);
      if (limit) params.set('limit', limit);

      const res = await api.get(`/graph/filter?${params.toString()}`);
      replaceGraphData(res.data);
    } catch (err) {
      console.error('Filter error:', err);
    }
  };

  // Auto-load Level 1 (flagged network) when UPID is in the URL
  useEffect(() => {
    if (upid && !autoLoaded.current) {
      autoLoaded.current = true;
      handleLoadFlagged();
    }
  }, [upid]);

  const buttonStyle = (level) => ({
    width: '100%',
    padding: '8px',
    background: currentLevel === level ? '#4CAF50' : '#455A64',
    border: currentLevel === level ? '2px solid #fff' : '2px solid transparent',
    borderRadius: '4px',
    color: '#fff',
    cursor: 'pointer',
    fontSize: '13px',
    marginBottom: '6px',
    fontWeight: currentLevel === level ? 'bold' : 'normal',
  });

  const checkboxLabelStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    fontSize: '12px',
    color: 'var(--text-secondary)',
    cursor: 'pointer',
    padding: '3px 0',
  };

  return (
    <div style={{
      background: 'var(--bg-sidebar)',
      borderRight: '1px solid var(--border-color)',
      padding: '16px',
      overflowY: 'auto',
      display: 'flex',
      flexDirection: 'column',
      flexShrink: 0,
      ...style,
    }}>
      <h2 style={{ color: 'var(--text-primary)', fontSize: '16px', margin: '0 0 16px 0' }}>
        Graph Explorer
      </h2>

      <button onClick={handleLoadFlagged} style={buttonStyle(1)}>
        Load PAX Network (Level I)
      </button>

      <button onClick={handleLoadPeople} style={buttonStyle(2)}>
        Load All People (Level II)
      </button>

      <button onClick={handleShowAll} style={buttonStyle(3)}>
        Show All Details (Level III)
      </button>

      {hasSummary && (
        <button
          onClick={handleToggleSummary}
          style={{
            width: '100%',
            padding: '8px',
            background: summaryVisible ? '#E91E63' : '#5C6BC0',
            border: 'none',
            borderRadius: '4px',
            color: '#fff',
            cursor: 'pointer',
            fontSize: '13px',
            marginTop: '4px',
            marginBottom: '8px',
          }}
        >
          {summaryVisible ? 'Hide Summary' : 'Show Summary'}
        </button>
      )}

      <hr style={{ border: 'none', borderTop: '1px solid var(--border-color)', margin: '8px 0 12px' }} />

      <label style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '6px', display: 'block' }}>
        Derog Filters
      </label>

      {DEROG_TYPES.map((dt) => (
        <label key={dt.key} style={checkboxLabelStyle}>
          <input
            type="checkbox"
            checked={derogFilters[dt.key]}
            onChange={() => handleDerogFilterChange(dt.key)}
          />
          <span style={{
            width: '10px',
            height: '10px',
            borderRadius: '50%',
            background: dt.color,
            display: 'inline-block',
          }} />
          {dt.label}
        </label>
      ))}

      <label style={{ ...checkboxLabelStyle, marginTop: '6px' }}>
        <input
          type="checkbox"
          checked={derogFilters.derogOnly}
          onChange={() => handleDerogFilterChange('derogOnly')}
        />
        Show only passengers w/ Derog
      </label>

      <button
        onClick={handleApplyDerogFilters}
        style={{
          width: '100%',
          padding: '6px',
          background: '#4CAF50',
          border: 'none',
          borderRadius: '4px',
          color: '#fff',
          cursor: 'pointer',
          fontSize: '13px',
          marginTop: '8px',
          marginBottom: '8px',
        }}
      >
        Apply
      </button>

      <div style={{ marginTop: '10px' }}>
        <SearchBar upid={upid} replaceGraphData={replaceGraphData} />
      </div>

      {currentLevel === 3 && (
        <>
          <hr style={{ border: 'none', borderTop: '1px solid var(--border-color)', margin: '8px 0 16px' }} />

          <div style={{ marginBottom: '12px' }}>
            <label style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px', display: 'block' }}>
              Result Limit (empty = all)
            </label>
            <input
              type="number"
              value={limit}
              onChange={(e) => setLimit(e.target.value ? parseInt(e.target.value) : '')}
              placeholder="No limit"
              style={{
                width: '100%',
                padding: '6px 8px',
                background: 'var(--bg-input)',
                border: '1px solid var(--border-light)',
                borderRadius: '4px',
                color: 'var(--text-primary)',
                fontSize: '13px',
                boxSizing: 'border-box',
              }}
            />
          </div>

          <FilterPanel filters={filters} onFilterChange={onFilterChange} />
          <DateFilter filters={filters} onFilterChange={onFilterChange} />

          <button
            onClick={handleApplyFilters}
            style={{
              width: '100%',
              padding: '6px',
              background: '#FF9800',
              border: 'none',
              borderRadius: '4px',
              color: '#fff',
              cursor: 'pointer',
              fontSize: '13px',
              marginBottom: '16px',
            }}
          >
            Apply Filters
          </button>
        </>
      )}

    </div>
  );
}