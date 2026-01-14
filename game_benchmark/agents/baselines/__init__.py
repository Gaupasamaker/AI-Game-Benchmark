"""Baselines para los diferentes juegos."""

from __future__ import annotations
from .carball_bot import CarBallBot, GoalieBot, StrikerBot
from .micorts_bot import MicroRTSBot
from .micorts_econ_bot import MicroRTSEconBot
from .tacticfps_bot import TacticFPSBot

__all__ = ["CarBallBot", "GoalieBot", "StrikerBot", "MicroRTSBot", "MicroRTSEconBot", "TacticFPSBot"]
