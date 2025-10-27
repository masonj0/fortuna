# python_service/adapters/__init__.py

# Import all adapter classes to make them available for dynamic loading.
from .at_the_races_adapter import AtTheRacesAdapter
from .betfair_adapter import BetfairAdapter
from .betfair_greyhound_adapter import BetfairGreyhoundAdapter
from .brisnet_adapter import BrisnetAdapter
from .drf_adapter import DRFAdapter
from .equibase_adapter import EquibaseAdapter
from .fanduel_adapter import FanDuelAdapter
from .gbgb_api_adapter import GbgbApiAdapter
from .greyhound_adapter import GreyhoundAdapter
from .harness_adapter import HarnessAdapter
from .horseracingnation_adapter import HorseRacingNationAdapter
from .nyrabets_adapter import NYRABetsAdapter
from .oddschecker_adapter import OddscheckerAdapter
from .punters_adapter import PuntersAdapter
from .racing_and_sports_adapter import RacingAndSportsAdapter
from .racing_and_sports_greyhound_adapter import RacingAndSportsGreyhoundAdapter
from .racingpost_adapter import RacingPostAdapter
from .racingtv_adapter import RacingTVAdapter
from .sporting_life_adapter import SportingLifeAdapter
from .tab_adapter import TabAdapter
from .template_adapter import TemplateAdapter
from .the_racing_api_adapter import TheRacingApiAdapter
from .timeform_adapter import TimeformAdapter
from .tvg_adapter import TVGAdapter
from .twinspires_adapter import TwinSpiresAdapter
from .xpressbet_adapter import XpressbetAdapter

# Define the public API for the adapters package, making it easy for the
# orchestrator to discover and use them.
__all__ = [
    "AtTheRacesAdapter",
    "BetfairAdapter",
    "BetfairGreyhoundAdapter",
    "BrisnetAdapter",
    "DRFAdapter",
    "EquibaseAdapter",
    "FanDuelAdapter",
    "GbgbApiAdapter",
    "GreyhoundAdapter",
    "HarnessAdapter",
    "HorseRacingNationAdapter",
    "NYRABetsAdapter",
    "OddscheckerAdapter",
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
    "XpressbetAdapter",
]
