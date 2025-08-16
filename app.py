import eventlet
eventlet.monkey_patch()

import os
from threading import RLock
from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, leave_room, emit
import random

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = os.urandom(24)
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

# --- NOVO SISTEMA DE CARTAS ---
CARD_DATA = {
    # Manilhas
    'zap.png': {'value': 11, 'name': 'Zap'},
    'copas.png': {'value': 10, 'name': 'Copas'},
    'espadilha.png': {'value': 9, 'name': 'Espadilha'},
    'ouros.png': {'value': 8, 'name': 'Ouros'},
    # Especiais
    'coringa.png': {'value': 7, 'name': 'Coringa'},
    'porcao.png': {'value': 0, 'name': 'Porcão'},
    # Comuns
    '3_of_clubs.png': {'value': 6, 'name': '3 de Paus'}, '3_of_diamonds.png': {'value': 6, 'name': '3 de Ouros'}, '3_of_hearts.png': {'value': 6, 'name': '3 de Copas'}, '3_of_spades.png': {'value': 6, 'name': '3 de Espadas'},
    '2_of_clubs.png': {'value': 5, 'name': '2 de Paus'}, '2_of_diamonds.png': {'value': 5, 'name': '2 de Ouros'}, '2_of_hearts.png': {'value': 5, 'name': '2 de Copas'}, '2_of_spades.png': {'value': 5, 'name': '2 de Espadas'},
    'ace_of_clubs.png': {'value': 4, 'name': 'Ás de Paus'}, 'ace_of_diamonds.png': {'value': 4, 'name': 'Ás de Ouros'}, 'ace_of_hearts.png': {'value': 4, 'name': 'Ás de Copas'},
    'king_of_clubs.png': {'value': 3, 'name': 'Rei de Paus', 'is_royal': True}, 'king_of_diamonds.png': {'value': 3, 'name': 'Rei de Ouros', 'is_royal': True}, 'king_of_hearts.png': {'value': 3, 'name': 'Rei de Copas', 'is_royal': True}, 'king_of_spades.png': {'value': 3, 'name': 'Rei de Espadas', 'is_royal': True},
    'jack_of_clubs.png': {'value': 2, 'name': 'Valete de Paus', 'is_royal': True}, 'jack_of_diamonds.png': {'value': 2, 'name': 'Valete de Ouros', 'is_royal': True}, 'jack_of_hearts.png': {'value': 2, 'name': 'Valete de Copas', 'is_royal': True}, 'jack_of_spades.png': {'value': 2, 'name': 'Valete de Espadas', 'is_royal': True},
    'queen_of_clubs.png': {'value': 1, 'name': 'Dama de Paus', 'is_royal': True}, 'queen_of_diamonds.png': {'value': 1, 'name': 'Dama de Ouros', 'is_royal': True}, 'queen_of_hearts.png': {'value': 1, 'name': 'Dama de Copas', 'is_royal': True}, 'queen_of_spades.png': {'value': 1, 'name': 'Dama de Espadas', 'is_royal': True},
    # Carta Virada
    'virada.png': {'value': -1, 'name': 'Carta Virada'}
}
FULL_DECK = list(CARD_DATA.keys())
FULL_DECK.remove('virada.png') # Não deve ser distribuída

games = {}
games_lock = RLock()

def create_new_game_state():
    return {
        "player_slots": [None, None, None, None], "player_order": [], "table": [],
        "hands_history": [], "current_player_idx": 0, "team1_hand_wins": 0,
        "team2_hand_wins": 0, "tied_hands": 0, "first_hand_winner_team": None,
        "hand_of_round": 1, "game_started": False, "round_over": False,
        "round_winner_team": None, "team1_score": 0, "team2_score": 0,
        "game_winner": None, "round_value": 1, "truco_state": "none",
        "truco_asker_team": None
    }

def get_views_for_all_players(room_name):
    views = {}
    with games_lock:
        state = games.get(room_name)
        if not state: return {}
        
        player_sids = [p['sid'] for p in state["player_slots"] if p and p['is_connected']]
        for sid in player_sids:
            player_slot_idx = next((i for i, p in enumerate(state["player_slots"]) if p and p['sid'] == sid), -1)
            if player_slot_idx == -1: continue
            
            player_info = state["player_slots"][player_slot_idx]
            player_team = 1 if player_slot_idx in [0, 2] else 2
            partner_idx = (player_slot_idx + 2) % 4
            partner_info = state["player_slots"][partner_idx]

            current_player_sid = state["player_order"][state["current_player_idx"]] if state["game_started"] and len(state["player_order"]) > state["current_player_idx"] else None
            current_player_info = next((p for p in state["player_slots"] if p and p['sid'] == current_player_sid), None)
            current_player_team = -1
            if current_player_info:
                current_player_slot_idx = next(i for i, p in enumerate(state["player_slots"]) if p and p['sid'] == current_player_sid)
                current_player_team = 1 if current_player_slot_idx in [0, 2] else 2

            is_my_turn = (state["game_started"] and current_player_sid == sid)
            is_my_teams_turn = (state["game_started"] and player_team == current_player_team)

            views[sid] = {
                "isMyTurn": is_my_turn, "isMyTeamsTurn": is_my_teams_turn, "myCards": player_info["cards"],
                "myName": player_info["name"], "myPlayerNumber": player_slot_idx + 1, "myTeam": player_team,
                "partnerName": partner_info["name"] if partner_info else "Aguardando...",
                "gameStarted": state["game_started"], "placar": {"time1": state["team1_score"], "time2": state["team2_score"]},
                "handPlacar": {"time1": state["team1_hand_wins"], "time2": state["team2_hand_wins"]},
                "mao": state["hand_of_round"], "jogadorDaVez": current_player_info['name'] if current_player_info else None,
                "mesa": [{"player": p["name"], "card": CARD_DATA.get(item["card_filename"], {}).get('name', '??')} for item in state["table"] for p in state["player_slots"] if p and p['sid'] == item['sid']],
                "handsHistory": [[{"player": p["name"], "card": CARD_DATA.get(card_item["card_filename"], {}).get('name', '??')} for card_item in hand for p in state["player_slots"] if p and p['sid'] == card_item['sid']] for hand in state["hands_history"]],
                "connected_players": [p["name"] for p in state["player_slots"] if p],
                "roundOver": state["round_over"], "roundWinner": state["round_winner_team"],
                "gameWinner": state["game_winner"], "roundValue": state["round_value"],
                "trucoState": state["truco_state"], "trucoAskerTeam": state["truco_asker_team"]
            }
    return views

def broadcast_state(room_name):
    player_views = get_views_for_all_players(room_name)
    for sid, view in player_views.items():
        socketio.emit('update_state', view, to=sid)

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('join')
def on_join(data):
    room, name, sid = data['room'], data['name'], request.sid
    join_room(room)
    game_should_start = False
    with games_lock:
        if room not in games: games[room] = create_new_game_state()
        state = games[room]
        reconnected_player = next((p for p in state["player_slots"] if p and p['name'] == name and not p['is_connected']), None)
        if reconnected_player:
            reconnected_player['sid'], reconnected_player['is_connected'] = sid, True
            print(f"Jogador {name} reconectou-se à sala {room}")
        elif len([p for p in state["player_slots"] if p]) < 4 and not any(p and p['name'] == name for p in state["player_slots"]):
            available_slot = next((i for i, v in enumerate(state["player_slots"]) if v is None), None)
            if available_slot is not None:
                state["player_slots"][available_slot] = {"sid": sid, "name": name, "cards": [], "is_connected": True}
                print(f"Jogador {name} (P{available_slot+1}) entrou na sala {room}")
                if len([p for p in state["player_slots"] if p]) == 4:
                    game_should_start = True
    if game_should_start:
        start_new_round(room)
    broadcast_state(room)

@socketio.on('play_card')
def on_play_card(data):
    room, card_index, sid = data['room'], data['card_index'], request.sid
    is_hidden = data.get('is_hidden', False)
    hand_is_over = False
    with games_lock:
        state = games.get(room, {})
        if not state.get("game_started"): return
        player_info = next((p for p in state["player_slots"] if p and p['sid'] == sid), None)
        is_my_turn = state["player_order"][state["current_player_idx"]] == sid
        if not player_info or not is_my_turn or not (0 <= card_index < len(player_info["cards"])): return
        if is_hidden and state['hand_of_round'] == 1: return
        
        card_filename = player_info["cards"].pop(card_index)
        card_value = CARD_DATA['virada.png']['value'] if is_hidden else CARD_DATA[card_filename]['value']
        
        state["table"].append({"sid": sid, "card_value": card_value, "card_filename": card_filename if not is_hidden else 'virada.png'})
        state["current_player_idx"] += 1
        if len(state["table"]) == 4: hand_is_over = True
    if hand_is_over:
        socketio.sleep(1)
        end_hand(room)
    broadcast_state(room)

# (O resto do app.py, a partir de 'disconnect', permanece igual)
@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    with games_lock:
        room_to_update = None
        for room, state in games.items():
            player = next((p for p in state["player_slots"] if p and p['sid'] == sid), None)
            if player:
                print(f"Jogador {player['name']} desconectou-se da sala {room}")
                player['is_connected'] = False
                room_to_update = room
                if state['truco_state'] != 'none':
                    state['truco_state'] = 'none'
                    state['round_value'] = 1
                break
    if room_to_update: broadcast_state(room_to_update)

@socketio.on('request_new_round')
def on_request_new_round(data):
    room = data['room']
    with games_lock:
        state = games.get(room)
        if state and state['round_over'] and not state['game_winner']:
            print(f"A iniciar nova rodada para a sala {room}")
            start_new_round(room)
    broadcast_state(room)

@socketio.on('call_truco')
def on_call_truco(data):
    room, sid = data['room'], request.sid
    with games_lock:
        state = games.get(room)
        if not state['game_started'] or state['hand_of_round'] == 1: return
        player_slot_idx = next((i for i, p in enumerate(state["player_slots"]) if p and p['sid'] == sid), -1)
        player_team = 1 if player_slot_idx in [0, 2] else 2
        current_player_sid = state["player_order"][state["current_player_idx"]]
        current_player_slot_idx = next(i for i, p in enumerate(state["player_slots"]) if p and p['sid'] == current_player_sid)
        current_player_team = 1 if current_player_slot_idx in [0, 2] else 2
        if player_team != current_player_team: return
        if state['truco_state'] == 'none':
            state['truco_state'], state['round_value'], state['truco_asker_team'] = 'pending', 3, player_team
        elif state['truco_state'] in ['pending', '6', '9'] and state['truco_asker_team'] != player_team:
            if state['round_value'] == 3: state['round_value'], state['truco_state'] = 6, '6'
            elif state['round_value'] == 6: state['round_value'], state['truco_state'] = 9, '9'
            elif state['round_value'] == 9: state['round_value'], state['truco_state'] = 12, '12'
            state['truco_asker_team'] = player_team
    broadcast_state(room)

@socketio.on('respond_truco')
def on_respond_truco(data):
    room, response = data['room'], data['response']
    with games_lock:
        state = games.get(room)
        if state['truco_state'] == 'none': return
        if response == 'accept':
            state['truco_state'] = 'none'
        elif response == 'refuse':
            winner_team = state['truco_asker_team']
            points = 1 if state['round_value'] == 3 else (state['round_value'] // 2)
            if winner_team == 1: state['team1_score'] += points
            else: state['team2_score'] += points
            state['round_over'], state['game_started'] = True, False
            state['truco_state'] = 'none'
            check_for_game_winner(state)
    broadcast_state(room)

def start_new_round(room):
    with games_lock:
        state = games[room]
        state.update({"game_started": True, "round_over": False, "round_winner_team": None, "team1_hand_wins": 0, "team2_hand_wins": 0, "tied_hands": 0, "first_hand_winner_team": None, "round_value": 1, "truco_state": "none", "hands_history": []})
        if not state["player_order"]:
            state["player_order"] = [p['sid'] for p in state["player_slots"] if p]
        else:
            state["player_order"] = state["player_order"][1:] + state["player_order"][:1]
        deck = FULL_DECK[:]
        random.shuffle(deck)
        while True:
            all_hands_ok, temp_deck, dealt_cards = True, deck[:], {}
            for slot in state["player_slots"]:
                if slot: dealt_cards[slot['sid']] = [temp_deck.pop() for _ in range(3)]
            for sid, hand in dealt_cards.items():
                if all(CARD_DATA[card].get('is_royal', False) for card in hand):
                    print(f"Mão de figuras para {next(p['name'] for p in state['player_slots'] if p and p['sid'] == sid)}. Re-embaralhando...")
                    deck = [card for card in deck if card not in hand]
                    random.shuffle(deck)
                    all_hands_ok = False
                    break
            if all_hands_ok:
                for sid, hand in dealt_cards.items():
                    player_slot = next(p for p in state["player_slots"] if p and p['sid'] == sid)
                    player_slot["cards"] = sorted(hand, key=lambda c: CARD_DATA[c]['value'], reverse=True)
                break
        start_new_hand(room, state)

def start_new_hand(room, state):
    state["table"], state["current_player_idx"] = [], 0
    state["hand_of_round"] = state["team1_hand_wins"] + state["team2_hand_wins"] + state["tied_hands"] + 1

def end_hand(room):
    with games_lock:
        state = games[room]
        state['hands_history'].append(list(state['table']))
        
        highest_card_val, winners = -2, []
        for item in state["table"]:
            if item['card_value'] > highest_card_val: highest_card_val, winners = item['card_value'], [item]
            elif item['card_value'] == highest_card_val: winners.append(item)
        
        hand_winner_team = None
        if len(winners) > 1:
            winner_sids = [w['sid'] for w in winners]
            winner_teams = [1 if next(i for i, p in enumerate(state["player_slots"]) if p and p['sid'] == sid) in [0, 2] else 2 for sid in winner_sids]
            if len(set(winner_teams)) == 1: hand_winner_team = winner_teams[0]
            else: state['tied_hands'] += 1
        else:
            winner_sid = winners[0]["sid"]
            winner_slot_idx = next(i for i, p in enumerate(state["player_slots"]) if p and p['sid'] == winner_sid)
            hand_winner_team = 1 if winner_slot_idx in [0, 2] else 2
        
        if hand_winner_team:
            if hand_winner_team == 1: state["team1_hand_wins"] += 1
            else: state["team2_hand_wins"] += 1
            if state['hand_of_round'] == 1: state['first_hand_winner_team'] = hand_winner_team
        
        winner_sid_to_start = winners[0]["sid"]
        winner_idx_in_order = state["player_order"].index(winner_sid_to_start)
        state["player_order"] = state["player_order"][winner_idx_in_order:] + state["player_order"][:winner_idx_in_order]

        round_over, round_winner = False, None
        if state["team1_hand_wins"] >= 2: round_winner = 1
        elif state["team2_hand_wins"] >= 2: round_winner = 2
        elif state['tied_hands'] > 0:
            if state['hand_of_round'] == 1: pass
            elif state['hand_of_round'] >= 2: round_winner = state['first_hand_winner_team']
        elif state['hand_of_round'] == 3:
            round_winner = 1 if state['team1_hand_wins'] > state['team2_hand_wins'] else 2
        
        if round_winner:
            state.update({"round_over": True, "game_started": False, "round_winner_team": round_winner})
            if round_winner == 1: state["team1_score"] += state["round_value"]
            else: state["team2_score"] += state["round_value"]
            check_for_game_winner(state)
        else:
            socketio.sleep(3)
            start_new_hand(room, state)
    broadcast_state(room)

def check_for_game_winner(state):
    if state["team1_score"] >= 12: state["game_winner"] = 1
    elif state["team2_score"] >= 12: state["game_winner"] = 2

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
