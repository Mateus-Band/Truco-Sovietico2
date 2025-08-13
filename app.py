import os
from threading import Lock
from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, leave_room, emit
import random

# --- Configuração da Aplicação ---
app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = os.urandom(24)  # Gera uma chave secreta segura
socketio = SocketIO(app, async_mode='eventlet')

# --- Constantes e Lógica do Jogo (adaptadas) ---
# (A lógica do TrucoGame foi movida e adaptada para dentro desta seção para simplicidade)
CARD_NAMES = {
    0: "Porcão", 1: "Q", 2: "J", 3: "K", 4: "A", 5: "2", 6: "3",
    7: "Coringa", 8: "Ouros", 9: "Espadilha", 10: "Copão", 11: "Zap"
}
FULL_DECK = [
    0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 5, 5, 5, 5,
    7, 8, 9, 10, 11
]

# --- Gestão de Estado Global ---
games = {}  # Dicionário para guardar o estado dos jogos de cada sala
games_lock = Lock()

def create_new_game_state():
    """Cria um estado de jogo inicial para uma nova sala."""
    return {
        "players": {},  # sid: player_info
        "player_order": [], # Lista de sids na ordem de jogo
        "deck": [],
        "table": [],
        "current_player_idx": 0,
        "team1_hand_wins": 0,
        "team2_hand_wins": 0,
        "hand_of_round": 1,
        "game_started": False,
        "round_winner_team": None
    }

def get_player_view(room_name, player_sid):
    """Cria a visão do jogo específica para um jogador."""
    with games_lock:
        state = games.get(room_name)
        if not state:
            return {}

        player_info = state["players"].get(player_sid)
        if not player_info:
            return {}
            
        is_my_turn = state["game_started"] and state["player_order"][state["current_player_idx"]] == player_sid

        return {
            "isMyTurn": is_my_turn,
            "myCards": player_info["cards"],
            "myPlayerNumber": player_info["number"],
            "gameStarted": state["game_started"],
            "placar": {"time1": state["team1_hand_wins"], "time2": state["team2_hand_wins"]},
            "mao": state["hand_of_round"],
            "jogadorDaVez": state["players"][state["player_order"][state["current_player_idx"]]]['number'] if state["game_started"] else None,
            "mesa": [{"player": state["players"][item["sid"]]["number"], "card": CARD_NAMES[item["card"]]} for item in state["table"]],
            "connected_players": [p["number"] for p in state["players"].values()],
            "roundWinner": state["round_winner_team"]
        }

# --- Eventos do Socket.IO ---

@socketio.on('join')
def on_join(data):
    """Quando um jogador entra numa sala."""
    room = data['room']
    sid = request.sid
    join_room(room)

    with games_lock:
        if room not in games:
            games[room] = create_new_game_state()

        state = games[room]
        if sid not in state["players"] and len(state["players"]) < 4:
            player_number = len(state["players"]) + 1
            state["players"][sid] = {"number": player_number, "cards": [], "sid": sid}
            state["player_order"].append(sid) # Adiciona na ordem de chegada
            print(f"Jogador {player_number} ({sid}) entrou na sala {room}")

            if len(state["players"]) == 4:
                # Jogo começa!
                start_new_round(room)
        
        # Envia a todos o estado atualizado da sala
        for player_sid in state["players"]:
            emit('update_state', get_player_view(room, player_sid), to=player_sid)

@socketio.on('play_card')
def on_play_card(data):
    room = data['room']
    card_index = data['card_index']
    sid = request.sid

    with games_lock:
        state = games.get(room, {})
        player_info = state.get("players", {}).get(sid)

        is_my_turn = state["game_started"] and state["player_order"][state["current_player_idx"]] == sid

        if not player_info or not is_my_turn or not (0 <= card_index < len(player_info["cards"])):
            emit('error', {'message': 'Jogada inválida.'})
            return

        card = player_info["cards"].pop(card_index)
        state["table"].append({"sid": sid, "card": card})

        # Avança para o próximo jogador
        state["current_player_idx"] += 1
        
        if len(state["table"]) == 4:
            # Todos jogaram, finalizar a mão
            end_hand(room)
        
        for player_sid in state["players"]:
            emit('update_state', get_player_view(room, player_sid), to=player_sid)

# --- Funções Auxiliares de Lógica de Jogo ---

def start_new_round(room):
    """Prepara uma nova rodada para uma sala."""
    state = games[room]
    state["game_started"] = True
    state["round_winner_team"] = None
    state["team1_hand_wins"] = 0
    state["team2_hand_wins"] = 0
    start_new_hand(room)

def start_new_hand(room):
    """Prepara uma nova mão (distribui cartas)."""
    state = games[room]
    state["table"] = []
    state["current_player_idx"] = 0
    state["hand_of_round"] = state["team1_hand_wins"] + state["team2_hand_wins"] + 1

    # Embaralhar e distribuir
    deck = FULL_DECK[:]
    random.shuffle(deck)
    for player_sid in state["player_order"]:
        state["players"][player_sid]["cards"] = sorted([deck.pop() for _ in range(3)], reverse=True)

def end_hand(room):
    """Determina o vencedor da mão e verifica o fim da rodada."""
    state = games[room]
    
    # Determinar vencedor da mão
    card_values = [item["card"] for item in state["table"]]
    if 0 in card_values and 11 in card_values: # Porcão e Zap
        winner_item = next(item for item in state["table"] if item["card"] == 0)
    else:
        winner_item = max(state["table"], key=lambda item: item["card"])
    
    winner_sid = winner_item["sid"]
    winner_number = state["players"][winner_sid]["number"]

    if winner_number in [1, 3]:
        state["team1_hand_wins"] += 1
    else:
        state["team2_hand_wins"] += 1
        
    # Definir quem começa a próxima mão
    winner_idx_in_order = state["player_order"].index(winner_sid)
    # Reorganiza a ordem para o vencedor começar
    state["player_order"] = state["player_order"][winner_idx_in_order:] + state["player_order"][:winner_idx_in_order]
    
    # Verificar se a rodada acabou
    if state["team1_hand_wins"] >= 2 or state["team2_hand_wins"] >= 2:
        state["round_winner_team"] = 1 if state["team1_hand_wins"] >= 2 else 2
        state["game_started"] = False # Pausa o jogo até ser reiniciado
    else:
        # Prepara para a próxima mão
        socketio.sleep(3) # Pausa para os jogadores verem o resultado
        start_new_hand(room)

# --- Rota HTTP Principal ---
@app.route('/')
def index():
    """Serve a página principal do jogo."""
    return render_template('index.html')

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
