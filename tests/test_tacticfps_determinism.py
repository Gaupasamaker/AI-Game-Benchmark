"""
Tests de determinismo y schema para TacticFPS.
"""

import pytest
from game_benchmark.envs import TacticFPSEnv
from game_benchmark.agents.base import RandomAgent
from game_benchmark.agents.baselines import TacticFPSBot
from game_benchmark.runner import GameRunner


class TestTacticFPSDeterminism:
    """Tests de determinismo para TacticFPS."""
    
    def test_same_seed_produces_same_result(self):
        """Mismo seed debe producir exactamente el mismo resultado."""
        env1 = TacticFPSEnv(max_ticks=50)
        env2 = TacticFPSEnv(max_ticks=50)
        
        seed = 42
        
        # Run 1
        obs1 = env1.reset(seed)
        bots1 = {pid: TacticFPSBot(pid, seed=42) for pid in env1.players}
        for _ in range(50):
            actions = {pid: bot.act(obs1[pid]) for pid, bot in bots1.items()}
            obs1, _, done, info1 = env1.step(actions)
            if done:
                break
        
        final_scores1 = env1.scores
        winner1 = env1.get_winner()
        
        # Run 2
        obs2 = env2.reset(seed)
        bots2 = {pid: TacticFPSBot(pid, seed=42) for pid in env2.players}
        for _ in range(50):
            actions = {pid: bot.act(obs2[pid]) for pid, bot in bots2.items()}
            obs2, _, done, info2 = env2.step(actions)
            if done:
                break
        
        final_scores2 = env2.scores
        winner2 = env2.get_winner()
        
        assert final_scores1 == final_scores2
        assert winner1 == winner2


class TestTacticFPSSchema:
    """Tests del schema de TacticFPS para compatibilidad."""
    
    def test_scores_property_exists(self):
        """El env debe tener propiedad scores."""
        env = TacticFPSEnv()
        env.reset(seed=42)
        
        assert hasattr(env, "scores")
        scores = env.scores
        assert isinstance(scores, dict)
        assert "player_1" in scores
        assert "player_2" in scores
    
    def test_scores_are_non_negative_integers(self):
        """Los scores deben ser enteros no negativos."""
        env = TacticFPSEnv()
        env.reset(seed=42)
        
        scores = env.scores
        
        for player_id, score in scores.items():
            assert isinstance(score, int)
            assert score >= 0
    
    def test_events_in_step_info(self):
        """step() debe devolver eventos en info."""
        env = TacticFPSEnv(max_ticks=50)
        env.reset(seed=42)
        
        bots = {pid: TacticFPSBot(pid, seed=42) for pid in env.players}
        
        for _ in range(50):
            obs = {pid: env._get_observation(pid) for pid in env.players}
            actions = {pid: bot.act(obs[pid]) for pid, bot in bots.items()}
            _, _, done, info = env.step(actions)
            if done:
                break
        
        assert "scores" in info
        assert "events" in info
        assert isinstance(info["events"], list)
    
    def test_get_winner_returns_normalized(self):
        """get_winner() debe retornar player_1 o player_2."""
        env = TacticFPSEnv(max_ticks=30)
        env.reset(seed=42)
        
        bots = {pid: TacticFPSBot(pid, seed=42) for pid in env.players}
        
        for _ in range(30):
            obs = {pid: env._get_observation(pid) for pid in env.players}
            actions = {pid: bot.act(obs[pid]) for pid, bot in bots.items()}
            _, _, done, _ = env.step(actions)
            if done:
                break
        
        winner = env.get_winner()
        assert winner in ["player_1", "player_2", None]


class TestTacticFPSEvents:
    """Tests de eventos en TacticFPS."""
    
    def test_kill_events_structure(self):
        """Eventos de kill deben tener estructura correcta."""
        env = TacticFPSEnv(max_ticks=100)
        env.reset(seed=42)
        
        bots = {pid: TacticFPSBot(pid, seed=42) for pid in env.players}
        
        all_events = []
        for _ in range(100):
            obs = {pid: env._get_observation(pid) for pid in env.players}
            actions = {pid: bot.act(obs[pid]) for pid, bot in bots.items()}
            _, _, done, info = env.step(actions)
            all_events.extend(info.get("events", []))
            if done:
                break
        
        # Verificar estructura de eventos
        for event in all_events:
            assert "tick" in event
            assert "type" in event
            
            if event["type"] == "kill":
                assert "killer_team" in event
                assert "victim_team" in event
                assert event["killer_team"] in ["T", "CT"]
                assert event["victim_team"] in ["T", "CT"]
    
    def test_bomb_events_structure(self):
        """Eventos de bomba deben tener estructura correcta."""
        env = TacticFPSEnv(max_ticks=100)
        env.reset(seed=42)
        
        bots = {pid: TacticFPSBot(pid, seed=42) for pid in env.players}
        
        all_events = []
        for _ in range(100):
            obs = {pid: env._get_observation(pid) for pid in env.players}
            actions = {pid: bot.act(obs[pid]) for pid, bot in bots.items()}
            _, _, done, info = env.step(actions)
            all_events.extend(info.get("events", []))
            if done:
                break
        
        bomb_events = [e for e in all_events if e["type"] in ["bomb_plant", "bomb_defuse", "bomb_explode"]]
        
        for event in bomb_events:
            assert "tick" in event
            assert "type" in event


class TestTacticFPSTeamMapping:
    """Tests del mapeo de equipos a player_1/player_2."""
    
    def test_t_team_is_player_1(self):
        """Team T debe mapearse a player_1."""
        env = TacticFPSEnv()
        env.reset(seed=42)
        
        # Forzar un kill de T
        env._kill_counts["T"] = 1
        env._kill_counts["CT"] = 0
        
        scores = env.scores
        assert scores["player_1"] == 1
        assert scores["player_2"] == 0
    
    def test_ct_team_is_player_2(self):
        """Team CT debe mapearse a player_2."""
        env = TacticFPSEnv()
        env.reset(seed=42)
        
        # Forzar un kill de CT
        env._kill_counts["T"] = 0
        env._kill_counts["CT"] = 2
        
        scores = env.scores
        assert scores["player_1"] == 0
        assert scores["player_2"] == 2
    
    def test_winner_normalization(self):
        """get_winner() debe normalizar T→player_1, CT→player_2."""
        from game_benchmark.envs.tacticfps import Team
        
        env = TacticFPSEnv()
        env.reset(seed=42)
        
        # Test T wins
        env._winning_team = Team.TERRORIST
        assert env.get_winner() == "player_1"
        
        # Test CT wins
        env._winning_team = Team.COUNTER_TERRORIST
        assert env.get_winner() == "player_2"
        
        # Test no winner
        env._winning_team = None
        assert env.get_winner() is None
