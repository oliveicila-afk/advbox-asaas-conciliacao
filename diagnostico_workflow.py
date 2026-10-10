#!/usr/bin/env python3
"""
Diagnóstico: Por que o workflow não está salvando o resultado?

Possíveis causas:
1. A consulta ao Advbox está retornando status 401 (Unauthorized)
2. A consulta está retornando 0 transações (filtro muito restritivo)
3. O arquivo não está sendo criado
4. O git push está falhando silenciosamente
"""

import subprocess
import json
from datetime import datetime

print("=" * 80)
print("DIAGNÓSTICO: Workflow Consultar Advbox")
print("=" * 80)
print(f"\nData: {datetime.now().isoformat()}\n")

# 1. Verificar os últimos workflows
print("1. ÚLTIMOS WORKFLOWS:")
print("-" * 80)
result = subprocess.run([
    "gh", "api",
    "repos/oliveicila-afk/advbox-asaas-conciliacao/actions/runs",
    "--paginate",
    "--jq", '.workflow_runs[0:3] | .[] | {id, name, status, conclusion, created_at}'
], capture_output=True, text=True)

if result.returncode == 0:
    for line in result.stdout.strip().split('\n'):
        if line.strip():
            data = json.loads(line)
            status = "✓" if data['conclusion'] == 'success' else "✗"
            print(f"{status} {data['created_at']}: {data['name']}")
            print(f"   Status: {data['status']} | Conclusion: {data['conclusion']}")

# 2. Verificar arquivos no repositório
print("\n2. ARQUIVOS COM 'RESULTADO' OU 'ADVBOX':")
print("-" * 80)
result = subprocess.run([
    "gh", "api",
    "repos/oliveicila-afk/advbox-asaas-conciliacao/contents",
    "--jq", '.[] | select(.name | contains("resultado") or contains("advbox")) | {name, size, updated_at: .path}'
], capture_output=True, text=True)

if result.returncode == 0:
    files = [line for line in result.stdout.strip().split('\n') if line.strip()]
    if files:
        for file_line in files:
            data = json.loads(file_line)
            print(f"• {data['name']} ({data['size']} bytes)")
    else:
        print("❌ Nenhum arquivo encontrado")

# 3. Verificar os dados conhecidos (STATUS_RECONCILIACAO.md)
print("\n3. STATUS ANTERIOR KNOWN:")
print("-" * 80)
print("Conforme STATUS_RECONCILIACAO.md (2026-10-09):")
print("• Advbox tinha 5 receitas: R$ 14.393,44")
print("  - 09/01: R$ 315,50")
print("  - 09/02: R$ 497,00")
print("  - 09/03: R$ 815,50")
print("  - 09/04: R$ 2.162,67")
print("  - 09/08: R$ 10.602,77")

print("\n4. PROBLEMA IDENTIFICADO:")
print("-" * 80)
print("Você disse: 'não ta faltando, tem registro a mais'")
print("Isso significa: Advbox tem MAIS de 5 transações que o que foi mostrado")
print("\nNecessário: Obter a lista ATUAL e COMPLETA do Advbox")
print("Período: Setembro 1-10, 2026")
print("Tarefa final: Mostrar quais transações estão EXTRA em Advbox")
print("=" * 80)
