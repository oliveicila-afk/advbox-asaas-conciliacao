# 📋 Guia de Extração de Dados Para Matching

**Objetivo**: Identificar quais clientes estão em Asaas mas NÃO estão em Advbox (01-10 de setembro)

**Tempo estimado**: 10-15 minutos para extrair ambos os dados

---

## 1️⃣ **Extrair do ASAAS (Receitas - 01 a 10 de Setembro)**

### Passo a passo:
1. Acesse: **Asaas → Transações Financeiras** (ou Receitas)
2. **Filtros**:
   - Data: **01 de setembro a 10 de setembro 2026**
   - Tipo: **Receitas** (apenas valores positivos)
3. **Exportar / Copiar** em formato CSV ou tabela

### Campos que preciso:
```
Data | Cliente/Descrição | Valor | Tipo de Transação
```

### Formato esperado (você pode colar assim):
```
01/09 | Cliente A | 1.000,00 | PIX Recebido
01/09 | Cliente B | 500,00 | Cartão de Crédito
02/09 | Cliente C | 2.500,00 | Transferência
...
```

**OU** você pode fornecer um **resumo por cliente**:
```
Cliente A:        R$ 1.000,00 (3 transações)
Cliente B:        R$ 500,00 (1 transação)
Cliente C:        R$ 2.500,00 (2 transações)
...
```

---

## 2️⃣ **Extrair do ADVBOX (Receitas - 01 a 10 de Setembro)**

### Passo a passo:
1. Acesse: **Advbox → Lançamentos** (ou Transações)
2. **Filtros**:
   - Data: **01 de setembro a 10 de setembro 2026**
   - Tipo: **Receita/Income**
3. **Exportar / Copiar** em formato CSV ou tabela

### Campos que preciso:
```
Data | Cliente/Descrição | Valor | Categoria
```

### Formato esperado:
```
01/09 | Cliente A - Fatura #123 | 1.000,00 | Contas a Receber
01/09 | Cliente B - Consultoria | 500,00 | Serviços
02/09 | Cliente C - Procedimento | 2.500,00 | Contas a Receber
...
```

---

## 3️⃣ **O Que Vou Fazer Com Esses Dados**

Assim que você enviar, vou:

✅ **Agrupar por cliente** em ambos os sistemas  
✅ **Comparar nomes** (mesmo que escrito de forma diferente)  
✅ **Identificar**:
   - Clientes que estão em Asaas mas NÃO em Advbox
   - Clientes que estão em Advbox mas NÃO em Asaas
   - Valores que estão faltando

✅ **Calcular** o total de receita faltando/duplicada  

---

## 💡 Dica Rápida

Se você tiver acesso a **Excel ou Google Sheets**, pode fazer isso ainda mais rápido:

1. **Copie a lista de Asaas** para uma coluna
2. **Copie a lista de Advbox** para outra coluna
3. **Agrupe por Cliente** (UNIQUE + SUMIF no Excel/Sheets)
4. **Cole aqui** que eu faço o matching

---

## 🎯 Próximas Ações

**IMEDIATO**:
Você consegue extrair esses dados de Asaas e Advbox nos próximos minutos?

**DEPOIS**:
Assim que receber, vou:
1. Fazer o matching preciso
2. Identificar exatamente qual é a divergência
3. Mostrar quais clientes/valores estão faltando

---

**Status**: ⏸️ Aguardando dados  
**Prioridade**: 🔴 CRÍTICA
