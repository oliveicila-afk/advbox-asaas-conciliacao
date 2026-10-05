# Análise de Divergências: Advbox vs Asaas

## Status Geral (Primeiros 10 dias de setembro 2026)

| Dia | Receitas OK? | Despesas OK? | Status | Observações |
|-----|-------------|-------------|--------|------------|
| 1 | ✗ | ✗ | ❌ Divergência | |
| 2 | ✗ | ✗ | ❌ Divergência | |
| 3 | ✗ | ✗ | ❌ Divergência | |
| 4 | ✗ | ✗ | ❌ Divergência | **ANALISADO**: Divergência grande em TRANSFERs |
| 5 | ✓ | ✓ | ✅ Match | |
| 6 | ✗ | ✓ | ❌ Divergência | Receita completamente faltando em Advbox |
| 7 | ✓ | ✓ | ✅ Match | |
| 8 | ✗ | ✗ | ❌ Divergência | **PRIORIDADE**: Maior divergência de despesas (R$ 78,758.92) |
| 9 | ✗ | ✗ | ❌ Divergência | |
| 10 | ✗ | ✗ | ❌ Divergência | |

**Resumo**: 2 dias com match perfeito (5, 7), 8 dias com divergências

---

## Análise Detalhada: Setembro 4, 2026

### Receitas
| Sistema | Itens | Total | Status |
|---------|-------|-------|--------|
| Asaas | 8 | R$ 2,613.67 | |
| Advbox | 7 | R$ 2,365.17 | |
| **Δ** | **-1** | **R$ 248.50** | **✗ Divergência** |

### Despesas
| Sistema | Itens | Total | Status |
|---------|-------|-------|--------|
| Asaas | 29 | R$ 26,504.74 | |
| Advbox | ? | R$ 14,987.39 | |
| **Δ** | **?** | **R$ 11,517.35** | **✗ Divergência Significativa** |

### Principais Achados - Setembro 4

**PROBLEMA IDENTIFICADO**: Asaas inclui transações de tipo `TRANSFER` que parecem não estar registradas no Advbox.

**Exemplo de Transferências não reconciliadas:**
1. TRANSFER (PIX) - R$ 11,133.35 para ELIZETH SOUZA DA CRUZ DE MELO
2. TRANSFER (PIX) - R$ 11,133.35 para ELIZETH SOUZA DA CRUZ DE MELO
3. TRANSFER (PIX) - R$ 3,750.00 para THIAGO

**Total de TRANSFERs em Asaas (Sept 4)**: ~R$ 26,000+ (explicaria a divergência de R$ 11,517.35)

### Hipóteses

1. **Transferências não são registradas em Advbox**: Advbox pode estar filtrando/excluindo TRANSFERs do cálculo
2. **Timing diferente**: Transferências podem estar em datas diferentes nos dois sistemas
3. **Categorização diferente**: Transferências podem estar em categoria diferente em Advbox

---

## Análise Detalhada: Setembro 8, 2026

> **STATUS**: Pendente - Requer acesso aos dados da API (tokens não disponíveis nesta sessão)

### Dados Esperados
- **Maior divergência de despesas identificada**: R$ 78,758.92
- Padrão suspeito: Similar ao padrão de setembro 4 (TRANSFERs não reconciliadas)

### Como Investigar Setembro 8

**Opção 1: Via GitHub Actions (Recomendado)**
1. Vá para: Actions → "Cache de Dados + Diagnóstico Offline"
2. Clique em "Run workflow"
3. Selecione:
   - `atualizar_cache`: "sim"
   - `dia_diagnostico`: "2026-09-08"
4. Aguarde conclusão (3-5 min)
5. Download do artefato `transactions-cache.json`

**Opção 2: Local (com tokens configurados)**
```bash
export ADVBOX_TOKEN="seu_token"
export ASAAS_TOKEN="seu_token"
export TIMEZONE="America/Manaus"

# Primeiro, gerar cache
python3 cache_transactions.py

# Depois, analisar offline (pode ser feito depois, sem tokens)
DIA_ALVO="2026-09-08" python3 diagnostico_transacoes_offline.py
```

---

## Padrão de Divergências Identificado

### Padrão Recorrente: Transações TRANSFER

Tipo de transação em Asaas: `TRANSFER`
- Descrição: PIX transfers, geralmente para pessoas específicas
- Valor: Variável (R$ 3k - R$ 11k+)
- Problema: Não aparecem em Advbox (ou aparecem com valores diferentes)

### Hipótese Principal
**As transações de TRANSFER (PIX) registradas em Asaas não estão sendo mapeadas/sincronizadas com Advbox de forma consistente.**

Evidência:
- Sept 4: Divergência de R$ 11,517.35 em despesas → Explicada por TRANSFERs
- Sept 8: Divergência de R$ 78,758.92 em despesas → Provavelmente também TRANSFERs

---

## Próximos Passos

1. **Confirmar hipótese para Sept 8**
   - Executar diagnóstico via GitHub Actions
   - Verificar se há muitas transações TRANSFER

2. **Analisar Setembro 6** (receita faltando)
   - Por que Advbox mostra 0.00 de receita quando Asaas tem R$ 6,000?

3. **Mapear tipos de transação**
   - Criar tabela de mapeamento: Asaas type → Advbox entry_type
   - Verificar se TRANSFER está sendo ignorado/filtrado

4. **Decisão de Negócio**
   - Confirmar com o usuário: Transferências PIX devem ser incluídas na reconciliação?
   - Se sim: Corrigir mapeamento em Advbox
   - Se não: Ajustar filtros em Asaas para excluir TRANSFERs

---

## Configurações Atuais

**Timezone**: America/Manaus
**Período**: Setembro 1-10, 2026
**API 1**: Asaas (Gateway de Pagamentos)
**API 2**: Advbox (Contabilidade)

**Campo de Data Usado**:
- Asaas: `date` (no item financeiro)
- Advbox: `date_payment` (formato YYYY-MM-DD string)

**Campos Reconciliados**:
- Advbox `entry_type: "income"` ↔ Asaas `type: "CREDIT_CARD_SALE"`, `"DEPOSIT"`, etc.
- Advbox `entry_type: "expense"` ↔ Asaas `type: "TRANSFER"`, `"MANUAL_FEE"`, etc.

---

**Última atualização**: 2026-10-04
**Status da sessão**: Continuação de contexto anterior
**Tokens disponíveis**: Não (usar GitHub Actions)
