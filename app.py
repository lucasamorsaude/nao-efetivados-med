import requests
import json
import time
import pandas as pd # NOVO: Importar a biblioteca pandas
from datetime import datetime # NOVO: Para usar a data no nome do arquivo
import os
from slack import enviar_planilha_para_slack
from datetime import datetime, timedelta


# --- 1. CONFIGURAÇÃO ---
# Substitua os valores abaixo pelos que você copiou do seu navegador

# Cole aqui o conteúdo do 'Authorization' e do 'Cookie' que você encontrou
# na aba Rede (F12) -> Request Headers. ESTA É A PARTE MAIS IMPORTANTE.
HEADERS = {
    'Authorization': os.getenv('AUTHORIZATION'),
    'Cookie': os.getenv('COOKIE')
}


hoje = datetime.today()
dia_da_semana = hoje.weekday()  # 0 = segunda, 1 = terça, ..., 5 = sexta, 6 = sábado, 7 = domingo

# Lógica para determinar data_inicio e data_fim
if dia_da_semana == 0:  # Segunda-feira
    data_fim = hoje - timedelta(days=2)  # Sexta-feira
    data_inicio = hoje - timedelta(days=3)  # Sábado
elif dia_da_semana in [1, 2, 3, 4]:  # De terça a sexta-feira
    data_fim = hoje - timedelta(days=2)  # Ontem
    data_inicio = hoje - timedelta(days=2)  # Anteontem
# Caso seja sábado ou domingo, não gera relatório
elif dia_da_semana in [5, 6]:  # Sábado ou Domingo
    print("Não há relatório a ser gerado hoje. Esperando até segunda-feira.")
    exit()


# Formatar as datas
data_inicio = data_inicio.strftime("%Y-%m-%d")
data_fim = data_fim.strftime("%Y-%m-%d")



# Parâmetros da busca inicial. Ajuste conforme precisar.
PARAMS = {
    'page': 1,
    'limit': 100,
    'dataCriacaoInicio': f'{data_inicio}', # Data de hoje para o exemplo
    'dataCriacaoFim': f'{data_fim}',
    'status': 1
}

# URLs das APIs que vamos usar
LIST_API_URL = 'https://amei.amorsaude.com.br/api/v1/propostas'
DETAIL_API_URL_TEMPLATE = 'https://amei.amorsaude.com.br/api/v1/propostas/{}'
CASHBACK_API_URL_TEMPLATE = 'https://amei.amorsaude.com.br/api/v1/cartao-todos/cashback?matriculaoucpf={}'


# --- 2. FUNÇÕES DA AUTOMAÇÃO ---

def get_cashback_balance(cpf):
    """Busca o saldo de cashback de um cliente pelo CPF."""
    if not cpf:
        return 'CPF não encontrado'
        
    cashback_url = CASHBACK_API_URL_TEMPLATE.format(cpf)
    try:
        response = requests.get(cashback_url, headers=HEADERS)
        if response.status_code == 200:
            data = response.json()
            # --- LINHA CORRIGIDA ---
            # Trocamos a chave 'saldo' por 'balanceAvailable' que você encontrou.
            saldo = data.get('balanceAvailable', 'Saldo não encontrado')
            return saldo
        elif response.status_code == 404:
            return 'Cliente sem cashback'
        else:
            return f'Erro {response.status_code}'
            
    except requests.exceptions.RequestException as e:
        print(f"Erro de conexão na API de cashback: {e}")
        return 'Erro de conexão'

def get_proposal_details_and_cashback(proposal_id):
    """Busca os detalhes de uma proposta e, em seguida, o cashback do paciente."""
    detail_url = DETAIL_API_URL_TEMPLATE.format(proposal_id)
    try:
        response = requests.get(detail_url, headers=HEADERS)
        if response.status_code == 200:
            data = response.json()
            paciente_info = data.get('paciente', {})
            criado_por_info = data.get('createdBy', {})
            
            cpf_paciente = paciente_info.get('cpf')
            
            # Agora, com o CPF em mãos, buscamos o cashback
            saldo_cashback = get_cashback_balance(cpf_paciente)
            
            # Monta o dicionário com todas as informações que queremos
            info_completa = {
                'id_proposta': proposal_id,
                'nome_paciente': paciente_info.get('nomeSocial') or paciente_info.get('nomeCompleto'),
                'cpf_paciente': cpf_paciente,
                'celular_paciente': paciente_info.get('celular'),
                'valor_proposta': data.get('valorTotal'),
                'criado_por': criado_por_info.get('fullName'),
                'saldo_cashback': saldo_cashback
            }
            return info_completa
        else:
            print(f"Erro ao buscar detalhes da proposta {proposal_id}. Status: {response.status_code}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Erro de conexão ao buscar detalhes: {e}")
        return None

# A função para buscar a lista de propostas continua a mesma
def get_all_proposal_ids(params):
    """Busca todas as páginas e retorna uma lista única de IDs."""
    print("Buscando lista de propostas...")
    initial_params = params.copy()
    initial_params['page'] = 1
    
    try:
        response = requests.get(LIST_API_URL, headers=HEADERS, params=initial_params)
        if response.status_code != 200:
            print(f"Erro inicial ao buscar propostas. Status: {response.status_code}")
            print(f"Resposta: {response.text}")
            return []

        data = response.json()
        total_pages = data.get('meta', {}).get('totalPages', 1)
        all_ids = {item['id'] for item in data.get('items', [])} # Inicia com a primeira página
        
        print(f"Total de páginas encontradas: {total_pages}")

        for page_num in range(2, total_pages + 1):
            print(f"Buscando IDs da página {page_num}/{total_pages}...")
            params['page'] = page_num
            response = requests.get(LIST_API_URL, headers=HEADERS, params=params)
            if response.status_code == 200:
                data = response.json()
                ids_da_pagina = {item['id'] for item in data.get('items', [])}
                all_ids.update(ids_da_pagina)
                time.sleep(0.5)
            else:
                print(f"Erro na página {page_num}. Pulando...")
        
        return list(all_ids)

    except requests.exceptions.RequestException as e:
        print(f"Ocorreu um erro de conexão: {e}")
        return []


# --- 3. EXECUÇÃO PRINCIPAL E GERAÇÃO DO EXCEL ---

if __name__ == "__main__":
    
    lista_de_ids = get_all_proposal_ids(PARAMS)
    
    if not lista_de_ids:
        print("Nenhuma proposta encontrada. Finalizando.")
    else:
        print(f"\nTotal de {len(lista_de_ids)} propostas únicas encontradas. Buscando detalhes...")
        dados_finais = []
        for i, proposta_id in enumerate(lista_de_ids):
            print(f"Processando... {i+1}/{len(lista_de_ids)} (ID da Proposta: {proposta_id})")
            dados_completos = get_proposal_details_and_cashback(proposta_id)
            if dados_completos:
                dados_finais.append(dados_completos)
            time.sleep(0.25) # Pausa para não sobrecarregar

        # --- 4. SALVAR EM EXCEL ---
        if dados_finais:
            print("\nGerando arquivo Excel...")
            # Cria um DataFrame do pandas com a lista de dicionários
            df = pd.DataFrame(dados_finais)

            # Gera um nome de arquivo com a data e hora atuais
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            nome_arquivo = f"Relatorio_Propostas.xlsx"

            # Salva o DataFrame em um arquivo Excel, sem a coluna de índice do pandas
            df.to_excel(nome_arquivo, index=False)
            
            print(f"\n✅ Dados salvos com sucesso no arquivo: {nome_arquivo}")

            try:
                enviar_planilha_para_slack()
                print("Planilha Enviada pelo Slack")

            except:
                print("Erro ao enviar planilha pelo Slack")
        else:
            print("\nNenhum dado detalhado foi extraído para gerar o arquivo.")