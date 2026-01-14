"""
Bot económico para MicroRTS.
Estrategia: maximizar economía respetando el cap de unidades.
"""

from __future__ import annotations
from ..base import BaseAgent


class MicroRTSEconBot(BaseAgent):
    """
    Bot económico que:
    1. Produce workers hasta cap/2
    2. Construye barracks
    3. Produce ejército con el resto del cap
    4. Ataca mid cuando tiene suficiente ejército
    """
    
    def __init__(self, player_id: str, unit_cap: int = 30):
        super().__init__(player_id)
        self.unit_cap = unit_cap
        self.phase = "economy"  # economy, military, attack
    
    def act(self, observation: dict) -> dict:
        resources = observation["resources"]
        units = observation["units"]
        
        # Contar unidades propias
        my_units = [u for u in units if u["owner"] == self.player_id]
        total_units = len(my_units)
        workers = sum(1 for u in my_units if u["type"] == "worker")
        soldiers = sum(1 for u in my_units if u["type"] == "soldier")
        ranged = sum(1 for u in my_units if u["type"] == "ranged")
        barracks = sum(1 for u in my_units if u["type"] == "barracks")
        army_size = soldiers + ranged
        
        # Target workers: ~40% del cap (dejando espacio para base + barracks + ejército)
        max_workers = (self.unit_cap * 4) // 10  # 40% workers (~12 con cap 30)
        
        # Fase ECONOMY: producir workers hasta el target
        if self.phase == "economy":
            if workers < max_workers and resources >= 50 and total_units < self.unit_cap:
                return {"type": "train_worker"}
            elif workers >= max_workers // 2 and barracks == 0 and resources >= 200:
                # Construir barracks cuando tenemos suficientes workers
                return {"type": "build_barracks"}
            elif barracks > 0 and workers >= max_workers // 2:
                self.phase = "military"
        
        # Fase MILITARY: producir ejército
        if self.phase == "military":
            # Seguir produciendo workers si hay espacio y estamos bajo target
            if workers < max_workers and resources >= 50 and total_units < self.unit_cap:
                return {"type": "train_worker"}
            
            # Producir ejército si hay espacio
            if total_units < self.unit_cap:
                if resources >= 100 and soldiers < ranged + 2:
                    return {"type": "train_soldier"}
                elif resources >= 150:
                    return {"type": "train_ranged"}
            
            # Atacar cuando el ejército es decente
            if army_size >= 5:
                self.phase = "attack"
        
        # Fase ATTACK: seguir produciendo y atacar
        if self.phase == "attack":
            # Seguir produciendo si hay recursos y espacio
            if total_units < self.unit_cap:
                if workers < max_workers and resources >= 50:
                    return {"type": "train_worker"}
                elif resources >= 100:
                    if ranged < soldiers:
                        return {"type": "train_ranged"}
                    return {"type": "train_soldier"}
            
            # Atacar mid
            return {"type": "attack_zone", "zone_id": "mid"}
        
        return {"type": "noop"}
    
    def reset(self) -> None:
        self.phase = "economy"
    
    @property
    def name(self) -> str:
        return "MicroRTSEconBot"
