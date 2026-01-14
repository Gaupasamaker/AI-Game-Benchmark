"""
Baselines para CarBall.

Tres estrategias diferentes:
- BallChaser: Persigue la pelota siempre
- Goalie: Defiende la portería propia
- Striker: Se posiciona detrás de la pelota para empujarla hacia gol
"""

from __future__ import annotations
import math
from ..base import BaseAgent


class CarBallBot(BaseAgent):
    """
    Bot BallChaser para CarBall.
    Estrategia simple: ir hacia la pelota y empujarla.
    """
    
    def __init__(self, player_id: str):
        super().__init__(player_id)
        self.target_goal_x = 1.0 if player_id == "player_1" else -1.0
    
    def act(self, observation: dict) -> dict:
        car = observation["car_self"]
        ball = observation["ball"]
        
        # Calcular ángulo hacia la pelota (coordenadas normalizadas)
        dx = ball["x"] - car["x"]
        dy = ball["y"] - car["y"]
        target_angle = math.atan2(dy, dx)
        
        # Desnormalizar el ángulo del coche
        car_angle = car["angle"] * math.pi
        
        # Diferencia de ángulo
        angle_diff = target_angle - car_angle
        while angle_diff > math.pi:
            angle_diff -= 2 * math.pi
        while angle_diff < -math.pi:
            angle_diff += 2 * math.pi
        
        # Decidir steering
        steer = 1 if angle_diff > 0.1 else (-1 if angle_diff < -0.1 else 0)
        
        # Distancia a la pelota (normalizada)
        distance = math.sqrt(dx**2 + dy**2)
        
        # Siempre adelante
        throttle = 1
        
        # Usar boost si estamos alineados y lejos
        use_boost = abs(angle_diff) < 0.3 and distance > 0.3 and car["boost"] > 0.2
        
        # Usar dash si estamos muy cerca y alineados
        use_dash = distance < 0.15 and abs(angle_diff) < 0.5
        
        return {
            "throttle": throttle,
            "steer": steer,
            "boost": use_boost,
            "dash": use_dash
        }
    
    @property
    def name(self) -> str:
        return "BallChaser"


class GoalieBot(BaseAgent):
    """
    Bot Goalie para CarBall.
    Estrategia: Defender la portería propia, perseguir solo si la pelota está cerca.
    """
    
    def __init__(self, player_id: str):
        super().__init__(player_id)
        # Portería propia (normalizada)
        self.goal_x = -1.0 if player_id == "player_1" else 1.0
        self.defend_x = -0.7 if player_id == "player_1" else 0.7
    
    def act(self, observation: dict) -> dict:
        car = observation["car_self"]
        ball = observation["ball"]
        
        car_angle = car["angle"] * math.pi
        
        # ¿La pelota está en mi mitad del campo?
        ball_in_my_half = (self.goal_x < 0 and ball["x"] < 0) or (self.goal_x > 0 and ball["x"] > 0)
        
        # ¿La pelota está muy cerca de mi portería?
        ball_danger = abs(ball["x"] - self.goal_x) < 0.4
        
        if ball_danger:
            # Modo interceptar: ir directo a la pelota
            target_x = ball["x"]
            target_y = ball["y"]
        elif ball_in_my_half:
            # Posicionarse entre la pelota y la portería
            target_x = self.defend_x
            target_y = ball["y"]  # Mismo Y que la pelota
        else:
            # La pelota está lejos, quedarse en posición defensiva
            target_x = self.defend_x
            target_y = 0.0  # Centro vertical
        
        # Calcular hacia dónde ir
        dx = target_x - car["x"]
        dy = target_y - car["y"]
        target_angle = math.atan2(dy, dx)
        
        angle_diff = target_angle - car_angle
        while angle_diff > math.pi:
            angle_diff -= 2 * math.pi
        while angle_diff < -math.pi:
            angle_diff += 2 * math.pi
        
        steer = 1 if angle_diff > 0.1 else (-1 if angle_diff < -0.1 else 0)
        
        distance = math.sqrt(dx**2 + dy**2)
        
        # Avanzar si no estamos en posición
        throttle = 1 if distance > 0.05 else 0
        
        # Boost solo si la pelota es peligrosa
        use_boost = ball_danger and abs(angle_diff) < 0.3 and car["boost"] > 0.3
        
        # Dash para interceptar
        use_dash = ball_danger and distance < 0.2
        
        return {
            "throttle": throttle,
            "steer": steer,
            "boost": use_boost,
            "dash": use_dash
        }
    
    @property
    def name(self) -> str:
        return "Goalie"


class StrikerBot(BaseAgent):
    """
    Bot Striker para CarBall.
    Estrategia: Posicionarse detrás de la pelota para empujarla hacia la portería enemiga.
    """
    
    def __init__(self, player_id: str):
        super().__init__(player_id)
        # Portería enemiga (normalizada)
        self.enemy_goal_x = 1.0 if player_id == "player_1" else -1.0
    
    def act(self, observation: dict) -> dict:
        car = observation["car_self"]
        ball = observation["ball"]
        
        car_angle = car["angle"] * math.pi
        
        # Calcular punto ideal: detrás de la pelota, alineado con la portería
        # Queremos estar en el lado opuesto de la portería respecto a la pelota
        offset = 0.15  # Distancia detrás de la pelota
        
        if self.enemy_goal_x > 0:
            # Portería a la derecha, posicionarse a la izquierda de la pelota
            target_x = ball["x"] - offset
        else:
            # Portería a la izquierda, posicionarse a la derecha de la pelota
            target_x = ball["x"] + offset
        
        target_y = ball["y"]
        
        # Calcular distancias
        dx_to_target = target_x - car["x"]
        dy_to_target = target_y - car["y"]
        dist_to_target = math.sqrt(dx_to_target**2 + dy_to_target**2)
        
        dx_to_ball = ball["x"] - car["x"]
        dy_to_ball = ball["y"] - car["y"]
        dist_to_ball = math.sqrt(dx_to_ball**2 + dy_to_ball**2)
        
        # ¿Estamos bien posicionados detrás de la pelota?
        behind_ball = (self.enemy_goal_x > 0 and car["x"] < ball["x"]) or \
                      (self.enemy_goal_x < 0 and car["x"] > ball["x"])
        well_positioned = behind_ball and abs(car["y"] - ball["y"]) < 0.1
        
        if well_positioned and dist_to_ball < 0.2:
            # ¡Atacar! Ir directo hacia la portería (a través de la pelota)
            target_angle = math.atan2(0 - car["y"], self.enemy_goal_x - car["x"])
            use_boost = True
            use_dash = dist_to_ball < 0.1
        elif dist_to_target < 0.05:
            # Ya estamos en posición, apuntar hacia la portería
            target_angle = math.atan2(0 - car["y"], self.enemy_goal_x - car["x"])
            use_boost = False
            use_dash = False
        else:
            # Ir hacia el punto detrás de la pelota
            target_angle = math.atan2(dy_to_target, dx_to_target)
            use_boost = dist_to_target > 0.3 and car["boost"] > 0.3
            use_dash = False
        
        angle_diff = target_angle - car_angle
        while angle_diff > math.pi:
            angle_diff -= 2 * math.pi
        while angle_diff < -math.pi:
            angle_diff += 2 * math.pi
        
        steer = 1 if angle_diff > 0.1 else (-1 if angle_diff < -0.1 else 0)
        throttle = 1
        
        return {
            "throttle": throttle,
            "steer": steer,
            "boost": use_boost and abs(angle_diff) < 0.3,
            "dash": use_dash
        }
    
    @property
    def name(self) -> str:
        return "Striker"
