const dreamTeam = {
  formation: "4-3-3",
  coach: {
    name: "Carlo Ancelotti",
    country: "Brazil",
    flagEmoji: "🇧🇷",
    club: "Brazil National Team",
    note: "The most decorated manager in Champions League history, Ancelotti transformed Brazil from a team searching for identity into genuine contenders by unlocking Vinícius Jr. as the focal point of a fluid, fearless attack. His calm authority and tactical flexibility make him the dream team's natural leader.",
  },
  players: [
    {
      name: "Emiliano Martínez",
      shortName: "DIBU",
      country: "Argentina",
      flagEmoji: "🇦🇷",
      club: "Aston Villa",
      position: "GK",
      role: "gk",
      accentColor: "#00529B",
      x: 226,
      y: 50,
      isCaptain: false,
      isKeyPlayer: true,
      note: "The penalty-saving hero of Qatar 2022, Martínez is the world's best shot-stopper and Argentina's emotional backbone — the keeper who wins matches when everything else has run out.",
    },
    {
      name: "Achraf Hakimi",
      shortName: "HAKIMI",
      country: "Morocco",
      flagEmoji: "🇲🇦",
      club: "Paris Saint-Germain",
      position: "RB",
      role: "def",
      accentColor: "#CE1126",
      x: 370,
      y: 140,
      isCaptain: false,
      isKeyPlayer: false,
      note: "The most attack-minded right back in world football, Hakimi combines elite pace with elite decision-making — as comfortable in the final third as he is defending his own box.",
    },
    {
      name: "Virgil van Dijk",
      shortName: "V.DIJK",
      country: "Netherlands",
      flagEmoji: "🇳🇱",
      club: "Liverpool",
      position: "CB",
      role: "def",
      accentColor: "#FF6600",
      x: 295,
      y: 140,
      isCaptain: false,
      isKeyPlayer: false,
      note: "Dominant in the air, commanding on the ground, and one of the few defenders capable of organizing an entire back four through voice alone — Van Dijk remains the gold standard at centre back.",
    },
    {
      name: "Joško Gvardiol",
      shortName: "GVARD.",
      country: "Croatia",
      flagEmoji: "🇭🇷",
      club: "Manchester City",
      position: "CB",
      role: "def",
      accentColor: "#EE1326",
      x: 157,
      y: 140,
      isCaptain: false,
      isKeyPlayer: false,
      note: "At 22, Gvardiol is already one of the three best central defenders in Europe — composed under pressure, quick in recovery, and increasingly dangerous when surging forward from the left side.",
    },
    {
      name: "Theo Hernández",
      shortName: "T.HERNDZ",
      country: "France",
      flagEmoji: "🇫🇷",
      club: "AC Milan",
      position: "LB",
      role: "def",
      accentColor: "#002395",
      x: 82,
      y: 140,
      isCaptain: false,
      isKeyPlayer: false,
      note: "The most explosive left back in world football at full speed, Hernández creates chaos in wide areas and has the technique to deliver in decisive moments from open play.",
    },
    {
      name: "Rodri",
      shortName: "RODRI",
      country: "Spain",
      flagEmoji: "🇪🇸",
      club: "Manchester City",
      position: "DM",
      role: "mid",
      accentColor: "#C60C30",
      x: 226,
      y: 222,
      isCaptain: false,
      isKeyPlayer: false,
      note: "The 2024 Ballon d'Or winner and the engine of Spain's dominance — Rodri reads the game two seconds faster than anyone else, breaking up attacks before they materialize and recycling possession with near-perfect efficiency.",
    },
    {
      name: "Jude Bellingham",
      shortName: "JUDE B.",
      country: "England",
      flagEmoji: "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
      club: "Real Madrid",
      position: "CM",
      role: "mid",
      accentColor: "#012169",
      x: 120,
      y: 270,
      isCaptain: false,
      isKeyPlayer: true,
      note: "Box-to-box brilliance, goals from impossible angles, and a competitive edge that raises every player around him — Bellingham is England's most complete midfielder in a generation and their best hope at 22.",
    },
    {
      name: "Pedri",
      shortName: "PEDRI",
      country: "Spain",
      flagEmoji: "🇪🇸",
      club: "FC Barcelona",
      position: "CM",
      role: "mid",
      accentColor: "#C60C30",
      x: 332,
      y: 270,
      isCaptain: false,
      isKeyPlayer: false,
      note: "A generational talent who sees passes that do not exist yet — Pedri controls tempo in tight spaces and delivers Spain's creative spark from central midfield with an economy that belies his age.",
    },
    {
      name: "Kylian Mbappé",
      shortName: "MBAPPÉ",
      country: "France",
      flagEmoji: "🇫🇷",
      club: "Real Madrid",
      position: "LW",
      role: "att",
      accentColor: "#002395",
      x: 90,
      y: 385,
      isCaptain: true,
      isKeyPlayer: false,
      note: "Twelve World Cup goals before age 27, four from breaking the all-time record — Mbappé is the fastest player in this tournament, the most lethal finisher, and the player most likely to define the entire event.",
    },
    {
      name: "Erling Haaland",
      shortName: "HAALAND",
      country: "Norway",
      flagEmoji: "🇳🇴",
      club: "Manchester City",
      position: "ST",
      role: "att",
      accentColor: "#EF2B2D",
      x: 226,
      y: 405,
      isCaptain: false,
      isKeyPlayer: true,
      note: "The most lethal centre forward on the planet, Haaland enters his first World Cup having already shattered qualifying scoring records — 16 goals in 8 matches — and hungry to prove his brilliance translates to the biggest stage.",
    },
    {
      name: "Vinícius Júnior",
      shortName: "VINÍ JR.",
      country: "Brazil",
      flagEmoji: "🇧🇷",
      club: "Real Madrid",
      position: "RW",
      role: "att",
      accentColor: "#009C3B",
      x: 362,
      y: 385,
      isCaptain: false,
      isKeyPlayer: false,
      note: "Electrifying at full sprint with the ball at his feet, Vinícius is the player defenders fear most in open space — his combination of dribbling, pace, and clinical finishing make him Brazil's most dangerous match-winner.",
    },
  ],
}

function buildCountryLegend(players) {
  const counts = {}
  const flags = {}
  players.forEach(p => {
    counts[p.country] = (counts[p.country] || 0) + 1
    flags[p.country] = p.flagEmoji
  })
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .map(([country, count]) => ({ country, count, flagEmoji: flags[country] }))
}

export default function DreamTeam() {
  const legend = buildCountryLegend(dreamTeam.players)
  const markingStyle = { stroke: 'white', strokeOpacity: 0.45, fill: 'none' }
  const stripeWidth = 452 / 8
  const stripes = Array.from({ length: 8 }, (_, i) => (
    <rect
      key={i}
      x={i * stripeWidth}
      y={0}
      width={stripeWidth}
      height={476}
      fill={i % 2 === 0 ? '#2d6a34' : '#286130'}
    />
  ))

  return (
    <div>
      {/* Page header */}
      <div style={{ textAlign: 'center', marginBottom: 24 }}>
        <h1 style={{
          fontFamily: 'Georgia, "Times New Roman", serif',
          fontSize: 32,
          fontWeight: 500,
          color: '#1a1a1a',
          margin: '0 0 6px',
        }}>
          2026 World Cup Dream Team
        </h1>
        <p style={{ fontSize: 14, color: '#888', margin: 0 }}>
          The best XI in the tournament — selected by form, squad depth, and the games that matter
        </p>
      </div>

      {/* Pitch card */}
      <div style={{
        background: 'white',
        borderRadius: 8,
        overflow: 'hidden',
        boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
        marginBottom: 16,
      }}>
        {/* Card header */}
        <div style={{
          padding: '14px 20px',
          borderBottom: '1px solid #f0f0f0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{
              fontSize: 11,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              color: '#888',
            }}>
              Starting XI
            </span>
            <span style={{
              background: '#1a1a1a',
              color: 'white',
              fontSize: 11,
              fontWeight: 600,
              padding: '2px 8px',
              borderRadius: 10,
            }}>
              {dreamTeam.formation}
            </span>
          </div>
          <span style={{ fontSize: 12, color: '#888' }}>
            Coach: {dreamTeam.coach.name} · {dreamTeam.coach.flagEmoji}
          </span>
        </div>

        {/* Pitch SVG */}
        <svg
          viewBox="0 0 452 476"
          style={{ width: '100%', display: 'block' }}
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            <filter id="dt-shadow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="1" stdDeviation="2" floodColor="rgba(0,0,0,0.5)" />
            </filter>
          </defs>

          {stripes}

          {/* Outer boundary */}
          <rect x={16} y={10} width={420} height={456} {...markingStyle} strokeWidth={1.5} />
          {/* Halfway line */}
          <line x1={16} y1={238} x2={436} y2={238} {...markingStyle} strokeWidth={1} />
          {/* Center circle */}
          <circle cx={226} cy={238} r={52} {...markingStyle} strokeWidth={1} />
          <circle cx={226} cy={238} r={3} stroke="white" strokeOpacity={0.45} fill="white" fillOpacity={0.45} />

          {/* Top penalty area (GK end) */}
          <rect x={109} y={10} width={234} height={68} {...markingStyle} strokeWidth={1} />
          <rect x={160} y={10} width={132} height={28} {...markingStyle} strokeWidth={1} />
          <circle cx={226} cy={58} r={2} fill="white" fillOpacity={0.45} />
          <path d="M 168 78 A 58 58 0 0 1 284 78" {...markingStyle} strokeWidth={1} />
          <rect x={192} y={4} width={68} height={10} {...markingStyle} strokeWidth={1} />
          <path d="M 16 22 A 12 12 0 0 0 28 10" {...markingStyle} strokeWidth={1} />
          <path d="M 424 10 A 12 12 0 0 0 436 22" {...markingStyle} strokeWidth={1} />

          {/* Bottom penalty area (attacking end) */}
          <rect x={109} y={398} width={234} height={68} {...markingStyle} strokeWidth={1} />
          <rect x={160} y={438} width={132} height={28} {...markingStyle} strokeWidth={1} />
          <circle cx={226} cy={418} r={2} fill="white" fillOpacity={0.45} />
          <path d="M 168 398 A 58 58 0 0 0 284 398" {...markingStyle} strokeWidth={1} />
          <rect x={192} y={462} width={68} height={10} {...markingStyle} strokeWidth={1} />
          <path d="M 16 454 A 12 12 0 0 1 28 466" {...markingStyle} strokeWidth={1} />
          <path d="M 436 454 A 12 12 0 0 0 424 466" {...markingStyle} strokeWidth={1} />

          {/* Attacking end label */}
          <text x={438} y={470} textAnchor="end" fill="white" fillOpacity={0.45} fontSize={8} fontFamily="sans-serif">
            ← attacking end
          </text>

          {/* Player nodes */}
          {dreamTeam.players.map((p) => {
            const r = p.isCaptain ? 24 : p.isKeyPlayer ? 21 : 18
            const isNotable = p.isKeyPlayer || p.isCaptain
            return (
              <g key={p.name} filter="url(#dt-shadow)">
                {p.isCaptain && (
                  <circle cx={p.x} cy={p.y} r={r + 5} fill="none" stroke="white" strokeWidth={2} />
                )}
                {isNotable && (
                  <circle cx={p.x} cy={p.y} r={r + 2} fill="none" stroke="white" strokeWidth={1.5} />
                )}
                <circle cx={p.x} cy={p.y} r={r} fill={p.accentColor} />
                <text
                  x={p.x}
                  y={p.y - (isNotable ? 4 : 2)}
                  textAnchor="middle"
                  fill="white"
                  fontSize={p.isCaptain ? 8.5 : 8}
                  fontWeight="700"
                  fontFamily="sans-serif"
                >
                  {p.shortName}
                </text>
                {isNotable && (
                  <text
                    x={p.x}
                    y={p.y + 4}
                    textAnchor="middle"
                    fill="white"
                    fillOpacity={0.85}
                    fontSize={6.5}
                    fontStyle="italic"
                    fontFamily="sans-serif"
                  >
                    {p.isCaptain ? 'captain' : 'key player'}
                  </text>
                )}
                <text
                  x={p.x}
                  y={p.y + (isNotable ? 12 : 8)}
                  textAnchor="middle"
                  fill="white"
                  fillOpacity={0.5}
                  fontSize={7}
                  fontFamily="sans-serif"
                >
                  {p.position}
                </text>
              </g>
            )
          })}
        </svg>

        {/* Country legend below pitch */}
        <div style={{
          padding: '10px 16px 14px',
          display: 'flex',
          flexWrap: 'wrap',
          gap: '8px 14px',
        }}>
          {legend.map(({ country, count, flagEmoji }) => (
            <span key={country} style={{ fontSize: 12, color: '#666' }}>
              {flagEmoji} {country} ({count})
            </span>
          ))}
        </div>
      </div>

      {/* Player card grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 10,
      }}>
        {dreamTeam.players.map(p => (
          <div
            key={p.name}
            style={{
              background: 'white',
              borderRadius: 8,
              borderLeft: `3px solid ${p.accentColor}`,
              padding: '12px 14px',
              boxShadow: '0 1px 2px rgba(0,0,0,0.06)',
            }}
          >
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 5,
            }}>
              <span style={{ fontSize: 15 }}>{p.flagEmoji}</span>
              <span style={{ fontSize: 13, fontWeight: 600, color: '#1a1a1a', flex: 1 }}>
                {p.name}
              </span>
              <span style={{ fontSize: 11, color: '#aaa' }}>{p.position}</span>
            </div>
            <div style={{ fontSize: 11, color: '#aaa', marginTop: 2 }}>
              {p.club}
            </div>
            <div style={{ fontSize: 12, color: '#555', lineHeight: 1.6, marginTop: 6 }}>
              {p.note}
            </div>
          </div>
        ))}

        {/* Coach card — full width */}
        <div style={{
          gridColumn: '1 / -1',
          background: 'white',
          borderRadius: 8,
          borderLeft: `3px solid #1a1a1a`,
          padding: '12px 14px',
          boxShadow: '0 1px 2px rgba(0,0,0,0.06)',
        }}>
          <div style={{
            fontSize: 10,
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            color: '#aaa',
            marginBottom: 4,
          }}>
            Coach
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span style={{ fontSize: 15 }}>{dreamTeam.coach.flagEmoji}</span>
            <span style={{ fontSize: 13, fontWeight: 600, color: '#1a1a1a', flex: 1 }}>
              {dreamTeam.coach.name}
            </span>
            <span style={{ fontSize: 11, color: '#aaa' }}>{dreamTeam.coach.country}</span>
          </div>
          <div style={{ fontSize: 11, color: '#aaa', marginTop: 2 }}>
            {dreamTeam.coach.club}
          </div>
          <div style={{ fontSize: 12, color: '#555', lineHeight: 1.6, marginTop: 6 }}>
            {dreamTeam.coach.note}
          </div>
        </div>
      </div>
    </div>
  )
}
