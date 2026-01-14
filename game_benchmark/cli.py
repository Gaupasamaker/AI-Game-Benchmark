"""
CLI - Interfaz de línea de comandos para el benchmark.
"""

import argparse
import json
import random
import sys
from pathlib import Path

from typing import Optional
from .envs import CarBallEnv, MicroRTSEnv, TacticFPSEnv
from .agents import RandomAgent
from .agents.baselines import CarBallBot, GoalieBot, StrikerBot, MicroRTSBot, MicroRTSEconBot, TacticFPSBot
from .runner.runner import GameRunner
from .runner.anticheat import AntiCheatConfig


def get_env(game: str):
    """Retorna el entorno para un juego."""
    envs = {
        "carball": CarBallEnv,
        "micorts": MicroRTSEnv,
        "tacticfps": TacticFPSEnv
    }
    if game not in envs:
        print(f"Error: Juego '{game}' no encontrado. Opciones: {list(envs.keys())}")
        sys.exit(1)
    return envs[game]


def get_agent_factory(game: str, agent_type: str, seed: Optional[int] = None):
    """Retorna factory de agente según tipo."""
    if agent_type == "random":
        return lambda pid, _seed=seed: RandomAgent(pid, seed=_seed)

    # CarBall: bots baseline explícitos (más divertidos para torneos)
    if game == "carball":
        if agent_type in ("ballchaser", "carball_bot", "carball"):
            return CarBallBot
        if agent_type in ("goalie", "carball_goalie"):
            return GoalieBot
        if agent_type in ("striker", "carball_striker"):
            return StrikerBot
    
    # MicroRTS: baseline y econ
    if game == "micorts":
        if agent_type in ("econ", "econbot", "micorts_econ"):
            return MicroRTSEconBot
    
    baselines = {
        "carball": CarBallBot,
        "micorts": MicroRTSBot,
        "tacticfps": TacticFPSBot
    }
    
    if agent_type == "baseline":
        return baselines.get(game, lambda pid: RandomAgent(pid))
    
    print(f"Error: Tipo de agente '{agent_type}' no encontrado.")
    sys.exit(1)


def cmd_match(args):
    """Ejecuta una partida única."""
    EnvClass = get_env(args.game)
    
    runner = GameRunner(
        anticheat_config=AntiCheatConfig(timeout_ms=args.timeout),
        record_replays=args.replay
    )
    
    env = EnvClass()
    agents = {}
    
    agent_types = args.agents.split(",")
    
    if len(env.players) == 4 and len(agent_types) == 2:
        # TacticFPS logic: distribuir 2 agentes en 2 equipos
        mid = 2
        for idx, pid in enumerate(env.players):
            # idx < 2 -> Team A (agent 0), idx >= 2 -> Team B (agent 1)
            a_idx = 0 if idx < mid else 1
            atype = agent_types[a_idx]
            agents[pid] = get_agent_factory(args.game, atype, seed=args.seed + a_idx)(pid)
    else:
        # Standard assignment
        for i, player_id in enumerate(env.players):
            if i >= len(agent_types): break
            agent_type = agent_types[i]
            agents[player_id] = get_agent_factory(args.game, agent_type, seed=args.seed + i)(player_id)
    
    result = runner.run_match(env, agents, seed=args.seed)
    
    print(f"\n{'='*50}")
    print(f"RESULTADO - {args.game.upper()}")
    print(f"{'='*50}")
    print(f"Seed: {result.seed}")
    print(f"Ticks: {result.ticks}")
    print(f"Ganador: {result.winner or 'EMPATE'}")
    print(f"Rewards: {result.rewards}")
    
    if args.output:
        with open(args.output, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        print(f"\nResultados guardados en: {args.output}")


def cmd_tournament(args):
    """Ejecuta un torneo round-robin."""
    EnvClass = get_env(args.game)
    
    runner = GameRunner(
        anticheat_config=AntiCheatConfig(timeout_ms=args.timeout)
    )
    
    agent_types = args.agents.split(",")
    agent_factories = {}
    
    for idx, agent_type in enumerate(agent_types):
        agent_factories[agent_type] = get_agent_factory(args.game, agent_type, seed=args.seed + idx)
    
    # Seeds deterministas por torneo (para reproducibilidad total)
    rng = random.Random(args.seed)
    seeds = [rng.randrange(0, 2**32) for _ in range(args.matches)]

    results = runner.run_tournament(
        env_factory=EnvClass,
        agent_factories=agent_factories,
        matches_per_pair=args.matches,
        seeds=seeds,
        side_swap=args.side_swap
    )
    
    print(f"\n{'='*50}")
    print(f"TORNEO - {args.game.upper()}")
    print(f"{'='*50}")
    print(f"Total partidas: {results['total_matches']}")
    print(f"\nLEADERBOARD:")
    print("-"*30)
    
    for i, (name, rating) in enumerate(runner.elo_system.get_leaderboard()):
        print(f"{i+1}. {name}: ELO {rating.elo:.0f} | W:{rating.wins} L:{rating.losses} D:{rating.draws}")
    
    if args.output:
        runner.save_results(results, args.output)
        print(f"\nResultados guardados en: {args.output}")


def cmd_demo(args):
    """Ejecuta una demo visual de un juego."""
    print(f"Ejecutando demo de {args.game}...")
    
    EnvClass = get_env(args.game)
    env = EnvClass()
    
    # Crear agentes baseline
    # Crear agentes
    if args.game == "tacticfps" and len(env.players) == 4:
        # 4 baseline bots
        agents = {
            "t1": TacticFPSBot("t1"),
            "t2": TacticFPSBot("t2"),
            "ct1": TacticFPSBot("ct1"),
            "ct2": TacticFPSBot("ct2")
        }
    elif args.game == "carball":
        agents = {
            "player_1": CarBallBot("player_1"),
            "player_2": CarBallBot("player_2")
        }
    elif args.game == "micorts":
        agents = {
            "player_1": MicroRTSBot("player_1"),
            "player_2": MicroRTSBot("player_2")
        }
    else:
        # Fallback genérico a Random
        agents = {}
        for pid in env.players:
            agents[pid] = RandomAgent(pid)
    
    obs = env.reset(args.seed)
    
    print(f"Juego: {env.name}")
    print(f"Jugadores: {env.players}")
    print(f"Max ticks: {env.max_ticks}")
    print("-"*40)

    # ... (código existente de demo) ...


def cmd_export(args):
    """Exporta resultados JSON a CSVs."""
    import json
    from game_benchmark.exporter import export_to_csv
    
    try:
        with open(args.input, "r") as f:
            data = json.load(f)
        
        print(f"Cargado {args.input}...")
        export_to_csv(data, args.output)
    except Exception as e:
        print(f"Error exportando: {e}")
        sys.exit(1)
    
    while not env.done:
        actions = {pid: agent.act(obs[pid]) for pid, agent in agents.items() if pid in obs}
        obs, rewards, done, info = env.step(actions)
        
        if env.current_tick % 30 == 0 or done:
            print(f"Tick {env.current_tick}: {info}")
    
    print("-"*40)
    print(f"FIN - Ganador: {env.get_winner() or 'EMPATE'}")


def main():
    parser = argparse.ArgumentParser(
        prog="game_benchmark",
        description="Benchmark IA-vs-IA con mini-juegos competitivos"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponibles")
    
    # Comando: match
    match_parser = subparsers.add_parser("match", help="Ejecutar una partida")
    match_parser.add_argument("--game", "-g", required=True, 
                              choices=["carball", "micorts", "tacticfps"])
    match_parser.add_argument("--agents", "-a", default="baseline,baseline",
                              help="Agentes separados por coma (ej: baseline,random)")
    match_parser.add_argument("--seed", "-s", type=int, default=42)
    match_parser.add_argument("--timeout", "-t", type=float, default=30.0)
    match_parser.add_argument("--replay", "-r", action="store_true")
    match_parser.add_argument("--output", "-o", help="Archivo de salida JSON")
    match_parser.set_defaults(func=cmd_match)
    
    # Comando: tournament
    tourney_parser = subparsers.add_parser("tournament", help="Ejecutar torneo")
    tourney_parser.add_argument("--game", "-g", required=True,
                                choices=["carball", "micorts", "tacticfps"])
    tourney_parser.add_argument("--agents", "-a", default="baseline,random",
                                help="Agentes para el torneo")
    tourney_parser.add_argument("--matches", "-m", type=int, default=10)
    tourney_parser.add_argument("--seed", "-s", type=int, default=42)
    tourney_parser.add_argument("--timeout", "-t", type=float, default=30.0)
    tourney_parser.add_argument("--output", "-o", help="Archivo de salida JSON")
    tourney_parser.add_argument("--side-swap", dest="side_swap", action="store_true", default=True,
                                help="Cada seed juega ida y vuelta (default: activado)")
    tourney_parser.add_argument("--no-side-swap", dest="side_swap", action="store_false",
                                help="Desactivar side swap")
    tourney_parser.set_defaults(func=cmd_tournament)

    # Export
    export_parser = subparsers.add_parser("export", help="Exportar JSON a CSVs")
    export_parser.add_argument("--input", "-i", required=True, help="Archivo JSON de entrada")
    export_parser.add_argument("--output", "-o", required=True, help="Directorio de salida")
    export_parser.set_defaults(func=cmd_export)
    
    # Comando: demo
    demo_parser = subparsers.add_parser("demo", help="Ejecutar demo visual de un juego")
    demo_parser.add_argument("--game", "-g", required=True,
                             choices=["carball", "micorts", "tacticfps"])
    demo_parser.add_argument("--seed", "-s", type=int, default=42)
    demo_parser.set_defaults(func=cmd_demo)
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == "__main__":
    main()
