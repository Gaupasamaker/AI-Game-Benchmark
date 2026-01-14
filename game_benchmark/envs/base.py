"""
Base Environment - Contrato común para todos los juegos.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseEnvironment(ABC):
    """
    Clase base abstracta para todos los entornos de juego.
    
    Todos los entornos deben ser deterministas dado un seed.
    """
    
    def __init__(self):
        self.players: list[str] = []
        self.current_tick: int = 0
        self.max_ticks: int = 0
        self.done: bool = False
        self._seed: int = 0
    
    @abstractmethod
    def reset(self, seed: int) -> dict[str, dict]:
        """
        Reinicia el entorno con una seed específica.
        
        Args:
            seed: Semilla para reproducibilidad determinista.
            
        Returns:
            Observaciones iniciales por jugador: {player_id: observation}
        """
        pass
    
    @abstractmethod
    def step(self, actions: dict[str, dict]) -> tuple[dict[str, dict], dict[str, float], bool, dict[str, Any]]:
        """
        Ejecuta un paso del juego con las acciones de todos los jugadores.
        
        Args:
            actions: Diccionario de acciones por jugador: {player_id: action}
            
        Returns:
            - observations: Observaciones por jugador
            - rewards: Recompensas por jugador
            - done: Si el juego ha terminado
            - info: Información adicional (ganador, stats, etc.)
        """
        pass
    
    @abstractmethod
    def get_valid_actions(self, player_id: str) -> list[dict]:
        """
        Retorna lista de acciones válidas para un jugador.
        
        Args:
            player_id: ID del jugador
            
        Returns:
            Lista de acciones válidas
        """
        pass
    
    @abstractmethod
    def get_winner(self) -> str | None:
        """
        Retorna el ID del ganador, o None si empate/no terminado.
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre del entorno."""
        pass
    
    def is_action_valid(self, player_id: str, action: dict) -> bool:
        """
        Verifica si una acción es válida.
        
        Args:
            player_id: ID del jugador
            action: Acción a validar
            
        Returns:
            True si la acción es válida
        """
        valid_actions = self.get_valid_actions(player_id)
        return action in valid_actions
    
    def get_observation(self, player_id: str) -> dict:
        """
        Obtiene la observación actual para un jugador específico.
        Implementación por defecto, puede ser sobrescrita.
        """
        return {}
