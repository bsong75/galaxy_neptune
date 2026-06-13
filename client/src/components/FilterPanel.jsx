import { NODE_COLORS } from '../constants';

const NODE_TYPES = Object.keys(NODE_COLORS);

const REL_TYPES = [
  'FROM_COUNTRY', 'BORN_IN', 'HAS_PHONE',
  'HAS_ADDRESS', 'CO_TRAVELER', 'HAS_SEACAT', 'HAS_VISA', 'HAS_SECONDARY',
];

export default function FilterPanel({ filters, onFilterChange }) {
  const handleNodeTypeToggle = (type) => {
    const current = filters.nodeTypes || [];
    const updated = current.includes(type)
      ? current.filter((t) => t !== type)
      : [...current, type];
    onFilterChange({ ...filters, nodeTypes: updated });
  };

  const handleRelTypeToggle = (type) => {
    const current = filters.relTypes || [];
    const updated = current.includes(type)
      ? current.filter((t) => t !== type)
      : [...current, type];
    onFilterChange({ ...filters, relTypes: updated });
  };

  return (
    <div style={{ marginBottom: '16px' }}>
      <label style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px', display: 'block' }}>
        Node Types
      </label>
      <div style={{ maxHeight: '150px', overflowY: 'auto', marginBottom: '12px' }}>
        {NODE_TYPES.map((type) => (
          <label
            key={type}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--text-secondary)', cursor: 'pointer', padding: '2px 0' }}
          >
            <input
              type="checkbox"
              checked={(filters.nodeTypes || []).includes(type)}
              onChange={() => handleNodeTypeToggle(type)}
            />
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: NODE_COLORS[type], display: 'inline-block' }} />
            {type}
          </label>
        ))}
      </div>

      <label style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px', display: 'block' }}>
        Relationship Types
      </label>
      <div style={{ maxHeight: '150px', overflowY: 'auto' }}>
        {REL_TYPES.map((type) => (
          <label
            key={type}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--text-secondary)', cursor: 'pointer', padding: '2px 0' }}
          >
            <input
              type="checkbox"
              checked={(filters.relTypes || []).includes(type)}
              onChange={() => handleRelTypeToggle(type)}
            />
            {type}
          </label>
        ))}
      </div>
    </div>
  );
}
