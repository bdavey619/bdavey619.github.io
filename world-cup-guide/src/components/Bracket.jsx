// 2026 World Cup knockout bracket
// 48 teams → top 2 per group (24) + 8 best 3rd-place teams = 32 advance
// R32 → R16 → QF → SF → Final

const TBD = { name: 'TBD', flag: '' }

// Pre-set bracket seedings (R32 matchups based on FIFA 2026 bracket draw)
// Left half feeds to the top of the bracket, right half to the bottom
const R32_MATCHES = [
  // Left bracket
  { id: 'r32-1',  home: '1st · Group A', away: '2nd · Group B' },
  { id: 'r32-2',  home: '1st · Group C', away: '2nd · Group D' },
  { id: 'r32-3',  home: '1st · Group E', away: '2nd · Group F' },
  { id: 'r32-4',  home: '1st · Group G', away: '2nd · Group H' },
  { id: 'r32-5',  home: '1st · Group B', away: '2nd · Group A' },
  { id: 'r32-6',  home: '1st · Group D', away: '2nd · Group C' },
  { id: 'r32-7',  home: '1st · Group F', away: '2nd · Group E' },
  { id: 'r32-8',  home: '1st · Group H', away: '2nd · Group G' },
  // Right bracket
  { id: 'r32-9',  home: '1st · Group I', away: '2nd · Group J' },
  { id: 'r32-10', home: '1st · Group K', away: '2nd · Group L' },
  { id: 'r32-11', home: 'Best 3rd (A/B/C/D)', away: 'Best 3rd (E/F/G/H)' },
  { id: 'r32-12', home: 'Best 3rd (I/J/K/L)', away: '2nd · Group L' },
  { id: 'r32-13', home: '1st · Group J', away: '2nd · Group K' },
  { id: 'r32-14', home: '1st · Group L', away: '2nd · Group J' },
  { id: 'r32-15', home: 'Best 3rd (A/B/C)', away: 'Best 3rd (D/E/F)' },
  { id: 'r32-16', home: 'Best 3rd (G/H/I)', away: 'Best 3rd (J/K/L)' },
]

const ROUNDS = [
  { id: 'r32', label: 'Round of 32', matches: 16, dates: 'Jul 1–4' },
  { id: 'r16', label: 'Round of 16', matches: 8,  dates: 'Jul 7–10' },
  { id: 'qf',  label: 'Quarter-finals', matches: 4, dates: 'Jul 14–15' },
  { id: 'sf',  label: 'Semi-finals', matches: 2, dates: 'Jul 18–19' },
  { id: 'f',   label: 'Final', matches: 1, dates: 'Jul 23' },
]

function MatchSlot({ home, away, isCompact, accentLeft }) {
  return (
    <div style={{
      background: 'white',
      borderRadius: 6,
      overflow: 'hidden',
      boxShadow: '0 1px 3px rgba(0,0,0,0.07)',
      minWidth: isCompact ? 120 : 150,
    }}>
      <TeamRow label={home} accentColor={accentLeft} />
      <div style={{ height: '0.5px', background: 'var(--surface)' }} />
      <TeamRow label={away} />
    </div>
  )
}

function TeamRow({ label, accentColor }) {
  const hasResult = false
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '6px 9px',
      borderLeft: accentColor ? `3px solid ${accentColor}` : '3px solid transparent',
    }}>
      <span style={{
        fontSize: 11,
        color: label.startsWith('TBD') || label.includes('·') || label.includes('Best') ? 'var(--gray-400)' : 'var(--gray-900)',
        fontStyle: label.includes('·') || label.includes('Best') ? 'italic' : 'normal',
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        maxWidth: 130,
      }}>
        {label}
      </span>
    </div>
  )
}

function RoundColumn({ round, leftMatches }) {
  const placeholders = Array.from({ length: round.matches }, (_, i) => ({
    id: `${round.id}-${i}`,
    home: leftMatches?.[i]?.home ?? 'TBD',
    away: leftMatches?.[i]?.away ?? 'TBD',
  }))

  const isFinal = round.id === 'f'

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: isFinal ? 0 : 8,
      justifyContent: 'space-around',
      flex: '0 0 auto',
    }}>
      {placeholders.map((m, i) => (
        <div key={m.id} style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', flex: 1 }}>
          <MatchSlot home={m.home} away={m.away} isCompact={round.matches > 4} />
        </div>
      ))}
    </div>
  )
}

export default function Bracket() {
  return (
    <div>
      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: 28 }}>
        <h1 style={{
          fontFamily: 'var(--font-serif)',
          fontSize: 28,
          fontWeight: 500,
          color: 'var(--gray-900)',
          margin: '0 0 4px',
        }}>
          Tournament Bracket
        </h1>
        <p style={{ fontSize: 13, color: 'var(--gray-500)', margin: 0 }}>
          Knockout stage begins July 1 · 32 teams advance from the group stage
        </p>
      </div>

      {/* Advance note */}
      <div style={{
        background: 'white',
        borderRadius: 8,
        padding: '14px 18px',
        marginBottom: 20,
        boxShadow: '0 1px 3px rgba(0,0,0,0.07)',
        display: 'flex',
        gap: 24,
        flexWrap: 'wrap',
      }}>
        {[
          { label: '24 teams', note: 'Top 2 from each of 12 groups' },
          { label: '+ 8 teams', note: 'Best 8 third-place finishers' },
          { label: '= 32 teams', note: 'Enter the Round of 32' },
        ].map(({ label, note }) => (
          <div key={label}>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--gray-900)' }}>{label}</div>
            <div style={{ fontSize: 11, color: 'var(--gray-500)' }}>{note}</div>
          </div>
        ))}
      </div>

      {/* Round headers + bracket scroll */}
      <div style={{
        background: 'white',
        borderRadius: 8,
        boxShadow: '0 1px 3px rgba(0,0,0,0.07)',
        overflow: 'hidden',
      }}>
        {/* Round labels */}
        <div style={{
          display: 'flex',
          borderBottom: '1px solid #f0f0f0',
          background: 'var(--gray-50)',
        }}>
          {ROUNDS.map(r => (
            <div key={r.id} style={{
              flex: 1,
              padding: '10px 12px',
              borderRight: '1px solid #f0f0f0',
              textAlign: 'center',
            }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--gray-900)' }}>{r.label}</div>
              <div style={{ fontSize: 10, color: 'var(--gray-400)', marginTop: 2 }}>{r.dates}</div>
            </div>
          ))}
        </div>

        {/* Scroll hint */}
        <div style={{
          padding: '6px 14px 4px',
          fontSize: 10,
          color: 'var(--gray-400)',
          fontFamily: 'var(--font-sans)',
          textAlign: 'right',
          borderBottom: '1px solid var(--gray-100)',
        }}>
          ← scroll to see full bracket →
        </div>

        {/* Bracket visual */}
        <div className="scroll-x" style={{
          padding: '16px 12px',
        }}>
          <div style={{
            display: 'flex',
            gap: 12,
            minHeight: 520,
            alignItems: 'stretch',
          }}>
            {/* R32 */}
            <div style={{
              flex: '0 0 auto',
              width: 158,
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
            }}>
              {R32_MATCHES.map(m => (
                <MatchSlot key={m.id} home={m.home} away={m.away} isCompact />
              ))}
            </div>

            {/* Connector */}
            <div style={{ width: 12, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <div style={{ width: 1, height: '100%', background: 'var(--gray-200)' }} />
            </div>

            {/* R16 */}
            <div style={{
              flex: '0 0 auto',
              width: 158,
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-around',
            }}>
              {Array.from({ length: 8 }, (_, i) => (
                <MatchSlot key={i} home="TBD" away="TBD" isCompact />
              ))}
            </div>

            <div style={{ width: 12, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <div style={{ width: 1, height: '100%', background: 'var(--gray-200)' }} />
            </div>

            {/* QF */}
            <div style={{
              flex: '0 0 auto',
              width: 158,
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-around',
            }}>
              {Array.from({ length: 4 }, (_, i) => (
                <MatchSlot key={i} home="TBD" away="TBD" />
              ))}
            </div>

            <div style={{ width: 12, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <div style={{ width: 1, height: '100%', background: 'var(--gray-200)' }} />
            </div>

            {/* SF */}
            <div style={{
              flex: '0 0 auto',
              width: 158,
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-around',
            }}>
              {Array.from({ length: 2 }, (_, i) => (
                <MatchSlot key={i} home="TBD" away="TBD" />
              ))}
            </div>

            <div style={{ width: 12, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <div style={{ width: 1, height: '100%', background: 'var(--gray-200)' }} />
            </div>

            {/* Final */}
            <div style={{
              flex: '0 0 auto',
              width: 158,
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
            }}>
              <div>
                <div style={{
                  fontSize: 9,
                  fontWeight: 700,
                  letterSpacing: '0.1em',
                  textTransform: 'uppercase',
                  color: 'var(--gray-500)',
                  marginBottom: 6,
                  textAlign: 'center',
                }}>
                  🏆 Final · Jul 23
                </div>
                <MatchSlot home="TBD" away="TBD" />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Third place match */}
      <div style={{
        marginTop: 16,
        background: 'white',
        borderRadius: 8,
        padding: '14px 18px',
        boxShadow: '0 1px 3px rgba(0,0,0,0.07)',
        display: 'flex',
        alignItems: 'center',
        gap: 16,
      }}>
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--gray-900)' }}>3rd Place Match · Jul 22</div>
          <div style={{ fontSize: 11, color: 'var(--gray-400)', marginTop: 4, fontStyle: 'italic' }}>TBD vs TBD · MetLife Stadium, East Rutherford</div>
        </div>
      </div>
    </div>
  )
}
