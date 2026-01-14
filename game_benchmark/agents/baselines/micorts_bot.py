"""
Bot baseline para MicroRTS.
Estrategia simple: economía primero, luego rush al mid.
"""

from __future__ import annotations
from ..base import BaseAgent


class MicroRTSBot(BaseAgent):
    """
    Bot simple para MicroRTS que:
    1. Construye workers hasta tener suficientes
    2. Construye barracks
    3. Produce ejército
    4. Ataca mid cuando tiene ventaja
    """
    
    def __init__(self, player_id: str):
        super().__init__(player_id)
        self.phase = "economy"  # economy, military, attack
    
    def act(self, observation: dict) -> dict:
        resources = observation["resources"]
        units = observation["units"]
        
        # Contar unidades propias
        my_units = [u for u in units if u["owner"] == self.player_id]
        workers = sum(1 for u in my_units if u["type"] == "worker")
        soldiers = sum(1 for u in my_units if u["type"] == "soldier")
        ranged = sum(1 for u in my_units if u["type"] == "ranged")
        barracks = sum(1 for u in my_units if u["type"] == "barracks")
        army_size = soldiers + ranged
        
        # Lógica de decisión
        if self.phase == "economy":
            if workers < 4 and resources >= 50:
                return {"type": "train_worker"}
            elif workers >= 4 and barracks == 0 and resources >= 200:
                return {"type": "build_barracks"}
            elif barracks > 0:
                self.phase = "military"
        
        if self.phase == "military":
            if resources >= 100 and soldiers < 3:
                return {"type": "train_soldier"}
            elif resources >= 150 and ranged < 2:
                return {"type": "train_ranged"}
            elif army_size >= 5:
                self.phase = "attack"
        
        if self.phase == "attack":
            # Seguir produciendo mientras atacamos
            if resources >= 100 and (soldiers + ranged) < 10:
                if ranged < soldiers:
                    return {"type": "train_ranged"}
                return {"type": "train_soldier"}
            
            return {"type": "attack_zone", "zone_id": "mid"}
        
        return {"type": "noop"}
    
    def reset(self) -> None:
        self.phase = "economy"
    
    @property
    def name(self) -> str:
        return "MicroRTSBot"
