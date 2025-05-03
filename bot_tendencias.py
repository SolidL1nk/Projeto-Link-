import os
import sys
import time
import logging
import traceback
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import discord
import asyncio
from deep_translator import GoogleTranslator

# Obtém o diretório base do projeto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Configuração de logging
logs_dir = os.path.join(BASE_DIR, "logs")
os.makedirs(logs_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(logs_dir, "bot_tendencias.log"), encoding='utf-8'),
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
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))
CMC_API_KEY = os.getenv("COINMARKETCAP_API_KEY")
CRYPTOPANIC_API_KEY = os.getenv("CRYPTOPANIC_API_KEY")

# Configurações
CONFIG = {
    "intervalo_verificacao": 3600,  # 1 hora em segundos
    "moedas_monitoradas": ["BTCUSDT", "SOLUSDT"],
    "max_tentativas_api": 3,
    "keywords": [
        "BTCUSDT", "SOLUSDT", "pump", "pumping", "whale", "breakout",
        "ATH", "Binance listing", "moon", "to the moon", "bullish",
        "new token", "presale", "fair launch", "IDO", "ICO",
        "airdrop", "new listing", "just launched"
    ]
}

# Intents do Discord
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Função para fazer requisições com retry
def fazer_request(url, headers=None, params=None, tentativas=3):
    for tentativa in range(1, tentativas + 1):
        try:
            r = requests.get(url, headers=headers, params=params, timeout=10)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            logging.warning(f"Tentativa {tentativa} falhou para {url}: {e}")
            if tentativa == tentativas:
                logging.error(f"{emoji('❌', '[ERRO]')} Falha definitiva para {url} após {tentativas} tentativas.")
                return None
            time.sleep(2)

# Scraping Reddit
def buscar_reddit():
    url = "https://www.reddit.com/r/CryptoCurrency/new/"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = fazer_request(url, headers)
    if r:
        try:
            soup = BeautifulSoup(r.text, 'html.parser')
            posts = soup.find_all("h3")
            texto = " ".join(post.text for post in posts)
            return texto.lower()
        except Exception as e:
            logging.error(f"{emoji('❌', '[ERRO]')} Erro ao processar dados do Reddit: {e}")
            logging.error(traceback.format_exc())
    return ""

# CoinMarketCap — Buscar os top market cap
def buscar_coinmarketcap_top():
    if not CMC_API_KEY:
        logging.warning("Chave de API do CoinMarketCap não configurada")
        return []
    
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
    headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY}
    params = {"start": "1", "limit": "5", "convert": "USD"}
    r = fazer_request(url, headers, params)
    if r and r.status_code == 200:
        try:
            data = r.json()
            nomes = [item['name'] for item in data.get('data', [])]
            return nomes
        except Exception as e:
            logging.error(f"{emoji('❌', '[ERRO]')} Erro ao processar dados do CoinMarketCap: {e}")
            logging.error(traceback.format_exc())
    else:
        logging.error(f"{emoji('❌', '[ERRO]')} Falha ao acessar CoinMarketCap: {r.status_code if r else 'Sem resposta'}")
    return []

# CryptoPanic News
def buscar_cryptopanic_news():
    if not CRYPTOPANIC_API_KEY:
        logging.warning("Chave de API do CryptoPanic não configurada")
        return []
    
    url = f"https://cryptopanic.com/api/v1/posts/?auth_token={CRYPTOPANIC_API_KEY}&public=true"
    r = fazer_request(url)
    if r:
        try:
            data = r.json()
            titulos = [item['title'] for item in data.get('results', [])]
            return titulos
        except Exception as e:
            logging.error(f"{emoji('❌', '[ERRO]')} Erro ao processar dados do CryptoPanic: {e}")
            logging.error(traceback.format_exc())
    return []

# Tradução via Google Translate
def traduzir_texto(texto):
    try:
        return GoogleTranslator(source='auto', target='pt').translate(texto)
    except Exception as e:
        logging.error(f"{emoji('❌', '[ERRO]')} Falha ao traduzir texto: {e}")
        logging.error(traceback.format_exc())
        return texto

# Função para buscar tendências e notícias
def buscar_tendencias():
    try:
        logging.info(f"{emoji('⏳', '[BUSCANDO]')} Coletando dados de tendências e notícias...")
        
        # Busca menções no Reddit
        texto_reddit = buscar_reddit()
        contagem = {}
        for palavra in CONFIG["keywords"]:
            count = texto_reddit.count(palavra.lower())
            if count > 0:
                contagem[palavra] = count
        
        # Busca top moedas por market cap
        moedas_top = buscar_coinmarketcap_top()
        
        # Busca notícias do CryptoPanic
        noticias = buscar_cryptopanic_news()
        
        logging.info(f"{emoji('✅', '[OK]')} Dados coletados com sucesso")
        
        return {
            "mencoes_reddit": contagem,
            "moedas_top": moedas_top,
            "noticias": noticias
        }
    
    except Exception as e:
        logging.error(f"{emoji('❌', '[ERRO]')} Erro ao buscar tendências: {e}")
        logging.error(traceback.format_exc())
        return None

# Função para monitorar tendências continuamente
async def monitorar_tendencias():
    await client.wait_until_ready()
    canal = client.get_channel(CHANNEL_ID)
    
    if not canal:
        logging.error(f"{emoji('❌', '[ERRO]')} Canal Discord {CHANNEL_ID} não encontrado")
        return
    
    logging.info(f"{emoji('✅', '[OK]')} Iniciando monitoramento de tendências no canal {canal.name}")
    
    while not client.is_closed():
        try:
            # Busca tendências e notícias
            dados = buscar_tendencias()
            
            if dados:
                # Envia relatório para o Discord
                await enviar_relatorio_crypto(canal, dados["mencoes_reddit"], dados["moedas_top"], dados["noticias"])
            
            # Aguarda até o próximo ciclo
            logging.info(f"{emoji('⏳', '[AGUARDANDO]')} Aguardando {CONFIG['intervalo_verificacao'] // 60} minutos até o próximo relatório...")
            await asyncio.sleep(CONFIG["intervalo_verificacao"])
        
        except Exception as e:
            logging.error(f"{emoji('❌', '[ERRO]')} Erro no loop de monitoramento: {e}")
            logging.error(traceback.format_exc())
            await asyncio.sleep(60)  # Espera 1 minuto em caso de erro

# Função para enviar relatório para o Discord
async def enviar_relatorio_crypto(channel, mentions, moedas_top, noticias):
    try:
        msg = f"{emoji('📊', '[RELATÓRIO]')} **Relatório Cripto (última 1h)**\n\n"
        
        if mentions:
            msg += f"**Menções relevantes no Reddit:**\n"
            for mention, count in mentions.items():
                mention_pt = traduzir_texto(mention)
                msg += f"• {mention_pt} — {count}x\n"
        else:
            msg += "Nenhuma menção relevante no Reddit.\n"
        
        if moedas_top:
            msg += f"\n**Top moedas por market cap:**\n"
            for moeda in moedas_top:
                moeda_pt = traduzir_texto(moeda)
                msg += f"• {moeda_pt}\n"
        else:
            msg += "\nNão foi possível listar moedas.\n"
        
        if noticias:
            msg += f"\n{emoji('📰', '[NOTÍCIAS]')} **Notícias CryptoPanic:**\n"
            for noticia in noticias[:5]:
                noticia_pt = traduzir_texto(noticia)
                msg += f"• {noticia_pt}\n"
        else:
            msg += "\nSem notícias recentes.\n"
        
        await channel.send(msg)
        logging.info(f"{emoji('✅', '[OK]')} Relatório enviado para o Discord")
    except Exception as e:
        logging.error(f"{emoji('❌', '[ERRO]')} Erro ao enviar relatório para o Discord: {e}")
        logging.error(traceback.format_exc())

# Evento de inicialização do Discord
@client.event
async def on_ready():
    logging.info(f"{emoji('✅', '[OK]')} Bot Discord conectado como {client.user}")
    client.loop.create_task(monitorar_tendencias())

# Função para iniciar o bot
def iniciar_bot():
    if not DISCORD_TOKEN:
        logging.error(f"{emoji('❌', '[ERRO]')} Token do Discord não encontrado no arquivo .env")
        return False
    
    logging.info(f"{emoji('🤖', '[BOT]')} Iniciando Bot de Tendências")
    
    try:
        client.run(DISCORD_TOKEN)
        return True
    except Exception as e:
        logging.error(f"{emoji('❌', '[ERRO]')} Erro ao iniciar bot Discord: {e}")
        logging.error(traceback.format_exc())
        return False

# Para execução direta deste módulo
if __name__ == "__main__":
    iniciar_bot()
