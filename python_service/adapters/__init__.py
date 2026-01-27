# python_service/adapters/__init__.py

from .at_the_races_adapter import AtTheRacesAdapter
from .betfair_adapter import BetfairAdapter
from .betfair_datascientist_adapter import BetfairDataScientistAdapter
from .betfair_greyhound_adapter import BetfairGreyhoundAdapter
from .brisnet_adapter import BrisnetAdapter
from .equibase_adapter import EquibaseAdapter
from .fanduel_adapter import FanDuelAdapter
from .gbgb_api_adapter import GbgbApiAdapter
from .greyhound_adapter import GreyhoundAdapter
from .harness_adapter import HarnessAdapter
from .oddschecker_adapter import OddscheckerAdapter
from .pointsbet_greyhound_adapter import PointsBetGreyhoundAdapter
from .racing_and_sports_adapter import RacingAndSportsAdapter
from .racing_and_sports_greyhound_adapter import RacingAndSportsGreyhoundAdapter
from .racingpost_adapter import RacingPostAdapter
from .sporting_life_adapter import SportingLifeAdapter
from .stubs import (
    HorseRacingNationAdapter,
    NYRABetsAdapter,
    PuntersAdapter,
    RacingTVAdapter,
    TabAdapter,
    TemplateAdapter,
)
from .the_racing_api_adapter import TheRacingApiAdapter
from .timeform_adapter import TimeformAdapter
from .tvg_adapter import TVGAdapter
from .twinspires_adapter import TwinSpiresAdapter
from .universal_adapter import UniversalAdapter
from .xpressbet_adapter import XpressbetAdapter

__all__ = [
    "AtTheRacesAdapter",
    "BetfairAdapter",
    "BetfairDataScientistAdapter",
    "BetfairGreyhoundAdapter",
    "BrisnetAdapter",
    "EquibaseAdapter",
    "FanDuelAdapter",
    "GbgbApiAdapter",
    "GreyhoundAdapter",
    "HarnessAdapter",
    "HorseRacingNationAdapter",
    "NYRABetsAdapter",
    "OddscheckerAdapter",
    "PointsBetGreyhoundAdapter",
    "PuntersAdapter",
    "RacingAndSportsAdapter",
    "RacingAndSportsGreyhoundAdapter",
    "RacingPostAdapter",
    "RacingTVAdapter",
    "SportingLifeAdapter",
    "TabAdapter",
    "TemplateAdapter",
    "TheRacingApiAdapter",
    "TimeformAdapter",
    "TVGAdapter",
    "TwinSpiresAdapter",
    "UniversalAdapter",
    "XpressbetAdapter",
]
