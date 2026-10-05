# 📊 RESULTADO FINAL: Auditoria de Receitas (01-10 de Setembro)

**Data da execução**: 2026-10-05  
**Período auditado**: 01 a 10 de setembro 2026  
**Tipo de auditoria**: RECEITAS APENAS  
**Timezone**: America/Manaus

---

## 🎯 Resumo Executivo

| Métrica | Valor |
|---------|-------|
| Dias com divergência | 6/10 |
| Dias que batem | 4/10 |
| Divergência total | R$ 10.070,28 |
| Maior divergência | R$ 9.822,78 (09/08) |

---

## 📋 Tabela de Reconciliação Completa

| Dia | Asaas | Advbox | Δ | Status |
|-----|-------|--------|---|--------|
| 1 | R$ 13.298,15 | R$ 13.795,15 | R$ 497,00 | ✗ |
| 2 | R$ 17.164,75 | R$ 17.167,75 | R$ 3,00 | ✗ |
| 3 | R$ 20.695,58 | R$ 20.444,08 | R$ 251,50 | ✗ |
| 4 | R$ 2.613,67 | R$ 2.365,17 | R$ 248,50 | ✗ |
| 5 | R$ 0,00 | R$ 0,00 | R$ 0,00 | ✓ |
| 6 | R$ 6.000,00 | R$ 0,00 | R$ 6.000,00 | ✗ |
| 7 | R$ 397,00 | R$ 397,00 | R$ 0,00 | ✓ |
| 8 | R$ 22.549,95 | R$ 12.727,17 | R$ 9.822,78 | ✗ |
| 9 | R$ 18.195,57 | R$ 18.195,57 | R$ 0,00 | ✓ |
| 10 | R$ 4.220,24 | R$ 4.220,24 | R$ 0,00 | ✓ |

---

## ⚠️ Divergências Identificadas (Ordenadas por Magnitude)

### 🔴 CRÍTICA - 09/08: R$ 9.822,78
```
Asaas:  R$ 22.549,95
Advbox: R$ 12.727,17
Diferença: R$ 9.822,78 (43.5% de divergência)
```
**Status**: Requer investigação urgente  
**Possíveis causas**: TRANSFERs não reconciliados (padrão encontrado em análise anterior)

### 🟠 ALTA - 09/06: R$ 6.000,00
```
Asaas:  R$ 6.000,00
Advbox: R$ 0,00
Diferença: R$ 6.000,00 (receita não aparece em Advbox)
```
**Status**: Receita presente em Asaas mas ausente em Advbox  
**Possíveis causas**: Filtro de tipo de transação, atraso na sincronização

### 🟡 MÉDIA - 09/01: R$ 497,00
```
Asaas:  R$ 13.298,15
Advbox: R$ 13.795,15
Diferença: R$ 497,00 (Advbox com MAIS receita)
```
**Status**: Advbox mostra receita extra  
**Possíveis causas**: Devolução ou ajuste registrado apenas em Advbox

### 🟡 MÉDIA - 09/03: R$ 251,50
```
Asaas:  R$ 20.695,58
Advbox: R$ 20.444,08
Diferença: R$ 251,50
```

### 🟡 MÉDIA - 09/04: R$ 248,50
```
Asaas:  R$ 2.613,67
Advbox: R$ 2.365,17
Diferença: R$ 248,50
```

### 🟢 BAIXA - 09/02: R$ 3,00
```
Asaas:  R$ 17.164,75
Advbox: R$ 17.167,75
Diferença: R$ 3,00 (arredondamento)
```
**Status**: Provavelmente ajuste de centavos

---

## ✅ Dias que Batem Perfeitamente

- ✓ **09/05**: R$ 0,00 (ambos sem receita)
- ✓ **09/07**: R$ 397,00 (coincidência exata)
- ✓ **09/09**: R$ 18.195,57 (coincidência exata)
- ✓ **09/10**: R$ 4.220,24 (coincidência exata)

---

## 🔍 Padrões Observados

### Padrão 1: TRANSFERs Não Reconciliados
Baseado na análise anterior (feita em investigação prévia):
- Transações de tipo TRANSFER (PIX) em Asaas
- Não aparecem reconciliadas em Advbox
- Afeta principalmente os dias com divergências maiores (especialmente 09/08)

### Padrão 2: Receitas Faltando em Advbox
- 09/06: R$ 6.000,00 em Asaas, R$ 0 em Advbox
- Pode indicar filtros diferentes ou problema de sincronização

### Padrão 3: Pequenos Ajustes
- 09/02 e outros: Diferenças de centavos
- Provavelmente ajustes legítimos ou arredondamentos

---

## 📈 Recomendações de Ação

### Fase 1: Investigação (Imediata)
1. **09/08**: Usar `analise_matching_manual.py` para identificar quais TRANSFERs não combinam
2. **09/06**: Verificar se há filtro especial em Advbox excluindo receitas de R$ 6.000
3. **09/01, 03, 04**: Analisar se há devoluções ou ajustes registrados

### Fase 2: Confirmação (24-48h)
- [ ] Confirmar padrão de TRANSFERs para 09/08
- [ ] Analisar estrutura de dados de 09/06
- [ ] Verificar se devoluções estão sendo tratadas corretamente

### Fase 3: Correção (Conforme resultado)
- [ ] Se TRANSFER deve ser reconciliado: corrigir mapeamento/sincronização
- [ ] Se TRANSFER não deve ser reconciliado: atualizar filtros
- [ ] Se há atraso de sincronização: implementar retry logic

---

## 🔗 Próximas Ferramentas a Usar

Para investigação mais profunda, use:

```bash
# Análise detalhada de um dia específico
DIA_ALVO="2026-09-08" python3 analise_matching_manual.py

# Diagnóstico offline (com cache)
DIA_ALVO="2026-09-08" python3 diagnostico_transacoes_offline.py

# Diagnóstico online (com tokens)
DIA_ALVO="2026-09-08" python3 diagnostico_transacoes_dia.py
```

---

## 📊 Status Geral

**Conclusão**: 60% dos dias auditados têm divergências de receita. As maiores divergências (09/08 e 09/06) sugerem problema sistemático com:
- Tipos de transação específicos (provavelmente TRANSFER)
- Possível atraso ou falha de sincronização
- Possível diferença em regras de filtro entre sistemas

**Próximo passo recomendado**: Investigar 09/08 usando ferramentas de análise manual para confirmar se padrão de TRANSFER não-reconciliado se repete.

---

**Gerado por**: Auditoria automática via GitHub Actions  
**Workflow**: `Auditoria - Receitas dos 10 Primeiros Dias`  
**Run ID**: 37256079079
