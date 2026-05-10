import { useState } from 'react'
import TeamPageOne from './components/TeamPageOne'
import TeamPageTwo from './components/TeamPageTwo'
import Overview from './components/Overview'
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
  const [activeGroup, setActiveGroup] = useState('I')
  const [selectedTeamId, setSelectedTeamId] = useState('france')
  const [activeView, setActiveView] = useState('guide')

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

  return (
    <div>
      {/* ── TOP NAV ──────────────────────────────────────── */}
      <div style={{
        background: '#f5f5f5',
        borderBottom: '1px solid #e0e0e0',
      }}>
        <div style={{
          maxWidth: 680,
          margin: '0 auto',
          padding: '12px 16px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <span style={{ fontSize: 15, fontWeight: 600, color: '#1a1a1a' }}>
            2026 World Cup Guide
          </span>
          <div style={{ display: 'flex', gap: 6 }}>
            {['guide', 'overview'].map(v => (
              <button
                key={v}
                onClick={() => setActiveView(v)}
                style={{
                  background: activeView === v ? '#1a1a1a' : 'white',
                  color: activeView === v ? 'white' : '#1a1a1a',
                  border: activeView === v ? 'none' : '1px solid #d0d0d0',
                  borderRadius: 20,
                  padding: '6px 16px',
                  fontSize: 13,
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                }}
              >
                {v.charAt(0).toUpperCase() + v.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── GROUP PILLS ──────────────────────────────────── */}
      {activeView === 'guide' && (
        <div style={{
          background: '#f5f5f5',
          borderBottom: '1px solid #e0e0e0',
          padding: '10px 0',
        }}>
          <div style={{
            maxWidth: 680,
            margin: '0 auto',
            display: 'flex',
            justifyContent: 'center',
            gap: 8,
            flexWrap: 'wrap',
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
                    color: isActive ? 'white' : '#555',
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
          <div style={{
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
                  key={t.id}
                  onClick={() => setSelectedTeamId(t.id)}
                  style={{
                    flex: 1,
                    padding: '10px 12px',
                    borderRadius: 6,
                    cursor: 'pointer',
                    background: isSelected ? '#fafafa' : 'white',
                    borderLeft: isSelected
                      ? `3px solid ${t.accentColor}`
                      : '3px solid transparent',
                  }}
                  onMouseEnter={e => {
                    if (!isSelected) e.currentTarget.style.background = '#f5f5f5'
                  }}
                  onMouseLeave={e => {
                    if (!isSelected) e.currentTarget.style.background = 'white'
                  }}
                >
                  <div style={{ fontSize: 22 }}>{t.flagEmoji}</div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#1a1a1a', marginTop: 4 }}>
                    {t.name}
                  </div>
                  <div style={{ fontSize: 11, color: '#888', marginTop: 2 }}>
                    #{t.meta.fifaRanking}
                  </div>
                  <div style={{ fontSize: 11, color: '#888' }}>
                    {t.meta.oddsToWin}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* ── PAGE CONTENT ─────────────────────────────────── */}
      <div style={{
        maxWidth: 680,
        margin: '0 auto',
        padding: '24px 16px',
        background: '#f0f0f0',
        minHeight: 'calc(100vh - 200px)',
      }}>
        {activeView === 'guide' ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ background: 'white', borderRadius: 8, overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
              <TeamPageOne team={selectedTeam} />
            </div>
            <div style={{ background: 'white', borderRadius: 8, overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
              <TeamPageTwo team={selectedTeam} />
            </div>
          </div>
        ) : (
          <Overview teams={teams} groups={GROUPS} onSelectTeam={selectTeam} />
        )}
      </div>
    </div>
  )
}
