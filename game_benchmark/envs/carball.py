"""
CarBall-v0 - Juego tipo Rocket League en 2D.

Arena rectangular con dos porterías, física simplificada de coches y pelota.
Observations normalizadas para compatibilidad con RL.
"""

from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from typing import Any

from .base import BaseEnvironment


@dataclass
class Vec2:
    """Vector 2D simple."""
    x: float = 0.0
    y: float = 0.0
    
    def __add__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x + other.x, self.y + other.y)
    
    def __sub__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x - other.x, self.y - other.y)
    
    def __mul__(self, scalar: float) -> "Vec2":
        return Vec2(self.x * scalar, self.y * scalar)
    
    def __rmul__(self, scalar: float) -> "Vec2":
        return self * scalar
    
    def magnitude(self) -> float:
        return math.sqrt(self.x ** 2 + self.y ** 2)
    
    def normalized(self) -> "Vec2":
        mag = self.magnitude()
        if mag == 0:
            return Vec2(0, 0)
        return Vec2(self.x / mag, self.y / mag)
    
    def dot(self, other: "Vec2") -> float:
        return self.x * other.x + self.y * other.y
    
    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y}
    
    @classmethod
    def from_angle(cls, angle: float, magnitude: float = 1.0) -> "Vec2":
        return cls(math.cos(angle) * magnitude, math.sin(angle) * magnitude)


@dataclass
class Ball:
    """Pelota del juego."""
    pos: Vec2 = field(default_factory=Vec2)
    vel: Vec2 = field(default_factory=Vec2)
    radius: float = 1.0  # Reducido de 2.0 según spec
    
    def update(self, dt: float) -> None:
        self.pos = self.pos + self.vel * dt
    
    def to_dict(self) -> dict:
        return {
            "pos": self.pos.to_dict(),
            "vel": self.vel.to_dict(),
            "radius": self.radius
        }


@dataclass
class Car:
    """Coche del jugador."""
    pos: Vec2 = field(default_factory=Vec2)
    vel: Vec2 = field(default_factory=Vec2)
    angle: float = 0.0  # Radianes
    boost: float = 100.0
    dash_cooldown: int = 0
    
    # Constantes ajustadas según spec
    max_speed: float = 15.0
    boost_speed: float = 25.0
    acceleration: float = 20.0
    turn_speed: float = 3.0
    friction: float = 0.99  # Ajustado de 0.98
    radius: float = 1.2  # Reducido de 2.5 según spec
    dash_power: float = 30.0
    dash_cooldown_ticks: int = 60
    boost_consumption: float = 2.0  # Por tick cuando usa boost
    
    def update(self, dt: float, throttle: int, steer: int, use_boost: bool, use_dash: bool) -> None:
        # Steering
        self.angle += steer * self.turn_speed * dt
        
        # Throttle
        forward = Vec2.from_angle(self.angle)
        
        # Velocidad máxima por defecto
        max_spd = self.max_speed
        
        if use_dash and self.dash_cooldown <= 0:
            # Dash: impulso instantáneo
            self.vel = self.vel + forward * self.dash_power
            self.dash_cooldown = self.dash_cooldown_ticks
            max_spd = self.boost_speed
        elif use_boost and self.boost > 0 and throttle > 0:
            # Boost
            self.vel = self.vel + forward * (self.acceleration * 1.5 * dt)
            self.boost = max(0, self.boost - self.boost_consumption)
            max_spd = self.boost_speed
        elif throttle != 0:
            # Normal throttle
            self.vel = self.vel + forward * (throttle * self.acceleration * dt)
            max_spd = self.max_speed
        
        # Limitar velocidad
        speed = self.vel.magnitude()
        if speed > max_spd:
            self.vel = self.vel.normalized() * max_spd
        
        # Fricción/drag
        self.vel = self.vel * self.friction
        
        # Actualizar posición
        self.pos = self.pos + self.vel * dt
        
        # Reducir cooldown del dash
        if self.dash_cooldown > 0:
            self.dash_cooldown -= 1
    
    def to_dict(self) -> dict:
        return {
            "pos": self.pos.to_dict(),
            "vel": self.vel.to_dict(),
            "angle": self.angle,
            "boost": self.boost,
            "dash_cooldown": self.dash_cooldown
        }


class CarBallEnv(BaseEnvironment):
    """
    Entorno CarBall-v0.
    
    - Arena: 100x60
    - Porterías en los extremos (apertura 20)
    - 1v1
    - Victoria: más goles en max_ticks o primero en llegar a max_goals
    - Observations normalizadas a [-1, 1]
    """
    
    # Constantes de normalización
    MAX_VEL = 30.0  # Velocidad máxima para normalizar
    
    def __init__(
        self,
        arena_width: float = 100.0,
        arena_height: float = 60.0,
        goal_width: float = 20.0,  # Ajustado de 15 según spec
        max_ticks: int = 2700,  # 90 segundos a 30 ticks/s
        max_goals: int = 7,  # Victoria por goles
        ticks_per_second: int = 30,
        restitution: float = 0.8  # Coeficiente de restitución para colisiones
    ):
        super().__init__()
        self.arena_width = arena_width
        self.arena_height = arena_height
        self.goal_width = goal_width
        self.max_ticks = max_ticks
        self.max_goals = max_goals
        self.ticks_per_second = ticks_per_second
        self.dt = 1.0 / ticks_per_second
        self.restitution = restitution
        
        self.players = ["player_1", "player_2"]
        self.cars: dict[str, Car] = {}
        self.ball: Ball = Ball()
        self.scores: dict[str, int] = {}
        self._winner: str | None = None
    
    @property
    def name(self) -> str:
        return "CarBall-v0"
    
    def reset(self, seed: int) -> dict[str, dict]:
        self._seed = seed
        self.rng = random.Random(seed)
        self.current_tick = 0
        self.done = False
        self._winner = None
        
        self.scores = {p: 0 for p in self.players}
        
        # Posiciones iniciales
        self._reset_positions()
        
        return {p: self._get_observation(p) for p in self.players}
    
    def _reset_positions(self) -> None:
        """Resetea posiciones tras gol o al inicio."""
        # Pelota en el centro
        self.ball = Ball(
            pos=Vec2(self.arena_width / 2, self.arena_height / 2),
            vel=Vec2(0, 0)
        )
        
        # Coches en sus mitades (posiciones de kickoff)
        self.cars = {
            "player_1": Car(
                pos=Vec2(self.arena_width * 0.25, self.arena_height / 2),
                angle=0,  # Mirando a la derecha
                boost=100.0
            ),
            "player_2": Car(
                pos=Vec2(self.arena_width * 0.75, self.arena_height / 2),
                angle=math.pi,  # Mirando a la izquierda
                boost=100.0
            )
        }
    
    def step(self, actions: dict[str, dict]) -> tuple[dict, dict, bool, dict]:
        if self.done:
            return (
                {p: self._get_observation(p) for p in self.players},
                {p: 0.0 for p in self.players},
                True,
                {"winner": self._winner}
            )
        
        self.current_tick += 1
        
        # Actualizar coches
        for player_id, car in self.cars.items():
            action = actions.get(player_id, {})
            car.update(
                self.dt,
                throttle=action.get("throttle", 0),
                steer=action.get("steer", 0),
                use_boost=action.get("boost", False),
                use_dash=action.get("dash", False)
            )
            
            # Colisiones con paredes
            self._handle_car_wall_collision(car)
        
        # Actualizar pelota
        self.ball.update(self.dt)
        
        # Colisiones pelota-coche
        for car in self.cars.values():
            self._handle_ball_car_collision(car)
        
        # Colisiones pelota-pared
        self._handle_ball_wall_collision()
        
        # Verificar goles
        goal_scored = self._check_goals()
        
        # Calcular rewards
        rewards = {p: 0.0 for p in self.players}
        if goal_scored:
            # Reward por marcar gol
            rewards[goal_scored] = 1.0
            other = "player_2" if goal_scored == "player_1" else "player_1"
            rewards[other] = -1.0
            self._reset_positions()
        
        # Check fin del juego
        # Por max_goals
        for player_id, score in self.scores.items():
            if score >= self.max_goals:
                self.done = True
                self._winner = player_id
                break
        
        # Por timeout
        if not self.done and self.current_tick >= self.max_ticks:
            self.done = True
            self._determine_winner()
        
        info = {
            "tick": self.current_tick,
            "scores": self.scores.copy(),
            "goal_scored": goal_scored,
            "time_left_s": (self.max_ticks - self.current_tick) / self.ticks_per_second
        }
        
        return (
            {p: self._get_observation(p) for p in self.players},
            rewards,
            self.done,
            info
        )
    
    def _handle_car_wall_collision(self, car: Car) -> None:
        """Rebote del coche con las paredes."""
        # Límites horizontales
        if car.pos.x - car.radius < 0:
            car.pos.x = car.radius
            car.vel.x *= -0.5
        elif car.pos.x + car.radius > self.arena_width:
            car.pos.x = self.arena_width - car.radius
            car.vel.x *= -0.5
        
        # Límites verticales
        if car.pos.y - car.radius < 0:
            car.pos.y = car.radius
            car.vel.y *= -0.5
        elif car.pos.y + car.radius > self.arena_height:
            car.pos.y = self.arena_height - car.radius
            car.vel.y *= -0.5
    
    def _handle_ball_car_collision(self, car: Car) -> None:
        """Colisión elástica entre pelota y coche."""
        diff = self.ball.pos - car.pos
        dist = diff.magnitude()
        min_dist = self.ball.radius + car.radius
        
        if dist < min_dist and dist > 0:
            # Separar objetos
            overlap = min_dist - dist
            normal = diff.normalized()
            self.ball.pos = self.ball.pos + normal * overlap
            
            # Colisión elástica simplificada
            relative_vel = self.ball.vel - car.vel
            vel_along_normal = relative_vel.dot(normal)
            
            if vel_along_normal < 0:
                impulse = -(1 + self.restitution) * vel_along_normal
                self.ball.vel = self.ball.vel + normal * impulse
    
    def _handle_ball_wall_collision(self) -> None:
        """Rebote de la pelota con las paredes."""
        goal_y_min = (self.arena_height - self.goal_width) / 2
        goal_y_max = (self.arena_height + self.goal_width) / 2
        
        # Pared izquierda (excepto portería)
        if self.ball.pos.x - self.ball.radius < 0:
            if not (goal_y_min < self.ball.pos.y < goal_y_max):
                self.ball.pos.x = self.ball.radius
                self.ball.vel.x *= -self.restitution
        
        # Pared derecha (excepto portería)
        if self.ball.pos.x + self.ball.radius > self.arena_width:
            if not (goal_y_min < self.ball.pos.y < goal_y_max):
                self.ball.pos.x = self.arena_width - self.ball.radius
                self.ball.vel.x *= -self.restitution
        
        # Paredes superior e inferior
        if self.ball.pos.y - self.ball.radius < 0:
            self.ball.pos.y = self.ball.radius
            self.ball.vel.y *= -self.restitution
        elif self.ball.pos.y + self.ball.radius > self.arena_height:
            self.ball.pos.y = self.arena_height - self.ball.radius
            self.ball.vel.y *= -self.restitution
    
    def _check_goals(self) -> str | None:
        """Verifica si hay gol. Retorna quién marcó o None."""
        goal_y_min = (self.arena_height - self.goal_width) / 2
        goal_y_max = (self.arena_height + self.goal_width) / 2
        
        # Gol en portería izquierda (player_2 marca)
        if self.ball.pos.x < 0 and goal_y_min < self.ball.pos.y < goal_y_max:
            self.scores["player_2"] += 1
            return "player_2"
        
        # Gol en portería derecha (player_1 marca)
        if self.ball.pos.x > self.arena_width and goal_y_min < self.ball.pos.y < goal_y_max:
            self.scores["player_1"] += 1
            return "player_1"
        
        return None
    
    def _determine_winner(self) -> None:
        """Determina el ganador basado en el marcador."""
        if self.scores["player_1"] > self.scores["player_2"]:
            self._winner = "player_1"
        elif self.scores["player_2"] > self.scores["player_1"]:
            self._winner = "player_2"
        else:
            self._winner = None  # Empate
    
    def _normalize_x(self, x: float) -> float:
        """Normaliza coordenada X a [-1, 1]."""
        return (x / self.arena_width) * 2 - 1
    
    def _normalize_y(self, y: float) -> float:
        """Normaliza coordenada Y a [-1, 1]."""
        return (y / self.arena_height) * 2 - 1
    
    def _normalize_vel(self, v: float) -> float:
        """Normaliza velocidad a [-1, 1]."""
        return max(-1.0, min(1.0, v / self.MAX_VEL))
    
    def _normalize_angle(self, angle: float) -> float:
        """Normaliza ángulo a [-1, 1] (donde -1 = -π, 1 = π)."""
        # Normalizar a [-π, π]
        while angle > math.pi:
            angle -= 2 * math.pi
        while angle < -math.pi:
            angle += 2 * math.pi
        return angle / math.pi
    
    def _get_observation(self, player_id: str) -> dict:
        """
        Genera observación NORMALIZADA para un jugador.
        Todos los valores en [-1, 1] o [0, 1].
        """
        my_car = self.cars[player_id]
        opponent_id = "player_2" if player_id == "player_1" else "player_1"
        opp_car = self.cars[opponent_id]
        
        time_left_s = (self.max_ticks - self.current_tick) / self.ticks_per_second
        
        return {
            # Metadatos
            "game_id": "carball_v0",
            "tick": self.current_tick,
            "time_left_s": time_left_s,
            
            # Marcador
            "score_self": self.scores[player_id],
            "score_opp": self.scores[opponent_id],
            
            # Mi coche (normalizado)
            "car_self": {
                "x": self._normalize_x(my_car.pos.x),
                "y": self._normalize_y(my_car.pos.y),
                "vx": self._normalize_vel(my_car.vel.x),
                "vy": self._normalize_vel(my_car.vel.y),
                "angle": self._normalize_angle(my_car.angle),
                "boost": my_car.boost / 100.0  # [0, 1]
            },
            
            # Oponente (normalizado)
            "car_opp": {
                "x": self._normalize_x(opp_car.pos.x),
                "y": self._normalize_y(opp_car.pos.y),
                "vx": self._normalize_vel(opp_car.vel.x),
                "vy": self._normalize_vel(opp_car.vel.y),
                "angle": self._normalize_angle(opp_car.angle),
                "boost": opp_car.boost / 100.0
            },
            
            # Pelota (normalizado)
            "ball": {
                "x": self._normalize_x(self.ball.pos.x),
                "y": self._normalize_y(self.ball.pos.y),
                "vx": self._normalize_vel(self.ball.vel.x),
                "vy": self._normalize_vel(self.ball.vel.y)
            },
            
            # Acciones válidas (para compatibilidad)
            "valid_actions": self.get_valid_actions(player_id)
        }
    
    def get_raw_state(self) -> dict:
        """Retorna estado sin normalizar (para visualización)."""
        return {
            "cars": {pid: car.to_dict() for pid, car in self.cars.items()},
            "ball": self.ball.to_dict(),
            "scores": self.scores.copy(),
            "tick": self.current_tick,
            "arena": {
                "width": self.arena_width,
                "height": self.arena_height,
                "goal_width": self.goal_width
            }
        }
    
    def get_valid_actions(self, player_id: str) -> list[dict]:
        """
        Retorna todas las combinaciones de acciones válidas.
        Para simplificar, retornamos las acciones como opciones discretas.
        """
        # Acciones simples discretizadas
        actions = []
        for throttle in [-1, 0, 1]:
            for steer in [-1, 0, 1]:
                for boost in [False, True]:
                    for dash in [False, True]:
                        actions.append({
                            "throttle": throttle,
                            "steer": steer,
                            "boost": boost,
                            "dash": dash
                        })
        return actions
    
    def get_winner(self) -> str | None:
        return self._winner
    
    def get_observation(self, player_id: str) -> dict:
        return self._get_observation(player_id)
