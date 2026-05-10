function hexToRgb(hex) {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return { r, g, b }
}

function darken(hex, amount = 0.3) {
  const { r, g, b } = hexToRgb(hex)
  return `rgb(${Math.round(r * (1 - amount))}, ${Math.round(g * (1 - amount))}, ${Math.round(b * (1 - amount))})`
}

const ROLE_COLORS = {
  mid: '#0d85c4',
  att: '#2aab6a',
}

export default function PitchDiagram({ players, accentColor }) {
  const roleColor = (role) => {
    if (role === 'gk') return accentColor
    if (role === 'def') return darken(accentColor, 0.3)
    return ROLE_COLORS[role] || '#888'
  }

  const nodeRadius = (p) => {
    if (p.isCaptain) return 24
    if (p.isKeyPlayer) return 21
    return 18
  }

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
    <svg
      viewBox="0 0 452 476"
      style={{ width: '100%', display: 'block' }}
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="1" stdDeviation="2" floodColor="rgba(0,0,0,0.5)" />
        </filter>
      </defs>

      {/* Pitch surface with alternating stripes */}
      {stripes}

      {/* Outer boundary */}
      <rect x={16} y={10} width={420} height={456} {...markingStyle} strokeWidth={1.5} />

      {/* Halfway line */}
      <line x1={16} y1={238} x2={436} y2={238} {...markingStyle} strokeWidth={1} />

      {/* Center circle */}
      <circle cx={226} cy={238} r={52} {...markingStyle} strokeWidth={1} />
      <circle cx={226} cy={238} r={3} stroke="white" strokeOpacity={0.45} fill="white" fillOpacity={0.45} />

      {/* Top penalty area (defending end — GK end) */}
      <rect x={109} y={10} width={234} height={68} {...markingStyle} strokeWidth={1} />
      {/* Top six-yard box */}
      <rect x={160} y={10} width={132} height={28} {...markingStyle} strokeWidth={1} />
      {/* Top penalty spot */}
      <circle cx={226} cy={58} r={2} fill="white" fillOpacity={0.45} />
      {/* Top penalty arc */}
      <path d="M 168 78 A 58 58 0 0 1 284 78" {...markingStyle} strokeWidth={1} />
      {/* Top goal */}
      <rect x={192} y={4} width={68} height={10} {...markingStyle} strokeWidth={1} />
      {/* Top corner arcs */}
      <path d="M 16 22 A 12 12 0 0 0 28 10" {...markingStyle} strokeWidth={1} />
      <path d="M 424 10 A 12 12 0 0 0 436 22" {...markingStyle} strokeWidth={1} />

      {/* Bottom penalty area (attacking end) */}
      <rect x={109} y={398} width={234} height={68} {...markingStyle} strokeWidth={1} />
      {/* Bottom six-yard box */}
      <rect x={160} y={438} width={132} height={28} {...markingStyle} strokeWidth={1} />
      {/* Bottom penalty spot */}
      <circle cx={226} cy={418} r={2} fill="white" fillOpacity={0.45} />
      {/* Bottom penalty arc */}
      <path d="M 168 398 A 58 58 0 0 0 284 398" {...markingStyle} strokeWidth={1} />
      {/* Bottom goal */}
      <rect x={192} y={462} width={68} height={10} {...markingStyle} strokeWidth={1} />
      {/* Bottom corner arcs */}
      <path d="M 16 454 A 12 12 0 0 1 28 466" {...markingStyle} strokeWidth={1} />
      <path d="M 436 454 A 12 12 0 0 0 424 466" {...markingStyle} strokeWidth={1} />

      {/* Player nodes */}
      {players.map((p) => {
        const r = nodeRadius(p)
        const fill = roleColor(p.role)
        return (
          <g key={p.name} filter="url(#shadow)">
            {/* Captain: double ring */}
            {p.isCaptain && (
              <circle cx={p.x} cy={p.y} r={r + 5} fill="none" stroke="white" strokeWidth={2} />
            )}
            {/* Key player ring */}
            {(p.isKeyPlayer || p.isCaptain) && (
              <circle cx={p.x} cy={p.y} r={r + 2} fill="none" stroke="white" strokeWidth={1.5} />
            )}
            {/* Main circle */}
            <circle cx={p.x} cy={p.y} r={r} fill={fill} />
            {/* Name */}
            <text
              x={p.x}
              y={p.y - (p.isKeyPlayer || p.isCaptain ? 4 : 2)}
              textAnchor="middle"
              fill="white"
              fontSize={p.isCaptain ? 8.5 : 8}
              fontWeight="700"
              fontFamily="sans-serif"
            >
              {p.shortName}
            </text>
            {/* "key player" label */}
            {(p.isKeyPlayer || p.isCaptain) && (
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
                key player
              </text>
            )}
            {/* Position */}
            <text
              x={p.x}
              y={p.y + (p.isKeyPlayer || p.isCaptain ? 12 : 8)}
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

      {/* Legend bottom-left */}
      <rect x={12} y={428} width={108} height={48} rx={3} fill="rgba(0,0,0,0.55)" />
      {[
        { label: 'Attack', color: ROLE_COLORS.att, y: 440 },
        { label: 'Midfield', color: ROLE_COLORS.mid, y: 450 },
        { label: 'Defence', color: darken(accentColor, 0.3), y: 460 },
        { label: 'GK', color: accentColor, y: 470 },
      ].map(({ label, color, y }) => (
        <g key={label}>
          <circle cx={22} cy={y - 2} r={4} fill={color} />
          <text x={30} y={y} fill="white" fillOpacity={0.8} fontSize={8} fontFamily="sans-serif">
            {label}
          </text>
        </g>
      ))}

      {/* Attacking end label bottom-right */}
      <text
        x={438}
        y={470}
        textAnchor="end"
        fill="white"
        fillOpacity={0.45}
        fontSize={8}
        fontFamily="sans-serif"
      >
        ← attacking end
      </text>
    </svg>
  )
}
