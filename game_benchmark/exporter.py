"""
Módulo para exportar resultados de torneos a CSV.
"""
import csv
import json
import os
from typing import List, Dict

def export_to_csv(json_data: Dict, output_dir: str):
    """Exporta datos del torneo a múltiples archivos CSV."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    matches = json_data.get("matches", [])
    leaderboard = json_data.get("leaderboard", [])
    game_name = matches[0].get("game", "unknown") if matches else "unknown"
    
    # 1. matches.csv
    matches_file = os.path.join(output_dir, "matches.csv")
    with open(matches_file, "w", newline="") as f:
        writer = csv.writer(f)
        header = ["game", "seed", "agent_a", "agent_b", "winner", "side_swap", 
                  "player_1_agent", "player_2_agent", "player_1_score", "player_2_score", "ticks"]
        writer.writerow(header)
        
        for m in matches:
            sides = m.get("sides", {})
            scores = m.get("final_scores", {})
            p1_agent = sides.get("player_1", "unknown")
            p2_agent = sides.get("player_2", "unknown")
            p1_score = scores.get("player_1", 0)
            p2_score = scores.get("player_2", 0)
            
            writer.writerow([
                m.get("game"),
                m.get("seed"),
                m.get("agent_a"),
                m.get("agent_b"),
                m.get("winner"),
                json_data.get("side_swap", False),
                p1_agent,
                p2_agent,
                p1_score,
                p2_score,
                m.get("ticks")
            ])
            
    # 2. leaderboard.csv
    leaderboard_file = os.path.join(output_dir, "leaderboard.csv")
    with open(leaderboard_file, "w", newline="") as f:
        writer = csv.writer(f)
        header = ["rank", "agent", "elo", "wins", "losses", "draws", "games_played"]
        writer.writerow(header)
        
        # leaderboard es una lista de [name, stats_dict]
        # stats_dict: {'elo': X, 'wins': W, ...}
        for rank, (name, stats) in enumerate(leaderboard, 1):
            writer.writerow([
                rank,
                name,
                round(stats.get("elo", 1200), 1),
                stats.get("wins", 0),
                stats.get("losses", 0),
                stats.get("draws", 0),
                stats.get("games_played", 0)
            ])

    # 3. matchups.csv (Matriz de enfrentamientos)
    matchups_file = os.path.join(output_dir, "matchups.csv")
    with open(matchups_file, "w", newline="") as f:
        writer = csv.writer(f)
        header = ["agent_a", "agent_b", "wins_a", "wins_b", "draws"]
        writer.writerow(header)
        
        # Calcular matchups desde matches
        pair_stats = {}
        for m in matches:
            p1 = m.get("dict", {}).get("player_1") # No, sides
            sides = m.get("sides", {})
            winner = m.get("winner")
            
            # Normalizar para que (A, B) sea la key ordenada
            agents = sorted([sides.get("player_1"), sides.get("player_2")])
            key = f"{agents[0]}_vs_{agents[1]}"
            
            if key not in pair_stats:
                pair_stats[key] = {"a": agents[0], "b": agents[1], "wins_a": 0, "wins_b": 0, "draws": 0}
            
            if winner == "player_1":
                win_agent = sides.get("player_1")
            elif winner == "player_2":
                win_agent = sides.get("player_2")
            else:
                win_agent = None
            
            if win_agent == pair_stats[key]["a"]:
                pair_stats[key]["wins_a"] += 1
            elif win_agent == pair_stats[key]["b"]:
                pair_stats[key]["wins_b"] += 1
            else:
                pair_stats[key]["draws"] += 1
        
        for k, s in pair_stats.items():
            writer.writerow([s["a"], s["b"], s["wins_a"], s["wins_b"], s["draws"]])

    # 4. events_agg.csv (Eventos agregados)
    events_file = os.path.join(output_dir, "events_agg.csv")
    with open(events_file, "w", newline="") as f:
        writer = csv.writer(f)
        header = ["game", "agent", "event_type", "count"]
        writer.writerow(header)
        
        # Agrupar eventos
        event_counts = {} # {(agent, type): count}
        
        for m in matches:
            sides = m.get("sides", {})
            events = m.get("events", [])
            
            # Mapear equipos a agentes para events
            # TacticFPS: killer_team=T -> agent=sides[player_1]
            p1_agent = sides.get("player_1")
            p2_agent = sides.get("player_2")
            
            for e in events:
                etype = e.get("type")
                agent = "unknown"
                
                # Intentar deducir agente
                if "killer_team" in e: # TacticFPS kill
                    team = e["killer_team"]
                    agent = p1_agent if team == "T" else p2_agent
                elif "planter" in e: # TacticFPS bomb
                    # Asumimos T planta -> p1
                    agent = p1_agent
                elif "defuser" in e: # TacticFPS defuse
                    # Asumimos CT defusa -> p2
                    agent = p2_agent
                elif "killer" in e and "victim_type" in e: # MicroRTS
                    # killer es "player_1" o "player_2"
                    killer_side = e["killer"]
                    agent = p1_agent if killer_side == "player_1" else p2_agent
                elif "scorer" in e: # CarBall (via goal_events, pero si se pasa a events)
                    # scorer usually player_1/player_2
                    pass
                else:
                    # Evento sin agente claro o global
                    agent = "global"
                
                key = (agent, etype)
                event_counts[key] = event_counts.get(key, 0) + 1
            
            # CarBall Goals
            for g in m.get("goal_events", []):
                scorer_side = g.get("scorer")
                agent = p1_agent if scorer_side == "player_1" else p2_agent
                key = (agent, "goal")
                event_counts[key] = event_counts.get(key, 0) + 1
                
        for (agent, etype), count in event_counts.items():
            writer.writerow([game_name, agent, etype, count])

    print(f"CSVs exportados a: {output_dir}")
