#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Análise completa (só leitura, nenhuma gravação) de um dia específico,
cruzando Advbox x Asaas nos DOIS sentidos:

  (1) Asaas -> Advbox: pra cada evento financeiro real na Asaas, existe o
      lançamento certo no Advbox (mesmo cliente, mesmo valor, data certa)?
      [é o que conciliar.py/revisao_3dias.py já fazem]

  (2) Advbox -> Asaas (NOVO, pedido pela Priscila): pra cada lançamento que
      está MARCADO COMO PAGO no Advbox nessa data (bank=ASAAS), existe um
      evento real correspondente na Asaas? Se não existir, é um "lançamento
      fantasma" — o Advbox acha que recebeu, mas o extrato real não mostra
      isso batendo naquele dia.

Não aplica nenhuma correção — só lê e relata.
"""

import json
import re
import sys
import time
import unicodedata
from datetime import datetime

import requests

ADVBOX_TOKEN = "FN01fkXyKtolS8GJMdtUiNQJfM6CWtRm7gxe2ZGacA6LGlsDOMMSvTmDo8Vn"
ASAAS_TOKEN = "$aact_prod_000MzkwODA2MWY2OGM3MWRlMDU2NWM3MzJlNzZmNGZhZGY6OmRjNTA3MGI0LWU2NjAtNDYxZS04MTRiLTkwMDdhZWZkNWM4ODo6JGFhY2hfMTIyYzZhY2ItMmFhYi00M2ZiLTgwMmUtZWUyNmQ0MmE4YTg5"

ADVBOX_BASE = "https://app.advbox.com.br/api/v1"
ASAAS_BASE = "https://api.asaas.com/v3"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

TIPOS_RECEITA = {"PAYMENT_RECEIVED", "RECEIVABLE_ANTICIPATION_GROSS_CREDIT"}
TIPO_TAXA_BANCARIA_CLIENTE = "PAYMENT_FEE"
TIPOS_ANTECIPACAO_BAIXA = {"RECEIVABLE_ANTICIPATION_DEBIT"}
TIPOS_ESTORNO = {"PIX_TRANSACTION_DEBIT_REFUND", "PAYMENT_REFUND"}
TIPOS_TRANSFER = {"TRANSFER"}
TAXAS_DIARIAS_TIPOS = {"INSTANT_TEXT_MESSAGE_FEE", "RECEIVABLE_ANTICIPATION_FEE", "INVOICE_FEE"}

TODOS_TIPOS_CONHECIDOS = (
    TIPOS_RECEITA | {TIPO_TAXA_BANCARIA_CLIENTE} | TIPOS_ANTECIPACAO_BAIXA
    | TIPOS_ESTORNO | TIPOS_TRANSFER | TAXAS_DIARIAS_TIPOS
)


def log(msg):
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}", flush=True)


def normalizar_nome(nome):
    if not nome:
        return ""
    nome = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    nome = re.sub(r"[^a-zA-Z0-9 ]", " ", nome)
    nome = re.sub(r"\s+", " ", nome).strip().lower()
    return nome


def centavos_iguais(a, b, tol=0.01):
    return abs(round(a, 2) - round(b, 2)) <= tol


def extrair_numero_fatura(item_asaas: dict) -> str:
    """Extrai o número da fatura/parcela de um item Asaas."""
    desc = (item_asaas.get("description") or "").strip()
    if not desc:
        return ""
    match = re.search(r'fatura\s+(?:nr\.?\s+)?(\d+)', desc, re.IGNORECASE)
    if match:
        return match.group(1)
    return ""


def extrair_nome_cliente_asaas(item_asaas: dict) -> str:
    """Extrai apenas o nome do cliente da description de um item Asaas."""
    desc = (item_asaas.get("description") or "").strip()
    if not desc:
        return ""
    match = re.search(r'fatura\s+nr\.?\s+\d+\s+(.+)', desc, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r'([A-Z][A-Z\s]+)$', desc)
    if match:
        return match.group(1).strip()
    return desc


def verificar_multiplas_parcelas_mesmo_cliente(nome_asaas: str, valor: float, asaas_itens: list) -> bool:
    """Verifica se há múltiplas transações do mesmo cliente com diferentes números de fatura."""
    nome_cliente = normalizar_nome(extrair_nome_cliente_asaas({"description": nome_asaas}))
    if not nome_cliente:
        nome_cliente = normalizar_nome(nome_asaas)
    if not nome_cliente:
        return False

    faturas_encontradas = set()
    for item in asaas_itens:
        nome_item = normalizar_nome(extrair_nome_cliente_asaas(item))
        valor_item = float(item.get("value", 0))
        if nome_item and (nome_cliente in nome_item or nome_item in nome_cliente) and centavos_iguais(valor, valor_item):
            fatura = extrair_numero_fatura(item)
            if fatura:
                faturas_encontradas.add(fatura)

    return len(faturas_encontradas) > 1


def advbox_get(path, params=None, tentativas=5):
    url = f"{ADVBOX_BASE}{path}"
    headers = {"Authorization": f"Bearer {ADVBOX_TOKEN}", "User-Agent": UA, "Accept": "application/json"}
    for tentativa in range(1, tentativas + 1):
        resp = requests.get(url, headers=headers, params=params or {}, timeout=30)
        if resp.status_code == 200:
            try:
                return resp.json()
            except ValueError:
                log(f"Advbox 200 mas corpo nao e JSON em {path} (tentativa {tentativa})")
        else:
            log(f"Advbox GET {path} -> status {resp.status_code} (tentativa {tentativa}/{tentativas})")
        time.sleep(min(2 ** tentativa, 20))
    raise RuntimeError(f"Falha ao consultar Advbox {path}")


def advbox_get_all_transactions(limite_paginas=50):
    todos, offset, limite = [], 0, 1000
    for _ in range(limite_paginas):
        pagina = advbox_get("/transactions", {"limit": limite, "offset": offset})
        itens = pagina if isinstance(pagina, list) else pagina.get("data", [])
        if not itens:
            break
        todos.extend(itens)
        if len(itens) < limite:
            break
        offset += limite
        time.sleep(0.3)
    log(f"Advbox: {len(todos)} lancamentos no total")
    return todos


def asaas_get(path, params=None, tentativas=5):
    url = f"{ASAAS_BASE}{path}"
    headers = {"access_token": ASAAS_TOKEN}
    for tentativa in range(1, tentativas + 1):
        resp = requests.get(url, headers=headers, params=params or {}, timeout=30)
        if resp.status_code == 200:
            try:
                return resp.json()
            except ValueError:
                log(f"Asaas 200 mas corpo nao e JSON em {path} (tentativa {tentativa})")
        else:
            log(f"Asaas {path} -> status {resp.status_code} (tentativa {tentativa}/{tentativas})")
        time.sleep(min(2 ** tentativa, 20))
    raise RuntimeError(f"Falha ao consultar Asaas {path}")


def asaas_financial_do_dia(data_alvo):
    todos, offset, limite = [], 0, 100
    while True:
        pagina = asaas_get("/financialTransactions", {"startDate": data_alvo, "finishDate": data_alvo, "limit": limite, "offset": offset})
        itens = pagina.get("data", [])
        if not itens:
            break
        todos.extend(itens)
        if not pagina.get("hasMore"):
            break
        offset += limite
        time.sleep(0.2)
    do_dia = [i for i in todos if i.get("date") == data_alvo]
    log(f"Asaas: {len(do_dia)} eventos financeiros em {data_alvo}")
    return do_dia


def encontrar_candidatos(nome_asaas, valor, advbox_itens):
    nome_norm = normalizar_nome(nome_asaas)
    candidatos = []
    for item in advbox_itens:
        nome_adv = normalizar_nome(item.get("name") or item.get("customer_name") or "")
        valor_adv = float(item.get("amount", 0) or 0)
        if not (nome_norm and nome_adv):
            continue
        if (nome_norm in nome_adv or nome_adv in nome_norm) and centavos_iguais(valor, valor_adv):
            candidatos.append(item)
    return candidatos


def analisar_dia(data_alvo, advbox_todos):
    asaas_itens = asaas_financial_do_dia(data_alvo)
    advbox_asaas = [i for i in advbox_todos if (i.get("debit_bank") or i.get("bank") or "").upper() == "ASAAS"]

    # ---------- SENTIDO 1: Asaas -> Advbox (já existente) ----------
    receita_asaas = [i for i in asaas_itens if i.get("type") in TIPOS_RECEITA]
    taxa_bancaria_asaas = [i for i in asaas_itens if i.get("type") == TIPO_TAXA_BANCARIA_CLIENTE]
    estorno_asaas = [i for i in asaas_itens if i.get("type") in TIPOS_ESTORNO]
    transfer_asaas = [i for i in asaas_itens if i.get("type") in TIPOS_TRANSFER]
    baixa_antecipacao_asaas = [i for i in asaas_itens if i.get("type") in TIPOS_ANTECIPACAO_BAIXA]
    outros_asaas = [i for i in asaas_itens if i.get("type") not in TODOS_TIPOS_CONHECIDOS]

    receita_ok, receita_data_errada, receita_faltando = [], [], []
    for item in receita_asaas:
        nome = (item.get("description") or "") + " " + (item.get("customerName") or "")
        valor = float(item.get("value", 0))
        candidatos = encontrar_candidatos(nome, valor, advbox_asaas)
        candidatos_no_dia = [c for c in candidatos if c.get("date_payment") == data_alvo]

        # Verifica se há múltiplas parcelas (faturas diferentes) do mesmo cliente
        # Passa asaas_itens COMPLETO (sem filtro de data) pra encontrar parcelas de qualquer data
        tem_multiplas_parcelas = verificar_multiplas_parcelas_mesmo_cliente(nome, valor, asaas_itens)

        if candidatos_no_dia:
            if not tem_multiplas_parcelas:
                receita_ok.append(item)
            else:
                # Múltiplas parcelas diferentes — deixa pra decisão manual
                receita_faltando.append({"asaas": item, "candidatos": len(candidatos)})
        elif len(candidatos) == 1:
            if not tem_multiplas_parcelas:
                receita_data_errada.append({"asaas": item, "advbox": candidatos[0]})
            else:
                # Múltiplas parcelas diferentes — deixa pra decisão manual
                receita_faltando.append({"asaas": item, "candidatos": len(candidatos)})
        else:
            receita_faltando.append({"asaas": item, "candidatos": len(candidatos)})

    taxa_ok, taxa_data_errada, taxa_faltando = [], [], []
    for item in taxa_bancaria_asaas:
        nome = (item.get("description") or "") + " " + (item.get("customerName") or "")
        valor = abs(float(item.get("value", 0)))
        candidatos = encontrar_candidatos(nome, valor, advbox_asaas)
        candidatos_no_dia = [c for c in candidatos if c.get("date_payment") == data_alvo]

        # Verifica se há múltiplas parcelas (faturas diferentes) do mesmo cliente
        # Passa asaas_itens COMPLETO (sem filtro de data) pra encontrar parcelas de qualquer data
        tem_multiplas_parcelas = verificar_multiplas_parcelas_mesmo_cliente(nome, valor, asaas_itens)

        if candidatos_no_dia:
            if not tem_multiplas_parcelas:
                taxa_ok.append(item)
            else:
                # Múltiplas parcelas diferentes — deixa pra decisão manual
                taxa_faltando.append({"asaas": item, "candidatos": len(candidatos)})
        elif len(candidatos) == 1:
            if not tem_multiplas_parcelas:
                taxa_data_errada.append({"asaas": item, "advbox": candidatos[0]})
            else:
                # Múltiplas parcelas diferentes — deixa pra decisão manual
                taxa_faltando.append({"asaas": item, "candidatos": len(candidatos)})
        else:
            taxa_faltando.append({"asaas": item, "candidatos": len(candidatos)})

    # Taxas diárias (comunicação, antecipação, fatura)
    taxas_diarias_asaas = [i for i in asaas_itens if i.get("type") in TAXAS_DIARIAS_TIPOS]
    taxa_diaria_ok, taxa_diaria_data_errada, taxa_diaria_faltando = [], [], []
    for item in taxas_diarias_asaas:
        nome = (item.get("description") or "") + " " + (item.get("customerName") or "")
        valor = abs(float(item.get("value", 0)))
        candidatos = encontrar_candidatos(nome, valor, advbox_asaas)
        candidatos_no_dia = [c for c in candidatos if c.get("date_payment") == data_alvo]

        tem_multiplas_parcelas = verificar_multiplas_parcelas_mesmo_cliente(nome, valor, asaas_itens)

        if candidatos_no_dia:
            if not tem_multiplas_parcelas:
                taxa_diaria_ok.append(item)
            else:
                taxa_diaria_faltando.append({"asaas": item, "candidatos": len(candidatos)})
        elif len(candidatos) == 1:
            if not tem_multiplas_parcelas:
                taxa_diaria_data_errada.append({"asaas": item, "advbox": candidatos[0]})
            else:
                taxa_diaria_faltando.append({"asaas": item, "candidatos": len(candidatos)})
        else:
            taxa_diaria_faltando.append({"asaas": item, "candidatos": len(candidatos)})

    # pares "Cobrança recebida" + "Baixa da antecipação" mesma fatura/valor no dia (liquido zero)
    pares_baixa = []
    for r in receita_asaas:
        fatura_r = re.search(r"fatura nr\.? (\d+)", r.get("description") or "")
        for b in baixa_antecipacao_asaas:
            fatura_b = re.search(r"fatura nr\.? (\d+)", b.get("description") or "")
            if fatura_r and fatura_b and fatura_r.group(1) == fatura_b.group(1) and centavos_iguais(abs(float(r.get("value", 0))), abs(float(b.get("value", 0)))):
                pares_baixa.append((r, b))

    # ---------- SENTIDO 2 (NOVO): Advbox -> Asaas ----------
    # Pra cada lancamento do Advbox marcado como pago nesse dia (bank=ASAAS),
    # existe evento real correspondente na Asaas (qualquer tipo, nao só receita)?
    todos_asaas_do_dia = asaas_itens  # já filtrado por data
    fantasmas = []
    advbox_pagos_no_dia = [i for i in advbox_asaas if i.get("date_payment") == data_alvo]

    # Somas de taxas diárias por tipo (para reconhecer consolidações)
    soma_msg_fee = sum(abs(float(i.get("value", 0))) for i in taxas_diarias_asaas if i.get("type") == "INSTANT_TEXT_MESSAGE_FEE")
    soma_anticipation_fee = sum(abs(float(i.get("value", 0))) for i in taxas_diarias_asaas if i.get("type") == "RECEIVABLE_ANTICIPATION_FEE")
    soma_invoice_fee = sum(abs(float(i.get("value", 0))) for i in taxas_diarias_asaas if i.get("type") == "INVOICE_FEE")

    for item in advbox_pagos_no_dia:
        nome_adv = item.get("name") or item.get("customer_name") or ""
        valor_adv = abs(float(item.get("amount", 0) or 0))
        desc_adv = (item.get("description") or "").upper()
        nome_norm = normalizar_nome(nome_adv)
        tem_correspondente = False

        # Verifica se é uma consolidação de taxa diária
        if "TAXA DE COMUNICA" in desc_adv and centavos_iguais(valor_adv, soma_msg_fee):
            tem_correspondente = True
        elif "TAXA DE ANTECIPA" in desc_adv and centavos_iguais(valor_adv, soma_anticipation_fee):
            tem_correspondente = True
        elif "TAXA DE FATURA" in desc_adv and centavos_iguais(valor_adv, soma_invoice_fee):
            tem_correspondente = True
        else:
            # Busca por correspondência individual (cliente + valor)
            for e in todos_asaas_do_dia:
                nome_e = (e.get("description") or "") + " " + (e.get("customerName") or "")
                valor_e = abs(float(e.get("value", 0)))
                if nome_norm and normalizar_nome(nome_e) and (nome_norm in normalizar_nome(nome_e) or normalizar_nome(nome_e) in nome_norm) and centavos_iguais(valor_adv, valor_e):
                    tem_correspondente = True
                    break

        if not tem_correspondente:
            fantasmas.append(item)

    return {
        "data": data_alvo,
        "receita_ok": receita_ok,
        "receita_data_errada": receita_data_errada,
        "receita_faltando": receita_faltando,
        "taxa_ok": taxa_ok,
        "taxa_data_errada": taxa_data_errada,
        "taxa_faltando": taxa_faltando,
        "taxa_diaria_ok": taxa_diaria_ok,
        "taxa_diaria_data_errada": taxa_diaria_data_errada,
        "taxa_diaria_faltando": taxa_diaria_faltando,
        "transferencias": transfer_asaas,
        "estornos": estorno_asaas,
        "outros_nao_classificados": outros_asaas,
        "pares_baixa_antecipacao": [(r.get("description"), r.get("value"), b.get("value")) for r, b in pares_baixa],
        "advbox_fantasmas": fantasmas,
        "total_advbox_pagos_no_dia": len(advbox_pagos_no_dia),
    }


def main():
    data_alvo = sys.argv[1] if len(sys.argv) > 1 else "2026-09-08"
    advbox_todos = advbox_get_all_transactions()
    resultado = analisar_dia(data_alvo, advbox_todos)
    with open(f"/home/claude/advbox-asaas-conciliacao/analise_{data_alvo}.json", "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2, default=str)
    log(f"Salvo em analise_{data_alvo}.json")


if __name__ == "__main__":
    main()
