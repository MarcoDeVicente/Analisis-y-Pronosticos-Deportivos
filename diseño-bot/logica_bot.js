// Variable global para la gráfica del bot
let chartBotRoiInstance = null;

async function renderizarDashboardBot() {
    // 1. Mostrar la sección correcta
    document.getElementById('modulo-futbol').classList.add('hidden');
    document.getElementById('modulo-beisbol').classList.add('hidden');
    document.getElementById('pantalla-inicio').classList.add('hidden');
    if (document.getElementById('modulo-parlay')) {
        document.getElementById('modulo-parlay').classList.add('hidden');
    }
    document.getElementById('modulo-bot-trading').classList.remove('hidden');

    // Datos simulados (mock data) por si no hay backend activo
    let datosBot = {
        fechas: ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Hoy'],
        balance: [0, -100, 150, 80, 290, 180, 430.50], // Crecimiento del dinero
        operaciones: [
            { fecha: '2026-06-04 10:15', partido: 'Cubs vs Athletics (L)', momio: '3.40', edge: '43.9%', estado: 'Pendiente' },
            { fecha: '2026-06-03 10:02', partido: 'Braves vs Blue Jays (L)', momio: '4.40', edge: '42.0%', estado: 'Ganada' },
            { fecha: '2026-06-03 10:02', partido: 'Astros vs Pirates (L)', momio: '2.58', edge: '8.6%', estado: 'Perdida' }
        ],
        summary: {
            ganancia_neta_total: 430.50,
            win_rate: 68.5,
            tickets_pendientes: 6
        }
    };

    // Intentar obtener datos reales del backend
    try {
        const res = await fetch(`${API_BASE}/bot/portafolio`);
        if (res.ok) {
            const data = await res.json();
            if (data.operaciones && data.operaciones.length > 0) {
                datosBot.fechas = data.chart.fechas;
                datosBot.balance = data.chart.balance;
                datosBot.operaciones = data.operaciones;
                datosBot.summary = data.summary;
                console.log("Datos del bot cargados desde el backend");
            }
        }
    } catch (err) {
        console.warn("No se pudo conectar con el backend para obtener el portafolio del bot, usando datos simulados.", err);
    }

    // Actualizar los elementos de resumen
    const gananciaTotalEl = document.getElementById('bot-ganancia-total');
    if (gananciaTotalEl) {
        const total = datosBot.summary.ganancia_neta_total;
        gananciaTotalEl.innerText = (total >= 0 ? '+' : '-') + '$' + Math.abs(total).toFixed(2);
        if (total >= 0) {
            gananciaTotalEl.className = "text-3xl font-black text-emerald-400";
        } else {
            gananciaTotalEl.className = "text-3xl font-black text-rose-400";
        }
    }
    const winRateEl = document.getElementById('bot-win-rate');
    if (winRateEl) {
        winRateEl.innerText = datosBot.summary.win_rate.toFixed(1) + '%';
    }
    const pendientesEl = document.getElementById('bot-pendientes');
    if (pendientesEl) {
        pendientesEl.innerText = datosBot.summary.tickets_pendientes;
    }

    // 2. Renderizar Gráfica de Línea con Chart.js
    const canvasRoi = document.getElementById('chart-bot-roi');
    if (canvasRoi) {
        if (chartBotRoiInstance) { chartBotRoiInstance.destroy(); }
        
        chartBotRoiInstance = new Chart(canvasRoi.getContext('2d'), {
            type: 'line',
            data: {
                labels: datosBot.fechas,
                datasets: [{
                    label: 'Balance Neto ($)',
                    data: datosBot.balance,
                    borderColor: '#34d399', // emerald-400
                    backgroundColor: 'rgba(52, 211, 153, 0.1)', // Fondo translúcido debajo de la línea
                    borderWidth: 3,
                    tension: 0.4, // Curvas suaves
                    fill: true,
                    pointBackgroundColor: '#090d16',
                    pointBorderColor: '#34d399',
                    pointBorderWidth: 2,
                    pointRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { display: false }, ticks: { color: '#64748b' } },
                    y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } }
                }
            }
        });
    }

    // 3. Renderizar la Tabla
    const tbody = document.getElementById('tabla-bot-body');
    if (tbody) {
        let htmlTabla = '';
        
        datosBot.operaciones.forEach(op => {
            // Colores dinámicos para el estado
            let colorEstado = 'text-blue-400 bg-blue-400/10 border-blue-400/20'; // Pendiente
            if (op.estado === 'Ganada') colorEstado = 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20';
            if (op.estado === 'Perdida') colorEstado = 'text-rose-400 bg-rose-400/10 border-rose-400/20';

            const fechaSimple = op.fecha.includes(' ') ? op.fecha.split(' ')[0] : op.fecha;

            htmlTabla += `
                <tr class="hover:bg-slate-800/30 transition-colors">
                    <td class="py-3 pl-2 text-slate-400 font-mono">${fechaSimple}</td>
                    <td class="py-3 font-semibold text-slate-200">${op.partido}</td>
                    <td class="py-3 text-center text-slate-300 font-mono">${op.momio}</td>
                    <td class="py-3 text-center text-indigo-400 font-bold">+${op.edge}</td>
                    <td class="py-3 text-right pr-2">
                        <span class="px-2 py-1 border rounded-md text-[10px] font-bold uppercase ${colorEstado}">
                            ${op.estado}
                        </span>
                    </td>
                </tr>
            `;
        });
        tbody.innerHTML = htmlTabla;
    }
}
