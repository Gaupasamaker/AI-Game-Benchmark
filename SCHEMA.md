# Game Benchmark Schema

Este documento define el formato JSON estándar generado por `game_benchmark`.

## Estructura Raíz
El archivo JSON contiene un objeto con las siguientes claves:

| Campo | Tipo | Descripción |
|---|---|---|
| `matches` | lista | Lista de objetos `MatchResult` (ver abajo). |
| `leaderboard` | dict | Clasificación ELO final (lista de tuplas `[nombre, rating_dict]`). |
| `total_matches` | int | Número total de partidas jugadas. |
| `side_swap` | bool | Indica si se usó el modo "ida y vuelta" (side swap). |

## Objeto MatchResult
Cada elemento en `matches` representa una partida individual.

### Campos Obligatorios
| Campo | Tipo | Descripción |
|---|---|---|
| `game` | string | Identificador del juego (ej: `carball`, `micorts`, `tacticfps`). |
| `seed` | int | Seed aleatoria utilizada para reproducibilidad. |
| `agent_a` | string | Nombre del agente "principal" (en torneos side-swap, varía). |
| `agent_b` | string | Nombre del oponente. |
| `sides` | dict | Mapeo de roles a agentes: `{"player_1": "AgentName", "player_2": "AgentName"}`. |
| `winner` | string/null | Ganador normalizado: `"player_1"`, `"player_2"`, o `null` (empate). |
| `ticks` | int | Duración de la partida en ticks. |
| `final_scores` | dict | Puntuación final: `{"player_1": int, "player_2": int}`. |
| `events` | lista | Lista de eventos ocurridos durante la partida. |
| `goal_events` | lista | Lista específica para goles (CarBall). Vacía en otros juegos. |
| `anticheat` | dict | Reporte de validación de acciones/tiempos. |

### Campos Específicos por Juego

#### 🚗 CarBall
*   **Scores**: Goles marcados.
*   **Events**: `[]` (Generalmente vacío, usa `goal_events`).
*   **Goal Events**: `[{"tick": 123, "scorer": "player_1"}]`.
*   **Sides**: `player_1` (Blue/Left), `player_2` (Orange/Right).

#### ⚔️ MicroRTS
*   **Scores**: Suma de HP de unidades vivas + bono control mapa (excluye recursos).
*   **Events**:
    *   `unit_killed`: `{"tick": t, "killer": "player_X", "victim_type": "IncludeType"}`
    *   `building_destroyed`: `{"tick": t, ...}`
    *   `zone_captured`: `{"tick": t, "zone": "mid", "capturer": "player_X"}`

#### 🔫 TacticFPS
*   **Scores**: Kills por equipo (`player_1`=T, `player_2`=CT).
*   **Events**:
    *   `kill`: `{"tick": t, "killer": "t1", "victim": "ct2", "killer_team": "T", ...}`
    *   `bomb_plant`: `{"tick": t, "planter": "t1"}`
    *   `bomb_defuse`: `{"tick": t, "defuser": "ct1"}`
    *   `bomb_explode`: `{"tick": t}`

## Ejemplo de Match JSON
```json
{
  "game": "tacticfps",
  "seed": 2746317213,
  "player_a": "econ",
  "player_b": "baseline",
  "sides": {
    "player_1": "econ",
    "player_2": "baseline"
  },
  "winner": "player_1",
  "ticks": 120,
  "final_scores": {
    "player_1": 1,
    "player_2": 0
  },
  "events": [
    {
      "tick": 45,
      "type": "kill",
      "killer_team": "T",
      "victim_team": "CT"
    }
  ],
  "anticheat": {
    "disqualified": [],
    "timeouts": {}
  }
}
```
