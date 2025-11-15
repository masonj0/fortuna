# python_service/adapters/__init__.py
# TEMPORARY FIX: Comment out the problematic adapter

from .at_the_races_adapter import AtTheRacesAdapter
from .betfair_adapter import BetfairAdapter
from .betfair_greyhound_adapter import BetfairGreyhoundAdapter
# from .betfair_datascientist_adapter import BetfairDataScientistAdapter  # DISABLED: PyInstaller NumPy issue
from .gbgb_api_adapter import GbgbApiAdapter
from .greyhound_adapter import GreyhoundAdapter
from .harness_adapter import HarnessAdapter
from .pointsbet_greyhound_adapter import PointsBetGreyhoundAdapter
from .racing_and_sports_adapter import RacingAndSportsAdapter
from .racing_and_sports_greyhound_adapter import RacingAndSportsGreyhoundAdapter
from .sporting_life_adapter import SportingLifeAdapter
from .the_racing_api_adapter import TheRacingApiAdapter
from .timeform_adapter import TimeformAdapter
from .tvg_adapter import TVGAdapter

__all__ = [
    "GbgbApiAdapter",
    "TVGAdapter",
    "BetfairAdapter",
    "BetfairGreyhoundAdapter",
    "RacingAndSportsGreyhoundAdapter",
    "AtTheRacesAdapter",
    "PointsBetGreyhoundAdapter",
    "RacingAndSportsAdapter",
    "SportingLifeAdapter",
    "TimeformAdapter",
    "HarnessAdapter",
    "GreyhoundAdapter",
    "TheRacingApiAdapter",
    # "BetfairDataScientistAdapter",  # DISABLED
]