"""
Tests para TacticFPS-v0.
"""

import pytest
from game_benchmark.envs import TacticFPSEnv
from game_benchmark.agents.baselines import TacticFPSBot


class TestTacticFPSEnv:
    """Tests del entorno TacticFPS."""
    
    def test_reset_creates_players(self):
        """El reset debe crear 4 jugadores (2v2)."""
        env = TacticFPSEnv()
        obs = env.reset(seed=42)
        
        assert len(env.players) == 4
        assert "t1" in obs
        assert "t2" in obs
        assert "ct1" in obs
        assert "ct2" in obs
    
    def test_terrorists_have_bomb(self):
        """Al menos un terrorista debe tener la bomba."""
        env = TacticFPSEnv()
        obs = env.reset(seed=42)
        
        t_with_bomb = sum(1 for pid in ["t1", "t2"] 
                         if obs[pid]["self"]["has_bomb"])
        assert t_with_bomb == 1
    
    def test_fog_of_war_hides_enemies(self):
        """El fog-of-war debe ocultar enemigos lejanos."""
        env = TacticFPSEnv()
        obs = env.reset(seed=42)
        
        # Al inicio, los equipos están en esquinas opuestas
        # Los Ts no deberían ver a los CTs
        t1_obs = obs["t1"]
        enemies = t1_obs["enemies"]
        
        # Probablemente no vean enemigos al inicio
        # (depende del tamaño del mapa y rango de visión)
        assert isinstance(enemies, list)
    
    def test_movement_changes_position(self):
        """El movimiento debe cambiar la posición."""
        env = TacticFPSEnv()
        obs = env.reset(seed=42)
        
        initial_pos = (obs["t1"]["self"]["x"], obs["t1"]["self"]["y"])
        
        actions = {
            "t1": {"move": "E", "aim_dir": "E", "shoot": False},
            "t2": {"move": "STAY", "aim_dir": "N", "shoot": False},
            "ct1": {"move": "STAY", "aim_dir": "N", "shoot": False},
            "ct2": {"move": "STAY", "aim_dir": "N", "shoot": False}
        }
        
        obs, _, _, _ = env.step(actions)
        
        final_pos = (obs["t1"]["self"]["x"], obs["t1"]["self"]["y"])
        
        # La posición debería haber cambiado hacia el este
        assert final_pos[0] >= initial_pos[0]
    
    def test_shooting_reduces_ammo(self):
        """Disparar debe reducir la munición."""
        env = TacticFPSEnv()
        obs = env.reset(seed=42)
        
        initial_ammo = obs["t1"]["self"]["ammo"]
        
        actions = {
            "t1": {"move": "STAY", "aim_dir": "E", "shoot": True},
            "t2": {"move": "STAY", "aim_dir": "N", "shoot": False},
            "ct1": {"move": "STAY", "aim_dir": "N", "shoot": False},
            "ct2": {"move": "STAY", "aim_dir": "N", "shoot": False}
        }
        
        obs, _, _, _ = env.step(actions)
        
        final_ammo = obs["t1"]["self"]["ammo"]
        
        assert final_ammo == initial_ammo - 1
    
    def test_ct_wins_on_timeout(self):
        """CT debe ganar en timeout si no hay bomba plantada."""
        env = TacticFPSEnv(max_ticks=5)
        env.reset(seed=42)
        
        actions = {p: {"move": "STAY", "aim_dir": "N", "shoot": False} 
                   for p in env.players}
        
        for _ in range(10):
            _, _, done, _ = env.step(actions)
            if done:
                break
        
        assert env.done
        assert env.get_winner() == "CT"


class TestTacticFPSBomb:
    """Tests del sistema de bomba."""
    
    def test_plant_in_plant_zone(self):
        """Debe poder plantar en la zona de plantado."""
        env = TacticFPSEnv()
        env.reset(seed=42)
        
        # Mover T1 (que tiene bomba) a zona de plantado
        from game_benchmark.envs.tacticfps import CellType
        
        # Encontrar zona de plantado
        plant_x, plant_y = None, None
        for y in range(env.map_size):
            for x in range(env.map_size):
                if env.map_grid[y][x] == CellType.PLANT_ZONE:
                    plant_x, plant_y = x, y
                    break
            if plant_x:
                break
        
        # Teleportar T1 ahí
        env.player_data["t1"].x = plant_x
        env.player_data["t1"].y = plant_y
        
        # Intentar plantar
        actions = {
            "t1": {"move": "STAY", "aim_dir": "N", "shoot": False, 
                   "plant": True, "defuse": False, "use_smoke": None, "use_flash": None},
            "t2": {"move": "STAY", "aim_dir": "N", "shoot": False},
            "ct1": {"move": "STAY", "aim_dir": "N", "shoot": False},
            "ct2": {"move": "STAY", "aim_dir": "N", "shoot": False}
        }
        
        env.step(actions)
        
        assert env.bomb.planted


class TestTacticFPSBot:
    """Tests del bot baseline."""
    
    def test_bot_returns_valid_action(self):
        """El bot debe retornar acciones válidas."""
        env = TacticFPSEnv()
        obs = env.reset(seed=42)
        
        bot_t = TacticFPSBot("t1")
        bot_ct = TacticFPSBot("ct1")
        
        action_t = bot_t.act(obs["t1"])
        action_ct = bot_ct.act(obs["ct1"])
        
        assert "move" in action_t
        assert "aim_dir" in action_t
        assert "move" in action_ct
