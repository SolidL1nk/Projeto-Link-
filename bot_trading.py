import pandas as pd
import os
import time
from binance.client import Client
from binance.enums import *
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging
from binance.exceptions import BinanceAPIException
import json
import matplotlib.pyplot as plt
import traceback
import sys
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
import discord

# Obtém o diretório base do projeto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Configuração de logging mais detalhada com suporte a codificação
logs_dir = os.path.join(BASE_DIR, "logs")
os.makedirs(logs_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(logs_dir, "bot_trading.log"), encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Definição da variável USE_EMOJI antes de ser usada
USE_EMOJI = True

# Verifica se está rodando no Windows e configura a codificação
if sys.platform.startswith('win'):
    # Tenta configurar a codificação do console para UTF-8
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleCP(65001)
        kernel32.SetConsoleOutputCP(65001)
    except:
        # Se falhar, remove emojis e caracteres especiais
        USE_EMOJI = False

# Função para substituir emojis por texto
def emoji(emoji_text, alt_text):
    if USE_EMOJI:
        return emoji_text
    else:
        return alt_text

# Carrega variáveis de ambiente
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Configurações da API Binance
api_key = os.getenv("KEY_BINANCE")
secret_key = os.getenv("SECRET_BINANCE")

# Configurações do bot
CONFIG = {
    "moedas": ["BTCUSDT", "SOLUSDT"],
    "periodo_candle": Client.KLINE_INTERVAL_1HOUR,
    "janela_media_curta": 7,
    "janela_media_longa": 40,
    "percentual_stop_loss": 0.04,  # 4% abaixo do preço de compra
    "percentual_take_profit": 0.05,  # 5% acima do preço de compra
    "intervalo_verificacao": 60 * 60,  # 1 hora em segundos
    "saldo_minimo_usdt": 20,  # Saldo mínimo para operar
    "max_tentativas_api": 3,  # Número máximo de tentativas para chamadas de API
    "modo_simulacao": False,  # Se True, não executa ordens reais
    "usar_rsi": True,  # Usar RSI como confirmação
    "limite_rsi_sobrevenda": 30,  # Limite de RSI para considerar sobrevenda
    "limite_rsi_sobrecompra": 70,  # Limite de RSI para considerar sobrecompra
    "arquivo_dados": os.path.join(BASE_DIR, "dados_bot.json"),
    "pasta_graficos": os.path.join(BASE_DIR, "graficos"),
    "discord_enabled": True,  # Habilita notificações via Discord
    "discord_channel_id": int(os.getenv("DISCORD_CHANNEL_ID", "0"))
}

# Cria pastas necessárias
os.makedirs(CONFIG["pasta_graficos"], exist_ok=True)
os.makedirs(logs_dir, exist_ok=True)

# Variáveis globais para comunicação entre módulos
cliente_binance = None
discord_client = None

# Inicializa o cliente Binance
def inicializar_binance():
    global cliente_binance
    
    # Verifica se as chaves de API estão definidas
    if not api_key or not secret_key:
        logging.error(f"{emoji('❌', '[ERRO]')} Chaves de API da Binance não encontradas no arquivo .env")
        logging.info("Crie um arquivo .env com KEY_BINANCE e SECRET_BINANCE")
        return False
    
    # Inicializa o cliente Binance com tratamento de erros
    try:
        cliente_binance = Client(api_key, secret_key)
        # Testa a conexão
        cliente_binance.get_account()
        logging.info(f"{emoji('✅', '[OK]')} Conexão com a Binance estabelecida com sucesso")
        return True
    except BinanceAPIException as e:
        logging.error(f"{emoji('❌', '[ERRO]')} Erro ao conectar com a Binance: {e}")
        return False
    except Exception as e:
        logging.error(f"{emoji('❌', '[ERRO]')} Erro desconhecido: {e}")
        return False

# Função para registrar o cliente Discord (será chamada pelo módulo principal)
def registrar_discord_client(client):
    global discord_client
    discord_client = client
    logging.info(f"{emoji('✅', '[OK]')} Cliente Discord registrado no módulo de trading")

# Função para enviar mensagem para o Discord
def enviar_discord(mensagem, arquivo=None):
    if not CONFIG["discord_enabled"] or discord_client is None:
        logging.warning(f"Discord não configurado ou desabilitado. Mensagem não enviada: {mensagem}")
        return
    
    try:
        canal = discord_client.get_channel(CONFIG["discord_channel_id"])
        if canal:
            # Cria uma tarefa assíncrona para enviar a mensagem
            discord_client.loop.create_task(enviar_mensagem_async(canal, mensagem, arquivo))
        else:
            logging.error(f"Canal Discord {CONFIG['discord_channel_id']} não encontrado")
    except Exception as e:
        logging.error(f"{emoji('❌', '[ERRO]')} Erro ao enviar mensagem para o Discord: {e}")
        logging.error(traceback.format_exc())

# Função assíncrona para enviar mensagem
async def enviar_mensagem_async(canal, mensagem, arquivo=None):
    try:
        if arquivo and os.path.exists(arquivo):
            await canal.send(mensagem, file=discord.File(arquivo))
            logging.info(f"Arquivo enviado para Discord: {arquivo}")
        else:
            if arquivo:
                logging.warning(f"Arquivo não encontrado: {arquivo}")
            await canal.send(mensagem)
    except Exception as e:
        logging.error(f"{emoji('❌', '[ERRO]')} Erro ao enviar mensagem assíncrona: {e}")
        logging.error(traceback.format_exc())

# Função para chamar API com retry
def chamar_api_com_retry(funcao, *args, **kwargs):
    for tentativa in range(1, CONFIG["max_tentativas_api"] + 1):
        try:
            return funcao(*args, **kwargs)
        except BinanceAPIException as e:
            logging.warning(f"Tentativa {tentativa}/{CONFIG['max_tentativas_api']}: Erro na API Binance: {e}")
            if tentativa == CONFIG["max_tentativas_api"]:
                logging.error(f"{emoji('❌', '[ERRO]')} Falha após {CONFIG['max_tentativas_api']} tentativas: {e}")
                raise
            time.sleep(2 ** tentativa)  # Espera exponencial
        except Exception as e:
            logging.error(f"{emoji('❌', '[ERRO]')} Erro inesperado: {e}")
            logging.debug(traceback.format_exc())
            raise

# Funções para manipulação de dados
def salvar_dados(dados):
    try:
        with open(CONFIG["arquivo_dados"], "w") as f:
            json.dump(dados, f, indent=4)
        logging.debug(f"{emoji('✅', '[OK]')} Dados salvos com sucesso em {CONFIG['arquivo_dados']}")
    except Exception as e:
        logging.error(f"{emoji('❌', '[ERRO]')} Erro ao salvar dados: {e}")
        logging.error(traceback.format_exc())

def carregar_dados():
    dados_padrao = {
        "posicoes": {moeda: False for moeda in CONFIG["moedas"]},
        "precos_compra": {moeda: 0 for moeda in CONFIG["moedas"]},
        "stop_losses": {moeda: 0 for moeda in CONFIG["moedas"]},
        "take_profits": {moeda: 0 for moeda in CONFIG["moedas"]},
        "ultima_alta_semanal": {moeda: 0 for moeda in CONFIG["moedas"]},
        "historico_operacoes": [],
        "historico_patrimonio": []
    }
    try:
        if os.path.exists(CONFIG["arquivo_dados"]):
            with open(CONFIG["arquivo_dados"], "r") as f:
                dados = json.load(f)
                # Garante que todas as chaves necessárias existam
                for chave, valor in dados_padrao.items():
                    if chave not in dados:
                        dados[chave] = valor
                    # Para dicionários aninhados, verifica cada moeda
                    if isinstance(valor, dict) and all(isinstance(k, str) for k in valor.keys()):
                        for moeda in CONFIG["moedas"]:
                            if moeda not in dados[chave]:
                                dados[chave][moeda] = dados_padrao[chave].get(moeda, 0 if chave != "posicoes" else False)
                return dados
        else:
            logging.info(f"Arquivo de dados não encontrado em {CONFIG['arquivo_dados']}. Criando novo arquivo.")
            salvar_dados(dados_padrao)
            return dados_padrao
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.warning(f"Erro ao carregar dados: {e}. Usando dados padrão.")
        return dados_padrao

def pegar_saldo():
    if cliente_binance is None:
        logging.error(f"{emoji('❌', '[ERRO]')} Cliente Binance não inicializado")
        return {"USDT": 0, "BTC": 0, "SOL": 0}
    
    saldo = {"USDT": 0}
    # Adiciona as moedas base (sem USDT)
    for moeda in CONFIG["moedas"]:
        moeda_base = moeda.replace("USDT", "")
        saldo[moeda_base] = 0
    
    try:
        conta = chamar_api_com_retry(cliente_binance.get_account)
        for ativo in conta['balances']:
            if ativo['asset'] in saldo:
                saldo[ativo['asset']] = float(ativo['free'])
    except Exception as e:
        logging.error(f"{emoji('❌', '[ERRO]')} Erro ao obter saldo: {e}")
    
    return saldo

def pegar_precos():
    if cliente_binance is None:
        logging.error(f"{emoji('❌', '[ERRO]')} Cliente Binance não inicializado")
        return {moeda: 0 for moeda in CONFIG["moedas"]}
    
    precos = {}
    for moeda in CONFIG["moedas"]:
        try:
            ticker = chamar_api_com_retry(cliente_binance.get_symbol_ticker, symbol=moeda)
            precos[moeda] = float(ticker['price'])
        except Exception as e:
            logging.error(f"{emoji('❌', '[ERRO]')} Erro ao obter preço de {moeda}: {e}")
            precos[moeda] = 0
    return precos

def atualizar_historico(dados):
    saldo = pegar_saldo()
    precos = pegar_precos()
    
    # Calcula o valor total em USDT
    total_usdt = saldo["USDT"]
    for moeda in CONFIG["moedas"]:
        moeda_base = moeda.replace("USDT", "")
        total_usdt += saldo[moeda_base] * precos[moeda]
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    dados.setdefault("historico_patrimonio", []).append({
        "timestamp": timestamp, 
        "saldo_total_usdt": total_usdt
    })
    
    # Mantém apenas os últimos 7 dias (168 horas)
    dados["historico_patrimonio"] = dados["historico_patrimonio"][-168:]
    return dados

def mostrar_valorizacao(dados):
    historico = dados.get("historico_patrimonio", [])
    if len(historico) < 2:
        logging.info("Histórico insuficiente para calcular valorização")
        return None, None
    
    atual = historico[-1]["saldo_total_usdt"]
    
    def buscar_antigo(horas):
        alvo = datetime.now() - timedelta(hours=horas)
        for item in reversed(historico):
            t = datetime.strptime(item["timestamp"], "%Y-%m-%d %H:%M:%S")
            if t <= alvo:
                return item["saldo_total_usdt"]
        return None
    
    antigo_24h = buscar_antigo(24)
    antigo_7d = buscar_antigo(24 * 7)
    
    variacao_24h = None
    variacao_7d = None
    
    if antigo_24h:
        variacao_24h = ((atual - antigo_24h) / antigo_24h) * 100
        logging.info(f"{emoji('📈', '[VALORIZACAO]')} Valorização em 24h: {variacao_24h:.2f}%")
    
    if antigo_7d:
        variacao_7d = ((atual - antigo_7d) / antigo_7d) * 100
        logging.info(f"{emoji('📊', '[VALORIZACAO]')} Valorização em 7 dias: {variacao_7d:.2f}%")
    
    return variacao_24h, variacao_7d

def pegar_dados(codigo, limit=100):
    if cliente_binance is None:
        logging.error(f"{emoji('❌', '[ERRO]')} Cliente Binance não inicializado")
        return pd.DataFrame()
    
    try:
        candles = chamar_api_com_retry(
            cliente_binance.get_klines,
            symbol=codigo,
            interval=CONFIG["periodo_candle"],
            limit=limit
        )
        
        df = pd.DataFrame(candles)
        df.columns = ["open_time", "open", "high", "low", "close", "volume", "close_time",
                      "quote_asset_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore"]
        
        # Converte tipos de dados
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")
        
        return df
    except Exception as e:
        logging.error(f"{emoji('❌', '[ERRO]')} Erro ao obter dados de {codigo}: {e}")
        return pd.DataFrame()

def calcular_indicadores(df):
    if df.empty:
        return df
    
    # Médias móveis
    df["media_curta"] = df["close"].rolling(window=CONFIG["janela_media_curta"]).mean()
    df["media_longa"] = df["close"].rolling(window=CONFIG["janela_media_longa"]).mean()
    
    # RSI (Relative Strength Index)
    if CONFIG["usar_rsi"]:
        delta = df['close'].diff()
        ganho = delta.where(delta > 0, 0)
        perda = -delta.where(delta < 0, 0)
        
        media_ganho = ganho.rolling(window=14).mean()
        media_perda = perda.rolling(window=14).mean()
        
        rs = media_ganho / media_perda
        df['rsi'] = 100 - (100 / (1 + rs))
    
    return df

def obter_lot_size(symbol):
    if cliente_binance is None:
        logging.error(f"{emoji('❌', '[ERRO]')} Cliente Binance não inicializado")
        return 0, 0, 0
    
    try:
        info = chamar_api_com_retry(cliente_binance.get_symbol_info, symbol=symbol)
        lot = next(f for f in info['filters'] if f['filterType'] == 'LOT_SIZE')
        notional = next(f for f in info['filters'] if f['filterType'] in ['MIN_NOTIONAL', 'NOTIONAL'])
        return float(lot['minQty']), float(lot['stepSize']), float(notional['minNotional'])
    except Exception as e:
        logging.error(f"{emoji('❌', '[ERRO]')} Erro ao obter lot_size para {symbol}: {e}")
        return 0, 0, 0

def ajustar_quantidade(symbol, quantidade, saldo_disponivel, preco):
    min_qty, step, min_notional = obter_lot_size(symbol)
    
    if min_qty == 0 or step == 0:
        return "0"
    
    quantidade = float(quantidade)
    
    # Ajusta para o step size
    quantidade = max(min_qty, round(quantidade // step * step, 8))
    
    # Limita ao saldo disponível
    quantidade = min(quantidade, saldo_disponivel / preco)
    
    # Verifica valor mínimo da ordem
    if quantidade * preco < min_notional:
        logging.warning(f"Valor da ordem ({quantidade * preco:.2f} USDT) abaixo do mínimo ({min_notional} USDT)")
        return "0"
    
    return f"{quantidade:.8f}".rstrip('0').rstrip('.')

def mostrar_grafico(df, symbol):
    if df.empty:
        logging.warning(f"Sem dados para gerar gráfico de {symbol}")
        return None
    
    try:
        plt.figure(figsize=(12, 8))
        
        # Subplot principal para preço e médias
        ax1 = plt.subplot(2, 1, 1)
        ax1.plot(df['close_time'], df['close'], label='Preço', color='blue')
        ax1.plot(df['close_time'], df['media_curta'], label=f'Média {CONFIG["janela_media_curta"]}', linestyle='--', color='green')
        ax1.plot(df['close_time'], df['media_longa'], label=f'Média {CONFIG["janela_media_longa"]}', linestyle='--', color='red')
        
        # Adiciona linhas para stop-loss e take-profit se estiver em posição
        dados = carregar_dados()
        if dados["posicoes"][symbol]:
            preco_compra = dados["precos_compra"][symbol]
            stop_loss = dados["stop_losses"][symbol]
            take_profit = dados["take_profits"][symbol]
            
            ax1.axhline(y=preco_compra, color='black', linestyle='-', alpha=0.5, label=f'Preço de Compra: {preco_compra:.2f}')
            ax1.axhline(y=stop_loss, color='red', linestyle=':', alpha=0.5, label=f'Stop-Loss: {stop_loss:.2f}')
            ax1.axhline(y=take_profit, color='green', linestyle=':', alpha=0.5, label=f'Take-Profit: {take_profit:.2f}')
        
        ax1.set_title(f'{symbol} - Análise Técnica')
        ax1.set_ylabel('Preço (USDT)')
        ax1.grid(True)
        ax1.legend()
        
        # Subplot para RSI
        if CONFIG["usar_rsi"] and 'rsi' in df.columns:
            ax2 = plt.subplot(2, 1, 2, sharex=ax1)
            ax2.plot(df['close_time'], df['rsi'], label='RSI', color='purple')
            ax2.axhline(y=CONFIG["limite_rsi_sobrecompra"], color='red', linestyle='--', alpha=0.5)
            ax2.axhline(y=CONFIG["limite_rsi_sobrevenda"], color='green', linestyle='--', alpha=0.5)
            ax2.set_ylabel('RSI')
            ax2.set_ylim(0, 100)
            ax2.grid(True)
            ax2.legend()
        
        plt.tight_layout()
        
        # Usa caminho absoluto para salvar o gráfico
        nome_arquivo = os.path.join(CONFIG["pasta_graficos"], f'grafico_{symbol}.png')
        plt.savefig(nome_arquivo)
        logging.info(f"{emoji('✅', '[OK]')} Gráfico salvo como {os.path.abspath(nome_arquivo)}")
        plt.close()
        
        # Verifica se o arquivo foi criado
        if os.path.exists(nome_arquivo):
            logging.info(f"Arquivo de gráfico confirmado: {nome_arquivo}")
        else:
            logging.error(f"Falha ao criar arquivo de gráfico: {nome_arquivo}")
        
        # Envia o gráfico para o Discord se habilitado
        if CONFIG["discord_enabled"]:
            mensagem = f"📊 **Gráfico atualizado de {symbol}**"
            enviar_discord(mensagem, nome_arquivo)
        
        return nome_arquivo
    except Exception as e:
        logging.error(f"{emoji('❌', '[ERRO]')} Erro ao gerar gráfico para {symbol}: {e}")
        logging.error(traceback.format_exc())
        return None

def atualizar_ultima_alta_semanal(dados):
    for moeda in CONFIG["moedas"]:
        try:
            # Obtém dados da última semana
            df = pegar_dados(moeda, limit=168)  # 7 dias * 24 horas
            if not df.empty:
                # Encontra o preço mais alto da semana
                preco_mais_alto = df['high'].max()
                dados["ultima_alta_semanal"][moeda] = preco_mais_alto
                logging.info(f"Última alta semanal de {moeda}: {preco_mais_alto:.2f} USDT")
        except Exception as e:
            logging.error(f"{emoji('❌', '[ERRO]')} Erro ao atualizar última alta semanal para {moeda}: {e}")
    return dados

def registrar_operacao(dados, moeda, tipo, quantidade, preco, motivo=""):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    operacao = {
        "timestamp": timestamp,
        "moeda": moeda,
        "tipo": tipo,
        "quantidade": quantidade,
        "preco": preco,
        "valor_total": float(quantidade) * preco,
        "motivo": motivo
    }
    dados.setdefault("historico_operacoes", []).append(operacao)
    
    # Envia notificação para o Discord
    if CONFIG["discord_enabled"]:
        emoji_op = "🟢" if tipo == "compra" else "🔴"
        mensagem = (
            f"{emoji_op} **{tipo.upper()} de {moeda}**\n"
            f"Quantidade: {quantidade}\n"
            f"Preço: {preco:.2f} USDT\n"
            f"Valor Total: {float(quantidade) * preco:.2f} USDT\n"
            f"Motivo: {motivo}"
        )
        enviar_discord(mensagem)
    
    return dados

def executar_compra(moeda, quantidade, preco_atual, dados, motivo=""):
    if cliente_binance is None:
        logging.error(f"{emoji('❌', '[ERRO]')} Cliente Binance não inicializado")
        return False, dados
    
    if CONFIG["modo_simulacao"]:
        logging.info(f"{emoji('🔸', '[SIMULACAO]')} Compra de {quantidade} {moeda} a {preco_atual:.2f} USDT")
        sucesso = True
    else:
        try:
            ordem = chamar_api_com_retry(
                cliente_binance.create_order,
                symbol=moeda,
                side=SIDE_BUY,
                type=ORDER_TYPE_MARKET,
                quantity=quantidade
            )
            logging.info(f"{emoji('✅', '[OK]')} Compra de {quantidade} {moeda} executada a {preco_atual:.2f} USDT")
            logging.debug(f"Detalhes da ordem: {ordem}")
            sucesso = True
        except Exception as e:
            logging.error(f"{emoji('❌', '[ERRO]')} Erro ao executar compra de {moeda}: {e}")
            sucesso = False
    
    if sucesso:
        # Atualiza dados da posição
        dados["posicoes"][moeda] = True
        dados["precos_compra"][moeda] = preco_atual
        dados["stop_losses"][moeda] = preco_atual * (1 - CONFIG["percentual_stop_loss"])
        dados["take_profits"][moeda] = preco_atual * (1 + CONFIG["percentual_take_profit"])
        
        # Registra a operação
        dados = registrar_operacao(dados, moeda, "compra", quantidade, preco_atual, motivo)
        
        # Salva os dados atualizados
        salvar_dados(dados)
    
    return sucesso, dados

def executar_venda(moeda, quantidade, preco_atual, dados, motivo=""):
    if cliente_binance is None:
        logging.error(f"{emoji('❌', '[ERRO]')} Cliente Binance não inicializado")
        return False, dados
    
    moeda_base = moeda.replace("USDT", "")
    
    if CONFIG["modo_simulacao"]:
        logging.info(f"{emoji('🔸', '[SIMULACAO]')} Venda de {quantidade} {moeda} a {preco_atual:.2f} USDT")
        sucesso = True
    else:
        try:
            ordem = chamar_api_com_retry(
                cliente_binance.create_order,
                symbol=moeda,
                side=SIDE_SELL,
                type=ORDER_TYPE_MARKET,
                quantity=quantidade
            )
            logging.info(f"{emoji('✅', '[OK]')} Venda de {quantidade} {moeda} executada a {preco_atual:.2f} USDT")
            logging.debug(f"Detalhes da ordem: {ordem}")
            sucesso = True
        except Exception as e:
            logging.error(f"{emoji('❌', '[ERRO]')} Erro ao executar venda de {moeda}: {e}")
            sucesso = False
    
    if sucesso:
        # Atualiza dados da posição
        dados["posicoes"][moeda] = False
        
        # Registra a operação
        dados = registrar_operacao(dados, moeda, "venda", quantidade, preco_atual, motivo)
        
        # Calcula lucro/prejuízo
        preco_compra = dados["precos_compra"][moeda]
        if preco_compra > 0:
            variacao_percentual = ((preco_atual - preco_compra) / preco_compra) * 100
            resultado = "LUCRO" if variacao_percentual >= 0 else "PREJUIZO"
            logging.info(f"{emoji('📈' if variacao_percentual >= 0 else '📉', '['+resultado+']')} Resultado: {variacao_percentual:.2f}% ({preco_atual - preco_compra:.2f} USDT)")
            
            # Envia resultado para o Discord
            if CONFIG["discord_enabled"]:
                emoji_resultado = "📈" if variacao_percentual >= 0 else "📉"
                mensagem = (
                    f"{emoji_resultado} **Resultado da operação {moeda}**\n"
                    f"{'Lucro' if variacao_percentual >= 0 else 'Prejuízo'}: {variacao_percentual:.2f}%\n"
                    f"Valor: {preco_atual - preco_compra:.2f} USDT"
                )
                enviar_discord(mensagem)
        
        # Salva os dados atualizados
        salvar_dados(dados)
    
    return sucesso, dados

def verificar_stop_loss_take_profit(dados):
    precos = pegar_precos()
    saldo = pegar_saldo()
    
    for moeda in CONFIG["moedas"]:
        moeda_base = moeda.replace("USDT", "")
        
        # Verifica se está em posição
        if dados["posicoes"][moeda]:
            preco_atual = precos[moeda]
            preco_compra = dados["precos_compra"][moeda]
            stop_loss = dados["stop_losses"][moeda]
            take_profit = dados["take_profits"][moeda]
            ultima_alta = dados["ultima_alta_semanal"][moeda]
            
            # Verifica se o preço atual está abaixo do stop-loss
            if preco_atual <= stop_loss:
                logging.info(f"{emoji('🔴', '[STOP-LOSS]')} Stop-Loss atingido para {moeda} a {preco_atual:.2f} USDT")
                
                # Calcula a quantidade disponível para venda
                quantidade = saldo[moeda_base]
                quantidade_ajustada = ajustar_quantidade(moeda, quantidade, quantidade, preco_atual)
                
                if float(quantidade_ajustada) > 0:
                    # Executa a venda
                    sucesso, dados = executar_venda(
                        moeda, 
                        quantidade_ajustada, 
                        preco_atual, 
                        dados, 
                        motivo="Stop-Loss"
                    )
            
            # Verifica se o preço atual está acima do take-profit
            # Ou se está acima da última alta semanal + 5%
            elif (preco_atual >= take_profit or 
                  (ultima_alta > 0 and preco_atual >= ultima_alta * 1.05)):
                
                motivo = "Take-Profit" if preco_atual >= take_profit else "Alta Semanal +5%"
                logging.info(f"{emoji('🟢', '[TAKE-PROFIT]')} {motivo} atingido para {moeda} a {preco_atual:.2f} USDT")
                
                # Calcula a quantidade disponível para venda
                quantidade = saldo[moeda_base]
                quantidade_ajustada = ajustar_quantidade(moeda, quantidade, quantidade, preco_atual)
                
                if float(quantidade_ajustada) > 0:
                    # Executa a venda
                    sucesso, dados = executar_venda(
                        moeda, 
                        quantidade_ajustada, 
                        preco_atual, 
                        dados, 
                        motivo=motivo
                    )
            
            # Verifica se está próximo do stop-loss ou take-profit para alertar
            elif CONFIG["discord_enabled"]:
                percentual_alerta = 0.02  # 2% de proximidade
                
                # Verifica proximidade do stop-loss
                diff_sl = (preco_atual - stop_loss) / preco_atual
                if 0 < diff_sl <= percentual_alerta:
                    mensagem = f"⚠️ **Alerta de proximidade de Stop-Loss**\n{moeda} está a {diff_sl*100:.2f}% do Stop-Loss ({stop_loss:.2f} USDT). Preço atual: {preco_atual:.2f} USDT"
                    enviar_discord(mensagem)
                
                # Verifica proximidade do take-profit
                diff_tp = (take_profit - preco_atual) / preco_atual
                if 0 < diff_tp <= percentual_alerta:
                    mensagem = f"📈 **Alerta de proximidade de Take-Profit**\n{moeda} está a {diff_tp*100:.2f}% do Take-Profit ({take_profit:.2f} USDT). Preço atual: {preco_atual:.2f} USDT"
                    enviar_discord(mensagem)
    
    return dados

def verificar_sinais_venda(dados):
    for moeda in CONFIG["moedas"]:
        # Verifica se está em posição
        if dados["posicoes"][moeda]:
            df = pegar_dados(moeda)
            if df.empty:
                continue
                
            df = calcular_indicadores(df)
            
            # Verifica cruzamento de médias para baixo
            cruzou_para_baixo = (df["media_curta"].iloc[-2] >= df["media_longa"].iloc[-2] and 
                                df["media_curta"].iloc[-1] < df["media_longa"].iloc[-1])
            
            # Verifica RSI em sobrecompra
            rsi_sobrecompra = False
            if CONFIG["usar_rsi"] and 'rsi' in df.columns:
                rsi_sobrecompra = df['rsi'].iloc[-1] > CONFIG["limite_rsi_sobrecompra"]
            
            if cruzou_para_baixo:
                logging.info(f"{emoji('🔴', '[VENDA]')} Sinal de venda detectado para {moeda} (cruzamento de médias para baixo)")
                
                # Obtém saldo e preço atual
                saldo = pegar_saldo()
                moeda_base = moeda.replace("USDT", "")
                preco_atual = float(cliente_binance.get_symbol_ticker(symbol=moeda)['price'])
                
                # Calcula a quantidade disponível para venda
                quantidade = saldo[moeda_base]
                quantidade_ajustada = ajustar_quantidade(moeda, quantidade, quantidade, preco_atual)
                
                if float(quantidade_ajustada) > 0:
                    # Executa a venda
                    sucesso, dados = executar_venda(
                        moeda, 
                        quantidade_ajustada, 
                        preco_atual, 
                        dados, 
                        motivo="Cruzamento de médias para baixo"
                    )
            
            elif rsi_sobrecompra:
                logging.info(f"{emoji('🔴', '[VENDA]')} Sinal de venda detectado para {moeda} (RSI em sobrecompra: {df['rsi'].iloc[-1]:.2f})")
                
                # Obtém saldo e preço atual
                saldo = pegar_saldo()
                moeda_base = moeda.replace("USDT", "")
                preco_atual = float(cliente_binance.get_symbol_ticker(symbol=moeda)['price'])
                
                # Calcula a quantidade disponível para venda
                quantidade = saldo[moeda_base]
                quantidade_ajustada = ajustar_quantidade(moeda, quantidade, quantidade, preco_atual)
                
                if float(quantidade_ajustada) > 0:
                    # Executa a venda
                    sucesso, dados = executar_venda(
                        moeda, 
                        quantidade_ajustada, 
                        preco_atual, 
                        dados, 
                        motivo="RSI em sobrecompra"
                    )
    
    return dados

def executar_estrategia_balanceada(dados, saldo_usdt):
    # Calcula o saldo disponível para cada moeda
    moedas_disponiveis = [m for m in CONFIG["moedas"] if not dados["posicoes"][m]]
    
    if not moedas_disponiveis:
        logging.info("Todas as moedas já estão em posição. Nenhuma compra será realizada.")
        return dados
    
    # Divide o saldo igualmente entre as moedas disponíveis
    saldo_por_moeda = saldo_usdt / len(moedas_disponiveis)
    compras_realizadas = 0
    
    for moeda in moedas_disponiveis:
        # Verifica se já está em posição
        if dados["posicoes"][moeda]:
            continue
        
        # Obtém dados e calcula indicadores
        df = pegar_dados(moeda)
        if df.empty:
            continue
            
        df = calcular_indicadores(df)
        preco_atual = float(cliente_binance.get_symbol_ticker(symbol=moeda)['price'])
        
        logging.info(f"{moeda} - Média {CONFIG['janela_media_curta']}: {df['media_curta'].iloc[-1]:.2f} | " +
                    f"Média {CONFIG['janela_media_longa']}: {df['media_longa'].iloc[-1]:.2f}")
        
        # Verifica cruzamento de médias para cima
        cruzou_para_cima = (df["media_curta"].iloc[-2] <= df["media_longa"].iloc[-2] and 
                           df["media_curta"].iloc[-1] > df["media_longa"].iloc[-1])
        
        # Verifica RSI em sobrevenda
        rsi_sobrevenda = False
        if CONFIG["usar_rsi"] and 'rsi' in df.columns and not pd.isna(df['rsi'].iloc[-1]):
            rsi_sobrevenda = df['rsi'].iloc[-1] < CONFIG["limite_rsi_sobrevenda"]
            logging.info(f"{moeda} - RSI: {df['rsi'].iloc[-1]:.2f}")
        
        # Sinal de compra: cruzamento de médias para cima e (opcional) RSI em sobrevenda
        sinal_compra = cruzou_para_cima
        if CONFIG["usar_rsi"]:
            sinal_compra = sinal_compra and (rsi_sobrevenda or df['rsi'].iloc[-1] < 50)
        
        if sinal_compra:
            logging.info(f"{emoji('🟢', '[COMPRA]')} Sinal de compra detectado para {moeda}!")
            
            # Calcula a quantidade a ser comprada
            quantidade = saldo_por_moeda / preco_atual
            quantidade_ajustada = ajustar_quantidade(moeda, quantidade, saldo_por_moeda, preco_atual)
            
            if float(quantidade_ajustada) > 0:
                # Executa a compra
                sucesso, dados = executar_compra(
                    moeda, 
                    quantidade_ajustada, 
                    preco_atual, 
                    dados, 
                    motivo="Cruzamento de médias para cima" + 
                           (" e RSI em sobrevenda" if rsi_sobrevenda else "")
                )
                
                if sucesso:
                    compras_realizadas += 1
            else:
                logging.info(f"Valor de {saldo_por_moeda:.2f} USDT abaixo do mínimo para {moeda}")
        
        # Gera o gráfico com os indicadores
        grafico_path = mostrar_grafico(df, moeda)
        if grafico_path:
            logging.info(f"Gráfico gerado com sucesso: {grafico_path}")
    
    if compras_realizadas == 0:
        logging.info("Nenhum sinal de compra válido detectado neste ciclo.")
    else:
        logging.info(f"{compras_realizadas} compra(s) realizada(s) com saldo balanceado.")
    
    return dados

def mostrar_resumo_operacoes(dados):
    operacoes = dados.get("historico_operacoes", [])
    if not operacoes:
        logging.info("Nenhuma operação registrada ainda.")
        return
    
    # Filtra operações das últimas 24 horas
    agora = datetime.now()
    operacoes_recentes = [
        op for op in operacoes 
        if (agora - datetime.strptime(op["timestamp"], "%Y-%m-%d %H:%M:%S")).total_seconds() < 24*60*60
    ]
    
    if operacoes_recentes:
        logging.info(f"{emoji('📋', '[RESUMO]')} Operações nas últimas 24 horas: {len(operacoes_recentes)}")
        for op in operacoes_recentes:
            tipo_emoji = emoji('🟢', '[COMPRA]') if op["tipo"] == "compra" else emoji('🔴', '[VENDA]')
            logging.info(f"{tipo_emoji} {op['timestamp']} - {op['tipo'].upper()} {op['quantidade']} {op['moeda']} a {op['preco']:.2f} USDT ({op['motivo']})")
    
    # Calcula resultado total
    compras = [op for op in operacoes if op["tipo"] == "compra"]
    vendas = [op for op in operacoes if op["tipo"] == "venda"]
    
    total_compras = sum(op["valor_total"] for op in compras)
    total_vendas = sum(op["valor_total"] for op in vendas)
    
    if total_compras > 0:
        resultado = ((total_vendas - total_compras) / total_compras) * 100
        logging.info(f"{emoji('💰', '[RESULTADO]')} Resultado total: {resultado:.2f}% ({total_vendas - total_compras:.2f} USDT)")

def executar_ciclo():
    try:
        # Carrega dados salvos
        dados_salvos = carregar_dados()
        
        # Obtém saldo e preços atuais
        saldo = pegar_saldo()
        precos = pegar_precos()
        
        # Calcula valor total em USDT
        total_usdt = saldo["USDT"]
        for moeda in CONFIG["moedas"]:
            moeda_base = moeda.replace("USDT", "")
            total_usdt += saldo[moeda_base] * precos[moeda]
        
        # Exibe resumo do saldo
        logging.info(f"{emoji('📊', '[RESUMO]')} Resumo do saldo:")
        logging.info(f"USDT: {saldo['USDT']:.2f}")
        for moeda in CONFIG["moedas"]:
            moeda_base = moeda.replace("USDT", "")
            logging.info(f"{moeda_base}: {saldo[moeda_base]} (aprox. {saldo[moeda_base] * precos[moeda]:.2f} USDT)")
        logging.info(f"Total estimado em USDT: {total_usdt:.2f}")
        
        # Atualiza histórico de patrimônio
        dados_salvos = atualizar_historico(dados_salvos)
        
        # Mostra valorização
        variacao_24h, variacao_7d = mostrar_valorizacao(dados_salvos)
        
        # Envia resumo para o Discord
        if CONFIG["discord_enabled"]:
            mensagem = (
                f"📊 **Resumo do Saldo**\n"
                f"💰 Total: {total_usdt:.2f} USDT\n"
            )
            
            for moeda in CONFIG["moedas"]:
                moeda_base = moeda.replace("USDT", "")
                mensagem += f"{moeda_base}: {saldo[moeda_base]} (≈ {saldo[moeda_base] * precos[moeda]:.2f} USDT)\n"
            
            if variacao_24h is not None:
                mensagem += f"📈 Valorização 24h: {variacao_24h:.2f}%\n"
            
            if variacao_7d is not None:
                mensagem += f"📊 Valorização 7d: {variacao_7d:.2f}%\n"
            
            enviar_discord(mensagem)
        
        # Atualiza última alta semanal
        dados_salvos = atualizar_ultima_alta_semanal(dados_salvos)
        
        # Verifica stop-loss e take-profit
        dados_salvos = verificar_stop_loss_take_profit(dados_salvos)
        
        # Verifica sinais de venda
        dados_salvos = verificar_sinais_venda(dados_salvos)
        
        # Executa estratégia de compra se tiver saldo suficiente
        if saldo['USDT'] > CONFIG["saldo_minimo_usdt"]:
            dados_salvos = executar_estrategia_balanceada(dados_salvos, saldo['USDT'])
        
        # Mostra resumo das operações
        mostrar_resumo_operacoes(dados_salvos)
        
        # Salva dados atualizados
        salvar_dados(dados_salvos)
        
        # Gera gráficos para todas as moedas
        for moeda in CONFIG["moedas"]:
            df = pegar_dados(moeda)
            if not df.empty:
                df = calcular_indicadores(df)
                grafico_path = mostrar_grafico(df, moeda)
                logging.info(f"Gráfico gerado para {moeda}: {grafico_path}")
        
        logging.info(f"{emoji('✅', '[OK]')} Ciclo de verificação concluído")
        return True
    except Exception as e:
        logging.error(f"{emoji('❌', '[ERRO]')} Erro durante o ciclo de verificação: {e}")
        logging.error(traceback.format_exc())
        return False

def iniciar_bot():
    logging.info(f"{emoji('🤖', '[BOT]')} Iniciando Bot de Trading de Criptomoedas")
    logging.info(f"Modo de simulação: {'ATIVADO' if CONFIG['modo_simulacao'] else 'DESATIVADO'}")
    logging.info(f"Moedas monitoradas: {', '.join(CONFIG['moedas'])}")
    
    # Cria pastas necessárias
    os.makedirs(CONFIG["pasta_graficos"], exist_ok=True)
    
    # Inicializa a conexão com a Binance
    if not inicializar_binance():
        logging.error("Falha ao inicializar conexão com a Binance. Encerrando.")
        return False
    
    # Executa um ciclo inicial
    return executar_ciclo()

# Função para execução contínua (usada pelo main.py)
def executar_continuamente():
    try:
        while True:
            executar_ciclo()
            
            # Aguarda até o próximo ciclo
            logging.info(f"{emoji('⏳', '[AGUARDANDO]')} Aguardando {CONFIG['intervalo_verificacao'] // 60} minutos até o próximo ciclo...")
            time.sleep(CONFIG['intervalo_verificacao'])
    except KeyboardInterrupt:
        logging.info(f"{emoji('👋', '[ENCERRADO]')} Bot encerrado pelo usuário")
    except Exception as e:
        logging.error(f"{emoji('❌', '[ERRO FATAL]')} Erro fatal: {e}")
        logging.error(traceback.format_exc())
        return False
    return True

# Para execução direta deste módulo
if __name__ == "__main__":
    iniciar_bot()
    executar_continuamente()
