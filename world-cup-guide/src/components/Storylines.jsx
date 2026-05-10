const storylines = [
  {
    id: 1,
    type: "historical",
    headline: "Four Goals From Immortality",
    subheadline: "Kylian Mbappé enters 2026 needing just four goals to break the all-time World Cup scoring record.",
    narrative: "Miroslav Klose set the record in 2014 with 16 goals across four tournaments — a number that felt untouchable. Mbappé enters 2026 with 12 goals after two World Cups, needing just four more at the peak of his powers at age 27. Watch every French attack knowing he is always one chance away from rewriting football history.",
    teamsOrPlayers: ["France", "Mbappé"],
    accentColor: "#002395",
  },
  {
    id: 2,
    type: "debut",
    headline: "Norway's 28-Year Wait Is Over",
    subheadline: "Erling Haaland scored 16 goals in qualifying to drag Norway to their first World Cup since 1998.",
    narrative: "Norway has not been to a World Cup since 1998 — the year Haaland was three years old. He responded by scoring 16 goals in 8 qualifying matches, shattering Robert Lewandowski's European qualifying record and carrying a small Nordic nation back onto the world stage almost single-handedly. Every Haaland goal in this tournament will feel like a country exhaling for the first time in a generation.",
    teamsOrPlayers: ["Norway", "Haaland"],
    accentColor: "#EF2B2D",
  },
  {
    id: 3,
    type: "redemption",
    headline: "Germany's Humiliation Must End Here",
    subheadline: "Back-to-back group stage exits in 2018 and 2022 were the worst stretch in German football history.",
    narrative: "Germany is one of the most decorated nations on earth — four World Cup titles, eleven final appearances, a byword for tournament excellence. Then came 2018 and 2022: back-to-back group stage exits that shocked the football world, unprecedented in the modern era of German football. Julian Nagelsmann's young squad, built around the brilliance of Jamal Musiala, arrives in North America knowing that only a deep run will begin to repair the damage.",
    teamsOrPlayers: ["Germany", "Musiala"],
    accentColor: "#C9A400",
  },
  {
    id: 4,
    type: "host",
    headline: "Mexico's Weight of Three Crowns",
    subheadline: "The only country to host the World Cup three times opens the tournament at the Azteca — with all the pressure that brings.",
    narrative: "Mexico becomes the first nation to host or co-host the men's World Cup three times (1970, 1986, 2026), and the Estadio Azteca hosts the opening match when El Tri faces South Africa on June 11. Home advantage at altitude — Mexico City sits 7,350 feet above sea level — brings a real edge, but performing in front of 87,000 of your own supporters carries its own burden. Mexico have been eliminated at the round of 16 seven consecutive times; 2026, at home, is their best chance to change that story.",
    teamsOrPlayers: ["Mexico"],
    accentColor: "#006847",
  },
  {
    id: 5,
    type: "generational",
    headline: "Ronaldo's Sixth: Playing Into Legend",
    subheadline: "No male player has ever appeared in six World Cups — until Cristiano Ronaldo does it at 41.",
    narrative: "If Ronaldo takes the field in Portugal's opening game, he becomes the oldest player in World Cup group stage history, threatening records set in the 1950s. His rival Lionel Messi will be on the same stage at 38, also in his sixth tournament — two generational figures sharing one final farewell that no sport has produced quite like this before. This is the last chapter of football's greatest rivalry; you are watching it happen in real time.",
    teamsOrPlayers: ["Portugal", "Ronaldo", "Messi"],
    accentColor: "#DA291C",
  },
  {
    id: 6,
    type: "historical",
    headline: "Argentina: No One Has Done This Since 1962",
    subheadline: "No nation has defended the World Cup title in 64 years. Scaloni's Argentina arrives trying to make history again.",
    narrative: "The last team to win back-to-back World Cups was Brazil in 1958 and 1962 — before most of today's competing federations even existed. Argentina won the greatest final in living memory in Qatar 2022, surviving Mbappé's hat-trick through extra time and penalties in a match watched by a billion people. Lionel Scaloni's squad arrives knowing that history is stacked against them, and that Argentina has never seemed to care much about what history says.",
    teamsOrPlayers: ["Argentina"],
    accentColor: "#00529B",
  },
  {
    id: 7,
    type: "redemption",
    headline: "Brazil's 24-Year Hunger",
    subheadline: "Vinícius Júnior leads the most talented Brazil squad in a generation, chasing a first World Cup title since 2002.",
    narrative: "Brazil has won the World Cup five times — more than any nation — but the last title came in 2002, before Vinícius Júnior was born. Now he is the fulcrum of the most exciting Brazilian attack in years, alongside teenage prodigy Endrick and the clinical Rodrygo, managed by Carlo Ancelotti, the most decorated club manager in football history. Brazil always arrives as a contender, but this squad feels like the real thing.",
    teamsOrPlayers: ["Brazil", "Vinícius Jr."],
    accentColor: "#009C3B",
  },
  {
    id: 8,
    type: "generational",
    headline: "Lamine Yamal Is Not Done Growing Up",
    subheadline: "Spain's 18-year-old phenomenon carries the weight of a defending champion — and the future of world football.",
    narrative: "Lamine Yamal was born on October 16, 2007 — the same day Lionel Messi played in his first Champions League final. He is 18 years old in June 2026, already a starter for defending World Cup champion Spain and arguably the most gifted teenager in the history of the sport. Watch for the moments where he does something that makes you forget he has barely graduated high school.",
    teamsOrPlayers: ["Spain", "Yamal"],
    accentColor: "#C60C30",
  },
]

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
                {s.teamsOrPlayers.map(tag => (
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
