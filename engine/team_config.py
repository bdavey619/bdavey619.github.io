"""
engine/team_config.py — Team configuration dataclass for the sports brief engine.

Each team is represented as a TeamConfig instance. Team-specific build scripts
import their config from here and assign it to CFG at module level.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TeamConfig:
    team_id: int           # MLB Stats API team ID
    team_abbr: str         # Short label used in linescore ("SD", "NYY")
    team_name: str         # Short team name ("Padres", "Yankees")
    team_city: str         # City name ("San Diego", "New York")
    home_venue: str        # Full venue name ("Petco Park", "Yankee Stadium")
    home_venue_short: str  # Brief venue name for subhead ("Petco", "the Stadium")
    league_id: int         # MLB league ID (104=NL, 103=AL)
    division_id: int       # MLB division ID (203=NL West, 201=AL East)
    division_name: str     # Full division name ("NL West", "AL East")
    division_short: str    # Short direction word ("West", "East")
    tz_offset: int         # UTC offset for local game times (-7=PT, -4=ET during DST)
    tz_label: str          # Timezone label ("PT", "ET")
    site_url: str          # Web brief URL (used in email footer)
    accent_color: str      # Primary brand color (CSS hex)


PADRES = TeamConfig(
    team_id=135,
    team_abbr="SD",
    team_name="Padres",
    team_city="San Diego",
    home_venue="Petco Park",
    home_venue_short="Petco",
    league_id=104,
    division_id=203,
    division_name="NL West",
    division_short="West",
    tz_offset=-7,
    tz_label="PT",
    site_url="https://bdavey619.github.io/padres/",
    accent_color="#2f241d",
)

GIANTS = TeamConfig(
    team_id=137,
    team_abbr="SF",
    team_name="Giants",
    team_city="San Francisco",
    home_venue="Oracle Park",
    home_venue_short="Oracle",
    league_id=104,
    division_id=203,
    division_name="NL West",
    division_short="West",
    tz_offset=-7,
    tz_label="PT",
    site_url="https://bdavey619.github.io/giants/",
    accent_color="#FD5A1E",
)

YANKEES = TeamConfig(
    team_id=147,
    team_abbr="NYY",
    team_name="Yankees",
    team_city="New York",
    home_venue="Yankee Stadium",
    home_venue_short="the Stadium",
    league_id=103,
    division_id=201,
    division_name="AL East",
    division_short="East",
    tz_offset=-4,
    tz_label="ET",
    site_url="https://bdavey619.github.io/yankees/",
    accent_color="#003087",
)

ATHLETICS = TeamConfig(
    team_id=133,
    team_abbr="ATH",
    team_name="Athletics",
    team_city="Sacramento",
    home_venue="Sutter Health Park",
    home_venue_short="Sutter Health",
    league_id=103,
    division_id=200,
    division_name="AL West",
    division_short="West",
    tz_offset=-7,
    tz_label="PT",
    site_url="https://bdavey619.github.io/athletics/",
    accent_color="#003831",
)
