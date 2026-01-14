"""
MicroRTS-v0 - Juego de estrategia tipo StarCraft II simplificado.

Grid-based con economía, producción y combate.
"""

from __future__ import annotations
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .base import BaseEnvironment


class UnitType(Enum):
    """Tipos de unidades."""
    WORKER = "worker"
    SOLDIER = "soldier"
    RANGED = "ranged"
    BASE = "base"
    BARRACKS = "barracks"


class ZoneType(Enum):
    """Tipos de zonas."""
    BASE_A = "base_a"
    BASE_B = "base_b"
    MID = "mid"
    EMPTY = "empty"


@dataclass
class Unit:
    """Unidad del juego."""
    unit_id: int
    unit_type: UnitType
    owner: str
    x: int
    y: int
    hp: int
    max_hp: int
    attack: int
    attack_range: int
    production_cooldown: int = 0
    
    # Costes y stats por tipo
    UNIT_STATS = {
        UnitType.WORKER: {"hp": 50, "attack": 5, "range": 1, "cost": 50, "build_time": 3},
        UnitType.SOLDIER: {"hp": 100, "attack": 15, "range": 1, "cost": 100, "build_time": 5},
        UnitType.RANGED: {"hp": 60, "attack": 20, "range": 3, "cost": 150, "build_time": 7},
        UnitType.BASE: {"hp": 500, "attack": 0, "range": 0, "cost": 0, "build_time": 0},
        UnitType.BARRACKS: {"hp": 200, "attack": 0, "range": 0, "cost": 200, "build_time": 10},
    }
    
    @classmethod
    def create(cls, unit_id: int, unit_type: UnitType, owner: str, x: int, y: int) -> "Unit":
        stats = cls.UNIT_STATS[unit_type]
        return cls(
            unit_id=unit_id,
            unit_type=unit_type,
            owner=owner,
            x=x,
            y=y,
            hp=stats["hp"],
            max_hp=stats["hp"],
            attack=stats["attack"],
            attack_range=stats["range"]
        )
    
    def to_dict(self) -> dict:
        return {
            "id": self.unit_id,
            "type": self.unit_type.value,
            "owner": self.owner,
            "x": self.x,
            "y": self.y,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "attack": self.attack,
            "range": self.attack_range,
            "cooldown": self.production_cooldown
        }
    
    def is_building(self) -> bool:
        return self.unit_type in [UnitType.BASE, UnitType.BARRACKS]
    
    def can_produce(self) -> bool:
        return self.is_building() and self.production_cooldown <= 0


@dataclass
class Zone:
    """Zona del mapa."""
    zone_id: str
    zone_type: ZoneType
    x_min: int
    x_max: int
    y_min: int
    y_max: int
    controller: str | None = None  # player_id o None
    control_points: int = 0
    resource_bonus: int = 0
    
    def contains(self, x: int, y: int) -> bool:
        return self.x_min <= x <= self.x_max and self.y_min <= y <= self.y_max
    
    def to_dict(self) -> dict:
        return {
            "id": self.zone_id,
            "type": self.zone_type.value,
            "bounds": {"x_min": self.x_min, "x_max": self.x_max, "y_min": self.y_min, "y_max": self.y_max},
            "controller": self.controller,
            "control_points": self.control_points
        }


class MicroRTSEnv(BaseEnvironment):
    """
    Entorno MicroRTS-v0.
    
    - Mapa: 24x24 grid
    - 3 zonas: base A, base B, mid
    - Macro steps cada 5 ticks
    - Victoria: destruir base o mayor score al timeout
    """
    
    # Constantes de producción
    MACRO_STEP_TICKS = 5
    RESOURCE_PER_TICK = 2
    MID_CONTROL_BONUS = 5
    VISION_RANGE = 5
    DEFAULT_MAX_UNITS = 30
    
    def __init__(
        self,
        map_size: int = 24,
        max_ticks: int = 600,  # ~2 minutos con macro steps
        max_units_per_player: int = 30,  # Cap de unidades por jugador
    ):
        super().__init__()
        self.map_size = map_size
        self.max_ticks = max_ticks
        self.max_units_per_player = max_units_per_player
        
        self.players = ["player_1", "player_2"]
        self.units: dict[int, Unit] = {}
        self.zones: dict[str, Zone] = {}
        self.resources: dict[str, int] = {}
        self._next_unit_id = 0
        self._winner: str | None = None
        self._events: list[dict] = []  # Eventos del tick actual
    
    @property
    def name(self) -> str:
        return "MicroRTS-v0"
    
    def reset(self, seed: int) -> dict[str, dict]:
        self._seed = seed
        self.rng = random.Random(seed)
        self.current_tick = 0
        self.done = False
        self._winner = None
        self._next_unit_id = 0
        self._events = []
        
        # Recursos iniciales
        self.resources = {p: 300 for p in self.players}
        
        # Crear zonas
        self._create_zones()
        
        # Crear unidades iniciales
        self.units = {}
        
        # Player 1: esquina inferior izquierda
        self._spawn_unit(UnitType.BASE, "player_1", 2, 2)
        self._spawn_unit(UnitType.WORKER, "player_1", 3, 2)
        self._spawn_unit(UnitType.WORKER, "player_1", 2, 3)
        
        # Player 2: esquina superior derecha
        self._spawn_unit(UnitType.BASE, "player_2", self.map_size - 3, self.map_size - 3)
        self._spawn_unit(UnitType.WORKER, "player_2", self.map_size - 4, self.map_size - 3)
        self._spawn_unit(UnitType.WORKER, "player_2", self.map_size - 3, self.map_size - 4)
        
        return {p: self._get_observation(p) for p in self.players}
    
    def _create_zones(self) -> None:
        """Crea las zonas del mapa."""
        mid = self.map_size // 2
        
        self.zones = {
            "base_a": Zone(
                zone_id="base_a",
                zone_type=ZoneType.BASE_A,
                x_min=0, x_max=6,
                y_min=0, y_max=6,
                controller="player_1"
            ),
            "base_b": Zone(
                zone_id="base_b",
                zone_type=ZoneType.BASE_B,
                x_min=self.map_size - 7, x_max=self.map_size - 1,
                y_min=self.map_size - 7, y_max=self.map_size - 1,
                controller="player_2"
            ),
            "mid": Zone(
                zone_id="mid",
                zone_type=ZoneType.MID,
                x_min=mid - 3, x_max=mid + 3,
                y_min=mid - 3, y_max=mid + 3,
                resource_bonus=self.MID_CONTROL_BONUS
            )
        }
    
    def _spawn_unit(self, unit_type: UnitType, owner: str, x: int, y: int) -> Unit:
        """Crea una nueva unidad."""
        unit = Unit.create(self._next_unit_id, unit_type, owner, x, y)
        self.units[self._next_unit_id] = unit
        self._next_unit_id += 1
        return unit
    
    def step(self, actions: dict[str, dict]) -> tuple[dict, dict, bool, dict]:
        if self.done:
            return (
                {p: self._get_observation(p) for p in self.players},
                {p: 0.0 for p in self.players},
                True,
                {"winner": self._winner}
            )
        
        self.current_tick += 1
        
        # Procesar recursos pasivos
        self._process_economy()
        
        # Procesar acciones de cada jugador
        for player_id, action in actions.items():
            self._process_action(player_id, action)
        
        # Procesar combate automático
        self._process_combat()
        
        # Actualizar control de zonas
        self._update_zone_control()
        
        # Reducir cooldowns
        for unit in self.units.values():
            if unit.production_cooldown > 0:
                unit.production_cooldown -= 1
        
        # Verificar condiciones de victoria
        self._check_victory()
        
        # Calcular rewards
        rewards = {p: 0.0 for p in self.players}
        
        # Capturar eventos del tick
        tick_events = self._events.copy()
        self._events = []
        
        info = {
            "tick": self.current_tick,
            "resources": self.resources.copy(),
            "unit_counts": self._get_unit_counts(),
            "scores": self.scores,
            "events": tick_events
        }
        
        return (
            {p: self._get_observation(p) for p in self.players},
            rewards,
            self.done,
            info
        )
    
    def _process_economy(self) -> None:
        """Genera recursos por trabajadores y control de mid."""
        for player_id in self.players:
            # Recursos base por trabajadores
            workers = sum(1 for u in self.units.values() 
                         if u.owner == player_id and u.unit_type == UnitType.WORKER)
            self.resources[player_id] += workers * self.RESOURCE_PER_TICK
            
            # Bonus por control de mid
            mid_zone = self.zones["mid"]
            if mid_zone.controller == player_id:
                self.resources[player_id] += mid_zone.resource_bonus
    
    def _process_action(self, player_id: str, action: dict) -> None:
        """Procesa la acción de un jugador."""
        action_type = action.get("type", "noop")
        
        if action_type == "train_worker":
            self._train_unit(player_id, UnitType.WORKER)
        elif action_type == "train_soldier":
            self._train_unit(player_id, UnitType.SOLDIER)
        elif action_type == "train_ranged":
            self._train_unit(player_id, UnitType.RANGED)
        elif action_type == "build_barracks":
            self._build_structure(player_id, UnitType.BARRACKS)
        elif action_type == "attack_zone":
            zone_id = action.get("zone_id", "mid")
            self._order_attack(player_id, zone_id)
        elif action_type == "defend_zone":
            zone_id = action.get("zone_id", "")
            self._order_defend(player_id, zone_id)
    
    def _train_unit(self, player_id: str, unit_type: UnitType) -> bool:
        """Entrena una unidad desde un edificio."""
        # Check cap de unidades
        player_units = sum(1 for u in self.units.values() if u.owner == player_id)
        if player_units >= self.max_units_per_player:
            return False
        
        stats = Unit.UNIT_STATS[unit_type]
        cost = stats["cost"]
        
        if self.resources[player_id] < cost:
            return False
        
        # Buscar edificio productor disponible
        if unit_type == UnitType.WORKER:
            producer_type = UnitType.BASE
        else:
            producer_type = UnitType.BARRACKS
        
        for unit in self.units.values():
            if (unit.owner == player_id and 
                unit.unit_type == producer_type and 
                unit.can_produce()):
                
                # Producir
                self.resources[player_id] -= cost
                unit.production_cooldown = stats["build_time"]
                
                # Spawn cerca del edificio
                spawn_x = unit.x + self.rng.choice([-1, 0, 1])
                spawn_y = unit.y + self.rng.choice([-1, 0, 1])
                spawn_x = max(0, min(self.map_size - 1, spawn_x))
                spawn_y = max(0, min(self.map_size - 1, spawn_y))
                
                self._spawn_unit(unit_type, player_id, spawn_x, spawn_y)
                return True
        
        return False
    
    def _build_structure(self, player_id: str, structure_type: UnitType) -> bool:
        """Construye un edificio."""
        # Check cap de unidades (edificios también cuentan)
        player_units = sum(1 for u in self.units.values() if u.owner == player_id)
        if player_units >= self.max_units_per_player:
            return False
        
        stats = Unit.UNIT_STATS[structure_type]
        cost = stats["cost"]
        
        if self.resources[player_id] < cost:
            return False
        
        # Buscar worker libre y posición válida
        for unit in list(self.units.values()):
            if (unit.owner == player_id and 
                unit.unit_type == UnitType.WORKER):
                
                # Construir en la posición del worker
                self.resources[player_id] -= cost
                build_x, build_y = unit.x, unit.y
                
                # El worker "se consume" para construir
                del self.units[unit.unit_id]
                
                new_building = self._spawn_unit(structure_type, player_id, build_x, build_y)
                new_building.production_cooldown = stats["build_time"]
                return True
        
        return False
    
    def _order_attack(self, player_id: str, zone_id: str) -> None:
        """Ordena a las unidades de combate atacar una zona."""
        if zone_id not in self.zones:
            return
        
        target_zone = self.zones[zone_id]
        target_x = (target_zone.x_min + target_zone.x_max) // 2
        target_y = (target_zone.y_min + target_zone.y_max) // 2
        
        for unit in self.units.values():
            if (unit.owner == player_id and 
                unit.unit_type in [UnitType.SOLDIER, UnitType.RANGED]):
                # Mover hacia el objetivo
                self._move_towards(unit, target_x, target_y)
    
    def _order_defend(self, player_id: str, zone_id: str) -> None:
        """Ordena defender una zona (base propia si no se especifica)."""
        if player_id == "player_1":
            default_zone = "base_a"
        else:
            default_zone = "base_b"
        
        zone_id = zone_id if zone_id in self.zones else default_zone
        target_zone = self.zones[zone_id]
        target_x = (target_zone.x_min + target_zone.x_max) // 2
        target_y = (target_zone.y_min + target_zone.y_max) // 2
        
        for unit in self.units.values():
            if (unit.owner == player_id and 
                unit.unit_type in [UnitType.SOLDIER, UnitType.RANGED]):
                self._move_towards(unit, target_x, target_y)
    
    def _move_towards(self, unit: Unit, target_x: int, target_y: int) -> None:
        """Mueve una unidad hacia un objetivo."""
        dx = target_x - unit.x
        dy = target_y - unit.y
        
        if dx != 0:
            unit.x += 1 if dx > 0 else -1
        if dy != 0:
            unit.y += 1 if dy > 0 else -1
        
        # Mantener en límites
        unit.x = max(0, min(self.map_size - 1, unit.x))
        unit.y = max(0, min(self.map_size - 1, unit.y))
    
    def _process_combat(self) -> None:
        """Procesa el combate automático entre unidades cercanas."""
        units_to_remove = []
        
        # Ordenar por unit_id para determinismo
        for unit_id, unit in sorted(self.units.items()):
            if unit.attack <= 0:
                continue
            
            # Buscar enemigos en rango (ordenados para determinismo)
            for target_id, target in sorted(self.units.items()):
                if target.owner == unit.owner:
                    continue
                if target_id in units_to_remove:
                    continue
                
                distance = abs(target.x - unit.x) + abs(target.y - unit.y)
                if distance <= unit.attack_range:
                    target.hp -= unit.attack
                    
                    if target.hp <= 0:
                        units_to_remove.append(target_id)
                        # Registrar evento
                        event_type = "building_destroyed" if target.is_building() else "unit_killed"
                        self._events.append({
                            "tick": self.current_tick,
                            "type": event_type,
                            "killer": unit.owner,
                            "victim_type": target.unit_type.value
                        })
                    break  # Solo un ataque por tick
        
        # Eliminar unidades muertas
        for unit_id in units_to_remove:
            if unit_id in self.units:
                del self.units[unit_id]
    
    def _update_zone_control(self) -> None:
        """Actualiza el control de zonas basado en presencia de unidades."""
        mid_zone = self.zones["mid"]
        prev_controller = mid_zone.controller
        
        p1_units = sum(1 for u in self.units.values() 
                      if u.owner == "player_1" and mid_zone.contains(u.x, u.y))
        p2_units = sum(1 for u in self.units.values() 
                      if u.owner == "player_2" and mid_zone.contains(u.x, u.y))
        
        if p1_units > p2_units:
            mid_zone.control_points = min(100, mid_zone.control_points + 5)
            if mid_zone.control_points >= 50:
                mid_zone.controller = "player_1"
        elif p2_units > p1_units:
            mid_zone.control_points = max(-100, mid_zone.control_points - 5)
            if mid_zone.control_points <= -50:
                mid_zone.controller = "player_2"
        else:
            # Decaimiento hacia neutral
            if mid_zone.control_points > 0:
                mid_zone.control_points -= 1
            elif mid_zone.control_points < 0:
                mid_zone.control_points += 1
            
            if abs(mid_zone.control_points) < 50:
                mid_zone.controller = None
        
        # Evento de captura de zona
        if mid_zone.controller != prev_controller and mid_zone.controller is not None:
            self._events.append({
                "tick": self.current_tick,
                "type": "zone_captured",
                "zone": "mid",
                "by": mid_zone.controller
            })
    
    def _check_victory(self) -> None:
        """Verifica condiciones de victoria."""
        # Victoria por destrucción de base
        p1_base = any(u.unit_type == UnitType.BASE and u.owner == "player_1" 
                      for u in self.units.values())
        p2_base = any(u.unit_type == UnitType.BASE and u.owner == "player_2" 
                      for u in self.units.values())
        
        if not p1_base:
            self.done = True
            self._winner = "player_2"
            return
        
        if not p2_base:
            self.done = True
            self._winner = "player_1"
            return
        
        # Timeout
        if self.current_tick >= self.max_ticks:
            self.done = True
            self._determine_winner_by_score()
    
    def _determine_winner_by_score(self) -> None:
        """Determina ganador por score al timeout usando self.scores."""
        s = self.scores
        
        if s["player_1"] > s["player_2"]:
            self._winner = "player_1"
        elif s["player_2"] > s["player_1"]:
            self._winner = "player_2"
        else:
            self._winner = None  # Empate
    
    def _get_unit_counts(self) -> dict:
        """Cuenta unidades por jugador y tipo."""
        counts = {p: {} for p in self.players}
        for unit in self.units.values():
            player_counts = counts[unit.owner]
            unit_type = unit.unit_type.value
            player_counts[unit_type] = player_counts.get(unit_type, 0) + 1
        return counts
    
    def _get_observation(self, player_id: str) -> dict:
        """Genera observación para un jugador."""
        visible_units = []
        
        # Unidades propias siempre visibles
        my_units = [u for u in self.units.values() if u.owner == player_id]
        visible_units.extend(my_units)
        
        # Unidades enemigas solo si están en rango de visión
        for unit in self.units.values():
            if unit.owner == player_id:
                continue
            
            # Verificar si alguna unidad propia lo ve
            for my_unit in my_units:
                distance = abs(unit.x - my_unit.x) + abs(unit.y - my_unit.y)
                if distance <= self.VISION_RANGE:
                    visible_units.append(unit)
                    break
        
        return {
            "resources": self.resources[player_id],
            "units": [u.to_dict() for u in visible_units],
            "zones": {z_id: z.to_dict() for z_id, z in self.zones.items()},
            "tick": self.current_tick,
            "max_ticks": self.max_ticks,
            "valid_actions": self.get_valid_actions(player_id)
        }
    
    def get_valid_actions(self, player_id: str) -> list[dict]:
        """Retorna acciones válidas macro."""
        actions = [
            {"type": "noop"},
            {"type": "train_worker"},
            {"type": "train_soldier"},
            {"type": "train_ranged"},
            {"type": "build_barracks"},
            {"type": "attack_zone", "zone_id": "mid"},
            {"type": "attack_zone", "zone_id": "base_a"},
            {"type": "attack_zone", "zone_id": "base_b"},
            {"type": "defend_zone", "zone_id": ""},
            {"type": "defend_zone", "zone_id": "mid"},
        ]
        return actions
    
    def get_winner(self) -> str | None:
        return self._winner
    
    def get_observation(self, player_id: str) -> dict:
        return self._get_observation(player_id)
    
    @property
    def scores(self) -> dict[str, int]:
        """Calcula el material score para cada jugador.
        
        Score = sum(HP de unidades) + (100 si controla mid)
        
        Nota: No incluimos recursos acumulados porque distorsionan
        (se acumulan infinitamente y crean scores de 10k+).
        """
        result = {}
        for player_id in self.players:
            score = 0
            # Puntos por unidades (HP)
            for unit in self.units.values():
                if unit.owner == player_id:
                    score += unit.hp
            # Puntos por control de mid
            if self.zones.get("mid") and self.zones["mid"].controller == player_id:
                score += 100
            result[player_id] = score
        return result
