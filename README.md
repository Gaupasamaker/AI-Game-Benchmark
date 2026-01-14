# Game Benchmark IA-vs-IA 🎮🤖

Suite de evaluación de agentes IA mediante 3 mini-juegos competitivos inspirados en esports.

## Juegos Disponibles

| Juego | Inspiración | Tipo | Jugadores |
|-------|-------------|------|-----------|
| **CarBall-v0** | Rocket League | Física 2D | 1v1 |
| **MicroRTS-v0** | StarCraft II | Estrategia | 1v1 |
| **TacticFPS-v0** | CS2 | Táctico | 2v2 |

## Instalación

```bash
cd "Game Benchmark"
pip install -e .
```

## Uso Rápido

### Ejecutar una partida

```bash
# CarBall con dos bots baseline
python -m game_benchmark.cli match --game carball --agents baseline,baseline --seed 42

# MicroRTS baseline vs random
python -m game_benchmark.cli match --game micorts --agents baseline,random

# TacticFPS
python -m game_benchmark.cli match --game tacticfps
```

### Ejecutar torneo

```bash
# Torneo de CarBall con 10 partidas (seed para reproducibilidad)
python -m game_benchmark.cli tournament --game carball --agents baseline,random --matches 10 --seed 42 --output carball_torneo.json

# Torneo de MicroRTS (determinista)
python -m game_benchmark.cli tournament --game micorts --agents baseline,random --matches 5 --seed 42 --output micorts_seed42.json
```

### Exportar y Analizar Resultados

```bash
# Exportar JSON a CSVs para análisis externo
python -m game_benchmark.cli export --input micorts_seed42.json --output ./analisis/

# Para visualizaciones avanzadas (Kaggle-style), usa el notebook incluido:
# notebooks/benchmark_analysis.ipynb
```

### Demo visual

```bash
python -m game_benchmark.cli demo --game carball --seed 123
```

## Crear tu propio agente

```python
from game_benchmark.agents import BaseAgent

class MiAgente(BaseAgent):
    def act(self, observation: dict) -> dict:
        # Tu lógica aquí
        # observation contiene el estado visible del juego
        # Retorna una acción válida
        
        valid_actions = observation.get("valid_actions", [])
        return valid_actions[0] if valid_actions else {}
```

## Estructura del Proyecto

```
game_benchmark/
├── envs/           # Entornos de juego
│   ├── base.py     # Clase base abstracta
│   ├── carball.py  # Rocket League 2D
│   ├── micorts.py  # RTS simplificado
│   └── tacticfps.py# Táctico CS2
├── agents/         # Agentes de IA
│   ├── base.py     # RandomAgent
│   └── baselines/  # Bots por defecto
├── runner/         # Sistema de partidas
│   ├── runner.py   # Ejecutor
│   ├── elo.py      # Sistema de ranking
│   └── anticheat.py# Validación
└── cli.py          # Interfaz de comandos
```

## API de Entornos

Todos los entornos implementan:

```python
# Reiniciar con seed determinista
obs = env.reset(seed=42)

# Ejecutar un paso
obs, rewards, done, info = env.step(actions)

# Acciones válidas
valid = env.get_valid_actions(player_id)

# Ganador
winner = env.get_winner()
```

## Interfaz Web 🌐

### Iniciar el servidor

```bash
cd "Game Benchmark"
python3 -m game_benchmark.web.app
```

Esto abre dos páginas:
- **http://127.0.0.1:5001/** - Match Viewer (visualización en tiempo real)
- **http://127.0.0.1:5001/dashboard** - Tournament Dashboard (análisis de resultados)

### Tournament Dashboard

El dashboard permite visualizar resultados de torneos guardados en JSON.

**Para usar el dashboard:**

1. Ejecuta un torneo y guarda los resultados:
   ```bash
   python -m game_benchmark.cli tournament -g carball \
       -a ballchaser,goalie,striker,random \
       -m 30 --seed 42 -o mi_torneo.json
   ```

2. Inicia el servidor web:
   ```bash
   python3 -m game_benchmark.web.app
   ```

3. Abre http://127.0.0.1:5001/dashboard y selecciona tu archivo JSON.

**Funcionalidades del dashboard:**
- 🏆 Leaderboard con ELO y W/L/D
- 📊 Win Rate por agente (gráfico apilado)
- 📈 Distribución de diferencia de scores
- ⚔️ Matriz de enfrentamientos (W-L-D)
- ⏱️ First Goal Timing (CarBall)
- ⚔️ Event Stats: kills y capturas de zona (MicroRTS)
- 🛡️ Panel Anti-Cheat
- 📋 Tabla de partidas filtrable con modal de replay

**Dónde colocar los JSON:**
Los archivos JSON deben estar en el directorio raíz del proyecto (`Game Benchmark/`).
El dashboard busca automáticamente archivos `.json` que contengan datos de torneos.

## Score en MicroRTS

El score final en MicroRTS se calcula como **material score**:
```
score = HP_unidades_vivas + (100 si controla zona mid)
```

### Unit Cap
Para evitar "worker spam" que distorsiona scores, hay un **cap de unidades por jugador**:
- Default: 30 unidades (configurable con `max_units_per_player=N`)
- Los edificios también cuentan
- Cuando se alcanza el cap, no se pueden crear más unidades

### Agentes MicroRTS
```bash
# Baseline original (conservador)
--agents baseline,random

# EconBot (optimiza economía respetando cap)  
--agents econ,random
```

## Características

- ✅ **Determinismo**: Todo reproducible por seed
- ✅ **Anti-trampas**: Timeouts + validación de acciones
- ✅ **Sistema ELO**: Ranking objetivo
- ✅ **Fog-of-war**: Información imperfecta
- ✅ **Baselines**: Bots de referencia incluidos
- ✅ **Interfaz web**: Visualización + Dashboard
- ✅ **Unit Cap**: Previene worker spam en MicroRTS

## Próximos Pasos

- [ ] Añadir más baselines (MCTS, RL básico)
- [x] ~~Visualizador web de partidas~~
- [x] ~~Dashboard de torneos~~
- [ ] API para competiciones online
- [ ] Más juegos (MOBA, Fighting, etc.)
