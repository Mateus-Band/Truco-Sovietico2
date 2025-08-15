document.addEventListener('DOMContentLoaded', () => {
    const socket = io();
//
    // UI Elements
    const roomControls = document.getElementById('room-controls');
    const nameInput = document.getElementById('name-input');
    const roomInput = document.getElementById('room-input');
    const joinButton = document.getElementById('join-button');
    const gameMain = document.getElementById('game-main');
    const gameMessage = document.getElementById('game-message');
    const scoreTeam1 = document.getElementById('scoreTeam1').querySelector('.score-value');
    const scoreTeam2 = document.getElementById('scoreTeam2').querySelector('.score-value');
    const team1Names = document.getElementById('team1-names');
    const team2Names = document.getElementById('team2-names');
    const handScoreTeam1 = document.getElementById('hand-score-team1');
    const handScoreTeam2 = document.getElementById('hand-score-team2');
    const roomNameDisplay = document.getElementById('room-name-display');
    const playerInfoDisplay = document.getElementById('player-info-display');
    const tableCardsEl = document.getElementById('table-cards');
    const roundValueEl = document.getElementById('round-value');
    const handsHistoryEl = document.getElementById('hands-history');
    const cardButtons = document.querySelectorAll('.btn-card');
    const playHiddenOption = document.getElementById('play-hidden-option');
    const playHiddenCheckbox = document.getElementById('play-hidden-checkbox');
    const trucoButton = document.getElementById('truco-button');
    const newRoundButton = document.getElementById('new-round-button');
    const trucoResponseOverlay = document.getElementById('truco-response-overlay');
    const trucoQuestion = document.getElementById('truco-question');
    const trucoResponseButtons = document.querySelector('.truco-response-buttons');
    const gameWinnerOverlay = document.getElementById('game-winner-overlay');
    const gameWinnerMessage = document.getElementById('game-winner-message');

    let currentRoom = null;

    // Join Logic
    joinButton.addEventListener('click', () => {
        const room = roomInput.value.trim().toLowerCase();
        const name = nameInput.value.trim();
        if (room && name) {
            currentRoom = room;
            socket.emit('join', { room, name });
            roomControls.style.display = 'none';
            gameMain.style.display = 'block';
            roomNameDisplay.textContent = `Sala: ${room}`;
        } else {
            alert('Por favor, insira o seu nome e o nome da sala.');
        }
    });

    // Main state update listener
    socket.on('update_state', (state) => {
        console.log("Estado recebido:", state);
        if (!state) return;

        scoreTeam1.textContent = state.placar.time1;
        scoreTeam2.textContent = state.placar.time2;
        handScoreTeam1.textContent = `Mãos: ${state.handPlacar.time1}`;
        handScoreTeam2.textContent = state.handPlacar.time2;

        const players = state.connected_players;
        team1Names.textContent = players.length > 2 ? `(${players[0]} & ${players[2]})` : '';
        team2Names.textContent = players.length > 3 ? `(${players[1]} & ${players[3]})` : '';
        playerInfoDisplay.textContent = `Você: ${state.myName} (Dupla: ${state.partnerName})`;

        tableCardsEl.innerHTML = state.mesa.length > 0 ? state.mesa.map(item => `<span>${item.player}: ${item.card}</span>`).join(' ') : 'Aguardando jogadas...';
        roundValueEl.textContent = state.roundValue;

        handsHistoryEl.innerHTML = state.handsHistory.map((hand, index) => {
            const handCards = hand.map(c => `${c.player}: ${c.card}`).join(', ');
            return `<div class="hand"><span class="hand-title">Mão ${index + 1}:</span> ${handCards}</div>`;
        }).join('');

        if (state.gameWinner) {
            gameWinnerMessage.textContent = `FIM DE JOGO! A Equipa ${state.gameWinner} venceu!`;
            gameWinnerOverlay.style.display = 'flex';
            gameMessage.textContent = `A Equipa ${state.gameWinner} venceu a partida!`;
            newRoundButton.style.display = 'none';
            trucoButton.style.display = 'none';
        } else if (state.roundOver) {
            gameMessage.textContent = `A Equipa ${state.roundWinner} venceu ${state.roundValue} ponto(s)!`;
            newRoundButton.style.display = 'block';
            trucoButton.style.display = 'none';
        } else if (state.gameStarted) {
            gameMessage.textContent = `Mão ${state.mao} - Vez de ${state.jogadorDaVez}`;
            newRoundButton.style.display = 'none';
        } else {
            gameMessage.textContent = `Aguardando jogadores... (${players.length}/4)`;
        }

        cardButtons.forEach((btn, index) => {
            const cardValue = state.myCards ? state.myCards[index] : null;
            if (cardValue !== undefined && cardValue !== null) {
                btn.textContent = CARD_NAMES[cardValue];
                btn.style.display = 'inline-block';
                btn.disabled = !state.isMyTurn;
            } else {
                btn.style.display = 'none';
            }
        });

        playHiddenOption.style.display = (state.gameStarted && state.mao > 1 && state.isMyTurn) ? 'block' : 'none';

        // --- REGRA ADICIONADA ---
        const canCallTruco = state.isMyTeamsTurn && state.trucoState === 'none' && state.mao > 1 && !state.roundOver;
        trucoButton.style.display = canCallTruco ? 'inline-block' : 'none';

        const shouldRespond = state.trucoState !== 'none' && state.trucoAskerTeam !== state.myTeam;
        if (shouldRespond) {
            const raiseValue = state.roundValue === 3 ? 6 : (state.roundValue === 6 ? 9 : 12);
            trucoQuestion.textContent = `A outra equipa pediu TRUCO (vale ${state.roundValue})! O que faz?`;
            trucoResponseOverlay.style.display = 'flex';
            trucoResponseButtons.querySelector('.btn-raise').style.display = state.roundValue < 12 ? 'inline-block' : 'none';
            trucoResponseButtons.querySelector('.btn-raise').textContent = `PEDIR ${raiseValue}!`;
        } else {
            trucoResponseOverlay.style.display = 'none';
        }
    });
    
    // Action emitters
    cardButtons.forEach((btn, index) => {
        btn.addEventListener('click', () => {
            if (!btn.disabled) {
                const isHidden = playHiddenCheckbox.checked;
                socket.emit('play_card', { room: currentRoom, card_index: index, is_hidden: isHidden });
                playHiddenCheckbox.checked = false;
            }
        });
    });

    trucoButton.addEventListener('click', () => socket.emit('call_truco', { room: currentRoom }));
    newRoundButton.addEventListener('click', () => socket.emit('request_new_round', { room: currentRoom }));

    trucoResponseButtons.addEventListener('click', (e) => {
        if (e.target.tagName === 'BUTTON') {
            const response = e.target.dataset.response;
            if(response === 'raise') {
                socket.emit('call_truco', { room: currentRoom });
            } else {
                socket.emit('respond_truco', { room: currentRoom, response });
            }
            trucoResponseOverlay.style.display = 'none';
        }
    });

    const CARD_NAMES = {
        "-1": "Carta Virada",
        0: "Porcão", 1: "Q", 2: "J", 3: "K", 4: "A", 5: "2", 6: "3",
        7: "Coringa", 8: "Ouros", 9: "Espadilha", 10: "Copão", 11: "Zap"
    };
});
