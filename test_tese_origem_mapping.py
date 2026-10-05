#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste das novas funções de mapeamento TESE + ORIGEM -> Centro de Custo.

Este script simula dados do /settings para validar a lógica de resolução
de centros de custo por tese e origem, SEM fazer chamadas reais às APIs.
"""

import re


def _valor_br_para_float(s: str):
    """'1.834,32' -> 1834.32"""
    s = (s or "").strip().replace(".", "").replace(",", ".")
    try:
        return round(float(s), 2)
    except ValueError:
        return None


# Simulando /settings do Advbox com dados de exemplo
SETTINGS_MOCK = {
    "financial": {
        "categories": [
            {"id": 1001, "category": "HONORÁRIOS CONTRATUAIS DE ÊXITO-RMC"},
            {"id": 1002, "category": "HONORÁRIOS CONTRATUAIS DE ÊXITO-CONSUMIDOR"},
            {"id": 1003, "category": "HONORÁRIOS CONTRATUAIS DE SUCUMBENCIAL-RMC"},
            {"id": 1004, "category": "ÊXITO DO CLIENTE-RMC"},
            {"id": 1005, "category": "ÊXITO DO CLIENTE-CONSUMIDOR"},
        ],
        "cost_centers": [
            {"id": 2001, "cost_center": "CONSUMIDOR-INSTAGRAM / MÍDIA SOCIAL"},
            {"id": 2002, "cost_center": "CONSUMIDOR-ESCRITÓRIO / DIRETA"},
            {"id": 2003, "cost_center": "RMC-INSTAGRAM / MÍDIA SOCIAL"},
            {"id": 2004, "cost_center": "RMC-ESCRITÓRIO / DIRETA"},
            {"id": 2005, "cost_center": "RMC-TRÁFEGO / MÍDIA PAGA"},
            {"id": 2006, "cost_center": "CONCURSO-INDICAÇÃO / INDICAÇÃO"},
        ],
        "lawsuit_types": [
            {"id": 1, "type": "RMC"},
            {"id": 2, "type": "CONSUMIDOR"},
            {"id": 3, "type": "CONCURSO"},
            {"id": 4, "type": "PM/AM"},
        ],
    }
}


def mapa_tese_grupo() -> dict:
    """Extrai TESE -> GRUPO a partir dos centros de custo."""
    ccs = SETTINGS_MOCK.get("financial", {}).get("cost_centers", [])
    mapa = {}
    for cc in ccs:
        nome = (cc.get("cost_center") or "").strip()
        if not nome:
            continue
        # Extrai a primeira parte antes de "-"
        grupo = re.split(r'[-/]', nome)[0].strip().upper()
        if grupo:
            for variacao in (grupo, grupo.rstrip('S')):
                if variacao:
                    mapa[variacao] = grupo
    return mapa


def resolver_centro_custo_por_tese_e_origem(tese: str, origem_cliente: str) -> str | None:
    """Resolve o centro de custo pelo mapeamento TESE + ORIGEM."""
    if not tese or not origem_cliente:
        return None

    tese_upper = tese.strip().upper()
    origem_upper = origem_cliente.strip().upper()

    ccs = SETTINGS_MOCK.get("financial", {}).get("cost_centers", [])

    # Procura exatamente "TESE-ORIGEM"
    for cc in ccs:
        nome = (cc.get("cost_center") or "").strip().upper()
        if f"{tese_upper}-{origem_upper}" in nome or nome.startswith(f"{tese_upper}-{origem_upper}"):
            return nome

    # Fallback: procura por palavras-chave parciais
    palavras_tese = set(re.findall(r'\w+', tese_upper))
    palavras_origem = set(re.findall(r'\w+', origem_upper))

    for cc in ccs:
        nome = (cc.get("cost_center") or "").strip().upper()
        partes = re.split(r'[-/]', nome)
        if len(partes) >= 2:
            palavras_grupo = set(re.findall(r'\w+', partes[0]))
            palavras_canal = set(re.findall(r'\w+', partes[1]))
            if (palavras_tese & palavras_grupo) and (palavras_origem & palavras_canal):
                return nome

    return None


def resolver_centro_custo_id(valor: str) -> int | None:
    """Converte nome de centro de custo no ID numérico."""
    if not valor:
        return None

    ccs = SETTINGS_MOCK.get("financial", {}).get("cost_centers", [])
    for cc in ccs:
        if (cc.get("cost_center") or "").strip().upper() == str(valor).strip().upper():
            return cc.get("id")
    return None


def test_case(nome: str, tese: str, origem: str, esperado: str | None) -> bool:
    """Testa um caso de mapeamento."""
    resultado = resolver_centro_custo_por_tese_e_origem(tese, origem)
    resultado_upper = resultado.upper() if resultado else None
    esperado_upper = esperado.upper() if esperado else None

    passou = resultado_upper == esperado_upper
    status = "✓ PASSOU" if passou else "✗ FALHOU"
    print(f"{status}: {nome}")
    print(f"  Tese={tese!r}, Origem={origem!r}")
    print(f"  Esperado: {esperado!r}")
    print(f"  Obteve:   {resultado!r}")

    if resultado:
        cc_id = resolver_centro_custo_id(resultado)
        print(f"  ID resolvido: {cc_id}")
    print()

    return passou


# ===== TESTES =====

print("=" * 70)
print("Testes de Mapeamento TESE + ORIGEM -> Centro de Custo")
print("=" * 70)
print()

# Debug: mostra o mapping de tese->grupo
mapa = mapa_tese_grupo()
print("Mapping TESE -> GRUPO:")
for tese, grupo in sorted(mapa.items()):
    print(f"  {tese} -> {grupo}")
print()

# Debug: mostra os centros de custo disponíveis
print("Centros de Custo Disponíveis:")
for cc in SETTINGS_MOCK["financial"]["cost_centers"]:
    print(f"  id={cc['id']:4d} | {cc['cost_center']}")
print()

# Testes positivos
print("TESTES POSITIVOS (deve encontrar):")
print("-" * 70)
tests_passed = 0
tests_total = 0

tests = [
    ("RMC + INSTAGRAM", "RMC", "INSTAGRAM", "RMC-INSTAGRAM / MÍDIA SOCIAL"),
    ("RMC + ESCRITÓRIO", "RMC", "ESCRITÓRIO", "RMC-ESCRITÓRIO / DIRETA"),
    ("CONSUMIDOR + INSTAGRAM", "CONSUMIDOR", "INSTAGRAM", "CONSUMIDOR-INSTAGRAM / MÍDIA SOCIAL"),
    ("CONSUMIDOR + ESCRITÓRIO", "CONSUMIDOR", "ESCRITÓRIO", "CONSUMIDOR-ESCRITÓRIO / DIRETA"),
    ("RMC + TRÁFEGO", "RMC", "TRÁFEGO", "RMC-TRÁFEGO / MÍDIA PAGA"),
    ("CONCURSO + INDICAÇÃO", "CONCURSO", "INDICAÇÃO", "CONCURSO-INDICAÇÃO / INDICAÇÃO"),
]

for nome, tese, origem, esperado in tests:
    tests_total += 1
    if test_case(nome, tese, origem, esperado):
        tests_passed += 1

# Testes negativos
print("TESTES NEGATIVOS (não deve encontrar ou retornar None):")
print("-" * 70)

neg_tests = [
    ("Sem tese", "", "INSTAGRAM", None),
    ("Sem origem", "RMC", "", None),
    ("Tese desconhecida", "TESE_INEXISTENTE", "INSTAGRAM", None),
    ("Origem desconhecida", "RMC", "ORIGEM_INEXISTENTE", None),
]

for nome, tese, origem, esperado in neg_tests:
    tests_total += 1
    if test_case(nome, tese, origem, esperado):
        tests_passed += 1

print("=" * 70)
print(f"RESULTADO: {tests_passed}/{tests_total} testes passaram")
print("=" * 70)

if tests_passed == tests_total:
    print("✓ Todos os testes passaram!")
    exit(0)
else:
    print(f"✗ {tests_total - tests_passed} teste(s) falharam")
    exit(1)
