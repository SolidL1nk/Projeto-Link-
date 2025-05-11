# Melhorias para o bot_ia.py

## 1. Aprimoramentos na Previsão de Preços

### 1.1 Indicadores Técnicos
O modelo atual usa apenas o preço de fechamento. Podemos melhorar incorporando indicadores técnicos:

```python
def adicionar_indicadores_tecnicos(df):
    """Adiciona indicadores técnicos ao DataFrame."""
    # Médias Móveis
    df['SMA_7'] = df['close'].rolling(window=7).mean()
    df['SMA_25'] = df['close'].rolling(window=25).mean()
    df['EMA_12'] = df['close'].ewm(span=12, adjust=False).mean()
    df['EMA_26'] = df['close'].ewm(span=26, adjust=False).mean()
    
    # MACD
    df['MACD'] = df['EMA_12'] - df['EMA_26']
    df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    # RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Bollinger Bands
    df['BB_middle'] = df['close'].rolling(window=20).mean()
    std = df['close'].rolling(window=20).std()
    df['BB_upper'] = df['BB_middle'] + (std * 2)
    df['BB_lower'] = df['BB_middle'] - (std * 2)
    
    # Volume OBV (On-Balance Volume)
    df['OBV'] = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()
    
    # Preencher valores NaN
    df.fillna(method='bfill', inplace=True)
    
    return df
```

### 1.2 Modelo LSTM Avançado
Melhorar o modelo LSTM para usar estes indicadores:

```python
def treinar_modelo_avancado(self) -> Sequential:
    """Treina um modelo LSTM avançado com indicadores técnicos."""
    df = self.coletar_dados_binance("BTCUSDT", 1000)
    df = self.adicionar_indicadores_tecnicos(df)
    
    # Selecionar características para o modelo
    features = ['close', 'SMA_7', 'SMA_25', 'MACD', 'RSI', 'BB_upper', 'BB_lower', 'OBV']
    dados = df[features].values
    
    # Normalizar todas as características
    dados_norm = self.scaler.fit_transform(dados)
    
    # Criar sequências
    X, y = [], []
    for i in range(60, len(dados_norm)):
        X.append(dados_norm[i-60:i])
        y.append(dados_norm[i, 0])  # Índice 0 = preço de fechamento
    
    X = np.array(X)
    y = np.array(y)
    
    # Divisão treino/teste
    split = int(0.8 * len(X))
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    
    # Construir modelo
    modelo = Sequential([
        LSTM(100, return_sequences=True, input_shape=(X_train.shape[1], X_train.shape[2])),
        LSTM(50, return_sequences=False),
        Dense(25),
        Dense(1)
    ])
    
    modelo.compile(optimizer='adam', loss='mean_squared_error')
    
    # Early stopping para evitar overfitting
    from tensorflow.keras.callbacks import EarlyStopping
    early_stop = EarlyStopping(monitor='val_loss', patience=10)
    
    # Treinar com validação
    modelo.fit(
        X_train, y_train,
        epochs=50,
        batch_size=32,
        validation_data=(X_test, y_test),
        callbacks=[early_stop]
    )
    
    modelo.save(CONFIG["modelo_path"])
    return modelo
```

### 1.3 Avaliação de Modelos
Adicionar métricas de avaliação para medir a precisão do modelo:

```python
def avaliar_modelo(self, X_test, y_test):
    """Avalia o desempenho do modelo com métricas."""
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
    
    y_pred = self.modelo.predict(X_test)
    
    # Desnormalizar para obter valores reais
    y_test_real = self.scaler.inverse_transform(y_test.reshape(-1, 1))
    y_pred_real = self.scaler.inverse_transform(y_pred)
    
    # Calcular métricas
    mse = mean_squared_error(y_test_real, y_pred_real)
    rmse = np.sqrt(mse)
    mae = mean_absolute_error(y_test_real, y_pred_real)
    r2 = r2_score(y_test_real, y_pred_real)
    
    # Calcular direção correta (alta/baixa)
    direction_actual = np.diff(y_test_real.flatten())
    direction_pred = np.diff(y_pred_real.flatten())
    direction_accuracy = np.mean((direction_actual > 0) == (direction_pred > 0))
    
    return {
        'MSE': mse,
        'RMSE': rmse,
        'MAE': mae,
        'R2': r2,
        'Direction Accuracy': direction_accuracy
    }
```

## 2. Análise de Sentimento Avançada

### 2.1 Agregação de Múltiplas Fontes
Expandir as fontes de notícias para uma análise de sentimento mais abrangente:

```python
def coletar_noticias_multi_fontes(self) -> List[Dict]:
    """Coleta notícias de múltiplas fontes."""
    noticias = []
    
    # CryptoPanic
    try:
        response = requests.get(f"{CONFIG['cryptopanic_api']}?auth_token={os.getenv('CRYPTOPANIC_API_KEY')}")
        for item in response.json().get('results', [])[:5]:
            noticias.append({
                "titulo": item['title'],
                "fonte": "CryptoPanic",
                "url": item['url'],
                "publicado_em": item['published_at']
            })
    except Exception as e:
        logging.warning(f"Erro ao coletar notícias do CryptoPanic: {e}")
    
    # CoinDesk
    try:
        response = requests.get("https://api.rss2json.com/v1/api.json?rss_url=https://www.coindesk.com/arc/outboundfeeds/rss/")
        for item in response.json().get('items', [])[:5]:
            noticias.append({
                "titulo": item['title'],
                "fonte": "CoinDesk",
                "url": item['link'],
                "publicado_em": item['pubDate']
            })
    except Exception as e:
        logging.warning(f"Erro ao coletar notícias do CoinDesk: {e}")
    
    # Cointelegraph
    try:
        response = requests.get("https://api.rss2json.com/v1/api.json?rss_url=https://cointelegraph.com/rss")
        for item in response.json().get('items', [])[:5]:
            noticias.append({
                "titulo": item['title'],
                "fonte": "Cointelegraph",
                "url": item['link'],
                "publicado_em": item['pubDate']
            })
    except Exception as e:
        logging.warning(f"Erro ao coletar notícias do Cointelegraph: {e}")
    
    return noticias
```

### 2.2 Análise de Sentimento por Moeda
Filtragem e análise de sentimento por moeda específica:

```python
def analisar_sentimento_por_moeda(self, noticias: List[Dict], moeda: str) -> Dict:
    """Analisa o sentimento das notícias para uma moeda específica."""
    # Filtra notícias relacionadas à moeda
    noticias_moeda = [n for n in noticias if moeda.lower() in n['titulo'].lower()]
    
    if not noticias_moeda:
        return {"sentimento": "neutro", "score": 0.5, "contagem": 0}
    
    # Analisa sentimento de cada notícia
    sentimentos = []
    for noticia in noticias_moeda:
        try:
            resultado = self.analisador_sentimento(noticia['titulo'])[0]
            # Converter escala 1-5 para -1 a 1
            score_ajustado = (int(resultado['label'][0]) - 3) / 2
            sentimentos.append(score_ajustado)
        except Exception as e:
            logging.warning(f"Erro ao analisar sentimento: {e}")
    
    # Calcula média de sentimento
    sentimento_medio = sum(sentimentos) / len(sentimentos) if sentimentos else 0
    
    # Classifica sentimento
    if sentimento_medio > 0.2:
        classificacao = "positivo"
    elif sentimento_medio < -0.2:
        classificacao = "negativo"
    else:
        classificacao = "neutro"
    
    return {
        "sentimento": classificacao,
        "score": sentimento_medio,
        "contagem": len(noticias_moeda)
    }
```

## 3. Aprendizado por Reforço

Implementar sistema de feedback para que o modelo aprenda com seus acertos e erros:

```python
def registrar_previsao(self, symbol: str, previsao: float, timestamp: datetime):
    """Registra uma previsão para posterior avaliação."""
    # Criar um registro da previsão
    registro = {
        "symbol": symbol,
        "valor_previsto": previsao,
        "timestamp_previsao": timestamp,
        "timestamp_alvo": timestamp + pd.Timedelta(hours=1)
    }
    
    # Salvar em um CSV
    df = pd.DataFrame([registro])
    if os.path.exists('previsoes.csv'):
        df.to_csv('previsoes.csv', mode='a', header=False, index=False)
    else:
        df.to_csv('previsoes.csv', index=False)

def avaliar_previsoes_passadas(self):
    """Avalia a precisão das previsões anteriores."""
    if not os.path.exists('previsoes.csv'):
        return {"precisao": 0, "contagem": 0}
    
    df = pd.read_csv('previsoes.csv')
    # Converter strings para datetime
    df['timestamp_alvo'] = pd.to_datetime(df['timestamp_alvo'])
    
    # Filtrar apenas previsões cujo timestamp_alvo já passou
    agora = datetime.now()
    df_avaliar = df[df['timestamp_alvo'] < agora].copy()
    
    if df_avaliar.empty:
        return {"precisao": 0, "contagem": 0}
    
    # Para cada previsão, verificar o valor real
    acertos = 0
    for _, row in df_avaliar.iterrows():
        try:
            # Obter o valor real para o timestamp alvo
            candles = self.client.get_historical_klines(
                symbol=row['symbol'],
                interval=CONFIG["intervalo_previsao"],
                start_str=str(row['timestamp_alvo'] - pd.Timedelta(minutes=5)),
                end_str=str(row['timestamp_alvo'] + pd.Timedelta(minutes=5))
            )
            
            if candles:
                valor_real = float(candles[0][4])  # Preço de fechamento
                
                # Calcular diferença percentual
                diferenca_pct = abs((valor_real - row['valor_previsto']) / valor_real)
                
                # Se a diferença for menor que 2%, consideramos um acerto
                if diferenca_pct < 0.02:
                    acertos += 1
        except Exception as e:
            logging.warning(f"Erro ao avaliar previsão: {e}")
    
    precisao = acertos / len(df_avaliar) if len(df_avaliar) > 0 else 0
    
    return {
        "precisao": precisao,
        "contagem": len(df_avaliar)
    }
```

## 4. Sistema de Decisão Inteligente

Implementar um sistema mais sofisticado para geração de recomendações:

```python
def gerar_recomendacao_avancada(self, symbol: str) -> Dict:
    """Gera uma recomendação avançada combinando múltiplos fatores."""
    # 1. Previsão de preço
    preco_atual = float(self.client.get_symbol_ticker(symbol=symbol)['price'])
    preco_previsto = self.prever_tendencia(symbol)
    variacao_prevista = (preco_previsto - preco_atual) / preco_atual
    
    # 2. Indicadores técnicos
    df = self.coletar_dados_binance(symbol, 100)
    df = self.adicionar_indicadores_tecnicos(df)
    ultimo = df.iloc[-1]
    
    # 3. Análise de sentimento
    noticias = self.coletar_noticias_multi_fontes()
    sentimento = self.analisar_sentimento_por_moeda(noticias, symbol[:3])  # BTC de BTCUSDT
    
    # 4. Volatilidade recente
    volatilidade = df['close'].pct_change().std() * np.sqrt(24)  # Anualizada
    
    # 5. Sistema de pontuação
    pontuacao = 0
    
    # Tendência de preço (até 3 pontos)
    if variacao_prevista > 0.05:
        pontuacao += 3
    elif variacao_prevista > 0.02:
        pontuacao += 2
    elif variacao_prevista > 0:
        pontuacao += 1
    elif variacao_prevista < -0.05:
        pontuacao -= 3
    elif variacao_prevista < -0.02:
        pontuacao -= 2
    elif variacao_prevista < 0:
        pontuacao -= 1
    
    # RSI (até 2 pontos)
    if ultimo['RSI'] < 30:  # Sobrevendido
        pontuacao += 2
    elif ultimo['RSI'] < 40:
        pontuacao += 1
    elif ultimo['RSI'] > 70:  # Sobrecomprado
        pontuacao -= 2
    elif ultimo['RSI'] > 60:
        pontuacao -= 1
    
    # MACD (até 2 pontos)
    if ultimo['MACD'] > ultimo['MACD_signal'] and ultimo['MACD'] > 0:
        pontuacao += 2
    elif ultimo['MACD'] > ultimo['MACD_signal']:
        pontuacao += 1
    elif ultimo['MACD'] < ultimo['MACD_signal'] and ultimo['MACD'] < 0:
        pontuacao -= 2
    elif ultimo['MACD'] < ultimo['MACD_signal']:
        pontuacao -= 1
    
    # Bandas de Bollinger (até 1 ponto)
    if ultimo['close'] < ultimo['BB_lower']:
        pontuacao += 1
    elif ultimo['close'] > ultimo['BB_upper']:
        pontuacao -= 1
    
    # Sentimento (até 2 pontos)
    if sentimento['sentimento'] == 'positivo':
        pontuacao += sentimento['contagem'] if sentimento['contagem'] <= 2 else 2
    elif sentimento['sentimento'] == 'negativo':
        pontuacao -= sentimento['contagem'] if sentimento['contagem'] <= 2 else 2
    
    # Interpretar pontuação
    if pontuacao >= 5:
        acao = "compra_forte"
        descricao = "Forte sinal de compra, múltiplos indicadores positivos"
    elif pontuacao >= 3:
        acao = "compra"
        descricao = "Sinal de compra moderado"
    elif pontuacao >= 1:
        acao = "compra_fraca"
        descricao = "Fraco sinal de compra, observe com cautela"
    elif pontuacao >= -1:
        acao = "neutro"
        descricao = "Mercado lateral, mantenha posições atuais"
    elif pontuacao >= -3:
        acao = "venda_fraca"
        descricao = "Fraco sinal de venda, considere reduzir posições"
    elif pontuacao >= -5:
        acao = "venda"
        descricao = "Sinal de venda moderado"
    else:
        acao = "venda_forte"
        descricao = "Forte sinal de venda, múltiplos indicadores negativos"
    
    return {
        "symbol": symbol,
        "preco_atual": preco_atual,
        "preco_previsto": preco_previsto,
        "variacao_prevista": variacao_prevista,
        "rsi": ultimo['RSI'],
        "sentimento": sentimento['sentimento'],
        "volatilidade": volatilidade,
        "pontuacao": pontuacao,
        "acao": acao,
        "descricao": descricao
    }
```

## 5. Sistema de Detecção de Padrões de Gráfico

```python
def detectar_padroes_graficos(self, symbol: str) -> List[Dict]:
    """Detecta padrões comuns em gráficos de velas."""
    df = self.coletar_dados_binance(symbol, 30)
    padroes = []
    
    # Adicionar colunas necessárias
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['open'] = df['open'].astype(float)
    df['close'] = df['close'].astype(float)
    
    # Doji (corpo pequeno)
    df['body_size'] = abs(df['close'] - df['open'])
    df['shadow_size'] = df['high'] - df['low']
    df['is_doji'] = df['body_size'] < (0.1 * df['shadow_size'])
    
    # Hammer (sombra inferior grande, corpo pequeno, sombra superior pequena)
    df['upper_shadow'] = df['high'] - df[['open', 'close']].max(axis=1)
    df['lower_shadow'] = df[['open', 'close']].min(axis=1) - df['low']
    df['is_hammer'] = (df['lower_shadow'] > (2 * df['body_size'])) & \
                      (df['upper_shadow'] < (0.2 * df['body_size']))
    
    # Shooting Star (sombra superior grande, corpo pequeno, sombra inferior pequena)
    df['is_shooting_star'] = (df['upper_shadow'] > (2 * df['body_size'])) & \
                            (df['lower_shadow'] < (0.2 * df['body_size']))
    
    # Engulfing Patterns
    for i in range(1, len(df)):
        # Bullish Engulfing
        if (df['open'].iloc[i-1] > df['close'].iloc[i-1]) and \
           (df['open'].iloc[i] < df['close'].iloc[i]) and \
           (df['open'].iloc[i] <= df['close'].iloc[i-1]) and \
           (df['close'].iloc[i] >= df['open'].iloc[i-1]):
            padroes.append({
                "tipo": "bullish_engulfing",
                "posicao": i,
                "data": df['timestamp'].iloc[i],
                "descricao": "Padrão de reversão de baixa para alta",
                "confianca": "média"
            })
        
        # Bearish Engulfing
        if (df['open'].iloc[i-1] < df['close'].iloc[i-1]) and \
           (df['open'].iloc[i] > df['close'].iloc[i]) and \
           (df['open'].iloc[i] >= df['close'].iloc[i-1]) and \
           (df['close'].iloc[i] <= df['open'].iloc[i-1]):
            padroes.append({
                "tipo": "bearish_engulfing",
                "posicao": i,
                "data": df['timestamp'].iloc[i],
                "descricao": "Padrão de reversão de alta para baixa",
                "confianca": "média"
            })
    
    # Morning Star (padrão de 3 velas de reversão de baixa)
    for i in range(2, len(df)):
        if (df['close'].iloc[i-2] < df['open'].iloc[i-2]) and \
           (abs(df['close'].iloc[i-1] - df['open'].iloc[i-1]) < df['body_size'].iloc[i-2] * 0.3) and \
           (df['close'].iloc[i] > df['open'].iloc[i]) and \
           (df['close'].iloc[i] > (df['open'].iloc[i-2] + df['close'].iloc[i-2]) / 2):
            padroes.append({
                "tipo": "morning_star",
                "posicao": i,
                "data": df['timestamp'].iloc[i],
                "descricao": "Padrão de reversão de baixa para alta (alta confiança)",
                "confianca": "alta"
            })
    
    # Evening Star (padrão de 3 velas de reversão de alta)
    for i in range(2, len(df)):
        if (df['close'].iloc[i-2] > df['open'].iloc[i-2]) and \
           (abs(df['close'].iloc[i-1] - df['open'].iloc[i-1]) < df['body_size'].iloc[i-2] * 0.3) and \
           (df['close'].iloc[i] < df['open'].iloc[i]) and \
           (df['close'].iloc[i] < (df['open'].iloc[i-2] + df['close'].iloc[i-2]) / 2):
            padroes.append({
                "tipo": "evening_star",
                "posicao": i,
                "data": df['timestamp'].iloc[i],
                "descricao": "Padrão de reversão de alta para baixa (alta confiança)",
                "confianca": "alta"
            })
    
    # Verificar as últimas velas para padrões Doji, Hammer e Shooting Star
    if df['is_doji'].iloc[-1]:
        padroes.append({
            "tipo": "doji",
            "posicao": len(df) - 1,
            "data": df['timestamp'].iloc[-1],
            "descricao": "Padrão Doji - indecisão do mercado",
            "confianca": "baixa"
        })
        
    if df['is_hammer'].iloc[-1]:
        padroes.append({
            "tipo": "hammer",
            "posicao": len(df) - 1,
            "data": df['timestamp'].iloc[-1],
            "descricao": "Padrão Hammer - possível reversão de baixa para alta",
            "confianca": "média"
        })
        
    if df['is_shooting_star'].iloc[-1]:
        padroes.append({
            "tipo": "shooting_star",
            "posicao": len(df) - 1,
            "data": df['timestamp'].iloc[-1],
            "descricao": "Padrão Shooting Star - possível reversão de alta para baixa",
            "confianca": "média"
        })
    
    return padroes
```

## 6. Geração de Relatórios Aprimorados

```python
def gerar_relatorio_avancado(self) -> str:
    """Gera um relatório avançado de mercado."""
    # Cabeçalho
    data_hora = datetime.now().strftime("%d/%m/%Y às %H:%M")
    relatorio = f"# 📊 **Relatório de Mercado - {data_hora}**\n\n"
    
    # Visão geral do mercado
    try:
        bitcoin_info = self.client.get_symbol_ticker(symbol="BTCUSDT")
        ethereum_info = self.client.get_symbol_ticker(symbol="ETHUSDT")
        solana_info = self.client.get_symbol_ticker(symbol="SOLUSDT")
        
        btc_price = float(bitcoin_info['price'])
        eth_price = float(ethereum_info['price'])
        sol_price = float(solana_info['price'])
        
        relatorio += "## 💰 **Visão Geral do Mercado**\n"
        relatorio += f"- Bitcoin (BTC): ${btc_price:,.2f}\n"
        relatorio += f"- Ethereum (ETH): ${eth_price:,.2f}\n"
        relatorio += f"- Solana (SOL): ${sol_price:,.2f}\n\n"
    except Exception as e:
        logging.error(f"Erro ao obter visão geral do mercado: {e}")
    
    # Análise e Recomendações
    relatorio += "## 🔍 **Análise e Recomendações**\n\n"
    
    for moeda in CONFIG["moedas"]:
        try:
            recomendacao = self.gerar_recomendacao_avancada(moeda)
            
            simbolo_curto = moeda[:3] if "USDT" in moeda else moeda
            
            # Emoji baseado na ação recomendada
            emoji = "🟢" if "compra" in recomendacao['acao'] else "🔴" if "venda" in recomendacao['acao'] else "⚪"
            
            relatorio += f"### {emoji} **{simbolo_curto}**\n"
            relatorio += f"- Preço Atual: ${recomendacao['preco_atual']:,.2f}\n"
            relatorio += f"- Previsão (1h): ${recomendacao['preco_previsto']:,.2f} "
            relatorio += f"({recomendacao['variacao_prevista']*100:+.2f}%)\n"
            relatorio += f"- RSI: {recomendacao['rsi']:.2f}\n"
            relatorio += f"- Sentimento: {recomendacao['sentimento'].capitalize()}\n"
            relatorio += f"- Volatilidade (24h): {recomendacao['volatilidade']*100:.2f}%\n"
            relatorio += f"- **Recomendação**: {recomendacao['descricao']}\n\n"
            
            # Padrões de gráfico
            padroes = self.detectar_padroes_graficos(moeda)
            if padroes:
                relatorio += "**Padrões Detectados:**\n"
                for padrao in padroes:
                    conf_emoji = "⭐⭐⭐" if padrao['confianca'] == "alta" else "⭐⭐" if padrao['confianca'] == "média" else "⭐"
                    relatorio += f"- {padrao['tipo'].replace('_', ' ').title()}: {padrao['descricao']} {conf_emoji}\n"
                relatorio += "\n"
            
        except Exception as e:
            logging.error(f"Erro ao gerar recomendação para {moeda}: {e}")
    
    # Notícias Relevantes
    relatorio += "## 📰 **Notícias Relevantes**\n\n"
    
    try:
        noticias = self.coletar_noticias_multi_fontes()
        for i, noticia in enumerate(noticias[:5]):
            fonte = noticia['fonte']
            titulo = noticia['titulo']
            
            # Tenta traduzir para português
            try:
                translator = Translator()
                titulo_traduzido = translator.translate(titulo, src='en', dest='pt').text
            except:
                titulo_traduzido = titulo
                
            sentimento = self.analisador_sentimento(titulo)[0]
            
            # Emoji baseado no sentimento
            if sentimento['label'].startswith('5') or sentimento['label'].startswith('4'):
                emoji = "🟢"  # Muito positivo ou positivo
            elif sentimento['label'].startswith('3'):
                emoji = "⚪"  # Neutro
            else:
                emoji = "🔴"  # Negativo ou muito negativo
                
            relatorio += f"{i+1}. {emoji} **{titulo_traduzido}**\n"
            relatorio += f"   Fonte: {fonte}\n\n"
    except Exception as e:
        logging.error(f"Erro ao processar notícias: {e}")
    
    # Memecoins em Alta
    relatorio += "## 🚀 **Memecoins em Alta**\n\n"
    memecoins = self.detectar_memecoins()
    if memeco
