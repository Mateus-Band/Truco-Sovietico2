from flask import Flask, jsonify, request
import random
import os
from threading import Lock

app = Flask(__name__)
app_lock = Lock()
# --- Definições do jogo ---
nomes_cartas = {
    0: "Porcão", 1: "Q", 2: "J", 3: "K", 4: "A", 5: "2", 6: "3",
    7: "Coringa", 8: "Ouros", 9: "Espadilha", 10: "Copão", 11: "Zap"
}

# Variáveis globais protegidas por lock
game_state = {
    'cartas_disponiveis': [],
    'jogadores': [[] for _ in range(4)],
    'mesa': [],
    'vez': 0,
    'ti1': 0,
    'ti2': 0,
    'rodada_atual': 1,
    'jogo_iniciado': False
}

# --- Funções do jogo ---
def resetar_cartas():
    game_state['cartas_disponiveis'] = [
        0, 1, 1, 1, 1, 2, 2, 2, 2,
        3, 3, 3, 3, 4, 4, 4, 5, 5, 5, 5,
        7, 8, 9, 10, 11
    ]
    random.shuffle(game_state['cartas_disponiveis'])

def distribuir():
    """Distribui 3 cartas para cada jogador"""
    for p in game_state['jogadores']:
        p.clear()
        for _ in range(3):
            if game_state['cartas_disponiveis']:
                p.append(game_state['cartas_disponiveis'].pop())

def reiniciar_rodada():
    """Reinicia completamente uma nova rodada"""
    with app_lock:
        resetar_cartas()
        distribuir()
        game_state['mesa'] = []
        game_state['vez'] = 0
        game_state['ti1'] = 0
        game_state['ti2'] = 0
        game_state['rodada_atual'] = 1
        game_state['jogo_iniciado'] = True

def iniciar_novo_turno():
    """Prepara um novo turno dentro da mesma rodada"""
    with app_lock:
        game_state['mesa'] = []
        game_state['vez'] = 0
        # Não resetamos o placar ou rodada aqui
        if len(game_state['cartas_disponiveis']) >= 12:  # Tem cartas suficientes?
            distribuir()
        else:
            resetar_cartas()
            distribuir()

def determinar_ganhador():
    valores = [c for _, c in game_state['mesa']]
    if 0 in valores and 11 in valores:  # Porcão e Zap
        return [i for i, c in game_state['mesa'] if c == 0][0]
    maior = max(valores)
    return [i for i, c in game_state['mesa'] if c == maior][0]

def jogar(indice):
    with app_lock:
        if not game_state['jogo_iniciado']:
            return "Jogo não iniciado. Clique em Iniciar Jogo."
        
        if game_state['vez'] > 3:
            return "Aguardando novo turno."
        
        if indice < 0 or indice >= len(game_state['jogadores'][game_state['vez']]):
            return "Índice de carta inválido."
        
        # Jogador joga uma carta
        carta = game_state['jogadores'][game_state['vez']].pop(indice)
        game_state['mesa'].append((game_state['vez'], carta))
        game_state['vez'] += 1

        # Verifica se todos jogaram
        if game_state['vez'] == 4:
            ganhador = determinar_ganhador()
            if ganhador in [0, 2]:
                game_state['ti1'] += 1
            else:
                game_state['ti2'] += 1
            
            # Verifica se alguém ganhou a rodada
            if game_state['ti1'] >= 2 or game_state['ti2'] >= 2:
                resultado = f"Time {1 if game_state['ti1'] >= 2 else 2} venceu a rodada!"
                reiniciar_rodada()
                return resultado
            
            # Prepara novo turno
            game_state['rodada_atual'] += 1
            iniciar_novo_turno()
            return "Novo turno iniciado!"
        
        return "Carta jogada com sucesso!"

# --- Rotas da API ---
@app.route('/cartas')
def get_cartas():
    if not game_state['jogo_iniciado']:
        return jsonify(cartas=["Jogo não iniciado"], status="aguardando")
    
    if game_state['vez'] > 3:
        return jsonify(cartas=["Aguardando novo turno"], status="espera")
    
    cartas = game_state['jogadores'][game_state['vez']]
    nomes = [nomes_cartas[c] for c in cartas]
    return jsonify(cartas=nomes, status="ativo", vez=game_state['vez']+1)

@app.route('/jogar/<int:indice>', methods=['POST'])
def jogar_carta(indice):
    if game_state['vez'] > 3 or indice < 0 or indice >= len(game_state['jogadores'][game_state['vez']]):
        return jsonify(resultado="Jogada inválida.")
    resultado = jogar(indice)
    return jsonify(resultado=resultado)

@app.route('/iniciar', methods=['POST'])
def iniciar():
    reiniciar_rodada()
    return jsonify(mensagem="Jogo iniciado!", status="sucesso")

@app.route('/resetar', methods=['POST'])
def resetar():
    reiniciar_rodada()
    return jsonify(mensagem="Jogo resetado com sucesso!", status="sucesso")

@app.route('/placar')
def placar():
    return jsonify(
        time1=game_state['ti1'],
        time2=game_state['ti2'],
        rodada=game_state['rodada_atual'],
        jogo_iniciado=game_state['jogo_iniciado']
    )

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)