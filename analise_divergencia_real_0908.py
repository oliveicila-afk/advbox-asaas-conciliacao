#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Análise da divergência REAL para 09/08
Usando dados reais fornecidos pelo usuário
"""

# ===== DADOS REAIS FORNECIDOS PELO USUÁRIO =====
# Advbox 09/08 - 98 receitas
ADVBOX_RECEITAS_0908 = [
    # Receitas individuais (resumido - totais R$ 98.760,66)
]
ADVBOX_TOTAL_0908 = 98_760.66
ADVBOX_COUNT_0908 = 98

# Asaas 09/08 - conforme script anterior
ASAAS_TOTAL_0908 = 22_549.95

# ===== ANÁLISE =====
print("\n" + "="*70)
print("📊 ANÁLISE DE DIVERGÊNCIA REAL - 09/08 (Setembro 8)")
print("="*70 + "\n")

print(f"ASAAS Receitas:")
print(f"  Total:     R$ {ASAAS_TOTAL_0908:>12.2f}")
print(f"  Registros: 1 análise do script\n")

print(f"ADVBOX Receitas:")
print(f"  Total:     R$ {ADVBOX_TOTAL_0908:>12.2f}")
print(f"  Registros: {ADVBOX_COUNT_0908} entradas individuais\n")

divergencia = abs(ASAAS_TOTAL_0908 - ADVBOX_TOTAL_0908)
percentual = (divergencia / max(ASAAS_TOTAL_0908, ADVBOX_TOTAL_0908)) * 100

print(f"DIVERGÊNCIA:")
print(f"  Valor:      R$ {divergencia:>12.2f}")
print(f"  Percentual: {percentual:>12.2f}%")
print(f"  Direção:    Advbox tem R$ {divergencia:,.2f} A MAIS")

print("\n" + "="*70)
print("❓ QUESTÕES PARA INVESTIGAÇÃO:")
print("="*70)
print("\n1. Asaas R$ 22.549,95 está COMPLETO ou incompleto?")
print(f"   - Se Advbox tem R$ 98.760,66, a diferença é ENORME (~{divergencia:,.2f})")
print("   - Possível: Asaas está mostrando apenas PARTE das transações do dia")
print("   - Possível: Há filtro ou erro na captura de dados do Asaas")

print("\n2. Os R$ 22.549,95 do Asaas estão em quais transações?")
print("   - São todas receitas do tipo PAYMENT_RECEIVED?")
print("   - Há TRANSFERs que o script está excluindo?")

print("\n3. Os R$ 98.760,66 do Advbox correspondem a QUAIS tipos de receita?")
print("   - Todas são 'income' (receita)?")
print("   - Há outras categorias misturadas?")

print("\n" + "="*70)
print("📌 PRÓXIMO PASSO:")
print("="*70)
print("\nPreciso de mais informações dos dados reais do Advbox para 09/08:")
print("  • Breakdown por tipo de receita")
print("  • Breakdown por descrição/categoria")
print("  • IDs das transações para matching manual com Asaas")
print("\nTambém preciso verificar se Asaas realmente tem apenas R$ 22.549,95")
print("ou se há transações faltando da captura.")
print("\n" + "="*70 + "\n")
