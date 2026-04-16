"""
config.py — Static configuration for Must Watch This Week.

All weights, marquee players, rivalries, and season parameters.
No I/O or network calls.
"""

# ---------------------------------------------------------------------------
# Scoring weights — components sum to 100
# ---------------------------------------------------------------------------
WEIGHTS = {
    "stakes":              30,
    "competitive_balance": 20,
    "momentum":            15,
    "star_power":          15,
    "narrative_flags":     20,
}

# ---------------------------------------------------------------------------
# Marquee players
# Key: "{SPORT}:{TEAM_ABBR}" — avoids BOS/MIL/PHI/ATL cross-sport collisions
# Tier: "superstar" or "star"
# ---------------------------------------------------------------------------
MARQUEE_PLAYERS: dict[str, list[dict]] = {
    # MLB
    "MLB:LAD": [
        {"name": "Shohei Ohtani",       "tier": "superstar"},
        {"name": "Mookie Betts",         "tier": "superstar"},
        {"name": "Freddie Freeman",      "tier": "star"},
    ],
    "MLB:SD":  [
        {"name": "Fernando Tatis Jr.",   "tier": "superstar"},
        {"name": "Manny Machado",        "tier": "star"},
    ],
    "MLB:NYM": [
        {"name": "Juan Soto",            "tier": "superstar"},
        {"name": "Pete Alonso",          "tier": "star"},
    ],
    "MLB:NYY": [
        {"name": "Aaron Judge",          "tier": "superstar"},
        {"name": "Gerrit Cole",          "tier": "star"},
    ],
    "MLB:ATL": [
        {"name": "Ronald Acuna Jr.",     "tier": "superstar"},
        {"name": "Spencer Strider",      "tier": "star"},
        {"name": "Matt Olson",           "tier": "star"},
    ],
    "MLB:HOU": [
        {"name": "Yordan Alvarez",       "tier": "superstar"},
        {"name": "Jose Altuve",          "tier": "star"},
    ],
    "MLB:PHI": [
        {"name": "Bryce Harper",         "tier": "superstar"},
        {"name": "Zack Wheeler",         "tier": "star"},
        {"name": "Trea Turner",          "tier": "star"},
    ],
    "MLB:BAL": [
        {"name": "Gunnar Henderson",     "tier": "superstar"},
        {"name": "Adley Rutschman",      "tier": "star"},
    ],
    "MLB:KC":  [
        {"name": "Bobby Witt Jr.",       "tier": "superstar"},
        {"name": "Salvador Perez",       "tier": "star"},
    ],
    "MLB:CLE": [
        {"name": "Jose Ramirez",         "tier": "superstar"},
        {"name": "Shane Bieber",         "tier": "star"},
    ],
    "MLB:TEX": [
        {"name": "Corey Seager",         "tier": "superstar"},
    ],
    "MLB:SEA": [
        {"name": "Julio Rodriguez",      "tier": "star"},
    ],
    "MLB:STL": [
        {"name": "Nolan Arenado",        "tier": "star"},
    ],
    "MLB:BOS": [
        {"name": "Rafael Devers",        "tier": "star"},
    ],
    "MLB:LAA": [
        {"name": "Mike Trout",           "tier": "superstar"},
    ],
    "MLB:MIN": [
        {"name": "Byron Buxton",         "tier": "star"},
    ],
    "MLB:CHC": [
        {"name": "Dansby Swanson",       "tier": "star"},
    ],
    "MLB:SF":  [
        {"name": "Matt Chapman",         "tier": "star"},
    ],
    "MLB:MIL": [],
    "MLB:CIN": [],
    "MLB:PIT": [],
    "MLB:AZ":  [],
    "MLB:COL": [],
    "MLB:WSH": [],
    "MLB:MIA": [],
    "MLB:TB":  [],
    "MLB:TOR": [],
    "MLB:DET": [],
    "MLB:CWS": [],
    "MLB:OAK": [],
    "MLB:OAK_ATH": [],

    # NBA
    "NBA:BOS": [
        {"name": "Jayson Tatum",         "tier": "superstar"},
        {"name": "Jaylen Brown",         "tier": "star"},
    ],
    "NBA:LAL": [
        {"name": "LeBron James",         "tier": "superstar"},
        {"name": "Anthony Davis",        "tier": "superstar"},
    ],
    "NBA:GSW": [
        {"name": "Stephen Curry",        "tier": "superstar"},
    ],
    "NBA:MIL": [
        {"name": "Giannis Antetokounmpo","tier": "superstar"},
        {"name": "Damian Lillard",       "tier": "star"},
    ],
    "NBA:DEN": [
        {"name": "Nikola Jokic",         "tier": "superstar"},
        {"name": "Jamal Murray",         "tier": "star"},
    ],
    "NBA:PHX": [
        {"name": "Kevin Durant",         "tier": "superstar"},
        {"name": "Devin Booker",         "tier": "superstar"},
    ],
    "NBA:PHI": [
        {"name": "Joel Embiid",          "tier": "superstar"},
        {"name": "Tyrese Maxey",         "tier": "star"},
    ],
    "NBA:MEM": [
        {"name": "Ja Morant",            "tier": "superstar"},
    ],
    "NBA:DAL": [
        {"name": "Luka Doncic",          "tier": "superstar"},
        {"name": "Kyrie Irving",         "tier": "star"},
    ],
    "NBA:MIN": [
        {"name": "Anthony Edwards",      "tier": "superstar"},
        {"name": "Karl-Anthony Towns",   "tier": "star"},
    ],
    "NBA:CLE": [
        {"name": "Donovan Mitchell",     "tier": "superstar"},
    ],
    "NBA:OKC": [
        {"name": "Shai Gilgeous-Alexander", "tier": "superstar"},
    ],
    "NBA:SAS": [
        {"name": "Victor Wembanyama",    "tier": "superstar"},
    ],
    "NBA:NYK": [
        {"name": "Jalen Brunson",        "tier": "star"},
    ],
    "NBA:IND": [
        {"name": "Tyrese Haliburton",    "tier": "star"},
    ],
    "NBA:MIA": [
        {"name": "Jimmy Butler",         "tier": "star"},
    ],
    "NBA:ATL": [
        {"name": "Trae Young",           "tier": "star"},
    ],
    "NBA:SAC": [
        {"name": "De'Aaron Fox",         "tier": "star"},
        {"name": "Domantas Sabonis",     "tier": "star"},
    ],
    "NBA:TOR": [
        {"name": "Scottie Barnes",       "tier": "star"},
    ],
    "NBA:LAC": [
        {"name": "Kawhi Leonard",        "tier": "superstar"},
    ],
    "NBA:NOP": [
        {"name": "Zion Williamson",      "tier": "star"},
    ],
    "NBA:ORL": [
        {"name": "Paolo Banchero",       "tier": "star"},
    ],
    "NBA:HOU": [
        {"name": "Jalen Green",          "tier": "star"},
    ],
    "NBA:CHI": [],
    "NBA:BKN": [],
    "NBA:DET": [],
    "NBA:CHA": [],
    "NBA:WAS": [],
    "NBA:POR": [],
    "NBA:UTA": [],
}

# ---------------------------------------------------------------------------
# Marquee pitchers — name → tier
# Used to detect ace_duel narrative flag when both probable starters qualify.
# Keep small and review quarterly alongside MARQUEE_PLAYERS.
# "elite" = clearly frontline ace; "star" = reliable top-of-rotation starter
# ---------------------------------------------------------------------------
MARQUEE_PITCHERS: dict[str, str] = {
    # Elite — ace-tier starters
    "Shohei Ohtani":       "elite",   # confirmed pitching in 2026
    "Yoshinobu Yamamoto":  "elite",
    "Paul Skenes":         "elite",
    "Tarik Skubal":        "elite",
    "Zack Wheeler":        "elite",
    "Gerrit Cole":         "elite",
    "Spencer Strider":     "elite",
    "Corbin Burnes":       "elite",
    "Chris Sale":          "elite",
    # Star — top-of-rotation starters
    "Logan Webb":          "star",
    "Framber Valdez":      "star",
    "Shane Bieber":        "star",
    "Kevin Gausman":       "star",
    "Hunter Greene":       "star",
    "Freddy Peralta":      "star",
    "Blake Snell":         "star",
    "Tyler Glasnow":       "star",
    "Dylan Cease":         "star",
    "George Kirby":        "star",
    "Sandy Alcantara":     "star",
    "Kodai Senga":         "star",
    "Luis Castillo":       "star",
}

# ---------------------------------------------------------------------------
# Rivalries — frozenset pairs using "{SPORT}:{ABBR}" keys
# ---------------------------------------------------------------------------
RIVALRIES: set[frozenset] = {
    # MLB
    frozenset({"MLB:NYY", "MLB:BOS"}),
    frozenset({"MLB:LAD", "MLB:SF"}),
    frozenset({"MLB:LAD", "MLB:SD"}),
    frozenset({"MLB:CHC", "MLB:STL"}),
    frozenset({"MLB:NYY", "MLB:NYM"}),
    frozenset({"MLB:PHI", "MLB:NYM"}),
    frozenset({"MLB:LAD", "MLB:HOU"}),
    frozenset({"MLB:ATL", "MLB:PHI"}),
    frozenset({"MLB:NYY", "MLB:HOU"}),
    frozenset({"MLB:BAL", "MLB:NYY"}),
    frozenset({"MLB:LAD", "MLB:ATL"}),
    frozenset({"MLB:BOS", "MLB:HOU"}),
    frozenset({"MLB:MIN", "MLB:CLE"}),
    # NBA
    frozenset({"NBA:BOS", "NBA:LAL"}),
    frozenset({"NBA:BOS", "NBA:MIA"}),
    frozenset({"NBA:GSW", "NBA:LAL"}),
    frozenset({"NBA:LAL", "NBA:LAC"}),
    frozenset({"NBA:BOS", "NBA:NYK"}),
    frozenset({"NBA:PHI", "NBA:BOS"}),
    frozenset({"NBA:MIL", "NBA:BOS"}),
    frozenset({"NBA:GSW", "NBA:CLE"}),
    frozenset({"NBA:DEN", "NBA:LAL"}),
    frozenset({"NBA:DAL", "NBA:OKC"}),
    frozenset({"NBA:MIL", "NBA:PHI"}),
}

# ---------------------------------------------------------------------------
# Playoff rematches (last 2 postseasons)
# ---------------------------------------------------------------------------
PLAYOFF_REMATCHES: set[frozenset] = {
    frozenset({"NBA:BOS", "NBA:DAL"}),   # 2024 NBA Finals
    frozenset({"MLB:LAD", "MLB:NYY"}),   # 2024 World Series
    frozenset({"MLB:LAD", "MLB:NYM"}),   # 2024 NLCS
    frozenset({"MLB:NYY", "MLB:CLE"}),   # 2024 ALCS
    frozenset({"NBA:DEN", "NBA:MIA"}),   # 2023 NBA Finals
    frozenset({"MLB:TEX", "MLB:AZ"}),    # 2023 World Series
    frozenset({"NBA:BOS", "NBA:MIA"}),   # 2023 ECF
    frozenset({"NBA:MIL", "NBA:BOS"}),   # 2023 ECF (Bucks vs Celtics)
}

# ---------------------------------------------------------------------------
# Season configuration
# ---------------------------------------------------------------------------
MLB_TOTAL_GAMES = 162
NBA_TOTAL_GAMES = 82

# Playoff race thresholds (games back from cutoff)
MLB_RACE_THRESHOLD     = 5.0   # games back from wild card spot or division lead
NBA_PLAYOFF_RANK_CUTOFF = 6    # top 6 → direct playoff berth
NBA_PLAYIN_RANK_CUTOFF  = 10   # 7–10 → play-in tournament

# Season phase multipliers (regular season stakes only)
SEASON_PHASE_MULTIPLIERS = {
    "early": 0.60,   # first 20% of season
    "mid":   0.85,   # 20–70%
    "late":  1.00,   # final 30%
}

# Timing filter — exclude events starting within N seconds of generation time
TIMING_FILTER_SECONDS = 3600   # 1 hour

# Candidate pool size
TOP_N_CANDIDATES = 10
