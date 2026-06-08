import { useState } from 'react'
import TeamPageOne from './components/TeamPageOne'
import TeamPageTwo from './components/TeamPageTwo'
import Overview from './components/Overview'
import Storylines from './components/Storylines'
import DreamTeam from './components/DreamTeam'
import Schedule from './components/Schedule'
import Homepage from './components/Homepage'
import Bracket from './components/Bracket'
import './App.css'

const teamModules = import.meta.glob('./data/teams/*.json', { eager: true })
const teams = Object.values(teamModules)
  .map(m => m.default)
  .sort((a, b) => {
    if (a.meta.group < b.meta.group) return -1
    if (a.meta.group > b.meta.group) return 1
    return a.name.localeCompare(b.name)
  })

const GROUPS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L']

function firstInGroup(group) {
  return teams.find(t => t.meta.group === group)
}

export default function App() {
  const [entered, setEntered] = useState(false)
  const [activeGroup, setActiveGroup] = useState('I')
  const [selectedTeamId, setSelectedTeamId] = useState('france')
  const [activeView, setActiveView] = useState('schedule')

  const selectedTeam = teams.find(t => t.id === selectedTeamId) ?? teams[0]
  const groupTeams = teams.filter(t => t.meta.group === activeGroup)

  function selectGroup(g) {
    setActiveGroup(g)
    const first = firstInGroup(g)
    if (first) setSelectedTeamId(first.id)
  }

  function selectTeam(team) {
    setSelectedTeamId(team.id)
    setActiveGroup(team.meta.group)
    setActiveView('guide')
  }

  if (!entered) return <Homepage onEnter={() => setEntered(true)} />

  return (
    <div style={{ fontFamily: 'var(--font-serif)' }}>
      {/* ── TOP NAV ──────────────────────────────────────── */}
      <div style={{
        background: 'white',
        borderBottom: '1px solid var(--gray-200)',
        position: 'sticky',
        top: 0,
        zIndex: 100,
      }}>
        <div style={{
          maxWidth: 680,
          margin: '0 auto',
          padding: '10px 16px',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
        }}>
          <button
            onClick={() => setEntered(false)}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: 0,
              fontFamily: 'var(--font-serif)',
              fontSize: 14,
              fontWeight: 700,
              color: 'var(--gray-900)',
              letterSpacing: '-0.01em',
              whiteSpace: 'nowrap',
              flexShrink: 0,
            }}
          >
            2026 WC
          </button>
          <div style={{ position: 'relative', flex: 1, minWidth: 0 }}>
          <div className="scroll-x" style={{ display: 'flex', gap: 5 }}>
            {[
              { id: 'schedule', label: 'Schedule' },
              { id: 'guide', label: 'Guide' },
              { id: 'overview', label: 'Overview' },
              { id: 'bracket', label: 'Bracket' },
              { id: 'storylines', label: 'Storylines' },
              { id: 'dreamteam', label: 'Dream Team' },
            ].map(({ id, label }) => (
              <button
                key={id}
                onClick={() => setActiveView(id)}
                style={{
                  background: activeView === id ? 'var(--gray-900)' : 'transparent',
                  color: activeView === id ? 'white' : 'var(--gray-500)',
                  border: activeView === id ? 'none' : '1px solid transparent',
                  borderRadius: 20,
                  padding: '5px 13px',
                  fontSize: 13,
                  cursor: 'pointer',
                  fontFamily: 'var(--font-sans)',
                  fontWeight: activeView === id ? 600 : 400,
                  whiteSpace: 'nowrap',
                  flexShrink: 0,
                  transition: 'all 0.15s',
                }}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="nav-fade-right" />
          </div>
        </div>
      </div>

      {/* ── GROUP PILLS ──────────────────────────────────── */}
      {activeView === 'guide' && (
        <div style={{
          background: 'var(--gray-100)',
          borderBottom: '1px solid var(--gray-200)',
          padding: '8px 0',
        }}>
          <div className="scroll-x" style={{
            maxWidth: 680,
            margin: '0 auto',
            display: 'flex',
            gap: 6,
            padding: '0 16px',
          }}>
            {GROUPS.map(g => {
              const isActive = g === activeGroup
              return (
                <button
                  key={g}
                  onClick={() => selectGroup(g)}
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: '50%',
                    fontSize: 13,
                    fontWeight: 500,
                    cursor: 'pointer',
                    border: isActive ? 'none' : '1px solid #d0d0d0',
                    background: isActive ? selectedTeam.accentColor : 'white',
                    color: isActive ? 'white' : 'var(--gray-700)',
                    fontFamily: 'inherit',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: 0,
                  }}
                >
                  {g}
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* ── TEAM CARDS ROW ───────────────────────────────── */}
      {activeView === 'guide' && (
        <div style={{
          background: 'white',
          borderBottom: '1px solid #e0e0e0',
        }}>
          <div className="team-cards-row" style={{
            maxWidth: 680,
            margin: '0 auto',
            padding: '8px 16px',
            display: 'flex',
            gap: 8,
          }}>
            {groupTeams.map(t => {
              const isSelected = t.id === selectedTeamId
              return (
                <div
                  className="team-card"
                  key={t.id}
                  onClick={() => setSelectedTeamId(t.id)}
                  style={{
                    flex: 1,
                    padding: '10px 12px',
                    borderRadius: 6,
                    cursor: 'pointer',
                    background: isSelected ? 'var(--gray-50)' : 'white',
                    borderLeft: isSelected
                      ? `3px solid ${t.accentColor}`
                      : '3px solid transparent',
                  }}
                  onMouseEnter={e => {
                    if (!isSelected) e.currentTarget.style.background = 'var(--gray-100)'
                  }}
                  onMouseLeave={e => {
                    if (!isSelected) e.currentTarget.style.background = 'white'
                  }}
                >
                  <div style={{ fontSize: 22 }}>{t.flagEmoji}</div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--gray-900)', marginTop: 4 }}>
                    {t.name}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--gray-500)', marginTop: 2 }}>
                    #{t.meta.fifaRanking}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--gray-500)' }}>
                    {t.meta.oddsToWin}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* ── PAGE CONTENT ─────────────────────────────────── */}
      {activeView === 'schedule' ? (
        <div style={{ background: 'var(--gray-100)', minHeight: 'calc(100vh - 100px)' }}>
          <Schedule teams={teams} onSelectTeam={selectTeam} />
        </div>
      ) : (
      <div style={{
        maxWidth: 680,
        margin: '0 auto',
        padding: '24px 16px',
        background: 'var(--surface)',
        minHeight: 'calc(100vh - 200px)',
      }}>
        {activeView === 'guide' ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ background: 'white', borderRadius: 8, overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
              <TeamPageOne team={selectedTeam} onViewStorylines={() => setActiveView('storylines')} />
            </div>
            <div style={{ background: 'white', borderRadius: 8, overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
              <TeamPageTwo team={selectedTeam} />
            </div>
          </div>
        ) : activeView === 'overview' ? (
          <Overview teams={teams} groups={GROUPS} onSelectTeam={selectTeam} />
        ) : activeView === 'bracket' ? (
          <Bracket />
        ) : activeView === 'storylines' ? (
          <Storylines />
        ) : (
          <DreamTeam />
        )}
      </div>
      )}
    </div>
  )
}
