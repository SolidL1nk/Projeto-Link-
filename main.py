import os
import sys
import subprocess
import time
import logging
import traceback
import signal
import psutil
import discord
import asyncio

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))

async def enviar_notificacao_discord(mensagem):
    """Envia notificações para o Discord."""
    try:
        client = discord.Client(intents=discord.Intents.default())
        await client.login(DISCORD_TOKEN)
        canal = await client.fetch_channel(DISCORD_CHANNEL_ID)
        await canal.send(mensagem)
        await client.close()
    except Exception as e:
        logging.error(f"Erro ao enviar notificação para o Discord: {e}")

# Obtém o diretório base do projeto
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Configuração de logging
logs_dir = os.path.join(BASE_DIR, "logs")
os.makedirs(logs_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(logs_dir, "main.log"), encoding='utf-8'),
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

# Configurações
CONFIG = {
    "modulos": {
        "trading": {
            "script": os.path.join(BASE_DIR, "modules", "bot_trading.py"),
            "processo": None,
            "pid": None,
            "ativo": False,
            "tentativas": 0,
            "max_tentativas": 5,
            "intervalo_reinicio": 10  # segundos
        },
        "discord": {
            "script": os.path.join(BASE_DIR, "modules", "bot_discord.py"),
            "processo": None,
            "pid": None,
            "ativo": False,
            "tentativas": 0,
            "max_tentativas": 5,
            "intervalo_reinicio": 10  # segundos
        },
        "tendencias": {
            "script": os.path.join(BASE_DIR, "modules", "bot_tendencias.py"),
            "processo": None,
            "pid": None,
            "ativo": False,
            "tentativas": 0,
            "max_tentativas": 5,
            "intervalo_reinicio": 10  # segundos
        },
        "ia": {  # Adicionado o módulo IA
            "script": os.path.join(BASE_DIR, "modules", "bot_ia.py"),
            "processo": None,
            "pid": None,
            "ativo": False,
            "tentativas": 0,
            "max_tentativas": 5,
            "intervalo_reinicio": 10  # segundos
        }
    },
    "intervalo_verificacao": 5,  # segundos
    "pasta_graficos": os.path.join(BASE_DIR, "graficos"),
    "pasta_logs": logs_dir
}

# Cria pastas necessárias
os.makedirs(CONFIG["pasta_graficos"], exist_ok=True)
os.makedirs(CONFIG["pasta_logs"], exist_ok=True)

# Função para iniciar um módulo
def iniciar_modulo(nome_modulo):
    modulo = CONFIG["modulos"][nome_modulo]
    
    if modulo["ativo"]:
        logging.warning(f"Módulo {nome_modulo} já está ativo")
        return True
    
    logging.info(f"{emoji('🚀', '[INICIANDO]')} Iniciando módulo {nome_modulo}...")
    
    try:
        # Verifica se o script existe
        if not os.path.exists(modulo["script"]):
            logging.error(f"Script {modulo['script']} não encontrado")
            return False
        
        # Redireciona saída para arquivos de log
        stdout_log = open(os.path.join(CONFIG["pasta_logs"], f"{nome_modulo}.stdout.log"), "w")
        stderr_log = open(os.path.join(CONFIG["pasta_logs"], f"{nome_modulo}.stderr.log"), "w")
        
        # Inicia o processo
        processo = subprocess.Popen(
            [sys.executable, modulo["script"]],
            stdout=stdout_log,
            stderr=stderr_log,
            cwd=BASE_DIR
        )

        # Atualiza informações do módulo
        modulo["processo"] = processo
        modulo["pid"] = processo.pid
        modulo["ativo"] = True
        modulo["tentativas"] = 0
        
        logging.info(f"{emoji('✅', '[OK]')} Módulo {nome_modulo} iniciado com PID {processo.pid}")
        return True
    
    except Exception as e:
        logging.error(f"Erro ao iniciar módulo {nome_modulo}: {e}")
        logging.error(traceback.format_exc())
        modulo["ativo"] = False
        modulo["tentativas"] += 1
        return False

# Função para verificar se um processo está ativo
def verificar_processo(pid):
    try:
        # Verifica se o processo existe
        processo = psutil.Process(pid)
        return processo.is_running()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False
    except Exception as e:
        logging.error(f"Erro ao verificar processo {pid}: {e}")
        return False

# Função para verificar o status de um módulo
def verificar_modulo(nome_modulo):
    modulo = CONFIG["modulos"][nome_modulo]
    
    # Se o módulo não está marcado como ativo, não há o que verificar
    if not modulo["ativo"]:
        return False
    
    # Verifica se o processo ainda está em execução
    if modulo["pid"] and verificar_processo(modulo["pid"]):
        return True
    
    # Verifica se o processo terminou
    if modulo["processo"]:
        retorno = modulo["processo"].poll()
        if retorno is not None:
            # Processo terminou
            stderr = modulo["processo"].stderr.read() if modulo["processo"].stderr else ""
            logging.warning(f"{emoji('⚠️', '[AVISO]')} Módulo {nome_modulo} encerrou com código {retorno}")
            if stderr:
                logging.error(f"Erro do módulo {nome_modulo}:\n{stderr}")
            
            # Marca o módulo como inativo
            modulo["ativo"] = False
            modulo["pid"] = None
            modulo["processo"] = None
            return False
    
    # Se chegou aqui, o processo não está mais em execução, mas não foi detectado pelo poll()
    logging.warning(f"{emoji('⚠️', '[AVISO]')} Módulo {nome_modulo} não está mais em execução")
    modulo["ativo"] = False
    modulo["pid"] = None
    modulo["processo"] = None
    return False

async def notificar_reinicio(nome_modulo):
    mensagem = f"⚠️ O módulo `{nome_modulo}` falhou e será reiniciado."
    await enviar_notificacao_discord(mensagem)

def reiniciar_modulo(nome_modulo):
    modulo = CONFIG["modulos"][nome_modulo]
    
    # Verifica se já excedeu o número máximo de tentativas
    if modulo["tentativas"] >= modulo["max_tentativas"]:
        logging.error(f"{emoji('❌', '[ERRO]')} Número máximo de tentativas excedido para o módulo {nome_modulo}")
        return False
    
    logging.info(f"{emoji('🔄', '[REINICIANDO]')} Tentando reiniciar módulo {nome_modulo}...")
    asyncio.run(notificar_reinicio(nome_modulo))
    # Tenta encerrar o processo se ainda estiver ativo
    if modulo["pid"] and verificar_processo(modulo["pid"]):
        try:
            os.kill(modulo["pid"], signal.SIGTERM)
            time.sleep(2)  # Dá um tempo para o processo encerrar
        except Exception as e:
            logging.warning(f"Erro ao encerrar processo {modulo['pid']}: {e}")
    
    # Marca o módulo como inativo
    modulo["ativo"] = False
    modulo["pid"] = None
    modulo["processo"] = None
    
    # Aguarda o intervalo de reinício
    time.sleep(modulo["intervalo_reinicio"])
    
    # Inicia o módulo novamente
    return iniciar_modulo(nome_modulo)

# Função para encerrar todos os módulos
def encerrar_modulos():
    for nome_modulo, modulo in CONFIG["modulos"].items():
        if modulo["ativo"] and modulo["pid"]:
            try:
                logging.info(f"{emoji('🛑', '[ENCERRANDO]')} Encerrando módulo {nome_modulo}...")
                os.kill(modulo["pid"], signal.SIGTERM)
            except Exception as e:
                logging.warning(f"Erro ao encerrar módulo {nome_modulo}: {e}")

# Função principal
def main():
    logging.info(f"{emoji('🚀', '[INICIANDO]')} Iniciando sistema completo de trading de criptomoedas")
    
    # Inicia os módulos em sequência
    iniciar_modulo("trading")
    time.sleep(5)  # Aguarda um pouco para o módulo de trading inicializar
    
    iniciar_modulo("discord")
    time.sleep(3)  # Aguarda um pouco para o módulo de discord inicializar
    
    iniciar_modulo("tendencias")
    
    # Loop principal
    try:
        while True:
            # Verifica o status de cada módulo
            for nome_modulo in CONFIG["modulos"]:
                if not verificar_modulo(nome_modulo):
                    # Se o módulo não está ativo, tenta reiniciá-lo
                    reiniciar_modulo(nome_modulo)
            
            # Aguarda o próximo ciclo de verificação
            time.sleep(CONFIG["intervalo_verificacao"])
    
    except KeyboardInterrupt:
        logging.info(f"{emoji('👋', '[ENCERRADO]')} Sistema encerrado pelo usuário")
    except Exception as e:
        logging.error(f"{emoji('❌', '[ERRO FATAL]')} Erro fatal: {e}")
        logging.error(traceback.format_exc())
    finally:
        logging.info("Encerrando todos os módulos...")
        encerrar_modulos()

if __name__ == "__main__":
    main()
