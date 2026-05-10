export default function HistoryTable({ history, accentColor }) {
  const pillBase = {
    display: 'inline-block',
    padding: '1px 7px',
    borderRadius: 3,
    fontSize: 11,
    fontWeight: 600,
    lineHeight: '18px',
  }

  function resultCell(row) {
    switch (row.tier) {
      case 'winner':
        return (
          <span style={{ ...pillBase, background: accentColor, color: '#fff' }}>
            Won
          </span>
        )
      case 'final':
        return (
          <span style={{ ...pillBase, background: '#e0e0e0', color: '#333' }}>
            Final
          </span>
        )
      case 'deep':
        return <span style={{ fontSize: 12, color: '#555' }}>{row.result}</span>
      case 'early':
        return <span style={{ fontSize: 12, color: '#888' }}>{row.result}</span>
      case 'dnq':
        return <span style={{ fontSize: 12, color: '#aaa', fontStyle: 'italic' }}>DNQ</span>
      default:
        return <span style={{ fontSize: 12 }}>{row.result}</span>
    }
  }

  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
      <thead>
        <tr>
          {['Year', 'Host', 'Result'].map(h => (
            <th
              key={h}
              style={{
                textAlign: 'left',
                padding: '3px 6px',
                borderBottom: '1px solid #e0e0e0',
                fontSize: 10,
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                color: '#888',
              }}
            >
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {history.map((row, i) => (
          <tr
            key={row.year}
            style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(0,0,0,0.02)' }}
          >
            <td style={{ padding: '4px 6px', fontWeight: 600, color: '#333', fontSize: 12 }}>
              {row.year}
            </td>
            <td style={{ padding: '4px 6px', color: '#666', fontSize: 12 }}>
              {row.host}
            </td>
            <td style={{ padding: '4px 6px' }}>{resultCell(row)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
