from flask import Flask, jsonify
import random
import os
from threading import Lock

# --- Constantes do Jogo ---
NUM_PLAYERS = 4
CARDS_PER_HAND = 3
HANDS_TO_WIN_ROUND = 2

CARD_NAMES = {
    0: "Porcão", 1: "Q", 2: "J", 3: "K", 4: "A", 5: "2", 6: "3",
    7: "Coringa", 8: "Ouros", 9: "Espadilha", 10: "Copão", 11: "Zap"
}

# O baralho completo, conforme a definição original.
FULL_DECK = [
    0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 5, 5, 5, 5,
    7, 8, 9, 10, 11
]

class TrucoGame:
    """Encapsula todo o estado e lógica do jogo de Truco."""

    def __init__(self):
        """Inicializa o jogo."""
        self.lock = Lock()
        self.reset_full_game()

    def reset_full_game(self):
        """Reseta o jogo para um estado não iniciado."""
        with self.lock:
            self.jogo_iniciado = False
            self.round_winner_team = None
            self._reset_round_state()

    def start_new_round(self):
        """Inicia uma nova rodada, distribuindo cartas e resetando placares da rodada."""
        with self.lock:
            self.jogo_iniciado = True
            self.round_winner_team = None
            self._reset_round_state()
            self._prepare_deck()
            self._distribute_cards()
            return {"mensagem": "Uma nova rodada começou!", "status": "sucesso"}

    def _reset_round_state(self):
        """Limpa o estado para uma nova rodada (mesa, placar da rodada, etc.)."""
        self.deck = []
        self.players = [[] for _ in range(NUM_PLAYERS)]
        self.table = []
        self.current_player_idx = 0
        self.team1_hand_wins = 0
        self.team2_hand_wins = 0
        self.hand_of_round = 1

    def _prepare_deck(self):
        """Prepara o baralho, embaralhando as cartas."""
        self.deck = FULL_DECK[:]
        random.shuffle(self.deck)

    def _distribute_cards(self):
        """
        Distribui cartas para os jogadores.
        Regra original mantida: Se não houver cartas suficientes, o baralho é reembaralhado.
        """
        if len(self.deck) < NUM_PLAYERS * CARDS_PER_HAND:
            self._prepare_deck()

        for i in range(NUM_PLAYERS):
            # A regra original de limpar e redistribuir a cada mão é mantida.
            self.players[i].clear()
            for _ in range(CARDS_PER_HAND):
                self.players[i].append(self.deck.pop())

    def play_card(self, card_index):
        """Processa a jogada de um jogador."""
        with self.lock:
            if not self.jogo_iniciado or self.current_player_idx >= NUM_PLAYERS:
                return {"resultado": "Jogada inválida ou fora de hora."}

            player_hand = self.players[self.current_player_idx]
            if not 0 <= card_index < len(player_hand):
                return {"resultado": "Índice da carta é inválido."}

            card = player_hand.pop(card_index)
            self.table.append({'player_idx': self.current_player_idx, 'card': card})
            self.current_player_idx += 1

            if self.current_player_idx == NUM_PLAYERS:
                return self._end_hand()  # Todos os 4 jogadores jogaram.

            return {"resultado": "Carta jogada. Aguardando próximo jogador."}

    def _end_hand(self):
        """Finaliza uma mão, determina o vencedor e verifica se a rodada acabou."""
        hand_winner_idx = self._get_hand_winner()
        winner_name = f"Jogador {hand_winner_idx + 1}"

        if hand_winner_idx in [0, 2]:
            self.team1_hand_wins += 1
        else:
            self.team2_hand_wins += 1

        if self.team1_hand_wins >= HANDS_TO_WIN_ROUND:
            self.round_winner_team = 1
            self.jogo_iniciado = False
            return {"resultado": f"{winner_name} venceu a mão! Time 1 venceu a rodada!"}

        if self.team2_hand_wins >= HANDS_TO_WIN_ROUND:
            self.round_winner_team = 2
            self.jogo_iniciado = False
            return {"resultado": f"{winner_name} venceu a mão! Time 2 venceu a rodada!"}

        self._start_new_hand()
        return {"resultado": f"{winner_name} venceu a mão! Começando a próxima mão."}

    def _start_new_hand(self):
        """
        Prepara para a próxima mão dentro da mesma rodada.
        Regra original mantida: a mesa é limpa e novas cartas são distribuídas.
        """
        self.table = []
        self.current_player_idx = 0  # A vez sempre reinicia do jogador 0 na nova mão.
        self.hand_of_round += 1
        self._distribute_cards()

    def _get_hand_winner(self):
        """Determina o jogador que venceu a mão com base nas cartas da mesa."""
        cards_on_table = [(item['player_idx'], item['card']) for item in self.table]
        card_values = [card for _, card in cards_on_table]

        # Regra especial mantida: Porcão (0) vs Zap (11)
        if 0 in card_values and 11 in card_values:
            return next(player_idx for player_idx, card in cards_on_table if card == 0)

        # Regra padrão: a carta de maior valor vence.
        return max(cards_on_table, key=lambda item: item[1])[0]

    def get_state(self):
        """Monta e retorna um objeto com o estado completo e atual do jogo."""
        with self.lock:
            # O jogador da vez é quem está visualizando as cartas.
            player_id_for_view = self.current_player_idx if self.current_player_idx < NUM_PLAYERS else 0
            
            player_cards = self.players[player_id_for_view]
            player_card_names = [CARD_NAMES.get(c, "??") for c in player_cards]

            return jsonify({
                "jogoIniciado": self.jogo_iniciado,
                "placar": {
                    "time1": self.team1_hand_wins,
                    "time2": self.team2_hand_wins,
                },
                "mao": self.hand_of_round,
                "jogadorDaVez": self.current_player_idx + 1 if self.jogo_iniciado and self.current_player_idx < NUM_PLAYERS else None,
                "cartasDoJogador": player_card_names,
                "rodadaFinalizada": self.round_winner_team is not None,
                "vencedorDaRodada": self.round_winner_team
            })

# --- Rotas da API Flask ---
app = Flask(__name__)
game = TrucoGame()

@app.route('/state')
def get_game_state():
    """Endpoint único que provê todo o estado do jogo para o cliente."""
    return game.get_state()

@app.route('/jogar/<int:indice>', methods=['POST'])
def jogar_carta(indice):
    """Endpoint para um jogador jogar uma carta."""
    resultado = game.play_card(indice)
    return jsonify(resultado)

@app.route('/iniciar', methods=['POST'])
def iniciar():
    """Endpoint para iniciar uma nova rodada."""
    return jsonify(game.start_new_round())

@app.route('/resetar', methods=['POST'])
def resetar():
    """Endpoint para resetar o jogo completamente."""
    game.reset_full_game()
    return jsonify(mensagem="Jogo resetado com sucesso!", status="sucesso")

# Rotas antigas podem ser removidas ou desativadas, pois /state as substitui.
@app.route('/cartas')
def get_cartas_antigo():
    return jsonify(cartas=["Endpoint desativado, use /state"], status="obsoleto")

@app.route('/placar')
def get_placar_antigo():
    return jsonify(error="Endpoint desativado, use /state")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
