"""
Tests para MicroRTS-v0.
"""

import pytest
from game_benchmark.envs import MicroRTSEnv
from game_benchmark.agents.baselines import MicroRTSBot


class TestMicroRTSEnv:
    """Tests del entorno MicroRTS."""
    
    def test_reset_creates_initial_units(self):
        """El reset debe crear unidades iniciales."""
        env = MicroRTSEnv()
        obs = env.reset(seed=42)
        
        p1_obs = obs["player_1"]
        units = p1_obs["units"]
        
        # Debe tener base y workers
        unit_types = [u["type"] for u in units if u["owner"] == "player_1"]
        assert "base" in unit_types
        assert "worker" in unit_types
    
    def test_resources_increase_over_time(self):
        """Los recursos deben incrementar con el tiempo."""
        env = MicroRTSEnv()
        obs = env.reset(seed=42)
        
        initial_resources = obs["player_1"]["resources"]
        
        actions = {p: {"type": "noop"} for p in env.players}
        
        for _ in range(10):
            obs, _, _, _ = env.step(actions)
        
        final_resources = obs["player_1"]["resources"]
        
        assert final_resources > initial_resources
    
    def test_train_worker_costs_resources(self):
        """Entrenar worker debe costar recursos."""
        env = MicroRTSEnv()
        obs = env.reset(seed=42)
        
        initial_resources = obs["player_1"]["resources"]
        
        actions = {
            "player_1": {"type": "train_worker"},
            "player_2": {"type": "noop"}
        }
        
        obs, _, _, _ = env.step(actions)
        
        # Recursos deben haber disminuido por el coste (50)
        # pero también aumentado por producción
        assert obs["player_1"]["resources"] < initial_resources + 50
    
    def test_game_ends_when_base_destroyed(self):
        """El juego debe terminar cuando se destruye una base."""
        env = MicroRTSEnv()
        env.reset(seed=42)
        
        # Forzar destrucción de base
        for unit_id, unit in list(env.units.items()):
            if unit.owner == "player_2" and unit.unit_type.value == "base":
                del env.units[unit_id]
                break
        
        # Trigger check
        env._check_victory()
        
        assert env.done
        assert env.get_winner() == "player_1"
    
    def test_baseline_bot_produces_units(self):
        """El bot baseline debe producir unidades."""
        env = MicroRTSEnv()
        obs = env.reset(seed=42)
        
        bot = MicroRTSBot("player_1")
        
        # Simular varias iteraciones
        for _ in range(50):
            action = bot.act(obs["player_1"])
            actions = {
                "player_1": action,
                "player_2": {"type": "noop"}
            }
            obs, _, done, _ = env.step(actions)
            if done:
                break
        
        # Debe haber más unidades que al inicio
        p1_units = [u for u in env.units.values() if u.owner == "player_1"]
        assert len(p1_units) >= 3


class TestMicroRTSZones:
    """Tests del sistema de zonas."""
    
    def test_mid_zone_starts_neutral(self):
        """La zona mid debe empezar neutral."""
        env = MicroRTSEnv()
        obs = env.reset(seed=42)
        
        zones = obs["player_1"]["zones"]
        assert zones["mid"]["controller"] is None
    
    def test_zone_control_changes_with_units(self):
        """El control de zona debe cambiar según unidades presentes."""
        env = MicroRTSEnv()
        env.reset(seed=42)
        
        # Mover unidad propia a mid
        mid = env.zones["mid"]
        mid_x = (mid.x_min + mid.x_max) // 2
        mid_y = (mid.y_min + mid.y_max) // 2
        
        # Crear soldado en mid para player_1
        from game_benchmark.envs.micorts import Unit, UnitType
        env._spawn_unit(UnitType.SOLDIER, "player_1", mid_x, mid_y)
        
        # Actualizar zona varias veces
        for _ in range(20):
            env._update_zone_control()
        
        assert env.zones["mid"].controller == "player_1"
