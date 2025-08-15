# These two lines MUST be the absolute first lines of code.
import eventlet
eventlet.monkey_patch()

import os
from threading import RLock
from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, leave_room, emit
import random

# --- Configuração da Aplicação ---
app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = os.urandom(24)
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

# --- Constantes do Jogo ---
CARD_NAMES = {
    0: "Porcão", 1: "Q", 2: "J", 3: "K", 4: "A", 5: "2", 6: "3",
    7: "Coringa", 8: "Ouros", 9: "Espadilha", 10: "Copão", 11: "Zap"
}
FULL_DECK = [
    0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 5, 5, 5, 5,
    7, 8, 9, 10, 11
]

# --- Gestão de Estado Global ---
games = {}
games_lock = RLock()

def create_new_game_state():
    return {"players": {}, "player_order": [], "table": [], "current_player_idx": 0, "team1_hand_wins": 0, "team2_hand_wins": 0, "hand_of_round": 1, "game_started": False, "round_winner_team": None}

def get_views_for_all_players(room_name):
    views = {}
    with games_lock:
        state = games.get(room_name)
        if not state: return {}
        for sid in state["players"]:
            player_info = state["players"].get(sid)
            if not player_info: continue
            is_my_turn = (state["game_started"] and len(state["player_order"]) > state["current_player_idx"] and state["player_order"][state["current_player_idx"]] == sid)
            current_player_sid_on_turn = state["player_order"][state["current_player_idx"]] if state["game_started"] and len(state["player_order"]) > state["current_player_idx"] else None
            views[sid] = {
                "isMyTurn": is_my_turn, "myCards": player_info["cards"], "myPlayerNumber": player_info["number"],
                "gameStarted": state["game_started"], "placar": {"time1": state["team1_hand_wins"], "time2": state["team2_hand_wins"]},
                "mao": state["hand_of_round"], "jogadorDaVez": state["players"][current_player_sid_on_turn]['number'] if current_player_sid_on_turn else None,
                "mesa": [{"player": state["players"][item["sid"]]["number"], "card": CARD_NAMES.get(item["card"], "??")} for item in state["table"]],
                "connected_players_count": len(state["players"]), "roundWinner": state["round_winner_team"]
            }
    return views

def broadcast_state(room_name):
    player_views = get_views_for_all_players(room_name)
    for sid, view in player_views.items():
        socketio.emit('update_state', view, to=sid)

# --- Rota HTTP Principal ---
@app.route('/')
def index():
    return render_template('index.html')

# --- Eventos do Socket.IO ---
@socketio.on('join')
def on_join(data):
    room = data['room']
    sid = request.sid
    join_room(room)
    game_should_start = False
    with games_lock:
        if room not in games:
            games[room] = create_new_game_state()
        state = games[room]
        if sid not in state["players"] and len(state["players"]) < 4:
            player_number = len(state["players"]) + 1
            state["players"][sid] = {"number": player_number, "cards": [], "sid": sid}
            state["player_order"].append(sid)
            print(f"Jogador {player_number} ({sid}) entrou na sala {room}")
            if len(state["players"]) == 4:
                game_should_start = True
    if game_should_start:
        print(f"SALA {room} CHEIA! A iniciar o jogo...")
        start_new_round(room)
    broadcast_state(room)

@socketio.on('play_card')
def on_play_card(data):
    room = data['room']
    card_index = data['card_index']
    sid = request.sid
    hand_is_over = False
    with games_lock:
        state = games.get(room, {})
        player_info = state.get("players", {}).get(sid)
        is_my_turn = state.get("game_started", False) and state["player_order"][state["current_player_idx"]] == sid
        if not player_info or not is_my_turn or not (0 <= card_index < len(player_info["cards"])):
            return
        card = player_info["cards"].pop(card_index)
        state["table"].append({"sid": sid, "card": card})
        state["current_player_idx"] += 1
        if len(state["table"]) == 4:
            hand_is_over = True
    if hand_is_over:
        socketio.sleep(1)
        end_hand(room)
    broadcast_state(room)

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    room_to_update = None
    with games_lock:
        for room, state in games.items():
            if sid in state["players"]:
                print(f"A remover jogador da sala {room}")
                state["player_order"].remove(sid)
                del state["players"][sid]
                room_to_update = room
                state["game_started"] = False 
                break
    if room_to_update:
        if not games[room_to_update]["players"]:
            print(f"A sala {room_to_update} está vazia. A remover.")
            del games[room_to_update]
        else:
            broadcast_state(room_to_update)

# --- Funções de Lógica de Jogo ---
def start_new_round(room):
    with games_lock:
        state = games[room]
        state["game_started"] = True
        state["round_winner_team"] = None
        state["team1_hand_wins"] = 0
        state["team2_hand_wins"] = 0
        state["player_order"] = state["player_order"][1:] + state["player_order"][:1]
        
        deck = FULL_DECK[:]
        random.shuffle(deck)
        for player_sid in state["player_order"]:
            state["players"][player_sid]["cards"] = sorted([deck.pop() for _ in range(3)], reverse=True)
            
        start_new_hand(room, state)

def start_new_hand(room, state):
    state["table"] = []
    state["current_player_idx"] = 0
    state["hand_of_round"] = state["team1_hand_wins"] + state["team2_hand_wins"] + 1

def end_hand(room):
    round_is_over = False
    with games_lock:
        state = games[room]
        card_values = [item["card"] for item in state["table"]]
        if 0 in card_values and 11 in card_values:
            winner_item = next(item for item in state["table"] if item["card"] == 0)
        else:
            winner_item = max(state["table"], key=lambda item: item["card"])
        winner_sid = winner_item["sid"]
        winner_number = state["players"][winner_sid]["number"]
        if winner_number in [1, 3]: state["team1_hand_wins"] += 1
        else: state["team2_hand_wins"] += 1
        winner_idx_in_order = state["player_order"].index(winner_sid)
        state["player_order"] = state["player_order"][winner_idx_in_order:] + state["player_order"][:winner_idx_in_order]
        
        if state["team1_hand_wins"] >= 2 or state["team2_hand_wins"] >= 2:
            state["round_winner_team"] = 1 if state["team1_hand_wins"] >= 2 else 2
            state["game_started"] = False
            round_is_over = True
            print(f"Fim da rodada! Time {state['round_winner_team']} venceu!")
    
    if not round_is_over:
        socketio.sleep(3)
        with games_lock:
            start_new_hand(room, games[room])
        broadcast_state(room)
    else:
        broadcast_state(room)
        
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
