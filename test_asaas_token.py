#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para diagnosticar o problema de autenticação com a API Asaas.

Uso:
  ASAAS_TOKEN="seu_token" python test_asaas_token.py

Este script tenta fazer uma chamada simples à API do Asaas para validar
se o token está funcionando corretamente.
"""

import os
import sys
import time
from datetime import datetime, timedelta

import requests

ASAAS_TOKEN = os.environ.get("ASAAS_TOKEN", "")
ASAAS_BASE = "https://api.asaas.com/v3"


def log(msg):
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}", flush=True)


def test_token():
    """Testa se o token Asaas está funcionando."""

    log("=" * 70)
    log("TESTE DE AUTENTICAÇÃO - API ASAAS")
    log("=" * 70)

    # 1. Verificar se o token está configurado
    if not ASAAS_TOKEN:
        log("❌ ERRO: ASAAS_TOKEN não configurado!")
        log("   Defina a variável de ambiente ASAAS_TOKEN com seu token de acesso.")
        log("")
        log("Exemplo de uso:")
        log("   ASAAS_TOKEN='seu_token_aqui' python test_asaas_token.py")
        return False

    log(f"✓ Token configurado (primeiros 20 chars): {ASAAS_TOKEN[:20]}...")
    log("")

    # 2. Tentar uma chamada simples à API
    log("Tentando chamar /financialTransactions com data de hoje...")

    # Usar data de hoje (ou ontem se preferir)
    data_hoje = datetime.now().strftime("%Y-%m-%d")

    headers = {"access_token": ASAAS_TOKEN}
    params = {
        "startDate": data_hoje,
        "finishDate": data_hoje,
        "limit": 1,
        "offset": 0
    }

    url = f"{ASAAS_BASE}/financialTransactions"

    log(f"URL: {url}")
    log(f"Headers: {{'access_token': '{ASAAS_TOKEN[:20]}...'}}")
    log(f"Params: {params}")
    log("")

    for tentativa in range(1, 4):
        try:
            log(f"Tentativa {tentativa}/3...")
            resp = requests.get(url, headers=headers, params=params, timeout=10)

            log(f"Status HTTP: {resp.status_code}")
            log(f"Content-Type: {resp.headers.get('content-type', 'N/A')}")
            log("")

            if resp.status_code == 200:
                log("✓ SUCESSO! O token está funcionando corretamente.")
                log("")
                try:
                    data = resp.json()
                    log(f"Resposta JSON recebida:")
                    log(f"  - Tipo de resposta: {type(data).__name__}")
                    if isinstance(data, dict):
                        log(f"  - Chaves: {list(data.keys())}")
                        if "data" in data:
                            log(f"  - Quantidade de itens: {len(data['data'])}")
                        if "hasMore" in data:
                            log(f"  - Há mais páginas: {data['hasMore']}")
                    elif isinstance(data, list):
                        log(f"  - Quantidade de itens: {len(data)}")
                except Exception as e:
                    log(f"Aviso: Resposta 200 mas não é JSON válido: {e}")

                return True

            elif resp.status_code == 401:
                log("❌ ERRO 401 - Não Autorizado")
                log("   Possíveis causas:")
                log("   1. O token está expirado")
                log("   2. O token foi revogado")
                log("   3. O token não é válido")
                log("   4. O formato do token está incorreto")
                log("")
                log("Ação recomendada:")
                log("   Verifique o token no Asaas e gere um novo se necessário.")
                log("   Após gerar novo token, atualize o secret ASAAS_TOKEN no GitHub.")

                try:
                    body = resp.json()
                    if "errors" in body:
                        log(f"   Erro detalhado: {body['errors']}")
                except:
                    log(f"   Corpo da resposta: {resp.text[:200]}")

                return False

            elif resp.status_code == 400:
                log("❌ ERRO 400 - Requisição Inválida")
                log("   Os parâmetros da requisição podem estar incorretos.")
                try:
                    body = resp.json()
                    log(f"   Erro: {body}")
                except:
                    log(f"   Corpo: {resp.text[:200]}")
                return False

            else:
                log(f"❌ ERRO {resp.status_code}")
                log(f"   Resposta: {resp.text[:500]}")

                if tentativa < 3:
                    log(f"   Aguardando antes de nova tentativa...")
                    time.sleep(2 ** tentativa)
                    continue

                return False

        except requests.exceptions.Timeout:
            log(f"❌ ERRO: Timeout na tentativa {tentativa}/3")
            if tentativa < 3:
                log(f"   Aguardando antes de nova tentativa...")
                time.sleep(2 ** tentativa)

        except requests.exceptions.ConnectionError as e:
            log(f"❌ ERRO: Falha de conexão - {e}")
            return False

        except Exception as e:
            log(f"❌ ERRO inesperado: {e}")
            return False

    log("❌ Falha após 3 tentativas")
    return False


if __name__ == "__main__":
    sucesso = test_token()

    log("")
    log("=" * 70)
    if sucesso:
        log("✓ DIAGNÓSTICO: Token está funcionando!")
        log("  O problema pode estar em outro lugar (Advbox, configuração, etc.)")
    else:
        log("❌ DIAGNÓSTICO: Problema com o token Asaas")
        log("  Próximas ações:")
        log("  1. Acesse o dashboard do Asaas")
        log("  2. Gere um novo token de acesso (API Key)")
        log("  3. Atualize o secret ASAAS_TOKEN no GitHub")
        log("  4. Execute este script novamente para validar")
    log("=" * 70)

    sys.exit(0 if sucesso else 1)
