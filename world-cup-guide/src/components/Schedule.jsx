import { useState, useEffect, useRef } from 'react'

const DATE_ORDER = [
  'Jun 11','Jun 12','Jun 13','Jun 14','Jun 15','Jun 16','Jun 17',
  'Jun 18','Jun 19','Jun 20','Jun 21','Jun 22','Jun 23','Jun 24',
  'Jun 25','Jun 26','Jun 27',
]

const DAY_NAMES = {
  'Jun 11': 'Wednesday', 'Jun 12': 'Thursday', 'Jun 13': 'Friday',
  'Jun 14': 'Saturday',  'Jun 15': 'Sunday',   'Jun 16': 'Monday',
  'Jun 17': 'Tuesday',   'Jun 18': 'Wednesday', 'Jun 19': 'Thursday',
  'Jun 20': 'Friday',    'Jun 21': 'Saturday',  'Jun 22': 'Sunday',
  'Jun 23': 'Monday',    'Jun 24': 'Tuesday',   'Jun 25': 'Wednesday',
  'Jun 26': 'Thursday',  'Jun 27': 'Friday',
}

// "Jun 11" → comparable number for today-detection
const DATE_TO_NUM = {}
DATE_ORDER.forEach((d, i) => { DATE_TO_NUM[d] = i })

function getTodayKey() {
  const now = new Date()
  const month = now.toLocaleString('en-US', { month: 'short' })
  const day = now.getDate()
  return `${month} ${day}` // e.g. "Jun 13"
}

function timeToSort(t) {
  const clean = t.replace(' ET', '').replace(' ', '')
  const isPM = clean.includes('PM')
  const isAM = clean.includes('AM')
  const num = parseInt(clean)
  if (clean === 'MidnightET' || clean === 'Midnight') return 2400
  let h = num
  if (isPM && h !== 12) h += 12
  if (isAM && h === 12) h = 0
  return h * 100
}

function buildMatches(teams) {
  const seen = new Set()
  const matches = []
  for (const team of teams) {
    for (const s of team.schedule) {
      const opponentTeam = teams.find(t => t.name === s.opponent)
      if (!opponentTeam) continue
      const homeTeam = s.isAway ? opponentTeam : team
      const awayTeam = s.isAway ? team : opponentTeam
      const key = [s.date, s.time, homeTeam.id, awayTeam.id].join('|')
      if (seen.has(key)) continue
      seen.add(key)
      matches.push({
        date: s.date,
        time: s.time,
        timeSort: timeToSort(s.time),
        group: team.meta.group,
        home: homeTeam,
        away: awayTeam,
        venue: s.venue,
        city: s.city,
      })
    }
  }
  return matches.sort((a, b) => {
    const di = DATE_ORDER.indexOf(a.date) - DATE_ORDER.indexOf(b.date)
    return di !== 0 ? di : a.timeSort - b.timeSort
  })
}

function groupByDate(matches) {
  const map = {}
  for (const m of matches) {
    if (!map[m.date]) map[m.date] = []
    map[m.date].push(m)
  }
  return map
}

export default function Schedule({ teams, onSelectTeam }) {
  const allMatches = buildMatches(teams)
  const [activeGroup, setActiveGroup] = useState('ALL')
  const dateRefs = useRef({})
  const todayKey = getTodayKey()

  const filtered = activeGroup === 'ALL'
    ? allMatches
    : allMatches.filter(m => m.group === activeGroup)

  const byDate = groupByDate(filtered)
  const dates = DATE_ORDER.filter(d => byDate[d])

  // Scroll to the first upcoming (today or future) date on mount / group change
  useEffect(() => {
    const todayIdx = DATE_TO_NUM[todayKey] ?? -1
    const target = dates.find(d => DATE_TO_NUM[d] >= todayIdx) ?? dates[0]
    if (target && dateRefs.current[target]) {
      setTimeout(() => {
        dateRefs.current[target]?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 80)
    }
  }, [activeGroup])

  return (
    <div>
      {/* Group filter — horizontal scroll, no wrap */}
      <div style={{
        background: 'white',
        borderBottom: '1px solid var(--gray-200)',
      }}>
        <div
          className="scroll-x"
          style={{
            maxWidth: 680,
            margin: '0 auto',
            display: 'flex',
            gap: 5,
            padding: '8px 16px',
            alignItems: 'center',
          }}
        >
          {['ALL', 'A','B','C','D','E','F','G','H','I','J','K','L'].map(g => (
            <button
              key={g}
              onClick={() => setActiveGroup(g)}
              style={{
                padding: g === 'ALL' ? '5px 12px' : '5px 9px',
                borderRadius: 20,
                fontSize: 12,
                fontWeight: activeGroup === g ? 600 : 400,
                cursor: 'pointer',
                border: 'none',
                background: activeGroup === g ? 'var(--gray-900)' : 'var(--gray-100)',
                color: activeGroup === g ? 'white' : 'var(--gray-500)',
                fontFamily: 'var(--font-sans)',
                flexShrink: 0,
                transition: 'all 0.15s',
              }}
            >
              {g === 'ALL' ? 'All groups' : `Group ${g}`}
            </button>
          ))}
        </div>
      </div>

      {/* "All times ET" note */}
      <div style={{
        maxWidth: 680,
        margin: '0 auto',
        padding: '10px 16px 0',
        fontSize: 11,
        color: 'var(--gray-400)',
        fontFamily: 'var(--font-sans)',
      }}>
        All kick-off times Eastern (ET)
      </div>

      {/* Match list */}
      <div style={{ maxWidth: 680, margin: '0 auto', padding: '10px 16px 48px' }}>
        {dates.map(date => {
          const isToday = date === todayKey
          const isFuture = DATE_TO_NUM[date] > (DATE_TO_NUM[todayKey] ?? -1)
          const isPast = DATE_TO_NUM[date] < (DATE_TO_NUM[todayKey] ?? 999)

          return (
            <div
              key={date}
              ref={el => { dateRefs.current[date] = el }}
              style={{ marginBottom: 28, scrollMarginTop: 60 }}
            >
              {/* Date header */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                marginBottom: 10,
                paddingBottom: 6,
                borderBottom: `1px solid ${isToday ? 'var(--gray-900)' : 'var(--gray-200)'}`,
              }}>
                <span style={{
                  fontSize: 15,
                  fontWeight: 700,
                  color: isPast ? 'var(--gray-400)' : 'var(--gray-900)',
                }}>
                  {date}
                </span>
                <span style={{ fontSize: 12, color: 'var(--gray-400)' }}>
                  {DAY_NAMES[date]}
                </span>
                {isToday && (
                  <span style={{
                    fontSize: 10,
                    fontWeight: 700,
                    letterSpacing: '0.08em',
                    background: 'var(--gray-900)',
                    color: 'white',
                    padding: '2px 7px',
                    borderRadius: 10,
                    fontFamily: 'var(--font-sans)',
                    textTransform: 'uppercase',
                  }}>
                    Today
                  </span>
                )}
                <span style={{
                  fontSize: 12,
                  color: 'var(--gray-400)',
                  marginLeft: 'auto',
                  fontFamily: 'var(--font-sans)',
                }}>
                  {byDate[date].length} match{byDate[date].length !== 1 ? 'es' : ''}
                </span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {byDate[date].map((m, i) => (
                  <MatchCard key={i} match={m} onSelectTeam={onSelectTeam} isPast={isPast} />
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function MatchCard({ match, onSelectTeam, isPast }) {
  const { time, group, home, away, city } = match
  return (
    <div style={{
      background: 'white',
      borderRadius: 8,
      padding: '10px 14px',
      boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
      display: 'grid',
      gridTemplateColumns: '52px 1fr 52px',
      alignItems: 'center',
      gap: 8,
      opacity: isPast ? 0.55 : 1,
    }}>
      {/* Time + group */}
      <div style={{ textAlign: 'center' }}>
        <div style={{
          fontSize: 12,
          fontWeight: 600,
          color: 'var(--gray-900)',
          fontFamily: 'var(--font-sans)',
        }}>
          {time.replace(' ET', '')}
        </div>
        <div style={{
          fontSize: 10,
          color: 'var(--gray-500)',
          background: 'var(--gray-100)',
          borderRadius: 3,
          padding: '1px 5px',
          marginTop: 3,
          display: 'inline-block',
          fontFamily: 'var(--font-sans)',
        }}>
          Grp {group}
        </div>
      </div>

      {/* Teams */}
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <TeamChip team={home} align="right" onSelectTeam={onSelectTeam} />
        <div style={{
          padding: '0 8px',
          fontSize: 11,
          fontWeight: 600,
          color: 'var(--gray-400)',
          flexShrink: 0,
          fontFamily: 'var(--font-sans)',
        }}>
          vs
        </div>
        <TeamChip team={away} align="left" onSelectTeam={onSelectTeam} />
      </div>

      {/* City */}
      <div style={{ textAlign: 'center' }}>
        <div style={{
          fontSize: 10,
          color: 'var(--gray-400)',
          lineHeight: 1.3,
          fontFamily: 'var(--font-sans)',
        }}>
          {city.split(',')[0]}
        </div>
      </div>
    </div>
  )
}

function TeamChip({ team, align, onSelectTeam }) {
  const [hovered, setHovered] = useState(false)
  const isRight = align === 'right'

  return (
    <button
      onClick={() => onSelectTeam(team)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      title="View team guide"
      style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        flexDirection: isRight ? 'row-reverse' : 'row',
        background: hovered ? 'var(--gray-100)' : 'none',
        border: 'none',
        cursor: 'pointer',
        padding: '4px 6px',
        fontFamily: 'var(--font-sans)',
        textAlign: isRight ? 'right' : 'left',
        borderRadius: 5,
        minWidth: 0,
        transition: 'background 0.12s',
      }}
    >
      <span style={{ fontSize: 20, flexShrink: 0 }}>{team.flagEmoji}</span>
      <div style={{ minWidth: 0, flex: 1 }}>
        <span style={{
          display: 'block',
          fontSize: 13,
          fontWeight: 600,
          color: 'var(--gray-900)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}>
          {team.name}
        </span>
        {hovered && (
          <span style={{
            display: 'block',
            fontSize: 10,
            color: team.accentColor,
            fontWeight: 500,
            letterSpacing: '0.04em',
          }}>
            View guide →
          </span>
        )}
      </div>
    </button>
  )
}
