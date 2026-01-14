"""
Game Runner - Ejecutor de partidas y torneos.
"""

from __future__ import annotations
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..envs.base import BaseEnvironment
from ..agents.base import BaseAgent
from .elo import EloSystem
from .anticheat import AntiCheat, AntiCheatConfig


@dataclass
class MatchResult:
    """Resultado de una partida."""
    game: str
    seed: int
    player_a: str
    player_b: str
    winner: str | None  # None = empate
    ticks: int
    rewards: dict[str, float]
    # Extra (para análisis): marcador final y eventos
    final_scores: dict | None = None
    goal_events: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)  # Eventos genéricos (kills, etc)
    agent_a: str | None = None
    agent_b: str | None = None
    sides: dict = field(default_factory=dict)  # {"player_1": "agent_name", "player_2": "agent_name"}
    replay: list[dict] = field(default_factory=list)
    anticheat_report: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "game": self.game,
            "seed": self.seed,
            "player_a": self.player_a,
            "player_b": self.player_b,
            "agent_a": self.agent_a,
            "agent_b": self.agent_b,
            "sides": self.sides,
            "winner": self.winner,
            "ticks": self.ticks,
            "rewards": self.rewards,
            "final_scores": self.final_scores,
            "goal_events": self.goal_events,
            "events": self.events,
            "anticheat": self.anticheat_report
        }


class GameRunner:
    """
    Ejecutor de partidas individuales y torneos.
    """
    
    def __init__(
        self, 
        anticheat_config: AntiCheatConfig | None = None,
        record_replays: bool = False
    ):
        self.anticheat = AntiCheat(anticheat_config)
        self.record_replays = record_replays
        self.elo_system = EloSystem()
    
    def run_match(
        self,
        env: BaseEnvironment,
        agents: dict[str, BaseAgent],
        seed: int
    ) -> MatchResult:
        """
        Ejecuta una partida completa.
        
        Args:
            env: Entorno del juego
            agents: Diccionario de {player_id: agent}
            seed: Semilla para reproducibilidad
            
        Returns:
            Resultado de la partida
        """
        # Reset
        self.anticheat.reset()
        for agent in agents.values():
            agent.reset()
        
        observations = env.reset(seed)
        replay = []
        total_rewards = {pid: 0.0 for pid in agents}
        goal_events = []
        all_events = []  # Eventos genéricos (kills, zone captures, etc)
        last_info = {}
        
        # Game loop
        while not env.done:
            actions = {}
            
            for player_id, agent in agents.items():
                obs = observations.get(player_id, {})
                obs["valid_actions"] = env.get_valid_actions(player_id)
                
                # Verificar descalificación
                if self.anticheat.is_disqualified(player_id):
                    actions[player_id] = obs["valid_actions"][0] if obs["valid_actions"] else {}
                    continue
                
                # Ejecutar agente con timeout
                action, success = self.anticheat.timed_call(
                    player_id,
                    agent.act,
                    obs,
                    tick=env.current_tick
                )
                
                if action is None:
                    action = obs["valid_actions"][0] if obs["valid_actions"] else {}
                
                # Validar acción
                action, valid = self.anticheat.validate_action(
                    player_id,
                    action,
                    obs["valid_actions"],
                    tick=env.current_tick
                )
                
                actions[player_id] = action
            
            # Ejecutar step
            observations, rewards, done, info = env.step(actions)
            last_info = info or {}
            # Capturar goles si el entorno lo reporta
            if isinstance(last_info, dict) and last_info.get("goal_scored"):
                goal_events.append({
                    "tick": last_info.get("tick", env.current_tick),
                    "scorer": last_info.get("goal_scored"),
                    "scores": last_info.get("scores")
                })
            
            # Capturar eventos genéricos si el entorno los reporta
            if isinstance(last_info, dict) and last_info.get("events"):
                all_events.extend(last_info.get("events", []))
            
            # Acumular rewards con penalizaciones
            for pid, reward in rewards.items():
                penalty = self.anticheat.get_penalty(pid)
                total_rewards[pid] += reward - penalty
            
            # Grabar replay si está habilitado
            if self.record_replays:
                replay.append({
                    "tick": env.current_tick,
                    "actions": actions,
                    "info": info
                })
        
        # Determinar ganador
        winner = env.get_winner()
        
        # Verificar descalificaciones
        for player_id in agents:
            if self.anticheat.is_disqualified(player_id):
                # El otro jugador gana por descalificación
                other = [p for p in agents if p != player_id][0]
                winner = other
                break
        
        # Extra: marcador final (si el entorno lo expone)
        final_scores = None
        if isinstance(last_info, dict) and "scores" in last_info:
            final_scores = last_info.get("scores")
        elif hasattr(env, "scores"):
            try:
                final_scores = getattr(env, "scores")
            except Exception:
                final_scores = None
        elif hasattr(env, "get_raw_state"):
            try:
                final_scores = env.get_raw_state().get("scores")
            except Exception:
                final_scores = None

        return MatchResult(
            game=env.name,
            seed=seed,
            player_a=list(agents.keys())[0],
            player_b=list(agents.keys())[1],
            winner=winner,
            ticks=env.current_tick,
            rewards=total_rewards,
            final_scores=final_scores,
            goal_events=goal_events,
            events=all_events,
            replay=replay if self.record_replays else [],
            anticheat_report=self.anticheat.to_dict()
        )
    
    def run_tournament(
        self,
        env_factory: callable,
        agent_factories: dict[str, callable],
        matches_per_pair: int = 10,
        seeds: list[int] | None = None,
        side_swap: bool = True
    ) -> dict:
        """
        Ejecuta un torneo round-robin con side swap.
        
        Args:
            env_factory: Función que crea el entorno
            agent_factories: {agent_name: función que crea el agente}
            matches_per_pair: Partidas por emparejamiento (total, incluyendo ida y vuelta)
            seeds: Lista de seeds (si None, se generan aleatorias)
            side_swap: Si True, cada seed se juega dos veces con lados intercambiados
            
        Returns:
            Resultados del torneo con rankings
        """
        agent_names = list(agent_factories.keys())
        results = []
        
        # Calcular seeds necesarias
        # Con side_swap=True, cada seed genera 2 partidas (ida y vuelta)
        seeds_needed = matches_per_pair // 2 if side_swap else matches_per_pair
        if seeds is None:
            seeds = [random.randint(0, 2**32 - 1) for _ in range(seeds_needed)]
        
        # Round-robin
        for i, name_a in enumerate(agent_names):
            for name_b in agent_names[i + 1:]:
                for seed in seeds:
                    # === PARTIDA IDA: A como player_1, B como player_2 ===
                    env = env_factory()
                    player_ids = env.players
                    

                    # Distribuir jugadores: A gets 1st half, B gets 2nd half
                    # Soporta 2 players (1v1) y 4 players (TeamvTeam)
                    n_players = len(player_ids)
                    mid = n_players // 2
                    
                    agents = {}
                    team_a_ids = player_ids[:mid]
                    team_b_ids = player_ids[mid:]
                    
                    for pid in team_a_ids:
                        agents[pid] = agent_factories[name_a](pid)
                    for pid in team_b_ids:
                        agents[pid] = agent_factories[name_b](pid)
                    
                    result = self.run_match(env, agents, seed)
                    result.agent_a = name_a
                    result.agent_b = name_b
                    # 'player_1' key representa al Team 1 (first half)
                    result.sides = {"player_1": name_a, "player_2": name_b}
                    results.append(result)
                    
                    # Actualizar ELO
                    # Winner puede ser ID específico (MicroRTS) o abstracto "player_X" (TacticFPS)
                    p1_wins = (result.winner == "player_1") or (result.winner in team_a_ids)
                    p2_wins = (result.winner == "player_2") or (result.winner in team_b_ids)
                    
                    if p1_wins:
                        elo_result = 1.0
                        result.winner = "player_1"
                    elif p2_wins:
                        elo_result = 0.0
                        result.winner = "player_2"
                    else:
                        elo_result = 0.5
                    self.elo_system.update_ratings(name_a, name_b, elo_result)
                    
                    # === PARTIDA VUELTA: B como player_1, A como player_2 (mismo seed) ===
                    if side_swap:
                        env = env_factory()
                        player_ids = env.players
                        
                        # Distribuir jugadores INVERSO: B gets 1st half, A gets 2nd half
                        agents = {}
                        team_a_ids = player_ids[:mid]  # First half slots
                        team_b_ids = player_ids[mid:]  # Second half slots
                        
                        for pid in team_a_ids:
                            agents[pid] = agent_factories[name_b](pid)  # B takes slot 1
                        for pid in team_b_ids:
                            agents[pid] = agent_factories[name_a](pid)  # A takes slot 2
                        
                        result = self.run_match(env, agents, seed)
                        result.agent_a = name_b  # Ahora B es "agent_a" (player_1 side)
                        result.agent_b = name_a
                        # 'player_1' key siempre es el primer slot
                        result.sides = {"player_1": name_b, "player_2": name_a}
                        results.append(result)
                        
                        # Actualizar ELO (invertido: B vs A)
                        p1_wins = (result.winner == "player_1") or (result.winner in team_a_ids)
                        p2_wins = (result.winner == "player_2") or (result.winner in team_b_ids)
                        
                        if p1_wins:
                            elo_result = 1.0  # B ganó (estaba en slot 1)
                            result.winner = "player_1"
                        elif p2_wins:
                            elo_result = 0.0  # A ganó (estaba en slot 2)
                            result.winner = "player_2"
                        else:
                            elo_result = 0.5
                        self.elo_system.update_ratings(name_b, name_a, elo_result)
        
        return {
            "matches": [r.to_dict() for r in results],
            "leaderboard": self.elo_system.to_dict(),
            "total_matches": len(results),
            "side_swap": side_swap
        }
    
    def save_results(self, results: dict, path: str | Path) -> None:
        """Guarda resultados en JSON."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w") as f:
            json.dump(results, f, indent=2)
