"""
Tests para el Runner y sistema ELO.
"""

import pytest
from game_benchmark.envs import CarBallEnv
from game_benchmark.agents import RandomAgent
from game_benchmark.agents.baselines import CarBallBot
from game_benchmark.runner import GameRunner, EloSystem, AntiCheat, AntiCheatConfig


class TestEloSystem:
    """Tests del sistema ELO."""
    
    def test_initial_rating(self):
        """Los jugadores nuevos deben empezar con 1500 ELO."""
        elo = EloSystem()
        rating = elo.get_rating("player_1")
        
        assert rating.elo == 1500.0
        assert rating.games_played == 0
    
    def test_winner_gains_elo(self):
        """El ganador debe ganar ELO."""
        elo = EloSystem()
        
        initial = elo.get_rating("player_1").elo
        elo.update_ratings("player_1", "player_2", result=1.0)
        final = elo.get_rating("player_1").elo
        
        assert final > initial
    
    def test_loser_loses_elo(self):
        """El perdedor debe perder ELO."""
        elo = EloSystem()
        
        initial = elo.get_rating("player_2").elo
        elo.update_ratings("player_1", "player_2", result=1.0)
        final = elo.get_rating("player_2").elo
        
        assert final < initial
    
    def test_draw_minimal_change(self):
        """Un empate debe producir cambios mínimos."""
        elo = EloSystem()
        
        initial_1 = elo.get_rating("player_1").elo
        initial_2 = elo.get_rating("player_2").elo
        
        elo.update_ratings("player_1", "player_2", result=0.5)
        
        # Cambio mínimo ya que ambos tienen mismo ELO
        assert abs(elo.get_rating("player_1").elo - initial_1) < 1
    
    def test_leaderboard_sorted(self):
        """El leaderboard debe estar ordenado por ELO."""
        elo = EloSystem()
        
        # Player 1 gana varios
        for _ in range(5):
            elo.update_ratings("player_1", "player_2", result=1.0)
        
        leaderboard = elo.get_leaderboard()
        
        assert leaderboard[0][0] == "player_1"
        assert leaderboard[0][1].elo > leaderboard[1][1].elo


class TestAntiCheat:
    """Tests del sistema anti-trampas."""
    
    def test_timeout_detection(self):
        """Debe detectar timeouts."""
        import time
        
        config = AntiCheatConfig(timeout_ms=1.0)  # 1ms muy estricto
        ac = AntiCheat(config)
        
        def slow_func():
            time.sleep(0.01)  # 10ms
            return "result"
        
        result, success = ac.timed_call("player_1", slow_func, tick=1)
        
        assert not success
        assert len(ac.get_violations("player_1")) == 1
    
    def test_action_validation(self):
        """Debe validar acciones."""
        ac = AntiCheat()
        
        valid_actions = [{"type": "move"}, {"type": "attack"}]
        invalid_action = {"type": "cheat"}
        
        action, valid = ac.validate_action("player_1", invalid_action, valid_actions, tick=1)
        
        assert not valid
        assert action == {"type": "move"}  # Retorna primera válida
    
    def test_disqualification(self):
        """Debe descalificar tras muchas violaciones."""
        config = AntiCheatConfig(max_violations=3)
        ac = AntiCheat(config)
        
        valid_actions = [{"type": "ok"}]
        
        for i in range(5):
            ac.validate_action("player_1", {"type": "bad"}, valid_actions, tick=i)
        
        assert ac.is_disqualified("player_1")


class TestGameRunner:
    """Tests del runner de partidas."""
    
    def test_run_match_returns_result(self):
        """run_match debe retornar un MatchResult."""
        runner = GameRunner()
        env = CarBallEnv(max_ticks=100)
        
        agents = {
            "player_1": RandomAgent("player_1", seed=42),
            "player_2": RandomAgent("player_2", seed=43)
        }
        
        result = runner.run_match(env, agents, seed=99)
        
        assert result.game == "CarBall-v0"
        assert result.seed == 99
        assert result.ticks > 0
        assert result.winner in ["player_1", "player_2", None]
    
    def test_tournament_generates_leaderboard(self):
        """El torneo debe generar un leaderboard."""
        runner = GameRunner()
        
        results = runner.run_tournament(
            env_factory=lambda: CarBallEnv(max_ticks=50),
            agent_factories={
                "random": lambda pid: RandomAgent(pid),
                "baseline": lambda pid: CarBallBot(pid)
            },
            matches_per_pair=2
        )
        
        assert "leaderboard" in results
        assert "matches" in results
        assert results["total_matches"] == 2
    
    def test_deterministic_with_same_seed(self):
        """Las partidas con misma seed deben ser deterministas."""
        runner = GameRunner()
        
        def run_once(seed):
            env = CarBallEnv(max_ticks=50)
            agents = {
                "player_1": CarBallBot("player_1"),
                "player_2": CarBallBot("player_2")
            }
            return runner.run_match(env, agents, seed=seed)
        
        result1 = run_once(123)
        result2 = run_once(123)
        
        assert result1.winner == result2.winner
        assert result1.ticks == result2.ticks
