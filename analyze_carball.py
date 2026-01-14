import json
from collections import defaultdict
from statistics import mean

PATH = "carball_4agents_v2.json"

def safe_div(a, b):
    return a / b if b else 0.0

with open(PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

matches = data["matches"]
ratings = data.get("leaderboard", {}).get("ratings", {})

agents = sorted(ratings.keys())

print("\n=== LEADERBOARD (ELO) ===")
for a in sorted(agents, key=lambda x: ratings[x]["elo"], reverse=True):
    r = ratings[a]
    print(f"- {a:10s} ELO {r['elo']:.1f} | W:{r['wins']} L:{r['losses']} D:{r['draws']} | win_rate:{r['win_rate']:.3f}")

# Matchup matrix: stats[A][B] = {W,L,D} desde perspectiva de A
stats = {a: {b: {"W":0, "L":0, "D":0, "N":0} for b in agents if b != a} for a in agents}

goal_diffs = defaultdict(list)   # por agente: dif goles a favor - en contra en cada match
first_goal_ticks = defaultdict(list)  # por match-up key "A_vs_B"
stomps = defaultdict(int)
games_count = defaultdict(int)

def match_agents(m):
    return m.get("agent_a"), m.get("agent_b")

def score_diff(m):
    fs = m.get("final_scores") or {}
    # player_1 corresponde a agent_a; player_2 a agent_b (según cómo construyes agents en runner)
    a = fs.get("player_1", 0)
    b = fs.get("player_2", 0)
    return a - b, a, b

for m in matches:
    a, b = match_agents(m)
    if not a or not b:
        continue

    # Resultado desde perspectiva de agent_a
    winner = m.get("winner")  # "player_1" / "player_2" / None
    if a in stats and b in stats[a]:
        stats[a][b]["N"] += 1
        if winner == "player_1":
            stats[a][b]["W"] += 1
        elif winner == "player_2":
            stats[a][b]["L"] += 1
        else:
            stats[a][b]["D"] += 1

    # score stats por agente
    d, sa, sb = score_diff(m)
    goal_diffs[a].append(d)
    goal_diffs[b].append(-d)

    games_count[a] += 1
    games_count[b] += 1

    # stomp: diferencia absoluta >=3
    if abs(d) >= 3:
        stomps[a] += 1
        stomps[b] += 1

    # primer gol
    ge = m.get("goal_events") or []
    if ge:
        tick0 = ge[0].get("tick")
        if isinstance(tick0, int):
            key = f"{a}_vs_{b}"
            first_goal_ticks[key].append(tick0)

print("\n=== MATCHUP MATRIX (W/L/D desde filas -> columnas) ===")
header = " " * 12 + " ".join([f"{b:>12s}" for b in agents])
print(header)
for a in agents:
    row = [f"{a:>12s}"]
    for b in agents:
        if a == b:
            row.append(f"{'-':>12s}")
        else:
            s = stats[a][b]
            row.append(f"{s['W']}-{s['L']}-{s['D']:d}".rjust(12))
    print("".join(row))

print("\n=== GOALS / STOMPS (por agente) ===")
for a in agents:
    diffs = goal_diffs[a]
    avg_diff = mean(diffs) if diffs else 0.0
    stomp_rate = safe_div(stomps[a], games_count[a])
    print(f"- {a:10s} avg_goal_diff: {avg_diff:+.2f} | stomp_rate(|diff|>=3): {stomp_rate:.2%} | games:{games_count[a]}")

print("\n=== FIRST GOAL TICK (por matchup A_vs_B) ===")
for k in sorted(first_goal_ticks.keys()):
    ticks = first_goal_ticks[k]
    print(f"- {k:24s} n={len(ticks):3d} | avg_tick={mean(ticks):.1f} | min={min(ticks)} | max={max(ticks)}")

print("\nDone.")
