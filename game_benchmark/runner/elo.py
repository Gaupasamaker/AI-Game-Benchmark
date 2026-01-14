"""
Sistema de ranking ELO.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class PlayerRating:
    """Rating de un jugador/agente."""
    elo: float = 1500.0
    games_played: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    
    @property
    def win_rate(self) -> float:
        if self.games_played == 0:
            return 0.0
        return self.wins / self.games_played


class EloSystem:
    """
    Sistema de ranking ELO para torneos.
    
    K-factor configurable para ajustar volatilidad.
    """
    
    def __init__(self, k_factor: float = 32.0, initial_elo: float = 1500.0):
        self.k_factor = k_factor
        self.initial_elo = initial_elo
        self.ratings: Dict[str, PlayerRating] = {}
    
    def get_rating(self, player_id: str) -> PlayerRating:
        """Obtiene o crea rating para un jugador."""
        if player_id not in self.ratings:
            self.ratings[player_id] = PlayerRating(elo=self.initial_elo)
        return self.ratings[player_id]
    
    def expected_score(self, rating_a: float, rating_b: float) -> float:
        """Calcula score esperado de A vs B."""
        return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400))
    
    def update_ratings(self, player_a: str, player_b: str, result: float) -> tuple[float, float]:
        """
        Actualiza ratings después de una partida.
        
        Args:
            player_a: ID del primer jugador
            player_b: ID del segundo jugador
            result: 1.0 si A gana, 0.0 si B gana, 0.5 si empate
            
        Returns:
            Nuevos ratings de A y B
        """
        rating_a = self.get_rating(player_a)
        rating_b = self.get_rating(player_b)
        
        expected_a = self.expected_score(rating_a.elo, rating_b.elo)
        expected_b = 1 - expected_a
        
        # Actualizar ELO
        new_elo_a = rating_a.elo + self.k_factor * (result - expected_a)
        new_elo_b = rating_b.elo + self.k_factor * ((1 - result) - expected_b)
        
        rating_a.elo = new_elo_a
        rating_b.elo = new_elo_b
        
        # Actualizar estadísticas
        rating_a.games_played += 1
        rating_b.games_played += 1
        
        if result == 1.0:
            rating_a.wins += 1
            rating_b.losses += 1
        elif result == 0.0:
            rating_a.losses += 1
            rating_b.wins += 1
        else:
            rating_a.draws += 1
            rating_b.draws += 1
        
        return new_elo_a, new_elo_b
    
    def get_leaderboard(self) -> list[tuple[str, PlayerRating]]:
        """Retorna ranking ordenado por ELO descendente."""
        return sorted(
            self.ratings.items(),
            key=lambda x: x[1].elo,
            reverse=True
        )
    
    def to_dict(self) -> dict:
        """Serializa el sistema para JSON."""
        return {
            "k_factor": self.k_factor,
            "initial_elo": self.initial_elo,
            "ratings": {
                player_id: {
                    "elo": r.elo,
                    "games_played": r.games_played,
                    "wins": r.wins,
                    "losses": r.losses,
                    "draws": r.draws,
                    "win_rate": r.win_rate
                }
                for player_id, r in self.ratings.items()
            }
        }
