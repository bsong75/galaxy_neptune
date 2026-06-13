export default function DateFilter({ filters, onFilterChange }) {
  return (
    <div style={{ marginBottom: '16px' }}>
      <label style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px', display: 'block' }}>
        Date Range (SeizureEvent)
      </label>
      <div style={{ display: 'flex', gap: '8px', flexDirection: 'column' }}>
        <input
          type="date"
          value={filters.dateFrom || ''}
          onChange={(e) => onFilterChange({ ...filters, dateFrom: e.target.value })}
          style={{
            padding: '4px 8px',
            background: 'var(--bg-input)',
            border: '1px solid var(--border-light)',
            borderRadius: '4px',
            color: 'var(--text-primary)',
            fontSize: '12px',
          }}
        />
        <input
          type="date"
          value={filters.dateTo || ''}
          onChange={(e) => onFilterChange({ ...filters, dateTo: e.target.value })}
          style={{
            padding: '4px 8px',
            background: 'var(--bg-input)',
            border: '1px solid var(--border-light)',
            borderRadius: '4px',
            color: 'var(--text-primary)',
            fontSize: '12px',
          }}
        />
      </div>
    </div>
  );
}
