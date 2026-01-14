"""
Bot baseline para TacticFPS.
Estrategia simple diferenciada por equipo.
"""

from __future__ import annotations
import random
from ..base import BaseAgent


class TacticFPSBot(BaseAgent):
    """
    Bot simple para TacticFPS que:
    - Ts: se mueven hacia la zona de plantado e intentan plantar
    - CTs: defienden la zona de plantado o defusan
    """
    
    def __init__(self, player_id: str, seed: int | None = None):
        super().__init__(player_id)
        self.rng = random.Random(seed)
        # Determinar equipo por ID
        self.is_terrorist = player_id.startswith("t")
    
    def act(self, observation: dict) -> dict:
        self_info = observation["self"]
        
        if not self_info["alive"]:
            return {}
        
        # Si está flasheado, no hacer nada
        if self_info.get("flashed_ticks", 0) > 0:
            return {"move": "STAY", "aim_dir": "N", "shoot": False}
        
        my_x, my_y = self_info["x"], self_info["y"]
        enemies = observation.get("enemies", [])
        bomb_info = observation.get("bomb", {})
        
        # Decidir aim basado en enemigos visibles
        aim_dir = "N"
        shoot = False
        
        if enemies:
            # Apuntar al enemigo más cercano
            closest = min(enemies, key=lambda e: abs(e["x"] - my_x) + abs(e["y"] - my_y))
            dx = closest["x"] - my_x
            dy = closest["y"] - my_y
            
            aim_dir = self._get_direction(dx, dy)
            
            # Disparar si está en rango
            dist = abs(dx) + abs(dy)
            if dist <= 8:
                shoot = True
        
        # Decidir movimiento
        if self.is_terrorist:
            move, plant = self._terrorist_movement(observation)
            return {
                "move": move,
                "aim_dir": aim_dir,
                "shoot": shoot,
                "plant": plant,
                "defuse": False,
                "use_smoke": None,
                "use_flash": None
            }
        else:
            move, defuse = self._ct_movement(observation)
            return {
                "move": move,
                "aim_dir": aim_dir,
                "shoot": shoot,
                "plant": False,
                "defuse": defuse,
                "use_smoke": None,
                "use_flash": None
            }
    
    def _terrorist_movement(self, obs: dict) -> tuple[str, bool]:
        """Movimiento para Ts: ir a plantar."""
        self_info = obs["self"]
        my_x, my_y = self_info["x"], self_info["y"]
        
        # Objetivo: zona de plantado (esquina derecha típicamente)
        # Asumir que está alrededor de (11, 7) en un mapa 15x15
        target_x, target_y = 11, 7
        
        bomb = obs.get("bomb", {})
        if bomb.get("planted"):
            # Defender la bomba
            return "STAY", False
        
        dx = target_x - my_x
        dy = target_y - my_y
        
        # Si estamos en la zona de plantado y tenemos la bomba
        if abs(dx) <= 1 and abs(dy) <= 1 and self_info.get("has_bomb"):
            return "STAY", True  # Intentar plantar
        
        return self._get_direction(dx, dy), False
    
    def _ct_movement(self, obs: dict) -> tuple[str, bool]:
        """Movimiento para CTs: ir a defusar o defender."""
        self_info = obs["self"]
        my_x, my_y = self_info["x"], self_info["y"]
        
        bomb = obs.get("bomb", {})
        
        if bomb.get("planted"):
            # Ir a defusar
            bomb_x = bomb.get("x", 11)
            bomb_y = bomb.get("y", 7)
            
            dx = bomb_x - my_x
            dy = bomb_y - my_y
            
            if abs(dx) <= 1 and abs(dy) <= 1:
                return "STAY", True  # Defusar
            
            return self._get_direction(dx, dy), False
        else:
            # Ir hacia la zona de plantado para defender
            target_x, target_y = 11, 7
            dx = target_x - my_x
            dy = target_y - my_y
            
            return self._get_direction(dx, dy), False
    
    def _get_direction(self, dx: int, dy: int) -> str:
        """Convierte delta a dirección."""
        if dx == 0 and dy == 0:
            return "STAY"
        
        if abs(dx) > abs(dy):
            return "E" if dx > 0 else "W"
        else:
            return "S" if dy > 0 else "N"
    
    @property
    def name(self) -> str:
        return "TacticFPSBot"
