"""
Base Agent - Contrato común para todos los agentes.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
import random


class BaseAgent(ABC):
    """
    Clase base abstracta para todos los agentes.
    
    Un agente recibe una observación y retorna una acción.
    """
    
    def __init__(self, player_id: str):
        self.player_id = player_id
    
    @abstractmethod
    def act(self, observation: dict) -> dict:
        """
        Decide qué acción tomar dada una observación.
        
        Args:
            observation: Estado visible del juego para este agente.
            
        Returns:
            Acción a ejecutar.
        """
        pass
    
    def reset(self) -> None:
        """
        Reinicia el estado interno del agente.
        Llamado al inicio de cada partida.
        """
        pass
    
    @property
    def name(self) -> str:
        """Nombre del agente para identificación."""
        return self.__class__.__name__


class RandomAgent(BaseAgent):
    """
    Agente que selecciona acciones aleatorias.
    Útil como baseline mínimo.
    """
    
    def __init__(self, player_id: str, seed: int | None = None):
        super().__init__(player_id)
        self.rng = random.Random(seed)
    
    def act(self, observation: dict) -> dict:
        """Selecciona una acción aleatoria de las válidas."""
        valid_actions = observation.get("valid_actions", [])
        if not valid_actions:
            return {}
        return self.rng.choice(valid_actions)
    
    def reset(self) -> None:
        pass
