# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2026-01-14

### Key Features
- **TacticFPS Benchmark Parity**:
    - Normalized scores (kills/team), detailed events (bomb logic), and side swap support.
    - Full 4-player support in CLI (teams mapped to generic Player 1 / Player 2 sides).
- **Benchmark Tools**:
    - **Schema Freeze**: Formal `SCHEMA.md` definition for JSON outputs.
    - **Export CLI**: New `export` command to generate `matches.csv`, `leaderboard.csv`, `matchups.csv`, `events_agg.csv`.
    - **Analysis Notebook**: Golden notebook (`notebooks/benchmark_analysis.ipynb`) for reproducible analysis.

### Enhancements
- **Global**:
    - Side Swap Tournaments enabled by default for fairness.
    - Dashboard updated with "Side Bias Check" and "Event Stats".
    - Improved baseline bots for all games.
- **MicroRTS**: Optimized pathfinding and resource gathering logic for econ bot.
- **CarBall**: Physics tweaks for ball handling consistency.

### Fixes
- Fixed `run_tournament` winner reporting for team-based games (normalized IDs).
- Resolved CLI agent assignment issues for multi-agent roster games.

### Documentation
- Updated README with CLI usage examples for new commands.
- Included comprehensive JSON schema documentation.
