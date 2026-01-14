"""
Servidor web Flask para la interfaz visual del benchmark.
"""

from __future__ import annotations
import json
import os
import threading
import time
import glob
from flask import Flask, render_template, jsonify, request, abort
from pathlib import Path

# Importar componentes del benchmark
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from game_benchmark.envs import CarBallEnv, MicroRTSEnv, TacticFPSEnv
from game_benchmark.agents import RandomAgent
from game_benchmark.agents.baselines import CarBallBot, GoalieBot, StrikerBot, MicroRTSBot, TacticFPSBot
from game_benchmark.runner import GameRunner, EloSystem


# Directorio base del proyecto (para buscar JSON)
PROJECT_ROOT = Path(__file__).parent.parent.parent

app = Flask(__name__, 
            template_folder=str(Path(__file__).parent / 'templates'),
            static_folder=str(Path(__file__).parent / 'static'))

# Estado global para partidas en curso
current_match = {
    "running": False,
    "game": None,
    "frames": [],
    "result": None,
    "tick": 0
}

elo_system = EloSystem()


def get_env_class(game: str):
    """Retorna la clase de entorno para un juego."""
    return {
        "carball": CarBallEnv,
        "micorts": MicroRTSEnv,
        "tacticfps": TacticFPSEnv
    }.get(game)


def get_agent(game: str, agent_type: str, player_id: str):
    """Crea un agente según tipo."""
    if agent_type == "random":
        return RandomAgent(player_id)
    
    # CarBall tiene 3 baselines
    if game == "carball":
        carball_agents = {
            "ballchaser": CarBallBot,
            "baseline": CarBallBot,
            "goalie": GoalieBot,
            "striker": StrikerBot
        }
        agent_class = carball_agents.get(agent_type, CarBallBot)
        return agent_class(player_id)
    
    # Otros juegos
    baselines = {
        "micorts": MicroRTSBot,
        "tacticfps": TacticFPSBot
    }
    return baselines.get(game, lambda p: RandomAgent(p))(player_id)


def serialize_game_state(env, game: str) -> dict:
    """Serializa el estado del juego para enviar al frontend."""
    if game == "carball":
        return {
            "cars": {pid: car.to_dict() for pid, car in env.cars.items()},
            "ball": env.ball.to_dict(),
            "scores": env.scores,
            "tick": env.current_tick,
            "maxTicks": env.max_ticks,
            "arena": {
                "width": env.arena_width,
                "height": env.arena_height,
                "goalWidth": env.goal_width
            }
        }
    elif game == "micorts":
        return {
            "units": [u.to_dict() for u in env.units.values()],
            "zones": {zid: z.to_dict() for zid, z in env.zones.items()},
            "resources": env.resources,
            "tick": env.current_tick,
            "maxTicks": env.max_ticks,
            "mapSize": env.map_size
        }
    elif game == "tacticfps":
        return {
            "players": {pid: p.to_dict(full=True) for pid, p in env.player_data.items()},
            "smokes": [{"x": s.x, "y": s.y, "ticks": s.ticks_remaining} for s in env.smokes],
            "bomb": {
                "planted": env.bomb.planted,
                "x": env.bomb.plant_x if env.bomb.planted else None,
                "y": env.bomb.plant_y if env.bomb.planted else None,
                "exploded": env.bomb.exploded
            },
            "map": [[cell.value for cell in row] for row in env.map_grid],
            "tick": env.current_tick,
            "maxTicks": env.max_ticks,
            "mapSize": env.map_size
        }
    return {}


def run_match_thread(game: str, agent1_type: str, agent2_type: str, seed: int, speed: float):
    """Ejecuta una partida en un hilo separado."""
    global current_match
    
    EnvClass = get_env_class(game)
    if not EnvClass:
        return
    
    max_ticks = {"carball": 600, "micorts": 200, "tacticfps": 120}.get(game, 300)
    env = EnvClass(max_ticks=max_ticks)
    
    if game == "tacticfps":
        agents = {pid: get_agent(game, agent1_type if pid.startswith("t") else agent2_type, pid) 
                  for pid in env.players}
    else:
        agents = {
            env.players[0]: get_agent(game, agent1_type, env.players[0]),
            env.players[1]: get_agent(game, agent2_type, env.players[1])
        }
    
    obs = env.reset(seed)
    current_match["frames"] = []
    current_match["tick"] = 0
    
    while not env.done and current_match["running"]:
        actions = {pid: agent.act(obs[pid]) for pid, agent in agents.items() if pid in obs}
        obs, rewards, done, info = env.step(actions)
        
        frame = serialize_game_state(env, game)
        current_match["frames"].append(frame)
        current_match["tick"] = env.current_tick
        
        time.sleep(1.0 / (30 * speed))
    
    if current_match["running"]:
        winner = env.get_winner()
        current_match["result"] = {
            "winner": winner,
            "scores": env.scores if hasattr(env, 'scores') else {}
        }
        
        if winner and game != "tacticfps":
            result_val = 1.0 if winner == env.players[0] else 0.0
            elo_system.update_ratings(agent1_type, agent2_type, result_val)
    
    current_match["running"] = False


def is_safe_path(requested_path: str) -> bool:
    """Valida que la ruta sea segura (evita path traversal)."""
    # Resolver la ruta absoluta
    try:
        abs_path = Path(requested_path).resolve()
        # Verificar que está dentro del directorio del proyecto
        return str(abs_path).startswith(str(PROJECT_ROOT.resolve()))
    except Exception:
        return False


# ============ Rutas principales ============

@app.route('/')
def index():
    """Página principal - Match viewer."""
    return render_template('index.html')


@app.route('/dashboard')
def dashboard():
    """Página de dashboard para resultados de torneos."""
    return render_template('dashboard.html')


# ============ APIs existentes ============

@app.route('/api/start_match', methods=['POST'])
def start_match():
    """Inicia una nueva partida."""
    global current_match
    
    if current_match["running"]:
        return jsonify({"error": "Ya hay una partida en curso"}), 400
    
    data = request.json
    game = data.get("game", "carball")
    agent1 = data.get("agent1", "baseline")
    agent2 = data.get("agent2", "baseline")
    seed = data.get("seed", 42)
    speed = data.get("speed", 1.0)
    
    current_match = {
        "running": True,
        "game": game,
        "frames": [],
        "result": None,
        "tick": 0
    }
    
    thread = threading.Thread(
        target=run_match_thread,
        args=(game, agent1, agent2, seed, speed)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({"status": "started", "game": game})


@app.route('/api/stop_match', methods=['POST'])
def stop_match():
    """Detiene la partida actual."""
    global current_match
    current_match["running"] = False
    return jsonify({"status": "stopped"})


@app.route('/api/match_state')
def match_state():
    """Retorna el estado actual de la partida."""
    frame_idx = request.args.get('frame', -1, type=int)
    
    if not current_match["frames"]:
        return jsonify({"running": current_match["running"], "frame": None})
    
    if frame_idx < 0 or frame_idx >= len(current_match["frames"]):
        frame_idx = len(current_match["frames"]) - 1
    
    return jsonify({
        "running": current_match["running"],
        "game": current_match["game"],
        "frame": current_match["frames"][frame_idx],
        "frameCount": len(current_match["frames"]),
        "result": current_match["result"]
    })


@app.route('/api/leaderboard')
def leaderboard():
    """Retorna el leaderboard actual (sesión en vivo)."""
    lb = elo_system.get_leaderboard()
    return jsonify([
        {
            "name": name,
            "elo": round(rating.elo),
            "wins": rating.wins,
            "losses": rating.losses,
            "games": rating.games_played
        }
        for name, rating in lb
    ])


@app.route('/api/run_tournament', methods=['POST'])
def run_tournament():
    """Ejecuta un torneo rápido."""
    data = request.json
    game = data.get("game", "carball")
    matches = data.get("matches", 5)
    
    EnvClass = get_env_class(game)
    if not EnvClass:
        return jsonify({"error": "Juego no válido"}), 400
    
    runner = GameRunner()
    
    agent_factories = {
        "baseline": lambda pid: get_agent(game, "baseline", pid),
        "random": lambda pid: get_agent(game, "random", pid)
    }
    
    # TacticFPS necesita más ticks
    max_ticks = 800 if game == "tacticfps" else 100
    
    try:
        results = runner.run_tournament(
            env_factory=lambda: EnvClass(max_ticks=max_ticks),
            agent_factories=agent_factories,
            matches_per_pair=matches
        )
    
        for name, rating in runner.elo_system.ratings.items():
            elo_system.ratings[name] = rating
        
        return jsonify({
            "totalMatches": results["total_matches"],
            "leaderboard": [
                {"name": n, "elo": round(r.elo), "wins": r.wins}
                for n, r in runner.elo_system.get_leaderboard()
            ]
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "details": traceback.format_exc()}), 500


# ============ APIs para Dashboard ============

@app.route('/api/result_files')
def list_result_files():
    """Lista archivos JSON de resultados disponibles."""
    json_files = []
    
    # Buscar en el directorio del proyecto y subdirectorios comunes
    for pattern in ["*.json", "results/*.json", "datasets/*.json"]:
        for path in PROJECT_ROOT.glob(pattern):
            # Filtrar archivos que parecen ser resultados de torneos
            if path.name.startswith("."):
                continue
            try:
                # Verificar que tiene estructura de torneo
                with open(path, 'r') as f:
                    data = json.load(f)
                    matches = data.get("matches", [])
                    
                    if matches or "leaderboard" in data:
                        # Identificar juego
                        game = "unknown"
                        if matches and len(matches) > 0:
                            game = matches[0].get("game", "unknown")
                        
                        json_files.append({
                            "name": path.name,
                            "path": str(path.relative_to(PROJECT_ROOT)),
                            "size": path.stat().st_size,
                            "game": game,
                            "matches": len(matches),
                            # timestamp para ordenar por más reciente
                            "mtime": path.stat().st_mtime
                        })
            except (json.JSONDecodeError, KeyError, Exception):
                continue
    
    # Ordenar por fecha de modificación (más reciente primero)
    json_files.sort(key=lambda x: x["mtime"], reverse=True)
    return jsonify(json_files)


@app.route('/api/download')
def download_file():
    """Descarga un archivo JSON de resultados."""
    from flask import send_file
    file_path = request.args.get('file', '')
    
    if not file_path:
        return jsonify({"error": "Parámetro 'file' requerido"}), 400
    
    full_path = PROJECT_ROOT / file_path
    
    if not is_safe_path(str(full_path)):
        abort(403, "Acceso denegado")
    
    if not full_path.exists() or not full_path.suffix == '.json':
        abort(404, "Archivo no encontrado")
    
    return send_file(full_path, as_attachment=True, download_name=full_path.name)


@app.route('/api/results')
def get_results():
    """Carga un archivo JSON de resultados."""
    file_path = request.args.get('file', '')
    
    if not file_path:
        return jsonify({"error": "Parámetro 'file' requerido"}), 400
    
    # Construir ruta completa
    full_path = PROJECT_ROOT / file_path
    
    # Validar seguridad de la ruta
    if not is_safe_path(str(full_path)):
        abort(403, "Acceso denegado: ruta no permitida")
    
    if not full_path.exists():
        abort(404, f"Archivo no encontrado: {file_path}")
    
    if not full_path.suffix == '.json':
        abort(400, "Solo se permiten archivos JSON")
    
    try:
        with open(full_path, 'r') as f:
            data = json.load(f)
        
        # Procesar datos para el dashboard
        processed = process_tournament_data(data)
        return jsonify(processed)
        
    except json.JSONDecodeError as e:
        abort(400, f"Error al parsear JSON: {str(e)}")


def process_tournament_data(data: dict) -> dict:
    """Procesa datos crudos de torneo para el dashboard."""
    matches = data.get("matches", [])
    leaderboard_raw = data.get("leaderboard", {})
    
    # Extraer agentes únicos
    agents = set()
    for m in matches:
        if m.get("agent_a"):
            agents.add(m["agent_a"])
        if m.get("agent_b"):
            agents.add(m["agent_b"])
    agents = sorted(agents)
    
    # Construir leaderboard ordenado
    leaderboard = []
    if "ratings" in leaderboard_raw:
        for name, info in leaderboard_raw["ratings"].items():
            leaderboard.append({
                "name": name,
                "elo": round(info.get("elo", 1500)),
                "wins": info.get("wins", 0),
                "losses": info.get("losses", 0),
                "draws": info.get("draws", 0),
                "games": info.get("games_played", 0),
                "winRate": round(info.get("win_rate", 0) * 100, 1)
            })
        leaderboard.sort(key=lambda x: x["elo"], reverse=True)
    
    # Construir matriz de matchups (W-L-D)
    matchups = {}
    for a1 in agents:
        matchups[a1] = {}
        for a2 in agents:
            matchups[a1][a2] = {"wins": 0, "losses": 0, "draws": 0, "total": 0}
    
    # Stats por agente para winrate
    agent_stats = {a: {"wins": 0, "losses": 0, "draws": 0, "total": 0} for a in agents}
    
    # Goal diff distribution
    goal_diffs = []
    
    # Scorelines counter
    scorelines = {}
    
    # First goal timing
    first_goal_ticks = []
    
    for m in matches:
        a1 = m.get("agent_a")
        a2 = m.get("agent_b")
        winner = m.get("winner")
        
        if not a1 or not a2:
            continue
        
        # Matchups
        matchups[a1][a2]["total"] += 1
        matchups[a2][a1]["total"] += 1
        
        if winner == m.get("player_a"):
            matchups[a1][a2]["wins"] += 1
            matchups[a2][a1]["losses"] += 1
            agent_stats[a1]["wins"] += 1
            agent_stats[a2]["losses"] += 1
        elif winner == m.get("player_b"):
            matchups[a1][a2]["losses"] += 1
            matchups[a2][a1]["wins"] += 1
            agent_stats[a1]["losses"] += 1
            agent_stats[a2]["wins"] += 1
        else:
            matchups[a1][a2]["draws"] += 1
            matchups[a2][a1]["draws"] += 1
            agent_stats[a1]["draws"] += 1
            agent_stats[a2]["draws"] += 1
        
        agent_stats[a1]["total"] += 1
        agent_stats[a2]["total"] += 1
        
        # Goal diff (desde perspectiva player_a / agent_a)
        if m.get("final_scores"):
            scores = m["final_scores"]
            score_a = scores.get(m.get("player_a"), 0)
            score_b = scores.get(m.get("player_b"), 0)
            goal_diffs.append(score_a - score_b)
            
            # Scoreline
            scoreline = f"{max(score_a, score_b)}-{min(score_a, score_b)}"
            scorelines[scoreline] = scorelines.get(scoreline, 0) + 1
        
        # First goal timing
        if m.get("goal_events") and len(m["goal_events"]) > 0:
            first_goal_ticks.append(m["goal_events"][0].get("tick", 0))
    
    # Stats globales
    total_goals = 0
    goals_per_agent = {a: 0 for a in agents}
    
    for m in matches:
        if m.get("final_scores"):
            for pid, score in m["final_scores"].items():
                total_goals += score
                if pid == m.get("player_a") and m.get("agent_a"):
                    goals_per_agent[m["agent_a"]] = goals_per_agent.get(m["agent_a"], 0) + score
                elif pid == m.get("player_b") and m.get("agent_b"):
                    goals_per_agent[m["agent_b"]] = goals_per_agent.get(m["agent_b"], 0) + score
    
    # Calcular winrate por agente
    winrate_data = []
    for agent in agents:
        stats = agent_stats[agent]
        total = stats["total"]
        if total > 0:
            winrate_data.append({
                "agent": agent,
                "winPct": round(stats["wins"] / total * 100, 1),
                "drawPct": round(stats["draws"] / total * 100, 1),
                "lossPct": round(stats["losses"] / total * 100, 1),
                "wins": stats["wins"],
                "draws": stats["draws"],
                "losses": stats["losses"]
            })
    
    # Top scorelines
    top_scorelines = sorted(
        [{"score": k, "count": v} for k, v in scorelines.items()],
        key=lambda x: x["count"],
        reverse=True
    )[:10]
    
    # Goal diff histogram (binned)
    goal_diff_bins = {}
    for diff in goal_diffs:
        goal_diff_bins[diff] = goal_diff_bins.get(diff, 0) + 1
    goal_diff_histogram = sorted(
        [{"diff": k, "count": v} for k, v in goal_diff_bins.items()],
        key=lambda x: x["diff"]
    )
    
    # Game info from first match
    game_name = matches[0].get("game", "Unknown") if matches else "Unknown"
    
    # First goal stats por agente
    first_goal_by_agent = {a: [] for a in agents}
    for m in matches:
        if m.get("goal_events") and len(m["goal_events"]) > 0:
            first_goal = m["goal_events"][0]
            tick = first_goal.get("tick", 0)
            scorer = first_goal.get("scorer")
            # Determinar qué agente marcó
            if scorer == m.get("player_a") and m.get("agent_a"):
                first_goal_by_agent[m["agent_a"]].append(tick)
            elif scorer == m.get("player_b") and m.get("agent_b"):
                first_goal_by_agent[m["agent_b"]].append(tick)
    
    # Calcular avg first goal por agente
    first_goal_avg = []
    for agent in agents:
        ticks = first_goal_by_agent[agent]
        if ticks:
            first_goal_avg.append({
                "agent": agent,
                "avgTick": round(sum(ticks) / len(ticks)),
                "count": len(ticks)
            })
    first_goal_avg.sort(key=lambda x: x["avgTick"])
    
    # First goal histogram (binned por cada 200 ticks)
    first_goal_bins = {}
    for tick in first_goal_ticks:
        bin_key = (tick // 200) * 200
        first_goal_bins[bin_key] = first_goal_bins.get(bin_key, 0) + 1
    first_goal_histogram = sorted(
        [{"tick": k, "count": v} for k, v in first_goal_bins.items()],
        key=lambda x: x["tick"]
    )
    
    # Calcular avg ticks
    all_ticks = [m.get("ticks", 0) for m in matches if m.get("ticks")]
    avg_ticks = round(sum(all_ticks) / len(all_ticks)) if all_ticks else None
    
    return {
        "metadata": {
            "game": game_name,
            "totalMatches": data.get("total_matches", len(matches)),
            "agents": agents,
            "agentCount": len(agents),
            "totalGoals": total_goals,
            "avgGoalsPerMatch": round(total_goals / len(matches), 1) if matches else 0,
            "avgFirstGoalTick": round(sum(first_goal_ticks) / len(first_goal_ticks)) if first_goal_ticks else None,
            "avgTicksPerMatch": avg_ticks,
            "sideSwap": data.get("side_swap", False)
        },
        "leaderboard": leaderboard,
        "matchups": matchups,
        "goalsPerAgent": goals_per_agent,
        "winrateData": winrate_data,
        "goalDiffHistogram": goal_diff_histogram,
        "topScorelines": top_scorelines,
        "firstGoalTicks": first_goal_ticks,
        "firstGoalHistogram": first_goal_histogram,
        "firstGoalAvgByAgent": first_goal_avg,
        "anticheatStats": extract_anticheat_stats(matches),
        "eventStats": extract_event_stats(matches),
        "sideBiasStats": extract_side_bias_stats(matches),
        "matches": matches
    }


def extract_event_stats(matches: list) -> dict:
    """Extrae estadísticas de eventos genéricos (kills, zone captures, etc)."""
    event_counts = {}
    events_by_agent = {}
    total_events = 0
    
    for m in matches:
        events = m.get("events", [])
        for e in events:
            total_events += 1
            event_type = e.get("type", "unknown")
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
            
            # Contar por agente (killer o by)
            agent = e.get("killer") or e.get("by")
            if agent:
                if agent not in events_by_agent:
                    events_by_agent[agent] = {}
                events_by_agent[agent][event_type] = events_by_agent[agent].get(event_type, 0) + 1
    
    # Calcular avg kills por partida
    total_kills = event_counts.get("unit_killed", 0) + event_counts.get("building_destroyed", 0)
    avg_kills_per_match = round(total_kills / len(matches), 1) if matches else 0
    
    return {
        "totalEvents": total_events,
        "byType": event_counts,
        "byAgent": events_by_agent,
        "avgKillsPerMatch": avg_kills_per_match
    }


def extract_side_bias_stats(matches: list) -> dict:
    """Extrae estadísticas de bias por lado (player_1 vs player_2)."""
    # Winrate por agente cuando juega como player_1 vs player_2
    agent_stats = {}  # {agent: {as_p1: {wins, games}, as_p2: {wins, games}}}
    
    p1_wins = 0
    p2_wins = 0
    p1_score_total = 0
    p2_score_total = 0
    
    for m in matches:
        sides = m.get("sides", {})
        winner = m.get("winner")
        scores = m.get("final_scores", {})
        
        p1_agent = sides.get("player_1")
        p2_agent = sides.get("player_2")
        
        # Estadísticas globales
        if winner == "player_1":
            p1_wins += 1
        elif winner == "player_2":
            p2_wins += 1
        
        p1_score_total += scores.get("player_1", 0)
        p2_score_total += scores.get("player_2", 0)
        
        # Estadísticas por agente
        for pid, agent in [("player_1", p1_agent), ("player_2", p2_agent)]:
            if not agent:
                continue
            if agent not in agent_stats:
                agent_stats[agent] = {
                    "as_p1": {"wins": 0, "games": 0},
                    "as_p2": {"wins": 0, "games": 0}
                }
            
            key = "as_p1" if pid == "player_1" else "as_p2"
            agent_stats[agent][key]["games"] += 1
            if winner == pid:
                agent_stats[agent][key]["wins"] += 1
    
    total = len(matches)
    
    # Calcular winrates por agente
    agent_winrates = {}
    for agent, stats in agent_stats.items():
        p1_games = stats["as_p1"]["games"]
        p2_games = stats["as_p2"]["games"]
        agent_winrates[agent] = {
            "as_p1": round(stats["as_p1"]["wins"] / p1_games * 100, 1) if p1_games else 0,
            "as_p2": round(stats["as_p2"]["wins"] / p2_games * 100, 1) if p2_games else 0,
            "p1_games": p1_games,
            "p2_games": p2_games
        }
    
    return {
        "p1WinRate": round(p1_wins / total * 100, 1) if total else 0,
        "p2WinRate": round(p2_wins / total * 100, 1) if total else 0,
        "p1AvgScore": round(p1_score_total / total) if total else 0,
        "p2AvgScore": round(p2_score_total / total) if total else 0,
        "byAgent": agent_winrates
    }


def extract_anticheat_stats(matches: list) -> dict:
    """Extrae estadísticas de anti-cheat de las partidas."""
    violations_by_agent = {}
    violation_examples = []
    total_violations = 0
    
    for m in matches:
        anticheat = m.get("anticheat", {})
        violations = anticheat.get("violations", [])
        
        for v in violations:
            total_violations += 1
            agent = v.get("agent") or v.get("player") or "unknown"
            violations_by_agent[agent] = violations_by_agent.get(agent, 0) + 1
            
            # Guardar ejemplos (máx 10)
            if len(violation_examples) < 10:
                violation_examples.append({
                    "agent": agent,
                    "tick": v.get("tick"),
                    "reason": v.get("reason") or v.get("type", "Unknown"),
                    "matchSeed": m.get("seed")
                })
    
    return {
        "totalViolations": total_violations,
        "byAgent": violations_by_agent,
        "examples": violation_examples
    }


def main():
    """Punto de entrada."""
    print("\n" + "="*50)
    print("🎮 Game Benchmark - Interfaz Visual")
    print("="*50)
    print("\nPáginas disponibles:")
    print("  • http://127.0.0.1:5001/          - Match Viewer")
    print("  • http://127.0.0.1:5001/dashboard - Tournament Dashboard")
    print("\nPresiona Ctrl+C para detener\n")
    
    app.run(debug=False, host='0.0.0.0', port=5001, threaded=True)


if __name__ == '__main__':
    main()
