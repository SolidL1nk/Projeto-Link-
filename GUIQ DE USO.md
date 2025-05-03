# Projeto-Link-
# **Guia de Uso do Projeto**



## **Visão Geral**

Este projeto é um sistema de trading automatizado e monitoramento de mercado de criptomoedas. Ele utiliza APIs, análise de dados e integração com o Discord para fornecer informações, executar operações e enviar notificações.



O sistema é dividido em módulos, cada um com responsabilidades específicas:



1. **`main.py`**: Gerencia os módulos do sistema.

2. **`bot_ia.py`**: Realiza análises de mercado e gera relatórios.

3. **`bot_discord.py`**: Interage com o Discord para receber comandos e enviar informações.

4. **`bot_trading.py`**: Executa estratégias de trading automatizado.

5. **`bot_tendencias.py`**: Monitora tendências e notícias relacionadas a criptomoedas.



---



## **1. Arquivo main.py**

### **Função Principal**

- Gerencia os módulos do sistema (IA, Discord, Trading, Tendências).

- Monitora os processos e reinicia módulos automaticamente em caso de falha.



### **Principais Funções**

- **`iniciar_modulo(nome_modulo)`**:

  - Inicia um módulo específico (ex.: bot_ia.py, `bot_discord.py`).

- **`verificar_modulo(nome_modulo)`**:

  - Verifica se um módulo está ativo e funcionando.

- **`reiniciar_modulo(nome_modulo)`**:

  - Reinicia um módulo caso ele tenha falhado.

- **`encerrar_modulos()`**:

  - Encerra todos os módulos ao finalizar o sistema.



### **Como Usar**

- Execute o arquivo main.py para iniciar o sistema completo:

  ```bash

  python main.py

  ```



---



## **2. Arquivo bot_ia.py**

### **Função Principal**

- Realiza análises de mercado, previsões e gera relatórios detalhados.

- Envia mensagens personalizadas e sugestões de mercado.



### **Principais Funções**

- **`prever_tendencia(symbol: str)`**:

  - Faz uma previsão para a próxima hora com base em dados históricos.

- **`gerar_relatorio()`**:

  - Gera um relatório completo com previsões, notícias e sugestões.

- **`gerar_sugestoes()`**:

  - Gera sugestões de compra ou venda com base nas previsões.

- **`responder_pergunta(pergunta: str)`**:

  - Responde a perguntas como "Qual é a previsão para BTC?".

- **`monitorar_mercado()`**:

  - Monitora o mercado e envia alertas para o Discord em caso de variações significativas.



### **Como Usar**

- Execute o arquivo para gerar relatórios e enviar mensagens para o Discord:

  ```bash

  python modules/bot_ia.py

  ```



---



## **3. Arquivo `bot_discord.py`**

### **Função Principal**

- Interage com o Discord para receber comandos e enviar informações.

- Integra-se com o módulo de IA para responder perguntas e gerar sugestões.



### **Principais Comandos**

- **`!saldo`**:

  - Mostra o saldo atual e a valorização em 24 horas e 7 dias.

- **`!grafico SIMBOLO`**:

  - Envia o gráfico mais recente de uma moeda (ex.: `!grafico BTCUSDT`).

- **`!ajuda`**:

  - Mostra a lista de comandos disponíveis.

- **`!operacoes`**:

  - Mostra as últimas operações realizadas.

- **`!status`**:

  - Verifica se o bot está funcionando.

- **`!sugestoes`**:

  - Mostra sugestões de mercado geradas pelo módulo de IA.

- **`!pergunta`**:

  - Responde a perguntas específicas, como "Qual é a previsão para BTC?".



### **Como Usar**

- Execute o arquivo para iniciar o bot no Discord:

  ```bash

  python modules/bot_discord.py

  ```



---



## **4. Arquivo `bot_trading.py`**

### **Função Principal**

- Executa estratégias de trading automatizado com base em indicadores técnicos.

- Monitora posições, executa ordens de compra/venda e envia notificações para o Discord.



### **Principais Funções**

- **`executar_compra(moeda, quantidade, preco_atual, dados, motivo)`**:

  - Executa uma ordem de compra.

- **`executar_venda(moeda, quantidade, preco_atual, dados, motivo)`**:

  - Executa uma ordem de venda.

- **`verificar_stop_loss_take_profit(dados)`**:

  - Monitora posições e executa ordens de venda ao atingir stop-loss ou take-profit.

- **`mostrar_valorizacao(dados)`**:

  - Calcula a valorização do portfólio em 24 horas e 7 dias.

- **`mostrar_grafico(df, symbol)`**:

  - Gera gráficos com indicadores técnicos.



### **Como Usar**

- Execute o arquivo para iniciar o módulo de trading:

  ```bash

  python modules/bot_trading.py

  ```



---



## **5. Arquivo `bot_tendencias.py`**

### **Função Principal**

- Monitora tendências e notícias relacionadas a criptomoedas.

- Envia relatórios para o Discord com menções relevantes e notícias recentes.



### **Principais Funções**

- **`buscar_reddit()`**:

  - Coleta menções relevantes no Reddit.

- **`buscar_coinmarketcap_top()`**:

  - Obtém as principais moedas por market cap no CoinMarketCap.

- **`buscar_cryptopanic_news()`**:

  - Coleta notícias recentes do CryptoPanic.

- **`monitorar_tendencias()`**:

  - Monitora tendências continuamente e envia relatórios para o Discord.



### **Como Usar**

- Execute o arquivo para iniciar o monitoramento de tendências:

  ```bash

  python modules/bot_tendencias.py

  ```



---



## **Fluxo de Integração**

1. **`main.py`**:

   - Gerencia os módulos e garante que todos estejam funcionando.

2. **`bot_ia.py`**:

   - Realiza análises e gera relatórios detalhados.

3. **`bot_discord.py`**:

   - Recebe comandos e envia informações para o Discord.

4. **`bot_trading.py`**:

   - Executa estratégias de trading automatizado.

5. **`bot_tendencias.py`**:

   - Monitora tendências e notícias para informar os usuários.



---



## **Exemplo de Uso**

1. Inicie o sistema completo:

   ```bash

   python main.py

   ```

2. No Discord, use os comandos:

   - `!saldo`: Para verificar o saldo atual.

   - `!grafico BTCUSDT`: Para visualizar o gráfico de uma moeda.

   - `!sugestoes`: Para receber sugestões de mercado.

   - `!pergunta Qual é a previsão para BTC?`: Para obter previsões específicas.



---



## **Resumo**

Este projeto é um sistema completo de trading e monitoramento de mercado, com integração ao Discord para facilitar a interação com os usuários. Ele é modular, permitindo que cada componente funcione de forma independente ou integrada.

