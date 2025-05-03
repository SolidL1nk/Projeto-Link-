import discord
import os
import json
import asyncio
import traceback
from dotenv import load_dotenv
import logging
import sys
import os
import sys

# Adiciona o diretório base ao sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from modules.bot_ia import IA_Assistente, gerar_mensagem_personalizada, responder_pergunta

# Obtém o diretório base do projeto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Configuração de logging
logs_dir = os.path.join(BASE_DIR, "logs")
os.makedirs(logs_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(logs_dir, "bot_discord.log"), encoding='utf-8'),
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

# Carrega variáveis do .env
load_dotenv(os.path.join(BASE_DIR, ".env"))
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))

# Configurações
CONFIG = {
    "arquivo_dados": os.path.join(BASE_DIR, "dados_bot.json"),
    "moedas": ["BTCUSDT", "SOLUSDT"],
    "percentual_alerta": 0.02,  # 2%
    "pasta_graficos": os.path.join(BASE_DIR, "graficos")
}

# Cria pastas necessárias
os.makedirs(CONFIG["pasta_graficos"], exist_ok=True)

# Intents do Discord
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Variável global para o módulo de trading
bot_trading = None

assistente = IA_Assistente()

def carregar_dados():
    try:
        if os.path.exists(CONFIG["arquivo_dados"]):
            with open(CONFIG["arquivo_dados"], "r") as f:
                dados = json.load(f)
                logging.info(f"Dados carregados com sucesso de {CONFIG['arquivo_dados']}")
                return dados
        else:
            logging.warning(f"Arquivo de dados não encontrado: {CONFIG['arquivo_dados']}")
            return {}
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Erro ao carregar dados: {e}")
        logging.error(traceback.format_exc())
        return {}

async def verificar_alertas():
    await client.wait_until_ready()
    canal = client.get_channel(CHANNEL_ID)
    
    if not canal:
        logging.error(f"Canal Discord {CHANNEL_ID} não encontrado")
        return
    
    logging.info(f"{emoji('✅', '[OK]')} Iniciando monitoramento de alertas no canal {canal.name}")
    
    while not client.is_closed():
        try:
            dados = carregar_dados()
            
            # Verificação de alertas é feita diretamente no módulo de trading
            # Este loop apenas mantém o bot Discord ativo
            
            await asyncio.sleep(3600)  # 1 hora
        except Exception as e:
            logging.error(f"Erro durante verificação de alertas: {e}")
            logging.error(traceback.format_exc())
            await asyncio.sleep(60)  # Espera 1 minuto em caso de erro

@client.event
async def on_ready():
    logging.info(f"{emoji('✅', '[OK]')} Bot Discord conectado como {client.user}")
    
    # Registra o cliente Discord no módulo de trading
    if bot_trading:
        bot_trading.registrar_discord_client(client)
        logging.info("Cliente Discord registrado no módulo de trading")
    else:
        logging.warning("Módulo de trading não disponível para registro do cliente Discord")
    
    # Inicia a tarefa de verificação de alertas
    client.loop.create_task(verificar_alertas())
    
    # Envia mensagem de inicialização
    try:
        canal = client.get_channel(CHANNEL_ID)
        if canal:
            await canal.send(f"{emoji('🤖', '[BOT]')} Bot de Trading Cripto iniciado e pronto para operar!")
            logging.info("Mensagem de inicialização enviada para o Discord")
        else:
            logging.error(f"Canal Discord {CHANNEL_ID} não encontrado para envio da mensagem de inicialização")
    except Exception as e:
        logging.error(f"Erro ao enviar mensagem de inicialização: {e}")
        logging.error(traceback.format_exc())

@client.event
async def on_message(message):
    # Ignora mensagens do próprio bot
    if message.author == client.user:
        return

    # Verifica se a mensagem é no canal correto
    if message.channel.id != CHANNEL_ID:
        return

    # Comando !saldo
    if message.content.lower() == "!saldo":
        logging.info("Comando !saldo recebido")
        dados = carregar_dados()
        
        if not dados or "historico_patrimonio" not in dados or not dados["historico_patrimonio"]:
            await message.channel.send("❌ Não há dados de saldo disponíveis.")
            logging.warning("Dados de saldo não disponíveis para o comando !saldo")
            return
        
        saldo_atual = dados["historico_patrimonio"][-1]["saldo_total_usdt"]
        historico = dados["historico_patrimonio"]

        def buscar_antigo(horas):
            from datetime import datetime, timedelta
            alvo = datetime.now() - timedelta(hours=horas)
            for item in reversed(historico):
                t = datetime.strptime(item["timestamp"], "%Y-%m-%d %H:%M:%S")
                if t <= alvo:
                    return item["saldo_total_usdt"]
            return None

        antigo_24h = buscar_antigo(24)
        antigo_7d = buscar_antigo(24*7)

        variacao_24h = f"{((saldo_atual - antigo_24h) / antigo_24h) * 100:.2f}%" if antigo_24h else "N/A"
        variacao_7d = f"{((saldo_atual - antigo_7d) / antigo_7d) * 100:.2f}%" if antigo_7d else "N/A"

        resposta = (
            f"📊 **Resumo Atual**:\n"
            f"💰 Saldo Total: **{saldo_atual:.2f} USDT**\n"
            f"📈 Valorização em 24h: {variacao_24h}\n"
            f"📈 Valorização em 7 dias: {variacao_7d}\n\n"
        )
        
        # Adiciona informações sobre posições atuais
        if "posicoes" in dados:
            resposta += "**Posições Atuais**:\n"
            for moeda, em_posicao in dados["posicoes"].items():
                status = "✅ ATIVA" if em_posicao else "❌ INATIVA"
                resposta += f"{moeda}: {status}\n"
                
                if em_posicao and "precos_compra" in dados and moeda in dados["precos_compra"]:
                    preco_compra = dados["precos_compra"][moeda]
                    stop_loss = dados["stop_losses"].get(moeda, 0)
                    take_profit = dados["take_profits"].get(moeda, 0)
                    
                    resposta += f"  Preço de compra: {preco_compra:.2f} USDT\n"
                    resposta += f"  Stop-Loss: {stop_loss:.2f} USDT\n"
                    resposta += f"  Take-Profit: {take_profit:.2f} USDT\n"
        
        await message.channel.send(resposta)
        logging.info("Resposta do comando !saldo enviada")

    # Comando !grafico
    elif message.content.lower().startswith("!grafico"):
        partes = message.content.split()
        if len(partes) == 2:
            symbol = partes[1].upper()
            logging.info(f"Comando !grafico recebido para {symbol}")
            
            arquivo = os.path.join(CONFIG["pasta_graficos"], f"grafico_{symbol}.png")
            logging.info(f"Procurando gráfico em: {arquivo}")
            
            if os.path.exists(arquivo):
                try:
                    await message.channel.send(f"📊 Gráfico mais recente de {symbol}:", file=discord.File(arquivo))
                    logging.info(f"Gráfico de {symbol} enviado com sucesso")
                except Exception as e:
                    logging.error(f"Erro ao enviar gráfico de {symbol}: {e}")
                    logging.error(traceback.format_exc())
                    await message.channel.send(f"❌ Erro ao enviar gráfico de {symbol}. Verifique os logs.")
            else:
                logging.warning(f"Gráfico não encontrado para {symbol} em {arquivo}")
                
                # Verifica se a pasta existe
                if not os.path.exists(CONFIG["pasta_graficos"]):
                    logging.error(f"Pasta de gráficos não existe: {CONFIG['pasta_graficos']}")
                    os.makedirs(CONFIG["pasta_graficos"], exist_ok=True)
                    logging.info(f"Pasta de gráficos criada: {CONFIG['pasta_graficos']}")
                
                # Lista os arquivos na pasta de gráficos
                try:
                    arquivos = os.listdir(CONFIG["pasta_graficos"])
                    logging.info(f"Arquivos na pasta de gráficos: {arquivos}")
                except Exception as e:
                    logging.error(f"Erro ao listar arquivos na pasta de gráficos: {e}")
                
                await message.channel.send(f"❌ Nenhum gráfico encontrado para {symbol}.")
        else:
            await message.channel.send("❌ Uso correto: `!grafico BTCUSDT`")
    
    # Comando !ajuda
    elif message.content.lower() == "!ajuda":
        logging.info("Comando !ajuda recebido")
        ajuda = (
            "**Comandos disponíveis:**\n"
            "`!saldo` - Mostra o saldo atual e valorização\n"
            "`!grafico SIMBOLO` - Mostra o gráfico mais recente (ex: !grafico BTCUSDT)\n"
            "`!operacoes` - Mostra as últimas operações realizadas\n"
            "`!status` - Verifica se o bot está funcionando\n"
            "`!ajuda` - Mostra esta mensagem de ajuda"
        )
        await message.channel.send(ajuda)
        logging.info("Resposta do comando !ajuda enviada")
    
    # Comando !operacoes
    elif message.content.lower() == "!operacoes":
        logging.info("Comando !operacoes recebido")
        dados = carregar_dados()
        operacoes = dados.get("historico_operacoes", [])
        
        if not operacoes:
            await message.channel.send("❌ Nenhuma operação registrada ainda.")
            logging.warning("Nenhuma operação registrada para o comando !operacoes")
            return
        
        # Limita a 10 operações mais recentes
        operacoes_recentes = operacoes[-10:]
        
        resposta = "**Últimas operações:**\n"
        for op in reversed(operacoes_recentes):
            emoji_op = "🟢" if op["tipo"] == "compra" else "🔴"
            resposta += f"{emoji_op} {op['timestamp']} - {op['tipo'].upper()} {op['quantidade']} {op['moeda']} a {op['preco']:.2f} USDT ({op['motivo']})\n"
        
        await message.channel.send(resposta)
        logging.info("Resposta do comando !operacoes enviada")
    
    # Comando !status
    elif message.content.lower() == "!status":
        logging.info("Comando !status recebido")
        await message.channel.send("✅ Bot de Trading está ativo e funcionando!")
        logging.info("Resposta do comando !status enviada")
    
    # Comando !debug
    elif message.content.lower() == "!debug":
        logging.info("Comando !debug recebido")
        
        # Verifica a estrutura de diretórios
        resposta = "**Informações de Debug:**\n"
        resposta += f"Diretório base: {BASE_DIR}\n"
        resposta += f"Arquivo de dados: {CONFIG['arquivo_dados']} (existe: {os.path.exists(CONFIG['arquivo_dados'])})\n"
        resposta += f"Pasta de gráficos: {CONFIG['pasta_graficos']} (existe: {os.path.exists(CONFIG['pasta_graficos'])})\n"
        
        # Lista arquivos na pasta de gráficos
        try:
            arquivos_graficos = os.listdir(CONFIG["pasta_graficos"])
            resposta += f"Arquivos de gráficos disponíveis: {len(arquivos_graficos)}\n"
            for arquivo in arquivos_graficos[:5]:  # Limita a 5 arquivos para não sobrecarregar a mensagem
                resposta += f"- {arquivo}\n"
            if len(arquivos_graficos) > 5:
                resposta += f"... e mais {len(arquivos_graficos) - 5} arquivo(s)\n"
        except Exception as e:
            resposta += f"Erro ao listar arquivos de gráficos: {str(e)}\n"
        
        await message.channel.send(resposta)
        logging.info("Resposta do comando !debug enviada")

    # Comando para sugestões
    if message.content.lower() == "!sugestoes":
        sugestoes = assistente.gerar_sugestoes()
        await message.channel.send(f"💡 **Sugestões de Mercado**:\n{sugestoes}")

    # Comando para perguntas
    elif message.content.lower().startswith("!pergunta"):
        pergunta = message.content[len("!pergunta "):]
        resposta = responder_pergunta(pergunta)
        await message.channel.send(resposta)

# Função para iniciar o bot Discord
def iniciar_bot(modulo_trading=None):
    global bot_trading
    bot_trading = modulo_trading
    
    if not DISCORD_TOKEN:
        logging.error("Token do Discord não encontrado no arquivo .env")
        return False
    
    try:
        logging.info(f"Iniciando bot Discord com token: {DISCORD_TOKEN[:5]}...")
        client.run(DISCORD_TOKEN)
        return True
    except Exception as e:
        logging.error(f"Erro ao iniciar bot Discord: {e}")
        logging.error(traceback.format_exc())
        return False

# Para execução direta deste módulo
if __name__ == "__main__":
    logging.info(f"{emoji('🤖', '[BOT]')} Iniciando Bot Discord")
    iniciar_bot()
