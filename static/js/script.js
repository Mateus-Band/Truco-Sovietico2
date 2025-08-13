document.addEventListener('DOMContentLoaded', () => {
    // Elementos DOM
    const cardsDisplay = document.getElementById('cardsDisplay');
    const gameMessage = document.getElementById('gameMessage');
    const scoreTeam1 = document.getElementById('scoreTeam1').querySelector('.score-value');
    const scoreTeam2 = document.getElementById('scoreTeam2').querySelector('.score-value');
    const roundNumberEl = document.getElementById('roundNumber');
    const playerTurnEl = document.getElementById('playerTurn');
    const btnStart = document.getElementById('btnStart');
    const btnReset = document.getElementById('btnReset');
    const cardButtons = [
        document.getElementById('btnCard1'),
        document.getElementById('btnCard2'),
        document.getElementById('btnCard3')
    ];

    let isRequestPending = false;

    function setControlsDisabled(state) {
        btnStart.disabled = state;
        btnReset.disabled = state;
        cardButtons.forEach(btn => btn.disabled = state);
    }

    function updateUI(state) {
        // Atualiza placar
        scoreTeam1.textContent = state.placar.time1;
        scoreTeam2.textContent = state.placar.time2;
        roundNumberEl.textContent = `Mão: ${state.mao}`;
        
        // Atualiza vez do jogador
        playerTurnEl.textContent = state.jogadorDaVez ? ` - Vez do Jogador ${state.jogadorDaVez}` : '';

        // Atualiza display de cartas
        if (state.cartasDoJogador.length > 0 && state.jogoIniciado) {
            cardsDisplay.textContent = `Suas cartas: ${state.cartasDoJogador.join(' | ')}`;
        } else if (!state.jogoIniciado) {
            cardsDisplay.textContent = "Clique em 'Iniciar Jogo' para uma nova rodada.";
        } else {
            cardsDisplay.textContent = "Aguardando sua vez ou a próxima mão...";
        }
        
        // Mensagem de fim de rodada
        if (state.rodadaFinalizada && !state.jogoIniciado) {
            gameMessage.textContent = `Fim da rodada! Time ${state.vencedorDaRodada} venceu!`;
        }

        // Atualiza botões de controle
        btnStart.disabled = state.jogoIniciado;
        btnReset.disabled = !state.jogoIniciado && !state.rodadaFinalizada;
        btnStart.textContent = state.jogoIniciado ? 'Jogo em Andamento' : 'Iniciar Nova Rodada';

        // Atualiza botões de cartas
        const canPlay = state.jogoIniciado && state.cartasDoJogador.length > 0;
        cardButtons.forEach((btn, index) => {
            const hasCard = index < state.cartasDoJogador.length;
            btn.disabled = !canPlay || !hasCard;
            btn.textContent = canPlay && hasCard ? `Jogar ${state.cartasDoJogador[index]}` : `Carta ${index + 1}`;
        });
    }

    async function fetchGameState() {
        if (isRequestPending) return;
        isRequestPending = true;
        try {
            // AQUI ESTÁ A CORREÇÃO PRINCIPAL: UMA ÚNICA CHAMADA PARA /api/state
            const response = await fetch('/api/state');
            if (!response.ok) throw new Error('Falha na comunicação com o servidor');
            const state = await response.json();
            updateUI(state);
        } catch (error) {
            console.error('Erro ao buscar estado:', error);
            gameMessage.textContent = 'Erro de conexão. Tentando reconectar...';
        } finally {
            isRequestPending = false;
        }
    }
    
    async function performAction(url, options) {
        setControlsDisabled(true);
        gameMessage.textContent = 'Processando...';
        try {
            const res = await fetch(url, options);
            if (!res.ok) throw new Error('Ação falhou');
            const data = await res.json();

            const message = data.resultado || data.mensagem || '';
            if (message) {
                 gameMessage.textContent = message;
            }
           
        } catch (error) {
            console.error('Erro na ação:', error);
            gameMessage.textContent = 'Ocorreu um erro. A interface será atualizada.';
        } finally {
            await fetchGameState(); 
        }
    }

    function playCard(indice) {
        performAction(`/api/play/${indice}`, { method: 'POST' });
    }
    
    cardButtons.forEach((button, index) => {
        button.addEventListener('click', () => playCard(index));
    });

    btnStart.addEventListener('click', () => {
        gameMessage.textContent = '';
        performAction('/api/start', { method: 'POST' });
    });
    
    btnReset.addEventListener('click', () => {
        performAction('/api/reset', { method: 'POST' });
    });
    
    // Inicialização e atualização periódica
    fetchGameState();
    setInterval(fetchGameState, 3000);
});
