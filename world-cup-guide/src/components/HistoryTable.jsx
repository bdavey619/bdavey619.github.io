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
          <span style={{ ...pillBase, background: 'var(--gray-200)', color: 'var(--gray-700)' }}>
            Final
          </span>
        )
      case 'deep':
        return <span style={{ fontSize: 12, color: 'var(--gray-700)' }}>{row.result}</span>
      case 'early':
        return <span style={{ fontSize: 12, color: 'var(--gray-500)' }}>{row.result}</span>
      case 'dnq':
        return <span style={{ fontSize: 12, color: 'var(--gray-400)', fontStyle: 'italic' }}>DNQ</span>
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
                borderBottom: '1px solid var(--gray-200)',
                fontSize: 10,
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                color: 'var(--gray-500)',
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
            <td style={{ padding: '4px 6px', fontWeight: 600, color: 'var(--gray-700)', fontSize: 12 }}>
              {row.year}
            </td>
            <td style={{ padding: '4px 6px', color: 'var(--gray-500)', fontSize: 12 }}>
              {row.host}
            </td>
            <td style={{ padding: '4px 6px' }}>{resultCell(row)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
