"""
Tests de determinismo y schema para MicroRTS.
"""

import pytest
from game_benchmark.envs import MicroRTSEnv
from game_benchmark.agents.base import RandomAgent
from game_benchmark.agents.baselines import MicroRTSBot
from game_benchmark.runner import GameRunner


class TestMicroRTSDeterminism:
    """Tests de determinismo para MicroRTS."""
    
    def test_same_seed_produces_same_result(self):
        """Mismo seed debe producir exactamente el mismo resultado."""
        env1 = MicroRTSEnv()
        env2 = MicroRTSEnv()
        
        seed = 42
        
        # Run 1
        obs1 = env1.reset(seed)
        actions1 = {p: {"type": "noop"} for p in env1.players}
        for _ in range(50):
            obs1, _, done, info1 = env1.step(actions1)
            if done:
                break
        
        final_scores1 = env1.scores
        winner1 = env1.get_winner()
        
        # Run 2
        obs2 = env2.reset(seed)
        actions2 = {p: {"type": "noop"} for p in env2.players}
        for _ in range(50):
            obs2, _, done, info2 = env2.step(actions2)
            if done:
                break
        
        final_scores2 = env2.scores
        winner2 = env2.get_winner()
        
        assert final_scores1 == final_scores2
        assert winner1 == winner2
    
    def test_tournament_determinism(self):
        """Dos torneos con mismo seed deben ser identicos."""
        runner1 = GameRunner()
        runner2 = GameRunner()
        
        def env_factory():
            return MicroRTSEnv(max_ticks=100)
        
        # Usar seeds fijos para que RandomAgent sea determinista
        agent_factories = {
            "baseline": lambda pid: MicroRTSBot(pid),
            "random": lambda pid: RandomAgent(pid, seed=999)
        }
        
        seeds = [42, 123, 456]
        
        results1 = runner1.run_tournament(
            env_factory=env_factory,
            agent_factories=agent_factories,
            matches_per_pair=3,
            seeds=seeds
        )
        
        results2 = runner2.run_tournament(
            env_factory=env_factory,
            agent_factories=agent_factories,
            matches_per_pair=3,
            seeds=seeds
        )
        
        # Comparar matches (sin anticheat que puede tener timestamps)
        for m1, m2 in zip(results1["matches"], results2["matches"]):
            assert m1["seed"] == m2["seed"]
            assert m1["winner"] == m2["winner"]
            assert m1["ticks"] == m2["ticks"]
            assert m1["final_scores"] == m2["final_scores"]
            assert m1["events"] == m2["events"]


class TestMicroRTSSchema:
    """Tests del schema de MicroRTS para compatibilidad con dashboard."""
    
    def test_match_has_final_scores(self):
        """Cada match debe incluir final_scores como dict."""
        runner = GameRunner()
        env = MicroRTSEnv(max_ticks=100)
        
        agents = {
            "player_1": MicroRTSBot("player_1"),
            "player_2": RandomAgent("player_2", seed=42)
        }
        
        result = runner.run_match(env, agents, seed=42)
        
        assert result.final_scores is not None
        assert isinstance(result.final_scores, dict)
        assert "player_1" in result.final_scores
        assert "player_2" in result.final_scores
        assert isinstance(result.final_scores["player_1"], int)
        assert isinstance(result.final_scores["player_2"], int)
    
    def test_match_has_goal_events_as_list(self):
        """goal_events debe existir como lista (aunque vacia para micorts)."""
        runner = GameRunner()
        env = MicroRTSEnv(max_ticks=100)
        
        agents = {
            "player_1": MicroRTSBot("player_1"),
            "player_2": RandomAgent("player_2", seed=42)
        }
        
        result = runner.run_match(env, agents, seed=42)
        
        assert hasattr(result, "goal_events")
        assert isinstance(result.goal_events, list)
    
    def test_match_has_events(self):
        """events debe existir como lista."""
        runner = GameRunner()
        env = MicroRTSEnv(max_ticks=100)
        
        agents = {
            "player_1": MicroRTSBot("player_1"),
            "player_2": RandomAgent("player_2", seed=42)
        }
        
        result = runner.run_match(env, agents, seed=42)
        
        assert hasattr(result, "events")
        assert isinstance(result.events, list)
    
    def test_match_to_dict_has_required_fields(self):
        """to_dict() debe incluir todos los campos requeridos."""
        runner = GameRunner()
        env = MicroRTSEnv(max_ticks=100)
        
        agents = {
            "player_1": MicroRTSBot("player_1"),
            "player_2": RandomAgent("player_2", seed=42)
        }
        
        result = runner.run_match(env, agents, seed=42)
        result.agent_a = "baseline"
        result.agent_b = "random"
        
        d = result.to_dict()
        
        # Campos requeridos
        required_fields = [
            "game", "seed", "player_a", "player_b",
            "agent_a", "agent_b", "winner", "ticks",
            "rewards", "final_scores", "goal_events", "events"
        ]
        
        for field in required_fields:
            assert field in d, f"Campo '{field}' no encontrado en to_dict()"


class TestMicroRTSScores:
    """Tests del calculo de scores en MicroRTS."""
    
    def test_scores_property_exists(self):
        """El env debe tener propiedad scores."""
        env = MicroRTSEnv()
        env.reset(seed=42)
        
        assert hasattr(env, "scores")
        scores = env.scores
        assert isinstance(scores, dict)
        assert "player_1" in scores
        assert "player_2" in scores
    
    def test_scores_are_positive_integers(self):
        """Los scores deben ser enteros positivos."""
        env = MicroRTSEnv()
        env.reset(seed=42)
        
        scores = env.scores
        
        for player_id, score in scores.items():
            assert isinstance(score, int)
            assert score >= 0
    
    def test_scores_change_during_game(self):
        """Los scores deben cambiar durante la partida."""
        env = MicroRTSEnv()
        env.reset(seed=42)
        
        initial_scores = env.scores.copy()
        
        actions = {
            "player_1": {"type": "train_worker"},
            "player_2": {"type": "noop"}
        }
        
        for _ in range(50):
            _, _, done, _ = env.step(actions)
            if done:
                break
        
        final_scores = env.scores
        
        # Al menos un score debe haber cambiado
        assert initial_scores != final_scores


class TestMicroRTSEvents:
    """Tests de eventos en MicroRTS."""
    
    def test_events_returned_in_info(self):
        """step() debe devolver eventos en info."""
        env = MicroRTSEnv()
        env.reset(seed=42)
        
        # Jugar hasta que haya combate
        actions = {
            "player_1": {"type": "attack_zone", "zone_id": "base_b"},
            "player_2": {"type": "noop"}
        }
        
        all_events = []
        for _ in range(100):
            _, _, done, info = env.step(actions)
            if "events" in info:
                all_events.extend(info["events"])
            if done:
                break
        
        # Verificar estructura de info
        assert "scores" in info
        assert "events" in info
        assert isinstance(info["events"], list)
    
    def test_kill_events_have_correct_structure(self):
        """Eventos de kill deben tener la estructura correcta."""
        env = MicroRTSEnv()
        env.reset(seed=42)
        
        # Forzar combate: mover soldados hacia el enemigo
        from game_benchmark.envs.micorts import UnitType
        
        # Crear soldados cerca del enemigo
        env._spawn_unit(UnitType.SOLDIER, "player_1", 20, 20)
        
        actions = {
            "player_1": {"type": "attack_zone", "zone_id": "base_b"},
            "player_2": {"type": "noop"}
        }
        
        kill_events = []
        for _ in range(200):
            _, _, done, info = env.step(actions)
            for event in info.get("events", []):
                if event.get("type") in ["unit_killed", "building_destroyed"]:
                    kill_events.append(event)
            if done:
                break
        
        # Si hay eventos, verificar estructura
        for event in kill_events:
            assert "tick" in event
            assert "type" in event
            assert "killer" in event
            assert "victim_type" in event


class TestMicroRTSUnitCap:
    """Tests del cap de unidades."""
    
    def test_units_respect_cap(self):
        """Con un cap bajo, units no debe exceder el limite."""
        env = MicroRTSEnv(max_ticks=200, max_units_per_player=10)
        env.reset(seed=42)
        
        # Intentar producir muchos workers
        for _ in range(100):
            actions = {
                "player_1": {"type": "train_worker"},
                "player_2": {"type": "train_worker"}
            }
            _, _, done, _ = env.step(actions)
            
            # Verificar cap en cada tick
            p1_units = sum(1 for u in env.units.values() if u.owner == "player_1")
            p2_units = sum(1 for u in env.units.values() if u.owner == "player_2")
            assert p1_units <= 10, f"player_1 tiene {p1_units} unidades (cap=10)"
            assert p2_units <= 10, f"player_2 tiene {p2_units} unidades (cap=10)"
            
            if done:
                break
    
    def test_default_cap_is_30(self):
        """El cap por defecto es 30."""
        env = MicroRTSEnv()
        assert env.max_units_per_player == 30
    
    def test_custom_cap(self):
        """Se puede configurar un cap custom."""
        env = MicroRTSEnv(max_units_per_player=15)
        assert env.max_units_per_player == 15
    
    def test_cap_blocks_production(self):
        """Produccion debe fallar cuando se alcanza el cap."""
        env = MicroRTSEnv(max_units_per_player=5)
        env.reset(seed=42)
        
        initial_units = sum(1 for u in env.units.values() if u.owner == "player_1")
        
        # Producir hasta el cap
        for _ in range(50):
            actions = {
                "player_1": {"type": "train_worker"},
                "player_2": {"type": "noop"}
            }
            env.step(actions)
        
        final_units = sum(1 for u in env.units.values() if u.owner == "player_1")
        
        # No debe exceder 5
        assert final_units <= 5
    
    def test_random_vs_baseline_with_cap(self):
        """Con cap, random vs baseline produce scores razonables."""
        from game_benchmark.runner import GameRunner
        from game_benchmark.agents.baselines import MicroRTSEconBot
        
        runner = GameRunner()
        env = MicroRTSEnv(max_ticks=200, max_units_per_player=20)
        
        agents = {
            "player_1": MicroRTSEconBot("player_1", unit_cap=20),
            "player_2": RandomAgent("player_2", seed=42)
        }
        
        result = runner.run_match(env, agents, seed=42)
        
        # Verificar que los scores son razonables (no 10k+)
        scores = result.final_scores
        assert scores["player_1"] < 5000, f"Score demasiado alto: {scores['player_1']}"
        assert scores["player_2"] < 5000, f"Score demasiado alto: {scores['player_2']}"

