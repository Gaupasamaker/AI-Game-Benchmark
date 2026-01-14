"""
TacticFPS-v0 - Juego táctico tipo CS2 en grid.

2v2 con fog-of-war, utilidades (smoke/flash), y objetivo plant/defuse.
"""

from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .base import BaseEnvironment


class Team(Enum):
    TERRORIST = "T"
    COUNTER_TERRORIST = "CT"


class Direction(Enum):
    N = (0, -1)
    S = (0, 1)
    E = (1, 0)
    W = (-1, 0)
    NE = (1, -1)
    NW = (-1, -1)
    SE = (1, 1)
    SW = (-1, 1)
    STAY = (0, 0)


class CellType(Enum):
    EMPTY = 0
    WALL = 1
    PLANT_ZONE = 2
    SPAWN_T = 3
    SPAWN_CT = 4


@dataclass
class Player:
    """Jugador en el juego."""
    player_id: str
    team: Team
    x: int
    y: int
    hp: int = 100
    ammo: int = 30
    has_bomb: bool = False
    has_smoke: bool = True
    has_flash: bool = True
    flashed_ticks: int = 0
    alive: bool = True
    aim_dir: Direction = Direction.N
    
    def to_dict(self, full: bool = True) -> dict:
        data = {
            "id": self.player_id,
            "team": self.team.value,
            "x": self.x,
            "y": self.y,
            "alive": self.alive,
        }
        if full:
            data.update({
                "hp": self.hp,
                "ammo": self.ammo,
                "has_bomb": self.has_bomb,
                "has_smoke": self.has_smoke,
                "has_flash": self.has_flash,
                "flashed_ticks": self.flashed_ticks,
                "aim_dir": self.aim_dir.name
            })
        return data


@dataclass
class Smoke:
    """Granada de humo activa."""
    x: int
    y: int
    ticks_remaining: int
    radius: int = 2


@dataclass
class BombState:
    """Estado de la bomba."""
    planted: bool = False
    plant_x: int = 0
    plant_y: int = 0
    plant_tick: int = 0
    defuse_progress: int = 0
    exploded: bool = False
    
    PLANT_TIME: int = 5
    DEFUSE_TIME: int = 10
    EXPLOSION_TIME: int = 45


class TacticFPSEnv(BaseEnvironment):
    """
    Entorno TacticFPS-v0.
    
    - Mapa: 15x15 grid
    - Teams: 2v2 (T vs CT)
    - Fog-of-war basado en Line-of-Sight
    - Victoria: eliminar enemigos, plantar+explotar, o defusar
    """
    
    FOV_ANGLE = math.pi / 2  # 90 grados
    VISION_RANGE = 10
    SHOOT_DAMAGE = 25
    FLASH_DURATION = 8
    SMOKE_DURATION = 20
    
    def __init__(
        self,
        map_size: int = 15,
        max_ticks: int = 120,
    ):
        super().__init__()
        self.map_size = map_size
        self.max_ticks = max_ticks
        
        # 4 jugadores: 2 por equipo
        self.players = ["t1", "t2", "ct1", "ct2"]
        self.player_data: dict[str, Player] = {}
        self.map_grid: list[list[CellType]] = []
        self.smokes: list[Smoke] = []
        self.bomb = BombState()
        self._winner: str | None = None
        self._winning_team: Team | None = None
        
        # Para scoring y eventos
        self._kill_counts: dict[str, int] = {"T": 0, "CT": 0}  # Kills por equipo
        self._events: list[dict] = []  # Eventos del match
    
    @property
    def name(self) -> str:
        return "TacticFPS-v0"
    
    def reset(self, seed: int) -> dict[str, dict]:
        self._seed = seed
        self.rng = random.Random(seed)
        self.current_tick = 0
        self.done = False
        self._winner = None
        self._winning_team = None
        
        # Crear mapa
        self._create_map()
        
        # Crear jugadores
        self._create_players()
        
        # Reset estados
        self.smokes = []
        self.bomb = BombState()
        self._kill_counts = {"T": 0, "CT": 0}
        self._events = []
        
        return {p: self._get_observation(p) for p in self.players}
    
    def _create_map(self) -> None:
        """Crea el mapa del juego."""
        self.map_grid = [[CellType.EMPTY for _ in range(self.map_size)] 
                         for _ in range(self.map_size)]
        
        # Paredes exteriores implícitas (manejadas por límites)
        
        # Añadir algunas paredes internas para cobertura
        # Pared horizontal central con huecos
        for x in range(3, self.map_size - 3):
            if x not in [self.map_size // 2 - 1, self.map_size // 2, self.map_size // 2 + 1]:
                self.map_grid[self.map_size // 2][x] = CellType.WALL
        
        # Paredes verticales para crear "sitios"
        for y in range(3, 7):
            self.map_grid[y][3] = CellType.WALL
            self.map_grid[y][self.map_size - 4] = CellType.WALL
        
        for y in range(self.map_size - 7, self.map_size - 3):
            self.map_grid[y][3] = CellType.WALL
            self.map_grid[y][self.map_size - 4] = CellType.WALL
        
        # Zona de plantado (centro-derecha)
        plant_center_x = self.map_size - 4
        plant_center_y = self.map_size // 2
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                px, py = plant_center_x + dx, plant_center_y + dy
                if 0 <= px < self.map_size and 0 <= py < self.map_size:
                    if self.map_grid[py][px] == CellType.EMPTY:
                        self.map_grid[py][px] = CellType.PLANT_ZONE
        
        # Spawns
        self.map_grid[1][1] = CellType.SPAWN_T
        self.map_grid[2][1] = CellType.SPAWN_T
        self.map_grid[self.map_size - 2][self.map_size - 2] = CellType.SPAWN_CT
        self.map_grid[self.map_size - 3][self.map_size - 2] = CellType.SPAWN_CT
    
    def _create_players(self) -> None:
        """Crea los jugadores."""
        self.player_data = {
            "t1": Player("t1", Team.TERRORIST, 1, 1, has_bomb=True),
            "t2": Player("t2", Team.TERRORIST, 1, 2),
            "ct1": Player("ct1", Team.COUNTER_TERRORIST, self.map_size - 2, self.map_size - 2),
            "ct2": Player("ct2", Team.COUNTER_TERRORIST, self.map_size - 2, self.map_size - 3),
        }
    
    def step(self, actions: dict[str, dict]) -> tuple[dict, dict, bool, dict]:
        if self.done:
            return (
                {p: self._get_observation(p) for p in self.players},
                {p: 0.0 for p in self.players},
                True,
                {"winner": self._winner, "winning_team": self._winning_team.value if self._winning_team else None}
            )
        
        self.current_tick += 1
        
        # Reducir efectos temporales
        self._update_effects()
        
        # Procesar acciones de cada jugador
        for player_id, action in actions.items():
            player = self.player_data[player_id]
            if player.alive and player.flashed_ticks <= 0:
                self._process_action(player, action)
        
        # Procesar disparos después del movimiento
        for player_id, action in actions.items():
            player = self.player_data[player_id]
            if player.alive and player.flashed_ticks <= 0:
                if action.get("shoot", False):
                    self._process_shoot(player)
        
        # Procesar bomba
        self._process_bomb()
        
        # Verificar victoria
        self._check_victory()
        
        # Calcular rewards
        rewards = {p: 0.0 for p in self.players}
        
        # Eventos nuevos este tick (copiar y limpiar)
        tick_events = self._events.copy()
        
        info = {
            "tick": self.current_tick,
            "bomb": {
                "planted": self.bomb.planted,
                "exploded": self.bomb.exploded,
            },
            "alive": {p: self.player_data[p].alive for p in self.players},
            "scores": self.scores,
            "events": tick_events
        }
        
        return (
            {p: self._get_observation(p) for p in self.players},
            rewards,
            self.done,
            info
        )
    
    def _update_effects(self) -> None:
        """Actualiza efectos temporales."""
        # Flash
        for player in self.player_data.values():
            if player.flashed_ticks > 0:
                player.flashed_ticks -= 1
        
        # Smokes
        self.smokes = [s for s in self.smokes if s.ticks_remaining > 0]
        for smoke in self.smokes:
            smoke.ticks_remaining -= 1
    
    def _process_action(self, player: Player, action: dict) -> None:
        """Procesa una acción de un jugador."""
        # Movimiento
        move_dir = action.get("move", "STAY")
        if move_dir in Direction.__members__:
            dx, dy = Direction[move_dir].value
            new_x, new_y = player.x + dx, player.y + dy
            
            # Verificar límites y paredes
            if (0 <= new_x < self.map_size and 
                0 <= new_y < self.map_size and
                self.map_grid[new_y][new_x] != CellType.WALL):
                player.x, player.y = new_x, new_y
        
        # Cambio de aim
        aim_dir = action.get("aim_dir", None)
        if aim_dir and aim_dir in Direction.__members__:
            player.aim_dir = Direction[aim_dir]
        
        # Smoke
        smoke_target = action.get("use_smoke", None)
        if smoke_target and player.has_smoke:
            sx, sy = smoke_target.get("x", player.x), smoke_target.get("y", player.y)
            if abs(sx - player.x) <= 5 and abs(sy - player.y) <= 5:
                self.smokes.append(Smoke(sx, sy, self.SMOKE_DURATION))
                player.has_smoke = False
        
        # Flash
        flash_dir = action.get("use_flash", None)
        if flash_dir and player.has_flash and flash_dir in Direction.__members__:
            self._process_flash(player, Direction[flash_dir])
            player.has_flash = False
        
        # Plant
        if action.get("plant", False):
            self._try_plant(player)
        
        # Defuse
        if action.get("defuse", False):
            self._try_defuse(player)
    
    def _process_shoot(self, player: Player) -> None:
        """Procesa un disparo."""
        if player.ammo <= 0:
            return
        
        player.ammo -= 1
        
        # Raycast en la dirección de aim
        dx, dy = player.aim_dir.value
        if dx == 0 and dy == 0:
            return
        
        x, y = player.x, player.y
        for _ in range(self.VISION_RANGE):
            x += dx
            y += dy
            
            if not (0 <= x < self.map_size and 0 <= y < self.map_size):
                break
            
            if self.map_grid[y][x] == CellType.WALL:
                break
            
            # Verificar humo
            if self._is_in_smoke(x, y):
                break
            
            # Verificar si hay enemigo
            for target in self.player_data.values():
                if (target.alive and 
                    target.team != player.team and
                    target.x == x and target.y == y):
                    target.hp -= self.SHOOT_DAMAGE
                    if target.hp <= 0:
                        target.alive = False
                        # Registrar kill
                        self._kill_counts[player.team.value] += 1
                        self._events.append({
                            "tick": self.current_tick,
                            "type": "kill",
                            "killer_team": player.team.value,
                            "victim_team": target.team.value,
                            "killer": player.player_id,
                            "victim": target.player_id
                        })
                        # Soltar bomba si la tenía
                        if target.has_bomb and not self.bomb.planted:
                            target.has_bomb = False
                    return
    
    def _process_flash(self, player: Player, direction: Direction) -> None:
        """Procesa una flash bang."""
        dx, dy = direction.value
        flash_x = player.x + dx * 3
        flash_y = player.y + dy * 3
        
        # Flashear a todos en LoS del punto de explosión
        for target in self.player_data.values():
            if not target.alive:
                continue
            
            dist = abs(target.x - flash_x) + abs(target.y - flash_y)
            if dist <= 4:
                # Verificar LoS desde flash a target
                if self._has_los(flash_x, flash_y, target.x, target.y):
                    target.flashed_ticks = self.FLASH_DURATION
    
    def _try_plant(self, player: Player) -> None:
        """Intenta plantar la bomba."""
        if player.team != Team.TERRORIST:
            return
        if not player.has_bomb:
            return
        if self.bomb.planted:
            return
        
        # Verificar que está en zona de plantado
        if self.map_grid[player.y][player.x] != CellType.PLANT_ZONE:
            return
        
        # Plantar (instantáneo en v0 para simplificar)
        self.bomb.planted = True
        self.bomb.plant_x = player.x
        self.bomb.plant_y = player.y
        self.bomb.plant_tick = self.current_tick
        player.has_bomb = False
        
        # Registrar evento
        self._events.append({
            "tick": self.current_tick,
            "type": "bomb_plant",
            "planter": player.player_id
        })
    
    def _try_defuse(self, player: Player) -> None:
        """Intenta desactivar la bomba."""
        if player.team != Team.COUNTER_TERRORIST:
            return
        if not self.bomb.planted or self.bomb.exploded:
            return
        
        # Verificar proximidad
        if abs(player.x - self.bomb.plant_x) > 1 or abs(player.y - self.bomb.plant_y) > 1:
            return
        
        # Incrementar progreso
        self.bomb.defuse_progress += 1
        
        if self.bomb.defuse_progress >= self.bomb.DEFUSE_TIME:
            # Bomba desactivada
            self.bomb.planted = False
            self.done = True
            self._winning_team = Team.COUNTER_TERRORIST
            
            # Registrar evento
            self._events.append({
                "tick": self.current_tick,
                "type": "bomb_defuse",
                "defuser": player.player_id
            })
    
    def _process_bomb(self) -> None:
        """Procesa el timer de la bomba."""
        if not self.bomb.planted or self.bomb.exploded:
            return
        
        ticks_since_plant = self.current_tick - self.bomb.plant_tick
        if ticks_since_plant >= self.bomb.EXPLOSION_TIME:
            self.bomb.exploded = True
            self.done = True
            self._winning_team = Team.TERRORIST
            
            # Registrar evento
            self._events.append({
                "tick": self.current_tick,
                "type": "bomb_explode"
            })
    
    def _check_victory(self) -> None:
        """Verifica condiciones de victoria."""
        if self.done:
            return
        
        t_alive = any(p.alive for p in self.player_data.values() if p.team == Team.TERRORIST)
        ct_alive = any(p.alive for p in self.player_data.values() if p.team == Team.COUNTER_TERRORIST)
        
        # Eliminación completa
        if not t_alive and not self.bomb.planted:
            self.done = True
            self._winning_team = Team.COUNTER_TERRORIST
            return
        
        if not ct_alive:
            self.done = True
            self._winning_team = Team.TERRORIST
            return
        
        # Timeout (CT gana si no hay bomba)
        if self.current_tick >= self.max_ticks:
            self.done = True
            self._winning_team = Team.COUNTER_TERRORIST
    
    def _is_in_smoke(self, x: int, y: int) -> bool:
        """Verifica si una posición está dentro de un humo."""
        for smoke in self.smokes:
            dist = abs(x - smoke.x) + abs(y - smoke.y)
            if dist <= smoke.radius:
                return True
        return False
    
    def _has_los(self, x1: int, y1: int, x2: int, y2: int) -> bool:
        """Verifica si hay línea de visión entre dos puntos."""
        dx = x2 - x1
        dy = y2 - y1
        steps = max(abs(dx), abs(dy))
        
        if steps == 0:
            return True
        
        for i in range(1, steps):
            x = x1 + int(dx * i / steps)
            y = y1 + int(dy * i / steps)
            
            if self.map_grid[y][x] == CellType.WALL:
                return False
            if self._is_in_smoke(x, y):
                return False
        
        return True
    
    def _get_visible_cells(self, player: Player) -> set[tuple[int, int]]:
        """Calcula las celdas visibles para un jugador."""
        visible = set()
        
        if not player.alive or player.flashed_ticks > 0:
            return visible
        
        # Visión 360 pero con rango limitado y LoS
        for dx in range(-self.VISION_RANGE, self.VISION_RANGE + 1):
            for dy in range(-self.VISION_RANGE, self.VISION_RANGE + 1):
                x, y = player.x + dx, player.y + dy
                
                if not (0 <= x < self.map_size and 0 <= y < self.map_size):
                    continue
                
                dist = abs(dx) + abs(dy)
                if dist > self.VISION_RANGE:
                    continue
                
                if self._has_los(player.x, player.y, x, y):
                    visible.add((x, y))
        
        return visible
    
    def _get_observation(self, player_id: str) -> dict:
        """Genera observación para un jugador."""
        player = self.player_data[player_id]
        
        # Calcular visibilidad del equipo
        team_visible = set()
        for p in self.player_data.values():
            if p.team == player.team:
                team_visible.update(self._get_visible_cells(p))
        
        # Información propia
        own_info = player.to_dict(full=True)
        
        # Aliados (info completa)
        allies = [p.to_dict(full=True) for p in self.player_data.values() 
                  if p.team == player.team and p.player_id != player_id]
        
        # Enemigos (solo si visibles)
        enemies = []
        for p in self.player_data.values():
            if p.team != player.team and p.alive:
                if (p.x, p.y) in team_visible:
                    enemies.append(p.to_dict(full=False))  # Info limitada
        
        # Mapa visible
        visible_map = []
        for y in range(self.map_size):
            row = []
            for x in range(self.map_size):
                if (x, y) in team_visible:
                    row.append(self.map_grid[y][x].value)
                else:
                    row.append(-1)  # No visible
            visible_map.append(row)
        
        # Bomba info
        bomb_info = {"planted": self.bomb.planted}
        if self.bomb.planted:
            if (self.bomb.plant_x, self.bomb.plant_y) in team_visible:
                bomb_info["x"] = self.bomb.plant_x
                bomb_info["y"] = self.bomb.plant_y
                bomb_info["ticks_remaining"] = max(0, 
                    self.bomb.EXPLOSION_TIME - (self.current_tick - self.bomb.plant_tick))
        
        return {
            "self": own_info,
            "allies": allies,
            "enemies": enemies,
            "visible_map": visible_map,
            "smokes": [{"x": s.x, "y": s.y} for s in self.smokes],
            "bomb": bomb_info,
            "tick": self.current_tick,
            "max_ticks": self.max_ticks,
            "valid_actions": self.get_valid_actions(player_id)
        }
    
    def get_valid_actions(self, player_id: str) -> list[dict]:
        """Retorna acciones válidas."""
        player = self.player_data[player_id]
        
        if not player.alive:
            return [{}]
        
        actions = []
        
        # Combinaciones de movimiento y aim
        for move in ["N", "S", "E", "W", "STAY"]:
            for aim in ["N", "S", "E", "W", "NE", "NW", "SE", "SW"]:
                for shoot in [False, True]:
                    action = {
                        "move": move,
                        "aim_dir": aim,
                        "shoot": shoot,
                        "plant": False,
                        "defuse": False,
                        "use_smoke": None,
                        "use_flash": None
                    }
                    actions.append(action)
        
        # Añadir opciones de plant/defuse/utilities si aplican
        # (simplificado - el jugador debe incluirlas en su acción)
        
        return actions[:50]  # Limitar para no explotar
    
    def get_winner(self) -> str | None:
        """Retorna el equipo ganador normalizado a player_1/player_2.
        
        Mapeo: T → player_1, CT → player_2
        """
        if self._winning_team == Team.TERRORIST:
            return "player_1"
        elif self._winning_team == Team.COUNTER_TERRORIST:
            return "player_2"
        return None
    
    def get_winning_team(self) -> str | None:
        """Retorna el equipo ganador como T/CT."""
        if self._winning_team:
            return self._winning_team.value
        return None
    
    def get_observation(self, player_id: str) -> dict:
        return self._get_observation(player_id)
    
    @property
    def scores(self) -> dict[str, int]:
        """Calcula scores normalizados a player_1/player_2.
        
        Mapeo:
        - player_1 = Team T (Terrorist) 
        - player_2 = Team CT (Counter-Terrorist)
        
        Score = kills por equipo
        """
        return {
            "player_1": self._kill_counts["T"],
            "player_2": self._kill_counts["CT"]
        }
