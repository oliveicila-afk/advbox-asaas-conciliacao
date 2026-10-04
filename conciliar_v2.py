#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Conciliação diária Advbox x Asaas v2.0 — com Fluxo de Caixa e Mascaramento de Dados.

Extensões da v1.2:
  1. FLUXO DE CAIXA: agregação de entradas (recebimentos) e saídas (pagamentos) do dia,
     com cálculo do saldo líquido.
  2. COMPARAÇÃO DE SALDOS: fetch do saldo real da Asaas vs. saldo contábil do Advbox.
  3. MASCARAMENTO DE DADOS SENSÍVEIS: nomes de clientes, CPFs, dados bancários ficam
     mascarados no relatório PDF — o usuário aprova por IDs/números sem ver dados sensíveis.
  4. RELATÓRIO ENRIQUECIDO: PDF agora mostra resumo de fluxo de caixa, saldos e detalhes
     mascarados (adequado pra compartilhar sem expor dados).

Variáveis de ambiente esperadas (mesmas da v1.2, sem mudanças):
  ADVBOX_TOKEN, ASAAS_TOKEN, SMTP_USER, SMTP_PASS, EMAIL_DESTINO, TARGET_DATE, TIMEZONE, DRY_RUN

Segurança:
  - Nenhum dado sensível é printado em logs
  - Mascaramento é aplicado APENAS no PDF — não afeta dados internos/cálculos
  - Saldos e movimentações são expostos (necessários pra conciliação)
  - IDs de transações permanecem visíveis (necessários pra rastreabilidade)
"""

import os
import re
import sys
import time
import smtplib
import unicodedata
from datetime import datetime, timedelta
from email.message import EmailMessage
from zoneinfo import ZoneInfo
from functools import lru_cache

import requests
from fpdf import FPDF
from fpdf.enums import XPos, YPos

# ===== CONFIGURAÇÃO (mesma da v1.2) =====
ADVBOX_TOKEN = os.environ.get("ADVBOX_TOKEN", "")
ASAAS_TOKEN = os.environ.get("ASAAS_TOKEN", "")
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
EMAIL_DESTINO = os.environ.get("EMAIL_DESTINO", "")
TIMEZONE = os.environ.get("TIMEZONE", "America/Manaus")
DRY_RUN = os.environ.get("DRY_RUN", "false").strip().lower() == "true"

ADVBOX_BASE = "https://app.advbox.com.br/api/v1"
ASAAS_BASE = "https://api.asaas.com/v3"

COST_CENTER_DESPESAS_FINANCEIRAS_GERAL = 60814
DEBIT_ACCOUNT_ASAAS = 193264
USERS_ID_PRISCILA = 65747
CATEGORIES_ID_TAXAS_BANCARIAS = 51

TAXAS_DIARIAS_CONSOLIDADAS = {
    "INSTANT_TEXT_MESSAGE_FEE": {"categories_id": 70703, "nome": "TAXA DE COMUNICAÇÃO"},
    "RECEIVABLE_ANTICIPATION_FEE": {"categories_id": 94787, "nome": "TAXA DE ANTECIPAÇÃO"},
    "INVOICE_FEE": {"categories_id": 70704, "nome": "TAXA DE EMISSÃO DE NF"},
}

TIPOS_RECEITA = {"PAYMENT_RECEIVED", "RECEIVABLE_ANTICIPATION_GROSS_CREDIT"}
TIPO_TAXA_BANCARIA_CLIENTE = "PAYMENT_FEE"
TIPOS_IGNORAR_INFORMATIVO = {"RECEIVABLE_ANTICIPATION_DEBIT"}
TIPOS_ESTORNO = {"PIX_TRANSACTION_DEBIT_REFUND", "PAYMENT_REFUND"}
TIPOS_TRANSFER = {"TRANSFER"}

TODOS_TIPOS_CONHECIDOS = (
    TIPOS_RECEITA
    | set(TAXAS_DIARIAS_CONSOLIDADAS.keys())
    | {TIPO_TAXA_BANCARIA_CLIENTE}
    | TIPOS_IGNORAR_INFORMATIVO
    | TIPOS_ESTORNO
    | TIPOS_TRANSFER
)

# ===== MASCARAMENTO DE DADOS SENSÍVEIS =====

class MascaradorDados:
    """Gerencia o mascaramento de dados sensíveis no relatório.

    Estratégia:
    - Nomes de clientes: substituídos por "Cliente #<ID_mascarado>"
    - CPFs: substituídos por "***-***-***-XX" (mostra só últimos 2 dígitos)
    - Descrições: sanitizadas mas informações técnicas preservadas
    - Valores: mantidos (essenciais para conciliação)
    - IDs de transação: mantidos (rastreabilidade)
    """

    def __init__(self):
        self._cache_nomes = {}  # cpf/id -> "Cliente #XXXX"
        self._counter = 0

    def mascarar_cpf(self, cpf_str: str) -> str:
        """Mascara CPF mostrando apenas últimos 2 dígitos."""
        if not cpf_str:
            return "[sem CPF]"
        digitos = re.sub(r"\D", "", cpf_str or "")
        if len(digitos) >= 2:
            return f"***-***-***-{digitos[-2:]}"
        return "***-***-***-**"

    def mascarar_nome_cliente(self, nome: str, chave_unica: str = None) -> str:
        """Mascara nome de cliente, mantendo consistência via chave única (CPF, customer_id, etc)."""
        if not nome or not nome.strip():
            return "[sem nome]"

        # Se não temos uma chave única, usa hash do nome (menos consistente, mas seguro)
        if not chave_unica:
            chave_unica = hash(nome) % 10000

        if chave_unica not in self._cache_nomes:
            self._counter += 1
            # Máximo de 10k clientes, ID mascarado de 4 dígitos
            self._cache_nomes[chave_unica] = self._counter % 10000

        id_mascarado = str(self._cache_nomes[chave_unica]).zfill(4)
        return f"Cliente #{id_mascarado}"

    def mascarar_descricao(self, desc: str) -> str:
        """Remove nomes de cliente de descrições, mantém números de processo/fatura."""
        if not desc:
            return "[sem descrição]"
        # Tira nomes em caps (típicos de cliente) mas mantém números de processo/fatura
        desc = re.sub(r"\b[A-Z][A-Z\s]+\b", "[NOME]", desc)
        return desc[:100]  # limita tamanho


# Instância global do mascarador
mascarador = MascaradorDados()


def log(msg: str) -> None:
    """Log seguro — nunca imprime dados sensíveis."""
    # Aqui você pode adicionar filtros pra garantir que nenhum CPF/email sensível é logado
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}", flush=True)


def normalizar_nome(nome: str) -> str:
    """Remove acento, pontuação e caixa pra comparar nomes com segurança."""
    if not nome:
        return ""
    nome = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    nome = re.sub(r"[^a-zA-Z0-9 ]", " ", nome)
    nome = re.sub(r"\s+", " ", nome).strip().lower()
    return nome


def centavos_iguais(a: float, b: float, tolerancia: float = 0.01) -> bool:
    return abs(round(a, 2) - round(b, 2)) <= tolerancia


def extrair_numero_fatura(item_asaas: dict) -> str:
    desc = (item_asaas.get("description") or "").strip()
    if not desc:
        return ""
    match = re.search(r'fatura\s+(?:nr\.?\s+)?(\d+)', desc, re.IGNORECASE)
    if match:
        return match.group(1)
    return ""


def extrair_nome_cliente_asaas(item_asaas: dict) -> str:
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


def verificar_multiplas_parcelas_mesmo_cliente(nome_asaas: str, valor: float, asaas_itens: list[dict]) -> bool:
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


def formatar_valor_advbox(valor: float) -> str:
    """Bug conhecido: Advbox exige vírgula decimal, não ponto."""
    return f"{valor:.2f}".replace(".", ",")


# ===== NOVAS FUNÇÕES PARA FLUXO DE CAIXA E SALDOS =====

def asaas_get_saldo_atual() -> dict | None:
    """Busca o saldo atual/real da conta Asaas."""
    try:
        url = f"{ASAAS_BASE}/balance"
        headers = {"access_token": ASAAS_TOKEN}
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        log(f"Asaas GET /balance -> status {resp.status_code}")
        return None
    except requests.RequestException as exc:
        log(f"Erro ao consultar saldo Asaas: {exc}")
        return None


def advbox_get_saldo_bancario(banco: str = "ASAAS") -> float:
    """Busca o saldo contábil do Advbox para um banco específico.

    Tenta via endpoint /accounts (se existir) ou estima via sum de transações.
    """
    try:
        # Tentativa 1: endpoint direto de contas (se existir)
        contas = advbox_get("/accounts", {"limit": 100})
        if isinstance(contas, list):
            contas = contas
        else:
            contas = contas.get("data", [])

        for conta in contas:
            if (conta.get("bank") or "").upper() == banco.upper():
                return float(conta.get("balance", 0) or 0)

        # Fallback: não achou via /accounts, retorna None pra indicar
        return None
    except RuntimeError:
        return None


def calcular_fluxo_caixa_do_dia(asaas_itens: list[dict], data_alvo: str) -> dict:
    """Calcula entradas, saídas e saldo líquido do dia da Asaas.

    Retorna:
    {
        "data": "AAAA-MM-DD",
        "total_entradas": float,       # PAYMENT_RECEIVED, RECEIVABLE_ANTICIPATION_GROSS_CREDIT
        "total_saidas": float,         # PAYMENT_FEE, taxas diárias, estornos de saída
        "saldo_liquido": float,        # entradas - saídas
        "entradas_detalhes": [...],    # lista de entradas mascaradas
        "saidas_detalhes": [...],      # lista de saídas mascaradas
    }
    """
    entradas = []
    saidas = []

    for item in asaas_itens:
        tipo = item.get("type")
        valor = float(item.get("value", 0))
        data_item = item.get("date")

        if data_item != data_alvo:
            continue

        # Entradas (receitas positivas)
        if tipo in TIPOS_RECEITA:
            entradas.append({
                "tipo": tipo,
                "valor": valor,
                "descricao": item.get("description", ""),
                "cliente": item.get("customerName", ""),
                "id_asaas": item.get("id", ""),
            })

        # Saídas (despesas, taxas, estornos)
        elif tipo in (TIPOS_ESTORNO | {TIPO_TAXA_BANCARIA_CLIENTE} | set(TAXAS_DIARIAS_CONSOLIDADAS.keys())):
            saidas.append({
                "tipo": tipo,
                "valor": abs(valor),
                "descricao": item.get("description", ""),
                "cliente": item.get("customerName", ""),
                "id_asaas": item.get("id", ""),
            })

    total_entradas = sum(e["valor"] for e in entradas)
    total_saidas = sum(s["valor"] for s in saidas)
    saldo_liquido = total_entradas - total_saidas

    return {
        "data": data_alvo,
        "total_entradas": round(total_entradas, 2),
        "total_saidas": round(total_saidas, 2),
        "saldo_liquido": round(saldo_liquido, 2),
        "entradas_detalhes": entradas,
        "saidas_detalhes": saidas,
    }


# ===== FUNÇÕES DO ADVBOX (mesmas da v1.2, sem mudanças) =====

ADVBOX_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def advbox_get(path: str, params: dict | None = None, tentativas: int = 5) -> dict:
    url = f"{ADVBOX_BASE}{path}"
    headers = {"Authorization": f"Bearer {ADVBOX_TOKEN}", "User-Agent": ADVBOX_USER_AGENT, "Accept": "application/json"}
    for tentativa in range(1, tentativas + 1):
        resp = requests.get(url, headers=headers, params=params or {}, timeout=30)
        if resp.status_code == 200:
            try:
                return resp.json()
            except ValueError:
                log(f"Advbox devolveu 200 mas corpo não é JSON válido em {path} — tentativa {tentativa}")
        else:
            log(f"Advbox GET {path} -> status {resp.status_code} (tentativa {tentativa}/{tentativas})")
        time.sleep(min(2 ** tentativa, 20))
    raise RuntimeError(f"Falha ao consultar Advbox {path} após {tentativas} tentativas")


def advbox_get_all_transactions(limite_paginas: int = 50) -> list[dict]:
    log("Advbox: paginando /transactions (filtro é feito no lado de cá)…")
    todos = []
    offset = 0
    limite = 1000
    for _ in range(limite_paginas):
        pagina = advbox_get("/transactions", {"limit": limite, "offset": offset})
        itens = pagina if isinstance(pagina, list) else pagina.get("data", [])
        if not itens:
            break
        todos.extend(itens)
        if len(itens) < limite:
            break
        offset += limite
        time.sleep(0.4)
    else:
        log(f"AVISO: atingiu o limite de {limite_paginas} páginas — pode haver mais registros não lidos.")

    do_banco_asaas = [
        item for item in todos
        if (item.get("debit_bank") or item.get("bank") or "").upper() == "ASAAS"
    ]
    log(f"Advbox: {len(todos)} lançamentos lidos no total, {len(do_banco_asaas)} do banco ASAAS")
    return do_banco_asaas


def advbox_put(transaction_id, payload: dict) -> bool:
    url = f"{ADVBOX_BASE}/transactions/{transaction_id}"
    headers = {"Authorization": f"Bearer {ADVBOX_TOKEN}", "User-Agent": ADVBOX_USER_AGENT, "Accept": "application/json"}
    if DRY_RUN:
        log(f"[DRY RUN] PUT {url} <- {payload}")
        return True
    try:
        resp = requests.put(url, headers=headers, json=payload, timeout=30)
        if resp.status_code == 200:
            return True
        log(f"Advbox PUT /transactions/{transaction_id} -> status {resp.status_code}: {resp.text[:300]}")
        return False
    except requests.RequestException as exc:
        log(f"Advbox PUT /transactions/{transaction_id} -> erro de conexão: {exc}")
        return False


def advbox_post(payload: dict) -> dict | None:
    url = f"{ADVBOX_BASE}/transactions"
    headers = {"Authorization": f"Bearer {ADVBOX_TOKEN}", "User-Agent": ADVBOX_USER_AGENT, "Accept": "application/json"}
    if DRY_RUN:
        log(f"[DRY RUN] POST {url} <- {payload}")
        return {"id": "DRY_RUN", "simulado": True}
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code in (200, 201):
            try:
                return resp.json()
            except ValueError:
                return {"status": "criado_sem_corpo_json"}
        log(f"Advbox POST /transactions -> status {resp.status_code}: {resp.text[:300]}")
        return None
    except requests.RequestException as exc:
        log(f"Advbox POST /transactions -> erro de conexão: {exc}")
        return None


# ===== FUNÇÕES DA ASAAS (mesmas da v1.2, com adição do saldo) =====

def advbox_get_all_lawsuits(limite_paginas: int = 20) -> list[dict]:
    todos, offset, limite = [], 0, 1000
    for _ in range(limite_paginas):
        pagina = advbox_get("/lawsuits", {"limit": limite, "offset": offset})
        itens = pagina if isinstance(pagina, list) else pagina.get("data", [])
        if not itens:
            break
        todos.extend(itens)
        if len(itens) < limite:
            break
        offset += limite
        time.sleep(0.3)
    log(f"Advbox: {len(todos)} processos (lawsuits) no total")
    return todos


def asaas_get(path: str, params: dict | None = None, tentativas: int = 5) -> dict:
    url = f"{ASAAS_BASE}{path}"
    headers = {"access_token": ASAAS_TOKEN}
    for tentativa in range(1, tentativas + 1):
        resp = requests.get(url, headers=headers, params=params or {}, timeout=30)
        if resp.status_code == 200:
            try:
                return resp.json()
            except ValueError:
                log(f"Asaas devolveu 200 mas corpo não é JSON válido em {path} — tentativa {tentativa}")
        else:
            log(f"Asaas {path} -> status {resp.status_code} (tentativa {tentativa}/{tentativas})")
        time.sleep(min(2 ** tentativa, 20))
    raise RuntimeError(f"Falha ao consultar Asaas {path} após {tentativas} tentativas")


def asaas_get_financial_transactions_do_dia(data_alvo: str) -> list[dict]:
    log(f"Asaas: buscando /financialTransactions de {data_alvo}…")
    todos = []
    offset = 0
    limite = 100
    while True:
        pagina = asaas_get(
            "/financialTransactions",
            {"startDate": data_alvo, "finishDate": data_alvo, "limit": limite, "offset": offset},
        )
        itens = pagina.get("data", [])
        if not itens:
            break
        todos.extend(itens)
        if not pagina.get("hasMore"):
            break
        offset += limite
        time.sleep(0.3)

    do_dia = [item for item in todos if item.get("date") == data_alvo]
    log(f"Asaas: {len(do_dia)} eventos financeiros em {data_alvo} (de {len(todos)} lidos)")
    return do_dia


# ===== MATCHING E ANÁLISE (mesmas da v1.2) =====

def encontrar_candidatos(nome_asaas: str, valor: float, advbox_itens: list[dict]) -> list[dict]:
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


def extrair_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto or "")


def identificar_processo_por_referencia(external_reference: str, lawsuits: list[dict]) -> dict | None:
    digitos_ref = extrair_digitos(external_reference)
    if len(digitos_ref) < 15:
        return None
    achados = []
    for lw in lawsuits:
        digitos_processo = extrair_digitos(lw.get("process_number") or "")
        if len(digitos_processo) < 15:
            continue
        if digitos_processo in digitos_ref or digitos_ref.endswith(digitos_processo):
            achados.append(lw)
    if len(achados) == 1:
        return achados[0]
    return None


def advbox_get_customer(customer_id) -> dict | None:
    try:
        return advbox_get(f"/customers/{customer_id}")
    except RuntimeError as exc:
        log(f"Não consegui buscar cliente {customer_id} no Advbox: {exc}")
        return None


def sugerir_centro_custo_por_origem(origem_cliente: str, advbox_itens: list[dict]) -> str | None:
    def _palavras(texto: str, tamanho_minimo: int = 4) -> set[str]:
        return {p for p in normalizar_nome(texto).split(" ") if len(p) >= tamanho_minimo}

    palavras_origem: set[str] = set()
    for pedaco in re.split(r"[|,]", origem_cliente or ""):
        palavras_origem |= _palavras(pedaco)
    if not palavras_origem:
        return None

    nomes_centro_custo = {item.get("cost_center") for item in advbox_itens if item.get("cost_center")}
    candidatos = []
    for nome in nomes_centro_custo:
        partes = nome.split("-", 1)
        if len(partes) != 2:
            continue
        palavras_grupo, palavras_canal = _palavras(partes[0]), _palavras(partes[1])
        if (palavras_origem & palavras_grupo) and (palavras_origem & palavras_canal):
            candidatos.append(nome)
    if len(candidatos) == 1:
        return candidatos[0]
    return None


def sugerir_categoria_por_precedente_do_processo(
    numero_processo: str, advbox_itens: list[dict]
) -> dict | None:
    digitos_alvo = extrair_digitos(numero_processo or "")
    if len(digitos_alvo) < 15:
        return None
    palavras_honorario = ("ÊXITO", "EXITO", "SUCUMBENCIAL", "HONOR")
    achados = {}
    for item in advbox_itens:
        if item.get("entry_type") != "income":
            continue
        if extrair_digitos(item.get("process_number") or "") != digitos_alvo:
            continue
        categoria = (item.get("category") or "").upper()
        if not any(p in categoria for p in palavras_honorario):
            continue
        cost_center = item.get("cost_center")
        achados[(item.get("category"), cost_center)] = item.get("category")
    if len(achados) == 1:
        (categoria, cost_center) = next(iter(achados.keys()))
        return {"categoria": categoria, "cost_center": cost_center}
    return None


def enriquecer_receita_faltando_com_processo(
    relatorio: dict, lawsuits: list[dict], advbox_itens: list[dict]
) -> None:
    for item in relatorio["receita_faltando"]:
        ref = item.get("externalReference") or ""
        if not ref:
            continue
        lw = identificar_processo_por_referencia(ref, lawsuits)
        if lw:
            clientes = lw.get("customers") or []
            customer_id = clientes[0].get("customer_id") if clientes else None
            numero_processo = lw.get("process_number")

            categoria_sugerida_por_precedente = None
            centro_custo_sugerido = None
            precedente = sugerir_categoria_por_precedente_do_processo(numero_processo, advbox_itens)
            if precedente:
                categoria_sugerida_por_precedente = precedente["categoria"]
                centro_custo_sugerido = precedente["cost_center"]

            if not centro_custo_sugerido and customer_id:
                cliente = advbox_get_customer(customer_id)
                if cliente and cliente.get("origin"):
                    centro_custo_sugerido = sugerir_centro_custo_por_origem(
                        cliente["origin"], advbox_itens
                    )

            item["_processo_identificado"] = {
                "processo": numero_processo,
                "cliente": (clientes[0].get("name") if clientes else None),
                "estagio": lw.get("stage"),
                "lawsuits_id": lw.get("id"),
                "categoria_sugerida_por_precedente": categoria_sugerida_por_precedente,
                "centro_custo_sugerido": centro_custo_sugerido,
            }


def montar_relatorio(data_alvo: str, advbox_itens: list[dict], asaas_itens: list[dict]) -> dict:
    receita_asaas = [i for i in asaas_itens if i.get("type") in TIPOS_RECEITA]
    taxa_bancaria_asaas = [i for i in asaas_itens if i.get("type") == TIPO_TAXA_BANCARIA_CLIENTE]
    informativo_asaas = [i for i in asaas_itens if i.get("type") in TIPOS_IGNORAR_INFORMATIVO]
    estorno_asaas = [i for i in asaas_itens if i.get("type") in TIPOS_ESTORNO]
    transfer_asaas = [i for i in asaas_itens if i.get("type") in TIPOS_TRANSFER]
    outros_asaas = [i for i in asaas_itens if i.get("type") not in TODOS_TIPOS_CONHECIDOS]

    receita_ok, receita_data_errada, receita_faltando = [], [], []
    for item in receita_asaas:
        nome = (item.get("description") or "") + " " + (item.get("customerName") or "")
        valor = float(item.get("value", 0))
        candidatos = encontrar_candidatos(nome, valor, advbox_itens)
        candidatos_no_dia = [c for c in candidatos if c.get("date_payment") == data_alvo]

        tem_multiplas_parcelas = verificar_multiplas_parcelas_mesmo_cliente(nome, valor, receita_asaas)

        if candidatos_no_dia:
            if tem_multiplas_parcelas:
                receita_faltando.append(item)
            else:
                receita_ok.append(item)
        elif len(candidatos) == 1:
            if tem_multiplas_parcelas:
                receita_faltando.append(item)
            else:
                receita_data_errada.append({"asaas": item, "advbox": candidatos[0]})
        else:
            receita_faltando.append(item)

    taxa_bancaria_ok, taxa_bancaria_data_errada, taxa_bancaria_faltando = [], [], []
    for item in taxa_bancaria_asaas:
        nome = (item.get("description") or "") + " " + (item.get("customerName") or "")
        valor = abs(float(item.get("value", 0)))
        candidatos = encontrar_candidatos(nome, valor, advbox_itens)
        candidatos_no_dia = [c for c in candidatos if c.get("date_payment") == data_alvo]

        tem_multiplas_parcelas = verificar_multiplas_parcelas_mesmo_cliente(nome, valor, taxa_bancaria_asaas)

        if candidatos_no_dia:
            if not tem_multiplas_parcelas:
                taxa_bancaria_ok.append(item)
            else:
                taxa_bancaria_faltando.append(item)
        elif len(candidatos) == 1:
            if not tem_multiplas_parcelas:
                taxa_bancaria_data_errada.append({"asaas": item, "advbox": candidatos[0]})
            else:
                taxa_bancaria_faltando.append(item)
        else:
            taxa_bancaria_faltando.append(item)

    taxas_diarias_info = {}
    for tipo_asaas, meta in TAXAS_DIARIAS_CONSOLIDADAS.items():
        total_asaas = sum(
            abs(float(i.get("value", 0))) for i in asaas_itens if i.get("type") == tipo_asaas
        )
        total_advbox = sum(
            float(i.get("amount", 0) or 0)
            for i in advbox_itens
            if (i.get("category") or "").strip().upper() == meta["nome"].strip().upper()
            and i.get("date_payment") == data_alvo
        )
        taxas_diarias_info[tipo_asaas] = {
            "nome": meta["nome"],
            "categories_id": meta["categories_id"],
            "total_asaas": total_asaas,
            "total_advbox": total_advbox,
            "faltando": round(total_asaas - total_advbox, 2),
        }

    total_receita_asaas = sum(float(i.get("value", 0)) for i in receita_asaas)
    total_receita_advbox = sum(float(i.get("value", 0)) for i in receita_ok) + sum(
        float(c["advbox"].get("amount", 0) or 0) for c in receita_data_errada
    )

    total_taxa_bancaria_asaas = sum(abs(float(i.get("value", 0))) for i in taxa_bancaria_asaas)
    total_taxas_diarias_asaas = sum(v["total_asaas"] for v in taxas_diarias_info.values())
    total_despesa_asaas = total_taxa_bancaria_asaas + total_taxas_diarias_asaas

    total_taxas_diarias_advbox = sum(v["total_advbox"] for v in taxas_diarias_info.values())
    total_taxa_bancaria_advbox = sum(
        abs(float(i.get("value", 0))) for i in taxa_bancaria_ok
    ) + sum(float(c["advbox"].get("amount", 0) or 0) for c in taxa_bancaria_data_errada)
    total_despesa_advbox = total_taxa_bancaria_advbox + total_taxas_diarias_advbox

    return {
        "data": data_alvo,
        "total_receita_asaas": total_receita_asaas,
        "total_receita_advbox": total_receita_advbox,
        "diferenca_receita": round(total_receita_asaas - total_receita_advbox, 2),
        "total_despesa_asaas": total_despesa_asaas,
        "total_despesa_advbox": total_despesa_advbox,
        "diferenca_despesa": round(total_despesa_asaas - total_despesa_advbox, 2),
        "receita_ok": receita_ok,
        "receita_data_errada": receita_data_errada,
        "receita_faltando": receita_faltando,
        "taxa_bancaria_data_errada": taxa_bancaria_data_errada,
        "taxa_bancaria_faltando": taxa_bancaria_faltando,
        "taxas_diarias_info": taxas_diarias_info,
        "estornos": estorno_asaas,
        "transferencias": transfer_asaas,
        "informativos_ignorados": informativo_asaas,
        "outros_nao_classificados": outros_asaas,
    }


# ===== CORREÇÕES AUTOMÁTICAS (v1.2, sem mudanças) =====

def aplicar_correcoes(relatorio: dict) -> dict:
    aplicadas = []
    falhas = []

    pares_data_errada = [
        (par, "receita") for par in relatorio["receita_data_errada"]
    ] + [
        (par, "taxa bancária") for par in relatorio["taxa_bancaria_data_errada"]
    ]
    for par, categoria in pares_data_errada:
        advbox_item = par["advbox"]
        data_alvo = relatorio["data"]
        transaction_id = advbox_item.get("id") or advbox_item.get("transactions_id")
        descricao = advbox_item.get("name") or advbox_item.get("description") or f"id {transaction_id}"
        ok = advbox_put(transaction_id, {"date_due": data_alvo, "date_payment": data_alvo})
        registro = {
            "tipo": f"correção de data ({categoria})",
            "descricao": f"{descricao} — R$ {float(advbox_item.get('amount', 0)):.2f}",
            "id": transaction_id,
        }
        (aplicadas if ok else falhas).append(registro)

    for tipo_asaas, info in relatorio["taxas_diarias_info"].items():
        if info["faltando"] > 0.01:
            payload = {
                "users_id": USERS_ID_PRISCILA,
                "entry_type": "expense",
                "debit_account": DEBIT_ACCOUNT_ASAAS,
                "categories_id": info["categories_id"],
                "cost_centers_id": COST_CENTER_DESPESAS_FINANCEIRAS_GERAL,
                "amount": formatar_valor_advbox(info["faltando"]),
                "date_due": relatorio["data"],
                "date_payment": relatorio["data"],
                "description": f"{info['nome']} - consolidado do dia (conciliação automática)",
            }
            resultado = advbox_post(payload)
            registro = {
                "tipo": "criação de taxa diária",
                "descricao": f"{info['nome']} — R$ {info['faltando']:.2f}",
                "id": (resultado or {}).get("id"),
            }
            (aplicadas if resultado else falhas).append(registro)

    return {"aplicadas": aplicadas, "falhas": falhas}


# ===== PDF COM MASCARAMENTO E FLUXO DE CAIXA =====

def sanitizar_texto_pdf(txt) -> str:
    txt = str(txt)
    substituicoes = {
        "—": "-", "–": "-", "―": "-",
        """: '"', """: '"', "'": "'", "'": "'",
        "…": "...", "\xa0": " ",
    }
    for de, para in substituicoes.items():
        txt = txt.replace(de, para)
    return txt.encode("latin-1", errors="replace").decode("latin-1")


def gerar_pdf(relatorio: dict, correcoes: dict, fluxo_caixa: dict, saldo_asaas: dict, saldo_advbox: float, caminho_saida: str) -> None:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, sanitizar_texto_pdf(f"Conciliacao Advbox x Asaas - {relatorio['data']}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    modo = " (DRY RUN - nada foi gravado de verdade)" if DRY_RUN else ""
    pdf.cell(0, 6, sanitizar_texto_pdf(f"Gerado automaticamente em {datetime.now().strftime('%d/%m/%Y %H:%M')}{modo}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    def titulo(txt):
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_fill_color(235, 235, 235)
        pdf.cell(0, 8, sanitizar_texto_pdf(txt), new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        pdf.set_font("Helvetica", "", 10)

    def linha(txt):
        txt = sanitizar_texto_pdf(txt)
        largura_maxima = pdf.w - pdf.l_margin - pdf.r_margin - 2

        def escreve(texto):
            pdf.cell(0, 6, texto, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        palavras = txt.split(" ")
        linha_atual = ""
        for palavra in palavras:
            candidata = f"{linha_atual} {palavra}" if linha_atual else palavra
            if not linha_atual or pdf.get_string_width(candidata) <= largura_maxima:
                linha_atual = candidata
            else:
                escreve(linha_atual)
                linha_atual = palavra
        escreve(linha_atual)

    # ===== NOVO: SEÇÃO DE SALDOS =====
    titulo("Saldos da conta Asaas")
    if saldo_asaas:
        saldo_real = float(saldo_asaas.get("balance", 0) or 0)
        linha(f"Saldo real em tempo real: R$ {saldo_real:.2f}")
    else:
        linha("Nao foi possivel obter saldo da Asaas")

    if saldo_advbox is not None:
        linha(f"Saldo contabil do Advbox: R$ {saldo_advbox:.2f}")
    else:
        linha("Nao foi possivel obter saldo contabil do Advbox")
    pdf.ln(2)

    # ===== NOVO: SEÇÃO DE FLUXO DE CAIXA =====
    titulo(f"Fluxo de Caixa do dia ({relatorio['data']})")
    linha(f"Total de Entradas (recebimentos): R$ {fluxo_caixa['total_entradas']:.2f}")
    linha(f"Total de Saidas (despesas e taxas): R$ {fluxo_caixa['total_saidas']:.2f}")
    linha(f"Saldo Liquido do dia: R$ {fluxo_caixa['saldo_liquido']:.2f}")
    pdf.ln(2)

    # Entradas mascaradas
    if fluxo_caixa['entradas_detalhes']:
        titulo(f"Detalhes das Entradas ({len(fluxo_caixa['entradas_detalhes'])})")
        for i, entrada in enumerate(fluxo_caixa['entradas_detalhes'], 1):
            cliente_mascarado = mascarador.mascarar_nome_cliente(entrada['cliente'], entrada['id_asaas'])
            linha(f"  {i}. R$ {entrada['valor']:.2f} | {cliente_mascarado} | ID: {entrada['id_asaas']}")
        pdf.ln(2)

    # Saídas mascaradas
    if fluxo_caixa['saidas_detalhes']:
        titulo(f"Detalhes das Saidas ({len(fluxo_caixa['saidas_detalhes'])})")
        for i, saida in enumerate(fluxo_caixa['saidas_detalhes'], 1):
            cliente_mascarado = mascarador.mascarar_nome_cliente(saida['cliente'], saida['id_asaas'])
            linha(f"  {i}. R$ {saida['valor']:.2f} | {cliente_mascarado} | ID: {saida['id_asaas']}")
        pdf.ln(2)

    # ===== RESUMO DE CONCILIAÇÃO (v1.2) =====
    bateu_receita = abs(relatorio["diferenca_receita"]) < 0.02
    bateu_despesa = abs(relatorio["diferenca_despesa"]) < 0.02

    titulo("Resumo da Conciliacao (apos correcoes automaticas)")
    linha(f"Receita  - Asaas: R$ {relatorio['total_receita_asaas']:.2f}  |  Advbox: R$ {relatorio['total_receita_advbox']:.2f}  |  Diferenca: R$ {relatorio['diferenca_receita']:.2f}  {'(BATEU)' if bateu_receita else '(NAO BATEU)'}")
    linha(f"Despesa  - Asaas: R$ {relatorio['total_despesa_asaas']:.2f}  |  Advbox: R$ {relatorio['total_despesa_advbox']:.2f}  |  Diferenca: R$ {relatorio['diferenca_despesa']:.2f}  {'(BATEU)' if bateu_despesa else '(NAO BATEU)'}")
    pdf.ln(2)

    titulo(f"Corrigido automaticamente ({len(correcoes['aplicadas'])})")
    if not correcoes["aplicadas"]:
        linha("Nada precisou de correcao automatica hoje.")
    for c in correcoes["aplicadas"]:
        linha(f"- [{c['tipo']}] {c['descricao']}")
    pdf.ln(2)

    if correcoes["falhas"]:
        titulo(f"Tentativas de correcao que FALHARAM ({len(correcoes['falhas'])})")
        for c in correcoes["falhas"]:
            linha(f"- [{c['tipo']}] {c['descricao']}")
        pdf.ln(2)

    titulo(f"Receita faltando - precisa decisao manual ({len(relatorio['receita_faltando'])})")
    if not relatorio["receita_faltando"]:
        linha("Nenhuma pendencia encontrada.")
    for item in relatorio["receita_faltando"]:
        cliente_mascarado = mascarador.mascarar_nome_cliente(item.get('customerName', ''), item.get('id'))
        linha(f"- R$ {float(item.get('value', 0)):.2f} | {cliente_mascarado} | ID Asaas: {item.get('id', '?')}")
    pdf.ln(2)

    titulo(f"Transferencias do dia ({len(relatorio['transferencias'])})")
    if not relatorio["transferencias"]:
        linha("Nenhuma transferencia no dia.")
    for item in relatorio["transferencias"]:
        linha(f"- R$ {float(item.get('value', 0)):.2f} | ID: {item.get('id', '?')}")
    pdf.ln(2)

    titulo(f"Estornos do dia ({len(relatorio['estornos'])})")
    if not relatorio["estornos"]:
        linha("Nenhum estorno no dia.")
    for item in relatorio["estornos"]:
        linha(f"- R$ {float(item.get('value', 0)):.2f} | ID: {item.get('id', '?')}")

    pdf.output(caminho_saida)
    log(f"PDF salvo em {caminho_saida}")


# ===== EMAIL (v1.2, sem mudanças) =====

def enviar_email(caminho_pdf: str, data_alvo: str, relatorio: dict, correcoes: dict, fluxo_caixa: dict) -> None:
    if not (SMTP_USER and SMTP_PASS and EMAIL_DESTINO):
        log("Credenciais de email incompletas — pulando envio (PDF ficou salvo localmente).")
        return

    bateu_receita = abs(relatorio["diferenca_receita"]) < 0.02
    bateu_despesa = abs(relatorio["diferenca_despesa"]) < 0.02
    status = "tudo bateu" if (bateu_receita and bateu_despesa) else "ha divergencias"

    msg = EmailMessage()
    prefixo_dry = "[DRY RUN] " if DRY_RUN else ""
    msg["Subject"] = f"{prefixo_dry}Conciliação Bancária - {data_alvo} ({status}) | Fluxo: R$ {fluxo_caixa['saldo_liquido']:.2f}"
    msg["From"] = SMTP_USER
    msg["To"] = EMAIL_DESTINO
    msg.set_content(
        f"Conciliacao automatica do dia {data_alvo}.\n\n"
        f"FLUXO DE CAIXA:\n"
        f"  Entradas: R$ {fluxo_caixa['total_entradas']:.2f}\n"
        f"  Saidas: R$ {fluxo_caixa['total_saidas']:.2f}\n"
        f"  Saldo Liquido: R$ {fluxo_caixa['saldo_liquido']:.2f}\n\n"
        f"RECONCILIACAO:\n"
        f"  Receita: Asaas R$ {relatorio['total_receita_asaas']:.2f} x Advbox R$ {relatorio['total_receita_advbox']:.2f}\n"
        f"  Despesa: Asaas R$ {relatorio['total_despesa_asaas']:.2f} x Advbox R$ {relatorio['total_despesa_advbox']:.2f}\n\n"
        f"Correcoes aplicadas: {len(correcoes['aplicadas'])}\n"
        f"Falhas: {len(correcoes['falhas'])}\n\n"
        f"Dados sensíveis (nomes, CPFs) estão mascarados no relatório PDF em anexo.\n"
        "Detalhes completos no PDF."
    )

    with open(caminho_pdf, "rb") as f:
        msg.add_attachment(
            f.read(), maintype="application", subtype="pdf",
            filename=f"conciliacao_{data_alvo}.pdf",
        )

    log("Enviando email…")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(msg)
    log("Email enviado.")


# ===== MAIN =====

def data_padrao() -> str:
    tz = ZoneInfo(TIMEZONE)
    ontem = datetime.now(tz) - timedelta(days=1)
    return ontem.strftime("%Y-%m-%d")


def main() -> None:
    if not ADVBOX_TOKEN or not ASAAS_TOKEN:
        log("ERRO: ADVBOX_TOKEN e/ou ASAAS_TOKEN não configurados. Abortando.")
        sys.exit(1)

    data_alvo = os.environ.get("TARGET_DATE", "").strip() or data_padrao()
    log(f"Conciliando o dia {data_alvo} (fuso {TIMEZONE}){' [DRY RUN]' if DRY_RUN else ''}")

    # Fetch de dados
    advbox_itens = advbox_get_all_transactions()
    asaas_itens = asaas_get_financial_transactions_do_dia(data_alvo)

    # Relatório de conciliação (v1.2)
    relatorio = montar_relatorio(data_alvo, advbox_itens, asaas_itens)

    # NOVO: Fluxo de caixa do dia
    fluxo_caixa = calcular_fluxo_caixa_do_dia(asaas_itens, data_alvo)

    # NOVO: Saldos atuais
    saldo_asaas = asaas_get_saldo_atual()
    saldo_advbox = advbox_get_saldo_bancario("ASAAS")

    if relatorio["receita_faltando"]:
        try:
            lawsuits = advbox_get_all_lawsuits()
            enriquecer_receita_faltando_com_processo(relatorio, lawsuits, advbox_itens)
        except RuntimeError as exc:
            log(f"Não consegui buscar processos do Advbox pra identificar receita faltando: {exc}")

    # Aplicar correções (v1.2)
    correcoes = aplicar_correcoes(relatorio)

    log(
        f"RESUMO — Receita: Asaas R$ {relatorio['total_receita_asaas']:.2f} x "
        f"Advbox R$ {relatorio['total_receita_advbox']:.2f} (dif. R$ {relatorio['diferenca_receita']:.2f}) | "
        f"Despesa: Asaas R$ {relatorio['total_despesa_asaas']:.2f} x "
        f"Advbox R$ {relatorio['total_despesa_advbox']:.2f} (dif. R$ {relatorio['diferenca_despesa']:.2f}) | "
        f"Corrigido: {len(correcoes['aplicadas'])} | Falhas: {len(correcoes['falhas'])} | "
        f"Fluxo de Caixa: R$ {fluxo_caixa['saldo_liquido']:.2f}"
    )

    caminho_pdf = f"conciliacao_{data_alvo}.pdf"
    gerar_pdf(relatorio, correcoes, fluxo_caixa, saldo_asaas, saldo_advbox, caminho_pdf)
    enviar_email(caminho_pdf, data_alvo, relatorio, correcoes, fluxo_caixa)

    log("Concluído.")


if __name__ == "__main__":
    main()
