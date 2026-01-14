"""
Tests para CarBall-v0.
"""

import pytest
from game_benchmark.envs import CarBallEnv
from game_benchmark.agents import RandomAgent
from game_benchmark.agents.baselines import CarBallBot


class TestCarBallEnv:
    """Tests del entorno CarBall."""
    
    def test_reset_returns_observations(self):
        """El reset debe retornar observaciones para ambos jugadores."""
        env = CarBallEnv()
        obs = env.reset(seed=42)
        
        assert "player_1" in obs
        assert "player_2" in obs
        assert "my_car" in obs["player_1"]
        assert "ball" in obs["player_1"]
    
    def test_deterministic_with_same_seed(self):
        """El mismo seed debe producir resultados idénticos."""
        env1 = CarBallEnv()
        env2 = CarBallEnv()
        
        obs1 = env1.reset(seed=123)
        obs2 = env2.reset(seed=123)
        
        assert obs1["player_1"]["ball"]["pos"] == obs2["player_1"]["ball"]["pos"]
    
    def test_step_advances_tick(self):
        """Step debe avanzar el tick."""
        env = CarBallEnv()
        env.reset(seed=42)
        
        actions = {
            "player_1": {"throttle": 1, "steer": 0, "boost": False, "dash": False},
            "player_2": {"throttle": 1, "steer": 0, "boost": False, "dash": False}
        }
        
        _, _, _, info = env.step(actions)
        
        assert env.current_tick == 1
    
    def test_game_ends_after_max_ticks(self):
        """El juego debe terminar después de max_ticks."""
        env = CarBallEnv(max_ticks=10)
        env.reset(seed=42)
        
        actions = {p: {"throttle": 0, "steer": 0, "boost": False, "dash": False} 
                   for p in env.players}
        
        for _ in range(15):
            _, _, done, _ = env.step(actions)
            if done:
                break
        
        assert env.done
        assert env.current_tick == 10
    
    def test_baseline_bot_returns_valid_action(self):
        """El bot baseline debe retornar acciones válidas."""
        env = CarBallEnv()
        obs = env.reset(seed=42)
        
        bot = CarBallBot("player_1")
        action = bot.act(obs["player_1"])
        
        assert "throttle" in action
        assert "steer" in action
        assert action["throttle"] in [-1, 0, 1]


class TestCarBallPhysics:
    """Tests de la física del juego."""
    
    def test_car_moves_with_throttle(self):
        """El coche debe moverse al acelerar."""
        env = CarBallEnv()
        obs = env.reset(seed=42)
        
        initial_x = obs["player_1"]["my_car"]["pos"]["x"]
        
        actions = {
            "player_1": {"throttle": 1, "steer": 0, "boost": False, "dash": False},
            "player_2": {"throttle": 0, "steer": 0, "boost": False, "dash": False}
        }
        
        for _ in range(10):
            obs, _, _, _ = env.step(actions)
        
        final_x = obs["player_1"]["my_car"]["pos"]["x"]
        
        assert final_x > initial_x
    
    def test_boost_increases_speed(self):
        """El boost debe aumentar la velocidad."""
        env = CarBallEnv()
        obs = env.reset(seed=42)
        
        # Sin boost
        actions_no_boost = {
            "player_1": {"throttle": 1, "steer": 0, "boost": False, "dash": False},
            "player_2": {"throttle": 0, "steer": 0, "boost": False, "dash": False}
        }
        
        for _ in range(5):
            obs, _, _, _ = env.step(actions_no_boost)
        
        vel_no_boost = obs["player_1"]["my_car"]["vel"]["x"]
        
        # Reset y probar con boost
        obs = env.reset(seed=42)
        actions_boost = {
            "player_1": {"throttle": 1, "steer": 0, "boost": True, "dash": False},
            "player_2": {"throttle": 0, "steer": 0, "boost": False, "dash": False}
        }
        
        for _ in range(5):
            obs, _, _, _ = env.step(actions_boost)
        
        vel_boost = obs["player_1"]["my_car"]["vel"]["x"]
        
        assert vel_boost > vel_no_boost
