// Elementos DOM
const cardsDisplay = document.getElementById('cardsDisplay');
const gameMessage = document.getElementById('gameMessage');
const scoreTeam1 = document.getElementById('scoreTeam1').querySelector('.score-value');
const scoreTeam2 = document.getElementById('scoreTeam2').querySelector('.score-value');
const roundNumber = document.getElementById('roundNumber');
const playerTurn = document.getElementById('playerTurn');
const btnStart = document.getElementById('btnStart');
const btnReset = document.getElementById('btnReset');
const btnCard1 = document.getElementById('btnCard1');
const btnCard2 = document.getElementById('btnCard2');
const btnCard3 = document.getElementById('btnCard3');

// Estado do cliente
let currentCards = [];
let gameActive = false;
let currentPlayerTurn = 0;

// Funções auxiliares
function updateUI() {
    // Atualiza botões de cartas
    const canPlay = gameActive && currentCards.length > 0;
    
    btnCard1.disabled = !canPlay || currentCards.length < 1;
    btnCard2.disabled = !canPlay || currentCards.length < 2;
    btnCard3.disabled = !canPlay || currentCards.length < 3;
    
    if (canPlay) {
        btnCard1.textContent = currentCards.length > 0 ? currentCards[0] : 'Carta 1';
        btnCard2.textContent = currentCards.length > 1 ? currentCards[1] : 'Carta 2';
        btnCard3.textContent = currentCards.length > 2 ? currentCards[2] : 'Carta 3';
    }
    
    // Atualiza botões de controle
    btnStart.disabled = gameActive;
    btnReset.disabled = !gameActive;
}

// Funções de comunicação com a API
async function fetchGameState() {
    try {
        const [cardsRes, scoreRes] = await Promise.all([
            fetch('/api/cards'),
            fetch('/api/score')
        ]);
        
        if (!cardsRes.ok || !scoreRes.ok) {
            throw new Error('Erro na comunicação com o servidor');
        }
        
        const cardsData = await cardsRes.json();
        const scoreData = await scoreRes.json();
        
        // Atualiza estado do jogo
        gameActive = scoreData.game_started;
        
        // Atualiza cartas
        if (cardsData.status === 'active' && Array.isArray(cardsData.cards)) {
            currentCards = cardsData.cards;
            cardsDisplay.textContent = `Suas cartas: ${currentCards.join(' | ')}`;
            currentPlayerTurn = cardsData.current_player || 0;
        } else {
            currentCards = [];
            cardsDisplay.textContent = cardsData.message || 'Aguardando...';
        }
        
        // Atualiza placar
        scoreTeam1.textContent = scoreData.team1;
        scoreTeam2.textContent = scoreData.team2;
        roundNumber.textContent = scoreData.current_round;
        
        // Atualiza informação de vez
        if (currentPlayerTurn > 0) {
            playerTurn.textContent = ` - Vez: Jogador ${currentPlayerTurn}`;
        } else {
            playerTurn.textContent = '';
        }
        
        // Atualiza UI
        updateUI();
        
    } catch (error) {
        console.error('Erro:', error);
        gameMessage.textContent = 'Erro ao conectar ao servidor. Tentando novamente...';
        setTimeout(fetchGameState, 3000);
    }
}

async function startGame() {
    try {
        const res = await fetch('/api/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!res.ok) {
            throw new Error('Erro ao iniciar o jogo');
        }
        
        const data = await res.json();
        gameMessage.textContent = data.message;
        await fetchGameState();
        
    } catch (error) {
        console.error('Erro:', error);
        gameMessage.textContent = 'Falha ao iniciar o jogo. Tente novamente.';
    }
}

async function resetGame() {
    try {
        const res = await fetch('/api/reset', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!res.ok) {
            throw new Error('Erro ao resetar o jogo');
        }
        
        const data = await res.json();
        gameMessage.textContent = data.message;
        await fetchGameState();
        
    } catch (error) {
        console.error('Erro:', error);
        gameMessage.textContent = 'Falha ao resetar o jogo. Tente novamente.';
    }
}

async function playCard(cardIndex) {
    try {
        const res = await fetch(`/api/play/${cardIndex}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!res.ok) {
            throw new Error('Erro ao jogar carta');
        }
        
        const data = await res.json();
        gameMessage.textContent = data.message;
        
        if (data.status === 'round_end') {
            // Feedback visual para o time vencedor
            const winningTeamEl = data.winner === 1 ? scoreTeam1 : scoreTeam2;
            winningTeamEl.classList.add('highlight');
            setTimeout(() => {
                winningTeamEl.classList.remove('highlight');
            }, 2000);
        }
        
        await fetchGameState();
        
    } catch (error) {
        console.error('Erro:', error);
        gameMessage.textContent = 'Falha ao jogar carta. Tente novamente.';
    }
}

// Event Listeners
btnStart.addEventListener('click', startGame);
btnReset.addEventListener('click', resetGame);

// Inicialização
document.addEventListener('DOMContentLoaded', () => {
    fetchGameState();
    setInterval(fetchGameState, 3000); // Atualiza a cada 3 segundos
});