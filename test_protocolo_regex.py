#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste dos padrões regex para leitura de protocolo.

Valida que a função interpretar_protocolo consegue extrair valores
de diferentes formatos de protocolo.
"""

import re


def _valor_br_para_float(s: str):
    """'1.834,32' -> 1834.32"""
    s = (s or "").strip().replace(".", "").replace(",", ".")
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def interpretar_protocolo_v1(textos: list[str]) -> dict:
    """Versão 1: padrões originais (mais restritivos)."""
    info = {
        "tem_protocolo": False,
        "exito": None,
        "sucumbencial": None,
        "repasse_cliente": None,
        "valor_creditado": None,
    }
    padroes = {
        "exito": r"honor[áa]rios?\s+(?:contratuais\s+)?de\s+[êe]xito[^\dR]*R?\$?\s*([\d.]+,\d{2})",
        "sucumbencial": r"honor[áa]rios?\s+sucumbenc\w*[^\dR]*R?\$?\s*([\d.]+,\d{2})",
        "repasse_cliente": r"repassad[oa][^\dR]*client[ea][^\dR]*R?\$?\s*([\d.]+,\d{2})",
        "valor_creditado": r"creditad[oa][^\dR]*R?\$?\s*([\d.]+,\d{2})",
    }
    for texto in textos:
        up = texto.upper()
        if any(p in up for p in ("HONORÁRIOS", "HONORARIOS", "SUCUMBENC", "ÊXITO", "EXITO", "REPASSAD")):
            info["tem_protocolo"] = True
        for chave, pad in padroes.items():
            if info[chave] is None:
                m = re.search(pad, texto, re.IGNORECASE)
                if m:
                    info[chave] = _valor_br_para_float(m.group(1))
    return info


def interpretar_protocolo_v2(textos: list[str]) -> dict:
    """Versão 2: padrões expandidos (mais permissivos)."""
    info = {
        "tem_protocolo": False,
        "exito": None,
        "sucumbencial": None,
        "repasse_cliente": None,
        "valor_creditado": None,
    }
    padroes = {
        # Honorários de êxito: mais flexível com separadores e ordem de palavras
        "exito": [
            r"honor[áa]rios?\s+(?:de\s+)?[êe]xito[^\dR$]*R?\$?\s*([\d.]+,\d{2})",
            r"[êe]xito[^\dR$]*R?\$?\s*([\d.]+,\d{2})",
            r"honor[áa]rios?[^\dR$]*[êe]xito[^\dR$]*R?\$?\s*([\d.]+,\d{2})",
        ],
        # Honorários sucumbenciais
        "sucumbencial": [
            r"honor[áa]rios?\s+sucumbenc\w*[^\dR$]*R?\$?\s*([\d.]+,\d{2})",
            r"sucumbenc\w*[^\dR$]*honor[áa]rios?[^\dR$]*R?\$?\s*([\d.]+,\d{2})",
            r"sucumbenc\w*[^\dR$]*R?\$?\s*([\d.]+,\d{2})",
        ],
        # Repasse à cliente (com ou sem menção a "cliente")
        "repasse_cliente": [
            r"repassad[oa][^\dR$]*client[ea][^\dR$]*R?\$?\s*([\d.]+,\d{2})",
            r"repasse[^\dR$]*client[ea][^\dR$]*R?\$?\s*([\d.]+,\d{2})",
            r"client[ea][^\dR$]*repasse[^\dR$]*R?\$?\s*([\d.]+,\d{2})",
            r"repasse[^\dR$]*R?\$?\s*([\d.]+,\d{2})",  # Simples: "Repasse: R$ XXX"
        ],
        # Valor creditado
        "valor_creditado": [
            r"creditad[oa][^\dR$]*R?\$?\s*([\d.]+,\d{2})",
            r"cr[ée]dito[^\dR$]*R?\$?\s*([\d.]+,\d{2})",
        ],
    }

    for texto in textos:
        up = texto.upper()
        if any(p in up for p in ("HONORÁRIO", "SUCUMBENC", "ÊXITO", "EXITO", "REPASSA", "CLIENTE")):
            info["tem_protocolo"] = True

        for chave, pads in padroes.items():
            if info[chave] is None:
                if isinstance(pads, str):
                    pads = [pads]
                for pad in pads:
                    m = re.search(pad, texto, re.IGNORECASE)
                    if m:
                        info[chave] = _valor_br_para_float(m.group(1))
                        break  # usa o primeiro que bater

    return info


# ===== EXEMPLOS DE PROTOCOLOS REAIS =====
# Baseados nos que foram lidos no diagnóstico

EXEMPLOS = [
    {
        "nome": "Formato Típico 1 (processo 5836169)",
        "textos": [
            "Ciente, aguardando alvará",
            "Honorários contratuais de êxito: R$ 1.234,56",
            "Repassado a cliente: R$ 234,56",
        ],
        "esperado": {
            "tem_protocolo": True,
            "exito": 1234.56,
            "sucumbencial": None,
            "repasse_cliente": 234.56,
            "valor_creditado": None,
        }
    },
    {
        "nome": "Formato Típico 2 (sucumbencial)",
        "textos": [
            "Parecer desfavorável recebido",
            "Honorários sucumbenciais: R$ 567,89",
            "Creditado cliente: R$ 400,00",
        ],
        "esperado": {
            "tem_protocolo": True,
            "exito": None,
            "sucumbencial": 567.89,
            "repasse_cliente": None,
            "valor_creditado": 400.00,
        }
    },
    {
        "nome": "Variação: Êxito com variante de escrita",
        "textos": [
            "Processo com êxito identificado",
            "Honorarios de exito: R$ 1.588,73",
        ],
        "esperado": {
            "tem_protocolo": True,
            "exito": 1588.73,
            "sucumbencial": None,
            "repasse_cliente": None,
            "valor_creditado": None,
        }
    },
    {
        "nome": "Formato Compacto (tudo em uma linha)",
        "textos": [
            "Êxito: R$ 3.608,27. Sucumbencial: R$ 0,00. Repasse: R$ 1.200,00.",
        ],
        "esperado": {
            "tem_protocolo": True,
            "exito": 3608.27,
            "sucumbencial": 0.00,
            "repasse_cliente": 1200.00,
            "valor_creditado": None,
        }
    },
    {
        "nome": "Sem valores numéricos (deve reconhecer protocolo mas sem números)",
        "textos": [
            "Honorários de êxito a definir",
            "Aguardando confirmação do cliente",
        ],
        "esperado": {
            "tem_protocolo": True,
            "exito": None,
            "sucumbencial": None,
            "repasse_cliente": None,
            "valor_creditado": None,
        }
    },
]


def teste_versao(versao_nome: str, funcao, exemplo: dict) -> bool:
    """Testa uma versão da função contra um exemplo."""
    resultado = funcao(exemplo["textos"])
    esperado = exemplo["esperado"]

    passou = resultado == esperado
    status = "✓" if passou else "✗"

    if not passou:
        print(f"\n{status} FALHOU: {versao_nome} - {exemplo['nome']}")
        print(f"  Textos: {exemplo['textos'][:1]}")
        print(f"  Esperado: {esperado}")
        print(f"  Obteve:   {resultado}")

        # Mostra diferenças
        for chave in esperado:
            if resultado[chave] != esperado[chave]:
                print(f"    DIFERENÇA em '{chave}': esperado {esperado[chave]!r}, obteve {resultado[chave]!r}")

    return passou


# ===== EXECUÇÃO =====

print("=" * 70)
print("Testes de Padrões Regex para Leitura de Protocolo")
print("=" * 70)
print()

# Versão 1 (original)
print("VERSÃO 1 (padrões originais):")
print("-" * 70)
v1_passed = 0
v1_total = 0
for exemplo in EXEMPLOS:
    v1_total += 1
    if teste_versao("V1", interpretar_protocolo_v1, exemplo):
        v1_passed += 1
        print(f"✓ {exemplo['nome']}")
    # (falhas já printadas acima)

print()
print(f"Resultado V1: {v1_passed}/{v1_total} testes passaram")

# Versão 2 (expandida)
print()
print("VERSÃO 2 (padrões expandidos):")
print("-" * 70)
v2_passed = 0
v2_total = 0
for exemplo in EXEMPLOS:
    v2_total += 1
    if teste_versao("V2", interpretar_protocolo_v2, exemplo):
        v2_passed += 1
        print(f"✓ {exemplo['nome']}")
    # (falhas já printadas acima)

print()
print(f"Resultado V2: {v2_passed}/{v2_total} testes passaram")

print()
print("=" * 70)
print(f"Resumo: V1={v1_passed}/{v1_total}  |  V2={v2_passed}/{v2_total}")
if v2_passed > v1_passed:
    print("✓ V2 (expandida) é melhor!")
elif v2_passed == v1_passed:
    print("≈ Ambas têm o mesmo desempenho")
else:
    print("✗ V1 (original) é melhor")
print("=" * 70)
