import asyncio  # Adicione esta linha
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Suprime avisos e mensagens de informação
import logging
import requests
import pandas as pd
import numpy as np
import discord
from datetime import datetime
from typing import Dict, List, Optional
from binance.client import Client
from transformers import pipeline
from tf_keras.models import Sequential, load_model
from tf_keras.layers import LSTM, Dense
from sklearn.preprocessing import MinMaxScaler
from googletrans import Translator  # Adicione esta importação

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# Carrega variáveis de ambiente
BINANCE_API_KEY = os.getenv("KEY_BINANCE")
BINANCE_SECRET_KEY = os.getenv("SECRET_BINANCE")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))

# Configurações da IA
CONFIG = {
    "moedas": ["BTCUSDT", "SOLUSDT"],
    "intervalo_previsao": "1h",
    "modelo_path": "modelo_lstm.h5",
    "coingecko_api": "https://api.coingecko.com/api/v3",
    "cryptopanic_api": "https://cryptopanic.com/api/v1/posts/"
}

class IA_Assistente:
    def __init__(self):
        self.client = Client(BINANCE_API_KEY, BINANCE_SECRET_KEY)
        # Substituí o modelo por um público disponível
        self.analisador_sentimento = pipeline('sentiment-analysis', model='nlptown/bert-base-multilingual-uncased-sentiment')
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        self.modelo = self.carregar_modelo()

    def carregar_modelo(self):
        """Carrega o modelo LSTM pré-treinado ou treina um novo."""
        if os.path.exists(CONFIG["modelo_path"]):
            return load_model(CONFIG["modelo_path"])
        else:
            return self.treinar_modelo()

    def coletar_dados_binance(self, symbol: str, limite: int = 100) -> pd.DataFrame:
        """Coleta dados históricos da Binance."""
        candles = self.client.get_historical_klines(
            symbol=symbol,
            interval=CONFIG["intervalo_previsao"],
            limit=limite
        )
        df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'trades', 'taker_buy_base', 'taker_buy_quote', 'ignore'])
        df['close'] = df['close'].astype(float)
        return df[['timestamp', 'close']]

    def preprocessar_dados(self, df: pd.DataFrame) -> np.ndarray:
        """Prepara os dados para o modelo LSTM."""
        dados = self.scaler.fit_transform(df['close'].values.reshape(-1, 1))
        sequencias, alvos = [], []
        for i in range(60, len(dados)):
            sequencias.append(dados[i-60:i, 0])
            alvos.append(dados[i, 0])
        return np.array(sequencias), np.array(alvos)

    def treinar_modelo(self) -> Sequential:
        """Treina um modelo LSTM para previsão de preços."""
        df = self.coletar_dados_binance("BTCUSDT", 1000)
        X, y = self.preprocessar_dados(df)
        modelo = Sequential([
            LSTM(50, return_sequences=True, input_shape=(X.shape[1], 1)),
            LSTM(50),
            Dense(1)
        ])
        modelo.compile(optimizer='adam', loss='mean_squared_error')
        modelo.fit(X, y.reshape(-1, 1), epochs=20, batch_size=32)
        modelo.save(CONFIG["modelo_path"])
        return modelo

    def prever_tendencia(self, symbol: str) -> float:
        """Faz uma previsão para a próxima hora."""
        df = self.coletar_dados_binance(symbol)
        X, _ = self.preprocessar_dados(df)
        previsao = self.modelo.predict(X[-1].reshape(1, -1, 1))
        return self.scaler.inverse_transform(previsao)[0][0]

    def analisar_noticias(self) -> List[Dict]:
        """Analisa notícias do CryptoPanic com NLP e traduz para português."""
        response = requests.get(f"{CONFIG['cryptopanic_api']}?auth_token={os.getenv('CRYPTOPANIC_API_KEY')}")
        noticias = []
        translator = Translator()  # Inicializa o tradutor
        for item in response.json().get('results', [])[:5]:
            sentimento = self.analisador_sentimento(item['title'])[0]
            titulo_traduzido = translator.translate(item['title'], src='en', dest='pt').text  # Tradução
            noticias.append({
                "titulo": titulo_traduzido,
                "sentimento": sentimento['label'],
                "score": sentimento['score']
            })
        return noticias

    def detectar_memecoins(self) -> List[Dict]:
        """Identifica memecoins com alta de +50% em 24h."""
        response = requests.get(f"{CONFIG['coingecko_api']}/coins/markets?vs_currency=usd&order=volume_desc")
        memecoins = []
        for coin in response.json():
            if 'meme' in coin['name'].lower() and coin['price_change_percentage_24h'] > 50:
                memecoins.append({
                    "nome": coin['name'],
                    "symbol": coin['symbol'],
                    "alta_24h": coin['price_change_percentage_24h']
                })
        return memecoins

    async def enviar_alerta_discord(self, mensagem: str):
        """Envia mensagens para o Discord."""
        client = discord.Client(intents=discord.Intents.default())
        await client.login(DISCORD_TOKEN)
        canal = await client.fetch_channel(DISCORD_CHANNEL_ID)
        await canal.send(mensagem)
        await client.close()

    def gerar_relatorio(self) -> str:
        """Gera um relatório completo de mercado."""
        relatorio = "**Relatório do Assistente IA**\n"

        # Previsões
        for moeda in CONFIG["moedas"]:
            previsao = self.prever_tendencia(moeda)
            relatorio += f"**Previsão {moeda}**: {previsao:.2f} USDT (próxima hora)\n"

        # Notícias
        relatorio += "\n📰 **Análise de Notícias**\n"
        for noticia in self.analisar_noticias():
            relatorio += f"- {noticia['titulo']} ({noticia['sentimento']} {noticia['score']:.2f})\n"

        # Memecoins
        relatorio += "\n🚀 **Memecoins em Alta**\n"
        for coin in self.detectar_memecoins():
            relatorio += f"- {coin['nome']} ({coin['alta_24h']:.2f}%)\n"

        # Recomendações
        relatorio += "\n💡 **Recomendações**\n"
        relatorio += "- Diversifique entre BTC e SOL\n"
        relatorio += "- Considere realizar lucros acima de 5%\n"

        relatorio += "\n💡 **Sugestões de Mercado**\n"
        relatorio += gerar_sugestoes()

        return relatorio

def gerar_mensagem_personalizada(evento: str) -> str:
    """Gera uma mensagem personalizada com base no evento."""
    mensagens = {
        "mercado_em_alta": "🚀 O mercado está em alta! Considere aproveitar as oportunidades.",
        "mercado_em_baixa": "📉 O mercado está em baixa. Talvez seja um bom momento para avaliar suas posições.",
        "noticia_importante": "📰 Uma notícia importante foi detectada! Confira os detalhes no relatório.",
    }
    return mensagens.get(evento, "🤖 Estou aqui para ajudar! O que você precisa?")

def gerar_sugestoes() -> str:
    """Gera sugestões com base nos dados de mercado."""
    sugestoes = []
    for moeda in CONFIG["moedas"]:
        previsao = assistente.prever_tendencia(moeda)
        if previsao > 1.05:  # Exemplo: se a previsão for 5% maior que o preço atual
            sugestoes.append(f"Considere comprar {moeda}, previsão de alta.")
        elif previsao < 0.95:  # Exemplo: se a previsão for 5% menor que o preço atual
            sugestoes.append(f"Considere vender {moeda}, previsão de baixa.")
    return "\n".join(sugestoes) if sugestoes else "Nenhuma sugestão no momento."

def responder_pergunta(pergunta: str) -> str:
    """Responde a perguntas comuns."""
    if "previsão" in pergunta.lower():
        moeda = pergunta.split()[-1].upper()  # Exemplo: "Qual é a previsão para BTC?"
        # Converte para o formato completo (ex.: BTC -> BTCUSDT)
        moeda_completa = f"{moeda}USDT"
        if moeda_completa in CONFIG["moedas"]:
            previsao = assistente.prever_tendencia(moeda_completa)
            return f"A previsão para {moeda} é {previsao:.2f} USDT na próxima hora."
        else:
            return f"Desculpe, não reconheço a moeda {moeda}."
    elif "tendências" in pergunta.lower():
        return "As tendências do mercado estão no relatório mais recente."
    else:
        return "Desculpe, não entendi sua pergunta. Tente novamente."

def monitorar_mercado():
    """Monitora o mercado e envia alertas."""
    for moeda in CONFIG["moedas"]:
        df = assistente.coletar_dados_binance(moeda)
        variacao = (df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2]
        if variacao > 0.05:  # Exemplo: alta maior que 5%
            asyncio.run(assistente.enviar_alerta_discord(f"🚀 {moeda} subiu mais de 5% nas últimas horas!"))
        elif variacao < -0.05:  # Exemplo: queda maior que 5%
            asyncio.run(assistente.enviar_alerta_discord(f"📉 {moeda} caiu mais de 5% nas últimas horas!"))

import time

# Uso Exemplo
if __name__ == "__main__":
    assistente = IA_Assistente()
    evento = "mercado_em_alta"  # Exemplo de evento
    mensagem = gerar_mensagem_personalizada(evento)
    asyncio.run(assistente.enviar_alerta_discord(mensagem))
    while True:
        try:
            logging.info("Iniciando geração do relatório...")
            relatorio = assistente.gerar_relatorio()
            logging.info("Relatório gerado com sucesso.")

            # Envia o relatório para o Discord
            import asyncio
            asyncio.run(assistente.enviar_alerta_discord(relatorio))

        except Exception as e:
            logging.error(f"Erro no módulo IA: {e}")

        # Aguarda 1 hora antes de gerar o próximo relatório
        time.sleep(3600)  # 3600 segundos = 1 hora