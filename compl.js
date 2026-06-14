// Imagina que esta función es la que llamas al hacer clic en "Generar Pronóstico"
async function consultarPronostico() {
    const local = document.getElementById('input-local').value;
    const visitante = document.getElementById('input-visitante').value;
    const url = `http://localhost:8000/api/pronostico/beisbol?local=${local}&visitante=${visitante}`;

    try {
        const respuesta = await fetch(url);
        const datos = await respuesta.json();

        // 1. Aquí actualizas tus tablas de carreras/goles normales...
        
        // 2. Lógica para el Value Bet
        actualizarPanelValueBet(datos.value_bet);

    } catch (error) {
        console.error("Error al consultar la API:", error);
    }
}

function actualizarPanelValueBet(valueBetData) {
    const panel = document.getElementById('panel-value-bet');
    
    // Si no hay datos, o la ventaja es menor al 4% (nuestro umbral de seguridad), ocultamos el panel
    if (!valueBetData || valueBetData.edge < 4.0) {
        panel.classList.add('hidden');
        return;
    }

    // Si hay ventaja real, mostramos el panel
    panel.classList.remove('hidden');

    // Rellenamos los datos en la interfaz
    document.getElementById('vb-seleccion').textContent = valueBetData.seleccion;
    document.getElementById('vb-prob-ia').textContent = valueBetData.prob_ia.toFixed(1) + '%';
    document.getElementById('vb-momio').textContent = valueBetData.momio_casino.toFixed(2);
    document.getElementById('vb-edge').textContent = '+' + valueBetData.edge.toFixed(1) + '%';
}

// Función temporal para el botón
function enviarAlPortafolio() {
    const seleccion = document.getElementById('vb-seleccion').textContent;
    const edge = document.getElementById('vb-edge').textContent;
    alert(`Enviando orden a SQLite: Apostar a ${seleccion} con ventaja de ${edge}`);
    // Aquí luego conectaremos otra ruta POST a FastAPI para guardar en BD
}