export default function Overview({ teams, groups, onSelectTeam }) {
  function groupTeams(g) {
    return teams
      .filter(t => t.meta.group === g)
      .sort((a, b) => a.meta.fifaRanking - b.meta.fifaRanking)
  }

  function keyMatch(gTeams) {
    const [t1, t2] = gTeams
    if (!t1 || !t2) return null
    const entry = t1.schedule?.find(s =>
      s.opponent.toLowerCase().includes(t2.name.split('-')[0].toLowerCase()) ||
      t2.name.toLowerCase().includes(s.opponent.toLowerCase().split(' ')[0])
    )
    return { team1: t1, team2: t2, date: entry?.date ?? null }
  }

  return (
    <div>
      <div style={{ textAlign: 'center', marginBottom: 32 }}>
        <h1 style={{
          fontFamily: 'Georgia, serif',
          fontSize: 32,
          margin: '0 0 4px',
          color: '#1a1a1a',
        }}>
          2026 World Cup — Group Stage
        </h1>
        <p style={{ fontSize: 14, color: '#888', margin: 0 }}>
          48 teams · 12 groups · June 12 – July 19
        </p>
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
        gap: 16,
      }}>
        {groups.map(g => {
          const gTeams = groupTeams(g)
          const topTwo = gTeams.slice(0, 2)
          const km = keyMatch(gTeams)

          return (
            <div key={g} style={{
              background: 'white',
              borderRadius: 8,
              overflow: 'hidden',
              boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
            }}>
              {/* Card header */}
              <div style={{
                background: '#1a1a1a',
                padding: '10px 14px',
              }}>
                <span style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: 'white',
                  letterSpacing: '0.06em',
                }}>
                  GROUP {g}
                </span>
              </div>

              {/* Team rows */}
              <div style={{ padding: '0 14px' }}>
                {gTeams.map((t, i) => {
                  const isFav = i === 0
                  const isLast = i === gTeams.length - 1
                  return (
                    <div
                      key={t.id}
                      onClick={() => onSelectTeam(t)}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '8px 0',
                        borderBottom: isLast ? 'none' : '0.5px solid #f0f0f0',
                        cursor: 'pointer',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ fontSize: 16 }}>{t.flagEmoji}</span>
                        <span style={{
                          fontSize: 13,
                          fontWeight: isFav ? 600 : 400,
                          color: '#1a1a1a',
                        }}>
                          {t.name}
                        </span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontSize: 11, color: '#888' }}>
                          #{t.meta.fifaRanking}
                        </span>
                        <span style={{ fontSize: 11, color: t.accentColor }}>
                          {t.meta.oddsToWin}
                        </span>
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* Card footer */}
              {km && (
                <div style={{
                  padding: '8px 14px 10px',
                  borderTop: '1px solid #f0f0f0',
                }}>
                  <span style={{ fontSize: 11, fontStyle: 'italic', color: '#888' }}>
                    Key match: {km.team1.name} vs {km.team2.name}
                    {km.date ? ` · ${km.date}` : ''}
                  </span>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
