import os
import pandas as pd
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# === CONFIGURAÇÕES ==========================

SLACK_TOKEN = os.getenv("SLACK_API_TOKEN")  # Vem do GitHub Secrets
SLACK_CHANNEL = ("C0926NK5V7D")  # Pode definir também como secret se quiser
USER_ID = ("U07KPPR7SJW")  # Coloque seu ID como secret se quiser mensagens diretas
PLANILHA_CAMINHO = "Relatorio_Propostas.xlsx"

# Cliente Slack
slack_client = WebClient(token=SLACK_TOKEN)

# === FUNÇÃO PRINCIPAL =======================

def enviar_planilha_para_slack():
    if not SLACK_TOKEN:
        print("❌ SLACK_API_TOKEN não encontrado nas variáveis de ambiente.")
        return

    if not os.path.exists(PLANILHA_CAMINHO):
        print("❌ Planilha não encontrada.")
        return

    df = pd.read_excel(PLANILHA_CAMINHO)

    if df.empty:
        print("⚠️ Planilha está vazia.")
        return

    quantidade_linhas = len(df)
    mensagem = (
        "Bom dia pessoal!!! 🌟\n"
        "<!channel>\n\n"
        f"Segue a planilha dos não efetivados para trabalharmos hoje. 📊\n\n"
        f"São *{quantidade_linhas}* pessoas, boraaaa. 💪"
    )

    try:
        slack_client.chat_postMessage(channel=SLACK_CHANNEL, text=mensagem)

        with open(PLANILHA_CAMINHO, "rb") as file_content:
            slack_client.files_upload_v2(
                channel=SLACK_CHANNEL,
                initial_comment="",
                filename=os.path.basename(PLANILHA_CAMINHO),
                file=file_content
            )

        print("✅ Mensagem e planilha enviadas com sucesso no Slack.")

    except SlackApiError as e:
        erro = f"❌ Erro ao enviar para o Slack: {e.response['error']}"
        print(erro)
        if USER_ID:
            try:
                slack_client.chat_postMessage(channel=USER_ID, text=erro)
            except Exception as dm_erro:
                print(f"⚠️ Também falhou ao tentar enviar a mensagem direta: {dm_erro}")

# === EXECUÇÃO ================================

if __name__ == "__main__":
    enviar_planilha_para_slack()
