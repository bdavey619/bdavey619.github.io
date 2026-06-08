import { storylines } from '../data/storylines.js'

function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r},${g},${b},${alpha})`
}

export default function Storylines() {
  return (
    <div>
      <div style={{ textAlign: 'center', marginBottom: 28 }}>
        <h1 style={{
          fontFamily: 'Georgia, "Times New Roman", serif',
          fontSize: 32,
          fontWeight: 500,
          color: '#1a1a1a',
          margin: '0 0 6px',
        }}>
          The Stories to Follow
        </h1>
        <p style={{ fontSize: 14, color: '#888', margin: 0 }}>
          Eight narratives that will define the 2026 World Cup
        </p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {storylines.map((s, i) => (
          <div
            key={s.id}
            style={{
              background: 'white',
              borderRadius: 8,
              overflow: 'hidden',
              boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
              display: 'flex',
            }}
          >
            {/* Left accent bar */}
            <div style={{ width: 4, flexShrink: 0, background: s.accentColor }} />

            {/* Card body */}
            <div style={{ padding: '20px 20px 20px 24px', flex: 1 }}>
              {/* Row 1: type pill + team/player tags */}
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                <span style={{
                  fontSize: 10,
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  background: '#f0f0f0',
                  color: '#555',
                  padding: '3px 8px',
                  borderRadius: 12,
                }}>
                  {s.type}
                </span>
                {s.teams.map(tag => (
                  <span
                    key={tag}
                    style={{
                      fontSize: 10,
                      textTransform: 'uppercase',
                      letterSpacing: '0.06em',
                      background: hexToRgba(s.accentColor, 0.12),
                      color: s.accentColor,
                      padding: '3px 8px',
                      borderRadius: 12,
                    }}
                  >
                    {tag}
                  </span>
                ))}
              </div>

              {/* Row 2: number + headline */}
              <div style={{ marginTop: 8 }}>
                <div style={{ fontSize: 11, color: '#aaa', fontFamily: 'inherit' }}>
                  {String(i + 1).padStart(2, '0')}
                </div>
                <div style={{
                  fontFamily: 'Georgia, "Times New Roman", serif',
                  fontSize: 22,
                  fontWeight: 500,
                  color: '#1a1a1a',
                  lineHeight: 1.2,
                  marginTop: 2,
                }}>
                  {s.headline}
                </div>
              </div>

              {/* Row 3: subheadline */}
              <div style={{
                fontSize: 13,
                fontStyle: 'italic',
                color: '#555',
                marginTop: 4,
              }}>
                {s.subheadline}
              </div>

              {/* Row 4: narrative */}
              <div style={{
                fontSize: 13,
                lineHeight: 1.75,
                color: '#444',
                marginTop: 10,
              }}>
                {s.narrative}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
