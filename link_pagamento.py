# gerar_links_em_lote_v3_formatado.py
import pandas as pd
import json
import time
from playwright.sync_api import sync_playwright, expect
import os

# --- CONFIGURAÇÕES ---
ARQUIVO_ENTRADA = "Relatorio_Propostas.xlsx"
ARQUIVO_SAIDA = "Relatorio_Propostas.xlsx"
EMAIL_LOGIN = os.getenv('MAISTODOS_EMAIL')
SENHA_LOGIN = os.getenv('MAISTODOS_SENHA')
TENTATIVAS_POR_LINHA = 3
ESPERA_ENTRE_TENTATIVAS = 5

def gerar_links_de_pagamento():
    # --- INÍCIO DO SCRIPT ---
    try:
        # AJUSTE: Forçamos a coluna 'cpf_paciente' a ser lida como texto (str)
        # para preservar os zeros à esquerda e a formatação.
        df = pd.read_excel(ARQUIVO_ENTRADA, dtype={'cpf_paciente': str, 'celular_paciente': str})
        print(f"Planilha '{ARQUIVO_ENTRADA}' lida com sucesso. {len(df)} linhas para processar.")

    except FileNotFoundError:
        print(f"ERRO: Arquivo '{ARQUIVO_ENTRADA}' não encontrado.")
        exit()
    except KeyError:
        print(f"ERRO: A coluna 'cpf_paciente' não foi encontrada na planilha. Verifique o nome da coluna.")
        exit()
    except Exception as e:
        print(f"ERRO ao ler a planilha: {e}")
        exit()

    with sync_playwright() as p:
        print("\n--- Iniciando Automação ---")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        try:
            print(" PASSO 1: Autenticando na plataforma...")
            page.goto("https://accounts.maistodos.com.br/login")
            page.fill('input[name="email"]', EMAIL_LOGIN)
            page.fill('input[name="password"]', SENHA_LOGIN)
            page.click('button[type="submit"]')
            expect(page).to_have_url("https://plataforma.maistodos.com.br/", timeout=30000)
            print("   -> Autenticação bem-sucedida! Sessão iniciada.")

            print(f"\n PASSO 2: Iniciando a geração de links em lote (com até {TENTATIVAS_POR_LINHA} tentativas por linha)...")
            links_gerados = []
            total_linhas = len(df)

            for indice, linha in df.iterrows():
                print(f"  - Processando linha {indice + 1}/{total_linhas}: {linha['nome_paciente']}")
                
                for tentativa in range(TENTATIVAS_POR_LINHA):
                    link_resultado = ""
                    try:
                        # A linha abaixo continua importante para garantir 11 dígitos com zeros à esquerda
                        cpf = str(linha['cpf_paciente']).zfill(11)
                        nome_cliente = str(linha['nome_paciente'])
                        valor_num = float(str(linha['valor_proposta']).replace(',', '.'))
                        valor_str = f"{valor_num:.2f}".replace('.', ',')
                        descricao = f"Proposta para {nome_cliente}"
                        parcelas = "1"
                        
                        page.goto("https://plataforma.maistodos.com.br/payments/payment-link/create")
                        
                        page.wait_for_selector('input[name="customerDocument"]')
                        page.fill('input[name="customerDocument"]', cpf)
                        page.fill('input[name="customerName"]', nome_cliente)
                        page.fill('input[name="messageMain"]', descricao)
                        page.fill('input[name="amount"]', valor_str)
                        page.fill('input[name="maxInstallments"]', parcelas)
                        page.get_by_text("Pix").click()
                        page.get_by_text("Cartão de crédito").click()

                        with page.expect_response("**/payments/payment-link/create", timeout=20000) as response_info:
                            page.click('button[type="submit"]:has-text("Gerar link")')
                        
                        response = response_info.value
                        
                        if not response.ok: raise Exception(f"API retornou erro {response.status}")

                        dados_resposta = None
                        for r_line in response.text().splitlines():
                            if r_line.startswith('1:'):
                                dados_resposta = json.loads(r_line[2:])
                                break
                        
                        if dados_resposta and dados_resposta.get('ok'):
                            link_resultado = dados_resposta['data']['url']
                            print(f"    -> Sucesso na tentativa {tentativa + 1}!")
                            break
                        else:
                            erro_msg = dados_resposta.get('error') if dados_resposta else 'Resposta Invalida'
                            raise Exception(f"Erro da aplicação: {erro_msg}")

                    except Exception as e:
                        print(f"    -> Tentativa {tentativa + 1} falhou: {e}")
                        link_resultado = f"ERRO: {e}"
                        if tentativa < TENTATIVAS_POR_LINHA - 1:
                            print(f"    -> Tentando novamente em {ESPERA_ENTRE_TENTATIVAS} segundos...")
                            time.sleep(ESPERA_ENTRE_TENTATIVAS)
                        else:
                            print(f"    -> ERRO FINAL nesta linha após {TENTATIVAS_POR_LINHA} tentativas.")
                
                links_gerados.append(link_resultado)

            print("\n PASSO 3: Adicionando links à planilha e salvando...")
            df['Link de Pagamento'] = links_gerados
            df.to_excel(ARQUIVO_SAIDA, index=False, engine='openpyxl')
            print(f"\nProcesso concluído! Planilha otimizada salva como '{ARQUIVO_SAIDA}'")

        finally:
            print("\nFechando o navegador.")
            browser.close()