document.addEventListener('DOMContentLoaded', () => {
    const socket = io();

    // Elementos da UI
    const roomControls = document.getElementById('room-controls');
    const roomInput = document.getElementById('room-input');
    const joinButton = document.getElementById('join-button');
    const gameMain = document.getElementById('game-main');
    const gameMessage = document.getElementById('game-message');
    const scoreTeam1 = document.getElementById('scoreTeam1').querySelector('.score-value');
    const scoreTeam2 = document.getElementById('scoreTeam2').querySelector('.score-value');
    const roomNameDisplay = document.getElementById('room-name-display');
    const playerNumberDisplay = document.getElementById('player-number-display');
    const tableCards = document.getElementById('table-cards');
    const cardButtons = [
        document.getElementById('btnCard1'),
        document.getElementById('btnCard2'),
        document.getElementById('btnCard3')
    ];

    let currentRoom = null;
    let myPlayerNumber = null;

    // Lógica de Conexão
    joinButton.addEventListener('click', () => {
        const room = roomInput.value.trim().toLowerCase();
        if (room) {
            currentRoom = room;
            socket.emit('join', { room: room });
            roomControls.style.display = 'none';
            gameMain.style.display = 'block';
            roomNameDisplay.textContent = `Sala: ${room}`;
        }
    });

    // Ouvinte Principal de Atualizações
    socket.on('update_state', (state) => {
        console.log("Estado recebido:", state);
        if (!state || Object.keys(state).length === 0) {
            // Se o estado estiver vazio, talvez o jogador tenha sido removido de uma sala
            return;
        }

        myPlayerNumber = state.myPlayerNumber;
        playerNumberDisplay.textContent = `Você é o Jogador ${myPlayerNumber}`;

        scoreTeam1.textContent = state.placar.time1;
        scoreTeam2.textContent = state.placar.time2;

        if (state.mesa.length > 0) {
            tableCards.innerHTML = state.mesa.map(item => `<span>J${item.player}: ${item.card}</span>`).join(' ');
        } else {
            tableCards.innerHTML = 'Aguardando jogadas...';
        }

        if(state.roundWinner) {
            gameMessage.textContent = `Time ${state.roundWinner} venceu a rodada!`;
        } else if (state.gameStarted) {
            gameMessage.textContent = `Mão ${state.mao} - Vez do Jogador ${state.jogadorDaVez}`;
        } else {
            gameMessage.textContent = `Aguardando jogadores... (${state.connected_players_count}/4)`;
        }

        cardButtons.forEach((btn, index) => {
            if (index < state.myCards.length) {
                btn.textContent = CARD_NAMES[state.myCards[index]];
                btn.style.display = 'inline-block';
                btn.disabled = !state.isMyTurn;
            } else {
                btn.style.display = 'none';
            }
        });
    });
    
    socket.on('error', (data) => {
        alert(`Erro: ${data.message}`);
    });

    // Emissores de Ações
    cardButtons.forEach((button, index) => {
        button.addEventListener('click', () => {
            if (currentRoom) {
                socket.emit('play_card', { room: currentRoom, card_index: index });
            }
        });
    });

    // Mapeamento de nomes de cartas
    const CARD_NAMES = {
        0: "Porcão", 1: "Q", 2: "J", 3: "K", 4: "A", 5: "2", 6: "3",
        7: "Coringa", 8: "Ouros", 9: "Espadilha", 10: "Copão", 11: "Zap"
    };
});
