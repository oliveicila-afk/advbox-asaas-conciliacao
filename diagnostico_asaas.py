#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnóstico SÓ-LEITURA da API do Asaas.

Objetivo: descobrir ONDE está o "Número do processo judicial" na API.
Hoje o robô usa o campo `externalReference` do /financialTransactions, mas na
tela da cobrança o "Número do processo judicial" é um campo separado e pode ter
valor diferente do "Identificador externo" (externalReference).

NÃO lança, NÃO edita, NÃO cria nada. Só faz GET e imprime nomes de campos.
Segurança: NÃO imprime nome de cliente nem CPF. Imprime só nomes de campos e os
campos ligados a processo/tribunal/referência (que são o alvo da comparação).
"""

import os
import json
import requests

ASAAS_BASE = "https://api.asaas.com/v3"
ASAAS_TOKEN = os.environ.get("ASAAS_TOKEN", "")
DATA = os.environ.get("TARGET_DATE", "2026-09-28")
HEADERS = {"access_token": ASAAS_TOKEN}

# Campos que PODEM conter o número do processo / tribunal — só esses têm valor
# impresso. O resto a gente mostra só o NOME do campo.
CHAVES_INTERESSE = ("process", "processo", "court", "tribunal", "external", "reference", "lawsuit")
# Campos sensíveis que NUNCA imprimimos o valor.
CHAVES_SENSIVEIS = ("name", "cpf", "cnpj", "customer", "email", "phone", "mobile")


def get(path, params=None):
    try:
        r = requests.get(f"{ASAAS_BASE}{path}", headers=HEADERS, params=params or {}, timeout=30)
        return r.status_code, r
    except requests.RequestException as e:
        return None, str(e)


def mostrar_campos(obj, rotulo):
    print(f"\n-- {rotulo}: campos presentes --")
    if not isinstance(obj, dict):
        print(f"   (não é objeto: {type(obj).__name__})")
        return
    for k in sorted(obj.keys()):
        v = obj[k]
        nome_l = k.lower()
        if any(s in nome_l for s in CHAVES_SENSIVEIS):
            print(f"   {k}: [oculto]")
        elif any(s in nome_l for s in CHAVES_INTERESSE):
            # valor interessante (processo/tribunal/ref) — mostramos
            print(f"   {k}: {v!r}   <== possível nº do processo/ref")
        elif isinstance(v, (dict, list)):
            print(f"   {k}: ({type(v).__name__})")
        else:
            print(f"   {k}: ({type(v).__name__})")


print("=" * 70)
print(f"1) /financialTransactions de {DATA} — campos de um evento de receita")
print("=" * 70)
status, r = get("/financialTransactions", {"startDate": DATA, "finishDate": DATA, "limit": 100})
payment_id = None
if status == 200:
    itens = r.json().get("data", [])
    receitas = [i for i in itens if i.get("type") in ("PAYMENT_RECEIVED", "RECEIVABLE_ANTICIPATION_GROSS_CREDIT")]
    print(f"status 200 | {len(itens)} eventos no total, {len(receitas)} receitas")
    if receitas:
        ex = receitas[0]
        mostrar_campos(ex, "financialTransaction (receita)")
        payment_id = ex.get("paymentId")
        print(f"\n   paymentId capturado: {payment_id!r}")
else:
    print(f"status: {status}")
    print((r.text[:400]) if hasattr(r, "text") else r)

if payment_id:
    print()
    print("=" * 70)
    print("2) /payments/{id} — a cobrança tem campo de número do processo?")
    print("=" * 70)
    status, r = get(f"/payments/{payment_id}")
    if status == 200:
        pay = r.json()
        mostrar_campos(pay, "payment")
        # Sub-objetos que às vezes guardam dados extras
        for sub in ("split", "fine", "interest", "discount", "chargeback", "refunds"):
            if isinstance(pay.get(sub), dict):
                mostrar_campos(pay[sub], f"payment.{sub}")
    else:
        print(f"status: {status}")
        print((r.text[:400]) if hasattr(r, "text") else r)

    print()
    print("=" * 70)
    print("3) /payments/{id} com expand — procura campos extras (se a API suportar)")
    print("=" * 70)
    # Alguns endpoints do Asaas expõem mais com ?expand ou endpoints irmãos.
    for p, params in [
        (f"/payments/{payment_id}", {"expand": "customer"}),
    ]:
        status, r = get(p, params)
        print(f"   {status}  GET {p}?{list(params.keys())}")

print()
print("Fim do diagnóstico Asaas (nada foi lançado ou alterado).")
