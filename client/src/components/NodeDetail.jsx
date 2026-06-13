import COUNTRY_NAMES from '../countryCodes';

const SEACAT_FIELDS = ['incident_id', 'description', 'incident_datetime', 'incident_location', 'incident_type'];
const MAIN_PAX_FIELDS = ['name', 'dob', 'citizenship_country', 'gender', 'id'];
const ASSOC_PERSON_FIELDS = ['name', 'dob', 'unf_psngr_id'];

const FIELD_LABELS = {
  name: 'Name',
  dob: 'DOB',
  citizenship_country: 'Citizenship',
  gender: 'Sex',
  id: 'Unified Person ID',
  unf_psngr_id: 'Unified Person ID',
  incident_id: 'Incident ID',
  description: 'Description',
  incident_datetime: 'Date/Time',
  incident_location: 'Location',
  incident_type: 'Incident Type',
};

function formatDob(value) {
  const d = new Date(value);
  if (isNaN(d)) return value;
  return d.toLocaleDateString('en-US', { month: '2-digit', day: '2-digit', year: 'numeric' });
}

function getEntries(node) {
  let fields;
  if (node.label === 'MainPassenger') fields = MAIN_PAX_FIELDS;
  else if (node.label === 'AssociatedPerson') fields = ASSOC_PERSON_FIELDS;
  else if (node.label === 'Seacat') fields = SEACAT_FIELDS;
  else return Object.entries(node.properties || {});

  return fields
    .filter(key => node.properties?.[key] !== undefined)
    .map(key => {
      let value = node.properties[key];
      if (key === 'dob') value = formatDob(value);
      if (key === 'citizenship_country') value = COUNTRY_NAMES[value] || value;
      return [FIELD_LABELS[key] || key, value];
    });
}

export default function NodeDetail({ node, onClose }) {
  if (!node) return null;

  const entries = getEntries(node);

  return (
    <div style={{
      position: 'absolute',
      top: '16px',
      right: '16px',
      background: 'var(--bg-panel)',
      border: '1px solid var(--border-hover)',
      borderRadius: '8px',
      padding: '16px',
      minWidth: '250px',
      maxWidth: '350px',
      color: 'var(--text-primary)',
      zIndex: 10,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <span style={{
          background: node.color,
          padding: '2px 10px',
          borderRadius: '12px',
          fontSize: '12px',
          fontWeight: 'bold',
        }}>
          {node.label}
        </span>
        <button
          onClick={onClose}
          style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '16px' }}
        >
          x
        </button>
      </div>
      <table style={{ width: '100%', fontSize: '12px' }}>
        <tbody>
          {entries.map(([key, value]) => (
            <tr key={key}>
              <td style={{ color: 'var(--text-dim)', padding: '2px 8px 2px 0', verticalAlign: 'top' }}>{key}</td>
              <td style={{ color: 'var(--text-secondary)', padding: '2px 0' }}>{String(value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
