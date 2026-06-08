import { useEffect, useState } from 'react'

const FLAGS = [
  '🇲🇽','🇨🇿','🇿🇦','🇰🇷','🇨🇦','🇧🇦','🇨🇭','🇶🇦',
  '🇧🇷','🇭🇹','🇲🇦','🏴󠁧󠁢󠁳󠁣󠁴󠁿','🇺🇸','🇵🇾','🇦🇺','🇹🇷',
  '🇩🇪','🇪🇨','🇨🇮','🇨🇼','🇳🇱','🇯🇵','🇹🇳','🇸🇪',
  '🇧🇪','🇳🇿','🇪🇬','🇮🇷','🇪🇸','🇺🇾','🇸🇦','🇨🇻',
  '🇫🇷','🇳🇴','🇮🇶','🇸🇳','🇦🇷','🇦🇹','🇯🇴','🇩🇿',
  '🇨🇴','🇺🇿','🇨🇩','🇵🇹','🏴󠁧󠁢󠁥󠁮󠁧󠁿','🇵🇦','🇬🇭','🇭🇷',
]

// Simple SVG player silhouettes
function PlayerSilhouette({ pose, color, size = 120 }) {
  const poses = {
    celebrate: (
      <g>
        <ellipse cx="50" cy="12" rx="8" ry="9" />
        <path d="M50 21 L44 50 L40 78 L46 78 L50 58 L54 78 L60 78 L56 50 Z" />
        <path d="M44 33 L22 20 L20 25 L42 38 Z" />
        <path d="M56 33 L78 20 L80 25 L58 38 Z" />
      </g>
    ),
    kick: (
      <g>
        <ellipse cx="50" cy="12" rx="8" ry="9" />
        <path d="M50 21 L44 50 L42 78 L48 78 L50 60 L52 78 L58 78 L56 50 Z" />
        <path d="M44 33 L25 28 L24 33 L43 38 Z" />
        <path d="M56 31 L72 18 L75 22 L59 36 Z" />
        <path d="M54 50 L75 45 L76 50 L55 56 Z" />
        <circle cx="82" cy="49" r="7" />
      </g>
    ),
    arms_out: (
      <g>
        <ellipse cx="50" cy="12" rx="8" ry="9" />
        <path d="M50 21 L44 50 L40 78 L46 78 L50 58 L54 78 L60 78 L56 50 Z" />
        <path d="M44 33 L15 33 L15 38 L44 38 Z" />
        <path d="M56 33 L85 33 L85 38 L56 38 Z" />
      </g>
    ),
    run: (
      <g>
        <ellipse cx="52" cy="10" rx="8" ry="9" />
        <path d="M52 19 L46 46 L38 72 L44 74 L50 52 L58 74 L64 72 L56 46 Z" />
        <path d="M46 30 L28 20 L26 25 L44 35 Z" />
        <path d="M58 28 L72 38 L70 43 L56 33 Z" />
      </g>
    ),
  }

  return (
    <svg
      viewBox="0 0 100 90"
      width={size}
      height={size * 0.9}
      style={{ fill: color, opacity: 0.85 }}
    >
      {poses[pose]}
    </svg>
  )
}

// Crowd dot field
function CrowdField({ width, height }) {
  const [dots] = useState(() => {
    const crowdColors = [
      '#e63946','#2196f3','#4caf50','#ff9800','#9c27b0',
      '#00bcd4','#f44336','#3f51b5','#8bc34a','#ffc107',
      '#ffffff','#ff5722','#607d8b','#e91e63',
    ]
    return Array.from({ length: 280 }, (_, i) => ({
      x: Math.sin(i * 2.4) * 48 + 50,
      y: Math.cos(i * 1.7) * 45 + 50,
      r: (Math.sin(i * 3.1) * 0.5 + 0.5) * 2.5 + 1,
      color: crowdColors[i % crowdColors.length],
      opacity: (Math.sin(i * 1.3) * 0.5 + 0.5) * 0.5 + 0.3,
    }))
  })

  return (
    <svg
      viewBox="0 0 100 100"
      preserveAspectRatio="xMidYMid slice"
      style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}
    >
      {dots.map((d, i) => (
        <circle key={i} cx={d.x} cy={d.y} r={d.r} fill={d.color} opacity={d.opacity} />
      ))}
    </svg>
  )
}

export default function Homepage({ onEnter }) {
  const [visible, setVisible] = useState(false)
  const [exiting, setExiting] = useState(false)

  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 80)
    return () => clearTimeout(t)
  }, [])

  function handleEnter() {
    setExiting(true)
    setTimeout(onEnter, 380)
  }

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      background: '#080c08',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
      fontFamily: "'Georgia', 'Times New Roman', serif",
      opacity: exiting ? 0 : (visible ? 1 : 0),
      transition: exiting ? 'opacity 0.38s ease' : 'opacity 0.6s ease',
    }}>

      {/* Pitch stripe texture */}
      <div style={{
        position: 'absolute',
        inset: 0,
        backgroundImage: 'repeating-linear-gradient(90deg, transparent, transparent 60px, rgba(255,255,255,0.012) 60px, rgba(255,255,255,0.012) 120px)',
        pointerEvents: 'none',
      }} />

      {/* Top header bar */}
      <div style={{
        position: 'relative',
        zIndex: 10,
        padding: '18px 28px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
      }}>
        <span style={{
          fontSize: 10,
          letterSpacing: '0.18em',
          textTransform: 'uppercase',
          color: 'rgba(255,255,255,0.4)',
          fontFamily: 'sans-serif',
        }}>
          The Official Watch Guide
        </span>
        <span style={{
          fontSize: 10,
          letterSpacing: '0.12em',
          textTransform: 'uppercase',
          color: 'rgba(255,255,255,0.4)',
          fontFamily: 'sans-serif',
        }}>
          United States · Canada · Mexico
        </span>
      </div>

      {/* Main content */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        position: 'relative',
        zIndex: 10,
        padding: '0 24px',
      }}>

        {/* Giant ghosted year */}
        <div style={{
          position: 'absolute',
          fontSize: 'clamp(160px, 28vw, 340px)',
          fontWeight: 700,
          color: 'transparent',
          WebkitTextStroke: '1px rgba(255,255,255,0.06)',
          lineHeight: 1,
          userSelect: 'none',
          pointerEvents: 'none',
          letterSpacing: '-0.04em',
        }}>
          2026
        </div>

        {/* Player silhouettes */}
        <div style={{
          position: 'absolute',
          bottom: 60,
          left: '50%',
          transform: 'translateX(-50%)',
          display: 'flex',
          alignItems: 'flex-end',
          gap: 0,
          pointerEvents: 'none',
          width: '100%',
          maxWidth: 700,
          justifyContent: 'space-around',
          padding: '0 40px',
        }}>
          <PlayerSilhouette pose="run" color="rgba(255,255,255,0.07)" size={80} />
          <PlayerSilhouette pose="kick" color="rgba(255,255,255,0.10)" size={110} />
          <PlayerSilhouette pose="celebrate" color="rgba(255,255,255,0.13)" size={140} />
          <PlayerSilhouette pose="arms_out" color="rgba(255,255,255,0.10)" size={110} />
          <PlayerSilhouette pose="run" color="rgba(255,255,255,0.07)" size={80} />
        </div>

        {/* Central text */}
        <div style={{ textAlign: 'center', position: 'relative' }}>
          <div style={{
            fontSize: 'clamp(9px, 1.4vw, 12px)',
            letterSpacing: '0.28em',
            textTransform: 'uppercase',
            color: 'rgba(255,255,255,0.45)',
            marginBottom: 14,
            fontFamily: 'sans-serif',
          }}>
            FIFA World Cup
          </div>

          <h1 style={{
            fontSize: 'clamp(52px, 9vw, 108px)',
            fontWeight: 400,
            color: 'white',
            margin: '0 0 6px',
            lineHeight: 1,
            letterSpacing: '-0.02em',
          }}>
            2026
          </h1>

          {/* Three host nation color bar */}
          <div style={{
            display: 'flex',
            justifyContent: 'center',
            gap: 3,
            margin: '16px auto',
            width: 180,
          }}>
            {/* USA */}
            <div style={{ flex: 1, height: 3, background: '#B22234', borderRadius: 2 }} />
            <div style={{ flex: 1, height: 3, background: '#ffffff', borderRadius: 2 }} />
            <div style={{ flex: 1, height: 3, background: '#3C3B6E', borderRadius: 2 }} />
            {/* Canada */}
            <div style={{ flex: 1, height: 3, background: '#FF0000', borderRadius: 2 }} />
            {/* Mexico */}
            <div style={{ flex: 1, height: 3, background: '#006847', borderRadius: 2 }} />
            <div style={{ flex: 1, height: 3, background: '#CE1126', borderRadius: 2 }} />
          </div>

          <div style={{
            fontSize: 'clamp(11px, 1.6vw, 14px)',
            color: 'rgba(255,255,255,0.5)',
            letterSpacing: '0.08em',
            marginBottom: 32,
            fontFamily: 'sans-serif',
          }}>
            June 11 – July 19 &nbsp;·&nbsp; 48 Teams &nbsp;·&nbsp; 12 Groups
          </div>

          {/* Enter button */}
          <button
            onClick={handleEnter}
            style={{
              background: '#2d7a2d',
              color: 'white',
              border: 'none',
              borderRadius: 4,
              padding: '14px 40px',
              fontSize: 14,
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              cursor: 'pointer',
              fontFamily: 'sans-serif',
              fontWeight: 600,
              boxShadow: '0 0 32px rgba(45,122,45,0.4)',
              transition: 'all 0.2s ease',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.background = '#3a9e3a'
              e.currentTarget.style.boxShadow = '0 0 48px rgba(45,122,45,0.6)'
              e.currentTarget.style.transform = 'translateY(-1px)'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = '#2d7a2d'
              e.currentTarget.style.boxShadow = '0 0 32px rgba(45,122,45,0.4)'
              e.currentTarget.style.transform = 'translateY(0)'
            }}
          >
            Enter the Guide →
          </button>
        </div>
      </div>

      {/* Flag strip marquee */}
      <div style={{
        position: 'relative',
        zIndex: 10,
        borderTop: '1px solid rgba(255,255,255,0.07)',
        overflow: 'hidden',
        padding: '10px 0',
        background: 'rgba(0,0,0,0.3)',
      }}>
        <style>{`
          @keyframes marquee {
            0% { transform: translateX(0); }
            100% { transform: translateX(-50%); }
          }
        `}</style>
        <div style={{
          display: 'flex',
          width: 'max-content',
          animation: 'marquee 30s linear infinite',
          gap: 16,
        }}>
          {[...FLAGS, ...FLAGS].map((flag, i) => (
            <span key={i} style={{ fontSize: 22, opacity: 0.7 }}>{flag}</span>
          ))}
        </div>
      </div>

      {/* Crowd dots — bottom section behind flag strip */}
      <div style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        height: '35%',
        pointerEvents: 'none',
        opacity: 0.6,
      }}>
        <CrowdField />
      </div>

      {/* Green pitch glow at very bottom */}
      <div style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        height: 120,
        background: 'linear-gradient(to top, rgba(20,80,20,0.35), transparent)',
        pointerEvents: 'none',
      }} />
    </div>
  )
}
