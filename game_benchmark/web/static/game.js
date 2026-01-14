/**
 * Game Benchmark - Renderizado Canvas y Control
 */

// ===== Estado Global =====
let currentGame = 'carball';
let animationId = null;
let isRunning = false;

// ===== Elementos DOM =====
const canvas = document.getElementById('game-canvas');
const ctx = canvas.getContext('2d');
const startBtn = document.getElementById('start-btn');
const stopBtn = document.getElementById('stop-btn');
const gameSelect = document.getElementById('game-select');
const tickDisplay = document.getElementById('tick-count');
const scoreDisplay = document.getElementById('score-display');
const resultBanner = document.getElementById('result-banner');

// ===== Navegación =====
document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const view = btn.dataset.view;

        // Actualizar botones
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        // Mostrar vista
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        document.getElementById(`${view}-view`).classList.add('active');

        // Actualizar leaderboard si es necesario
        if (view === 'leaderboard') {
            fetchLeaderboard();
        }
    });
});

// ===== Control de Partidas =====
const AGENT_OPTIONS = {
    'carball': [
        { value: 'ballchaser', label: '🏃 BallChaser' },
        { value: 'goalie', label: '🧤 Goalie' },
        { value: 'striker', label: '⚡ Striker' },
        { value: 'random', label: '🎲 Random' }
    ],
    'micorts': [
        { value: 'baseline', label: '🛡️ Econ (Baseline)' },
        { value: 'random', label: '🎲 Random' }
    ],
    'tacticfps': [
        { value: 'baseline', label: '🔫 TacticBot' },
        { value: 'random', label: '🎲 Random' }
    ]
};

function updateAgentSelects(game) {
    const opts = AGENT_OPTIONS[game] || AGENT_OPTIONS['carball'];
    const s1 = document.getElementById('agent1-select');
    const s2 = document.getElementById('agent2-select');

    [s1, s2].forEach((sel, idx) => {
        const current = sel.value;
        sel.innerHTML = opts.map(o => `<option value="${o.value}">${o.label}</option>`).join('');
        // Intentar preservar selección si es válida, sino poner default
        if (opts.some(o => o.value === current)) sel.value = current;
        else sel.value = opts[0].value;

        // Si es el segundo selector y hay opcion random, poner random por defecto para variar
        if (idx === 1 && opts.some(o => o.value === 'random') && !opts.some(o => o.value === current)) {
            // sel.value = 'random'; // Opcional
        }
    });

    // Actualizar también el select de velocidad si fuera necesario (TacticFPS va bien a 2x)
}

gameSelect.addEventListener('change', (e) => {
    updateAgentSelects(e.target.value);
});

// Inicializar
updateAgentSelects(gameSelect.value);

startBtn.addEventListener('click', startMatch);
stopBtn.addEventListener('click', stopMatch);

async function startMatch() {
    const game = gameSelect.value;
    const agent1 = document.getElementById('agent1-select').value;
    const agent2 = document.getElementById('agent2-select').value;
    const speed = parseFloat(document.getElementById('speed-select').value);
    const seed = Math.floor(Math.random() * 100000);

    currentGame = game;

    try {
        const resp = await fetch('/api/start_match', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ game, agent1, agent2, seed, speed })
        });

        if (resp.ok) {
            isRunning = true;
            startBtn.disabled = true;
            stopBtn.disabled = false;
            resultBanner.classList.add('hidden');
            startPolling();
        }
    } catch (err) {
        console.error('Error starting match:', err);
    }
}

async function stopMatch() {
    try {
        await fetch('/api/stop_match', { method: 'POST' });
    } catch (err) {
        console.error('Error stopping match:', err);
    }

    isRunning = false;
    startBtn.disabled = false;
    stopBtn.disabled = true;

    if (animationId) {
        cancelAnimationFrame(animationId);
        animationId = null;
    }
}

// ===== Polling del Estado =====
function startPolling() {
    async function poll() {
        if (!isRunning) return;

        try {
            const resp = await fetch('/api/match_state');
            const data = await resp.json();

            if (data.frame) {
                renderFrame(data.game, data.frame);
                tickDisplay.textContent = data.frame.tick || 0;
            }

            if (data.result) {
                showResult(data.result);
                isRunning = false;
                startBtn.disabled = false;
                stopBtn.disabled = true;
            }

            if (data.running) {
                animationId = requestAnimationFrame(poll);
            } else if (!data.result) {
                animationId = requestAnimationFrame(poll);
            }
        } catch (err) {
            console.error('Polling error:', err);
            animationId = requestAnimationFrame(poll);
        }
    }

    poll();
}

function showResult(result) {
    const text = result.winner
        ? `🏆 Ganador: ${result.winner}`
        : '🤝 Empate';

    resultBanner.querySelector('.result-text').textContent = text;
    resultBanner.classList.remove('hidden');
}

// ===== Renderizado =====
function renderFrame(game, frame) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    switch (game) {
        case 'carball':
            renderCarBall(frame);
            break;
        case 'micorts':
            renderMicroRTS(frame);
            break;
        case 'tacticfps':
            renderTacticFPS(frame);
            break;
    }
}

// ===== CarBall Renderer =====
function renderCarBall(frame) {
    const scaleX = canvas.width / frame.arena.width;
    const scaleY = canvas.height / frame.arena.height;
    const scale = Math.min(scaleX, scaleY);
    const offsetX = (canvas.width - frame.arena.width * scale) / 2;
    const offsetY = (canvas.height - frame.arena.height * scale) / 2;

    // Fondo arena
    ctx.fillStyle = '#1a472a';
    ctx.fillRect(offsetX, offsetY, frame.arena.width * scale, frame.arena.height * scale);

    // Líneas del campo
    ctx.strokeStyle = 'rgba(255,255,255,0.3)';
    ctx.lineWidth = 2;

    // Línea central
    ctx.beginPath();
    ctx.moveTo(offsetX + frame.arena.width * scale / 2, offsetY);
    ctx.lineTo(offsetX + frame.arena.width * scale / 2, offsetY + frame.arena.height * scale);
    ctx.stroke();

    // Círculo central
    ctx.beginPath();
    ctx.arc(
        offsetX + frame.arena.width * scale / 2,
        offsetY + frame.arena.height * scale / 2,
        30, 0, Math.PI * 2
    );
    ctx.stroke();

    // Porterías
    const goalY1 = offsetY + (frame.arena.height - frame.arena.goalWidth) / 2 * scale;
    const goalH = frame.arena.goalWidth * scale;

    ctx.fillStyle = '#3b82f6';
    ctx.fillRect(offsetX - 10, goalY1, 10, goalH);

    ctx.fillStyle = '#ef4444';
    ctx.fillRect(offsetX + frame.arena.width * scale, goalY1, 10, goalH);

    // Pelota
    ctx.fillStyle = '#ffffff';
    ctx.shadowColor = '#ffffff';
    ctx.shadowBlur = 10;
    ctx.beginPath();
    ctx.arc(
        offsetX + frame.ball.pos.x * scale,
        offsetY + frame.ball.pos.y * scale,
        frame.ball.radius * scale,
        0, Math.PI * 2
    );
    ctx.fill();
    ctx.shadowBlur = 0;

    // Coches
    const colors = { player_1: '#3b82f6', player_2: '#ef4444' };

    for (const [pid, car] of Object.entries(frame.cars)) {
        ctx.save();
        ctx.translate(
            offsetX + car.pos.x * scale,
            offsetY + car.pos.y * scale
        );
        ctx.rotate(car.angle);

        // Cuerpo del coche
        ctx.fillStyle = colors[pid];
        ctx.fillRect(-12, -8, 24, 16);

        // Dirección
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(8, -4, 6, 8);

        ctx.restore();

        // Boost indicator
        if (car.boost > 0) {
            ctx.fillStyle = `rgba(255, 200, 0, ${car.boost / 100})`;
            ctx.fillRect(
                offsetX + car.pos.x * scale - 15,
                offsetY + car.pos.y * scale + 15,
                30 * (car.boost / 100),
                4
            );
        }
    }

    // Marcador
    if (frame.scores) {
        document.querySelector('.score.p1').textContent = frame.scores.player_1 || 0;
        document.querySelector('.score.p2').textContent = frame.scores.player_2 || 0;
    }
}

// ===== MicroRTS Renderer =====
function renderMicroRTS(frame) {
    const cellSize = Math.min(canvas.width, canvas.height) / frame.mapSize;
    const offsetX = (canvas.width - cellSize * frame.mapSize) / 2;
    const offsetY = (canvas.height - cellSize * frame.mapSize) / 2;

    // Grid
    ctx.strokeStyle = 'rgba(255,255,255,0.1)';
    for (let x = 0; x <= frame.mapSize; x++) {
        ctx.beginPath();
        ctx.moveTo(offsetX + x * cellSize, offsetY);
        ctx.lineTo(offsetX + x * cellSize, offsetY + frame.mapSize * cellSize);
        ctx.stroke();
    }
    for (let y = 0; y <= frame.mapSize; y++) {
        ctx.beginPath();
        ctx.moveTo(offsetX, offsetY + y * cellSize);
        ctx.lineTo(offsetX + frame.mapSize * cellSize, offsetY + y * cellSize);
        ctx.stroke();
    }

    // Zonas
    for (const [zid, zone] of Object.entries(frame.zones)) {
        let color = 'rgba(100,100,100,0.2)';
        if (zone.controller === 'player_1') color = 'rgba(59,130,246,0.3)';
        else if (zone.controller === 'player_2') color = 'rgba(239,68,68,0.3)';
        else if (zone.type === 'mid') color = 'rgba(245,158,11,0.3)';

        ctx.fillStyle = color;
        ctx.fillRect(
            offsetX + zone.bounds.x_min * cellSize,
            offsetY + zone.bounds.y_min * cellSize,
            (zone.bounds.x_max - zone.bounds.x_min + 1) * cellSize,
            (zone.bounds.y_max - zone.bounds.y_min + 1) * cellSize
        );
    }

    // Unidades
    const unitColors = {
        player_1: '#3b82f6',
        player_2: '#ef4444'
    };

    const unitIcons = {
        worker: '⛏',
        soldier: '⚔',
        ranged: '🏹',
        base: '🏠',
        barracks: '⚒'
    };

    for (const unit of frame.units) {
        const x = offsetX + unit.x * cellSize + cellSize / 2;
        const y = offsetY + unit.y * cellSize + cellSize / 2;

        // Fondo circular
        ctx.fillStyle = unitColors[unit.owner] || '#888';
        ctx.beginPath();
        ctx.arc(x, y, cellSize / 3, 0, Math.PI * 2);
        ctx.fill();

        // Icono
        ctx.fillStyle = '#fff';
        ctx.font = `${cellSize / 2}px Arial`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(unitIcons[unit.type] || '?', x, y);

        // HP bar
        if (unit.hp < unit.max_hp) {
            const hpRatio = unit.hp / unit.max_hp;
            ctx.fillStyle = '#333';
            ctx.fillRect(x - cellSize / 3, y + cellSize / 3, cellSize * 2 / 3, 3);
            ctx.fillStyle = hpRatio > 0.5 ? '#10b981' : '#ef4444';
            ctx.fillRect(x - cellSize / 3, y + cellSize / 3, cellSize * 2 / 3 * hpRatio, 3);
        }
    }

    // Recursos
    document.querySelector('.score.p1').textContent = frame.resources?.player_1 || 0;
    document.querySelector('.score.p2').textContent = frame.resources?.player_2 || 0;
}

// ===== TacticFPS Renderer =====
function renderTacticFPS(frame) {
    const cellSize = Math.min(canvas.width, canvas.height) / frame.mapSize;
    const offsetX = (canvas.width - cellSize * frame.mapSize) / 2;
    const offsetY = (canvas.height - cellSize * frame.mapSize) / 2;

    // Mapa
    for (let y = 0; y < frame.mapSize; y++) {
        for (let x = 0; x < frame.mapSize; x++) {
            const cell = frame.map[y]?.[x] ?? 0;

            let color = '#1a1a2e';
            if (cell === 1) color = '#4a4a6a'; // Wall
            else if (cell === 2) color = '#2d4a2d'; // Plant zone

            ctx.fillStyle = color;
            ctx.fillRect(
                offsetX + x * cellSize,
                offsetY + y * cellSize,
                cellSize - 1,
                cellSize - 1
            );
        }
    }

    // Humos
    for (const smoke of frame.smokes) {
        ctx.fillStyle = 'rgba(200,200,200,0.6)';
        ctx.beginPath();
        ctx.arc(
            offsetX + smoke.x * cellSize + cellSize / 2,
            offsetY + smoke.y * cellSize + cellSize / 2,
            cellSize * 2,
            0, Math.PI * 2
        );
        ctx.fill();
    }

    // Bomba
    if (frame.bomb.planted && frame.bomb.x != null) {
        ctx.fillStyle = '#ef4444';
        ctx.beginPath();
        ctx.arc(
            offsetX + frame.bomb.x * cellSize + cellSize / 2,
            offsetY + frame.bomb.y * cellSize + cellSize / 2,
            cellSize / 2,
            0, Math.PI * 2
        );
        ctx.fill();

        // Pulso
        ctx.strokeStyle = 'rgba(239,68,68,0.5)';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(
            offsetX + frame.bomb.x * cellSize + cellSize / 2,
            offsetY + frame.bomb.y * cellSize + cellSize / 2,
            cellSize * (1 + Math.sin(Date.now() / 200) * 0.3),
            0, Math.PI * 2
        );
        ctx.stroke();
    }

    // Jugadores
    const teamColors = { T: '#f59e0b', CT: '#3b82f6' };

    for (const [pid, player] of Object.entries(frame.players)) {
        if (!player.alive) continue;

        const x = offsetX + player.x * cellSize + cellSize / 2;
        const y = offsetY + player.y * cellSize + cellSize / 2;

        // Cuerpo
        ctx.fillStyle = teamColors[player.team];
        ctx.beginPath();
        ctx.arc(x, y, cellSize / 3, 0, Math.PI * 2);
        ctx.fill();

        // Flash effect
        if (player.flashed_ticks > 0) {
            ctx.fillStyle = 'rgba(255,255,255,0.8)';
            ctx.beginPath();
            ctx.arc(x, y, cellSize / 2, 0, Math.PI * 2);
            ctx.fill();
        }

        // ID
        ctx.fillStyle = '#fff';
        ctx.font = '10px Arial';
        ctx.textAlign = 'center';
        ctx.fillText(pid.toUpperCase(), x, y + 4);
    }

    // Score (T alive vs CT alive)
    const tAlive = Object.values(frame.players).filter(p => p.team === 'T' && p.alive).length;
    const ctAlive = Object.values(frame.players).filter(p => p.team === 'CT' && p.alive).length;
    document.querySelector('.score.p1').textContent = tAlive;
    document.querySelector('.score.p2').textContent = ctAlive;
}

// ===== Leaderboard =====
async function fetchLeaderboard() {
    try {
        const resp = await fetch('/api/leaderboard');
        const data = await resp.json();

        const container = document.getElementById('leaderboard-table');

        if (data.length === 0) {
            container.innerHTML = '<p style="padding: 20px; text-align: center; color: var(--text-dim);">No hay datos aún. ¡Ejecuta algunas partidas!</p>';
            return;
        }

        let html = `
            <div class="lb-row header">
                <span class="lb-rank">#</span>
                <span class="lb-name">Agente</span>
                <span class="lb-stats">W/L</span>
                <span class="lb-elo">ELO</span>
            </div>
        `;

        data.forEach((entry, i) => {
            html += `
                <div class="lb-row">
                    <span class="lb-rank">${i + 1}</span>
                    <span class="lb-name">${entry.name}</span>
                    <span class="lb-stats">${entry.wins}/${entry.losses}</span>
                    <span class="lb-elo">${entry.elo}</span>
                </div>
            `;
        });

        container.innerHTML = html;
    } catch (err) {
        console.error('Error fetching leaderboard:', err);
    }
}

document.getElementById('refresh-lb-btn').addEventListener('click', fetchLeaderboard);

// ===== Tournament =====
document.getElementById('run-tourney-btn').addEventListener('click', async () => {
    const game = document.getElementById('tourney-game').value;
    const matches = parseInt(document.getElementById('tourney-matches').value);
    const btn = document.getElementById('run-tourney-btn');
    const resultsDiv = document.getElementById('tourney-results');

    btn.disabled = true;
    btn.textContent = '⏳ Ejecutando...';
    resultsDiv.innerHTML = '';

    try {
        const resp = await fetch('/api/run_tournament', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ game, matches })
        });

        const data = await resp.json();

        let html = `
            <div style="background: var(--bg-card); padding: 20px; border-radius: 12px;">
                <h3>✅ Torneo Completado</h3>
                <p>Total partidas: ${data.totalMatches}</p>
                <h4 style="margin-top: 16px;">Resultados:</h4>
        `;

        data.leaderboard.forEach((entry, i) => {
            html += `<p>${i + 1}. ${entry.name} - ELO: ${entry.elo} (${entry.wins} wins)</p>`;
        });

        html += '</div>';
        resultsDiv.innerHTML = html;

    } catch (err) {
        resultsDiv.innerHTML = `<p style="color: var(--danger);">Error: ${err.message}</p>`;
    } finally {
        btn.disabled = false;
        btn.textContent = '🏆 Ejecutar Torneo';
    }
});

// ===== Inicialización =====
ctx.fillStyle = '#1a1a2e';
ctx.fillRect(0, 0, canvas.width, canvas.height);
ctx.fillStyle = '#94a3b8';
ctx.font = '20px Inter';
ctx.textAlign = 'center';
ctx.fillText('🎮 Selecciona un juego y pulsa Iniciar', canvas.width / 2, canvas.height / 2);
