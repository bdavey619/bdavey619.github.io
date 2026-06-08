import PitchDiagram from './PitchDiagram'

export default function TeamPageTwo({ team }) {
  const {
    accentColor, name, nickname, meta, schedule,
    history, allTimeRecord, pitch,
  } = team

  const muted = 'var(--gray-500)'
  const serif = 'var(--font-serif)'

  const SectionLabel = ({ label }) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 8 }}>
      <div style={{ width: 3, height: 12, background: accentColor, flexShrink: 0 }} />
      <span style={{
        fontSize: 9,
        fontWeight: 700,
        letterSpacing: '0.1em',
        textTransform: 'uppercase',
        color: muted,
        fontFamily: 'var(--font-sans)',
      }}>
        {label}
      </span>
    </div>
  )

  function resultBadge(row) {
    const base = {
      display: 'inline-block',
      padding: '1px 7px',
      borderRadius: 3,
      fontSize: 10,
      fontWeight: 600,
      lineHeight: '16px',
      fontFamily: 'var(--font-sans)',
    }
    switch (row.tier) {
      case 'winner':
        return <span style={{ ...base, background: accentColor, color: '#fff' }}>{row.result}</span>
      case 'final':
        return <span style={{ ...base, background: 'var(--gray-200)', color: 'var(--gray-700)' }}>{row.result}</span>
      case 'deep':
        return <span style={{ fontSize: 11, color: 'var(--gray-700)', fontFamily: 'var(--font-sans)' }}>{row.result}</span>
      case 'early':
        return <span style={{ fontSize: 11, color: muted, fontFamily: 'var(--font-sans)' }}>{row.result}</span>
      case 'dnq':
        return <span style={{ fontSize: 11, color: 'var(--gray-400)', fontStyle: 'italic', fontFamily: 'var(--font-sans)' }}>DNQ</span>
      default:
        return <span style={{ fontSize: 11, fontFamily: 'var(--font-sans)' }}>{row.result}</span>
    }
  }

  return (
    <div style={{
      fontFamily: serif,
      background: '#fff',
      color: 'var(--gray-900)',
      overflow: 'hidden',
      border: '1px solid #e0e0e0',
      borderTop: 'none',
      marginTop: 16,
    }}>

      {/* 1. TOP BORDER */}
      <div style={{
        height: 4,
        background: accentColor,
        borderRadius: '2px 2px 0 0',
      }} />

      {/* 2. HEADER */}
      <div style={{
        background: '#fff',
        padding: '0.75rem 1.5rem 0.65rem',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        borderBottom: '0.5px solid #e0e0e0',
      }}>
        {/* Left — label + name + nickname on same line */}
        <div>
          <div style={{
            fontSize: 10,
            color: muted,
            letterSpacing: '0.05em',
            textTransform: 'uppercase',
            fontFamily: 'var(--font-sans)',
            marginBottom: 2,
          }}>
            2026 FIFA WORLD CUP · WATCH GUIDE · P.2
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
            <span style={{
              fontFamily: serif,
              fontSize: 22,
              fontWeight: 500,
              lineHeight: 1,
              color: 'var(--gray-900)',
            }}>
              {name}
            </span>
            <span style={{
              fontSize: 15,
              fontStyle: 'italic',
              color: muted,
            }}>
              {nickname}
            </span>
          </div>
        </div>

        {/* Right — four stat pills with dividers */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 0, fontFamily: 'var(--font-sans)' }}>
          {[
            { label: 'FIFA RANKING', value: `#${meta.fifaRanking}`, colored: false },
            { label: 'ODDS TO WIN', value: meta.oddsToWin, colored: true },
            { label: 'IMPLIED PROB.', value: meta.impliedProbability, colored: false },
            { label: 'GROUP', value: meta.group, colored: false },
          ].map(({ label, value, colored }, i) => (
            <div key={label} style={{ display: 'flex', alignItems: 'center' }}>
              {i > 0 && (
                <div style={{
                  width: '0.5px',
                  height: 30,
                  background: 'var(--gray-200)',
                  margin: '0 10px',
                }} />
              )}
              <div style={{ textAlign: 'center' }}>
                <div style={{
                  fontSize: 9,
                  color: muted,
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  marginBottom: 1,
                }}>
                  {label}
                </div>
                <div style={{
                  fontSize: 22,
                  fontWeight: 500,
                  lineHeight: 1,
                  color: colored ? accentColor : 'var(--gray-900)',
                }}>
                  {value}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 3. MAIN BODY */}
      <div className="team-body-grid-p2" style={{
        display: 'grid',
        gridTemplateColumns: '1fr 228px',
        minHeight: 400,
      }}>

        {/* LEFT — PitchDiagram */}
        <div className="team-left-col-p2" style={{
          padding: '1rem 1.2rem 1rem 1.5rem',
          borderRight: '0.5px solid #e0e0e0',
        }}>
          <PitchDiagram players={pitch.players} accentColor={accentColor} />
        </div>

        {/* RIGHT PANEL */}
        <div style={{ display: 'flex', flexDirection: 'column' }}>

          {/* SCHEDULE */}
          <div style={{ padding: '1rem 1.1rem 0.9rem', borderBottom: '0.5px solid #e0e0e0' }}>
            <SectionLabel label={`Group ${meta.group} Schedule`} />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {schedule.map((match, i) => (
                <div
                  key={i}
                  style={{
                    background: 'var(--gray-50)',
                    borderRadius: 6,
                    padding: '8px 10px',
                  }}
                >
                  {/* Date + city row */}
                  <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    marginBottom: 3,
                  }}>
                    <span style={{
                      fontSize: 9,
                      color: muted,
                      fontWeight: 700,
                      fontFamily: 'var(--font-sans)',
                      textTransform: 'uppercase',
                      letterSpacing: '0.04em',
                    }}>
                      {match.date} · {match.time}
                    </span>
                    <span style={{
                      fontSize: 9,
                      color: muted,
                      fontFamily: 'var(--font-sans)',
                    }}>
                      {match.city}
                    </span>
                  </div>
                  {/* Teams + home/away */}
                  <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}>
                    <span style={{
                      fontSize: 13,
                      fontWeight: 500,
                      fontFamily: serif,
                    }}>
                      {match.isAway ? `${name} vs ${match.opponent}` : `${name} vs ${match.opponent}`}
                    </span>
                    <span style={{
                      fontSize: 9,
                      fontWeight: 600,
                      fontFamily: 'var(--font-sans)',
                      color: match.isAway ? muted : accentColor,
                      marginLeft: 6,
                      whiteSpace: 'nowrap',
                    }}>
                      {match.isAway ? 'Away' : 'Home'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* HISTORY */}
          <div style={{ flex: 1, padding: '1rem 1.1rem 0.9rem' }}>
            <SectionLabel label="Tournament History" />

            {/* Table rows */}
            <div>
              {history.map((row, i) => (
                <div
                  key={row.year}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '34px 1fr auto',
                    alignItems: 'center',
                    padding: '3.5px 0',
                    borderBottom: i < history.length - 1 ? '0.5px solid #e8e8e8' : 'none',
                  }}
                >
                  <span style={{ fontSize: 10, color: muted, fontFamily: 'var(--font-sans)' }}>
                    {row.year}
                  </span>
                  <span style={{ fontSize: 11, color: 'var(--gray-900)', fontFamily: 'var(--font-sans)' }}>
                    {row.host}
                  </span>
                  <span>{resultBadge(row)}</span>
                </div>
              ))}
            </div>

            {/* Summary tiles */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr 1fr',
              gap: 5,
              marginTop: 10,
            }}>
              {[
                { label: 'appearances', value: allTimeRecord.appearances },
                { label: 'titles', value: allTimeRecord.titles },
                { label: 'finals', value: allTimeRecord.finals },
              ].map(({ label, value }) => (
                <div
                  key={label}
                  style={{
                    background: 'var(--gray-50)',
                    borderRadius: 6,
                    padding: '5px 4px',
                    textAlign: 'center',
                    fontFamily: 'var(--font-sans)',
                  }}
                >
                  <div style={{ fontSize: 16, fontWeight: 500, lineHeight: 1 }}>{value}</div>
                  <div style={{ fontSize: 9, color: muted, marginTop: 3, letterSpacing: '0.03em' }}>
                    {label}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* 4. FOOTER */}
      <div style={{
        borderTop: '0.5px solid #e0e0e0',
        padding: '6px 1.5rem',
        display: 'flex',
        justifyContent: 'space-between',
        fontSize: 10,
        color: 'var(--gray-400)',
        fontFamily: 'var(--font-sans)',
        fontStyle: 'normal',
      }}>
        <span>World Cup Watch Guide · 2026 · p.2</span>
        <span>Odds: DraftKings · May 5, 2026</span>
      </div>
    </div>
  )
}
