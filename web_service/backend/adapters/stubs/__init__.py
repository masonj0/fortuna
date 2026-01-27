# python_service/adapters/stubs/__init__.py
"""Non-functional stub adapters."""

from .horseracingnation_adapter import HorseRacingNationAdapter
from .nyrabets_adapter import NYRABetsAdapter
from .punters_adapter import PuntersAdapter
from .racingtv_adapter import RacingTVAdapter
from .tab_adapter import TabAdapter
from .template_adapter import TemplateAdapter

__all__ = [
    "HorseRacingNationAdapter",
    "NYRABetsAdapter",
    "PuntersAdapter",
    "RacingTVAdapter",
    "TabAdapter",
    "TemplateAdapter",
]
