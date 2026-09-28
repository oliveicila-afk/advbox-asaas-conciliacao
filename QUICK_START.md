# 🚀 Quick Start - Resolver Erro 401 em 20 Minutos

## O Problema (em 1 linha)
Token Asaas expirou → API retorna 401 → Workflow falha → Sem lançamentos no Advbox

## A Solução (em 5 passos)

### ✅ Passo 1: Obter Novo Token (5 min)
```
1. Acesse: https://www.asaas.com/login
2. Vá para: Configurações → Integrações → API  
3. Clique: "Gerar Nova Chave de API"
4. Copie: O token gerado (começa com $aact_prod_)
```

### ✅ Passo 2: Validar Token Localmente (2 min)
```bash
export ASAAS_TOKEN="cole_seu_token_aqui"
python test_asaas_token.py
```
✓ Deve retornar: `✓ SUCESSO! O token está funcionando corretamente.`

### ✅ Passo 3: Atualizar GitHub Secrets (2 min)
```
1. Vá para: github.com/seu_repo/settings/secrets/actions
2. Procure: ASAAS_TOKEN
3. Clique: "Update secret"
4. Cole: O novo token
5. Clique: "Update secret"
```

### ✅ Passo 4: Testar no GitHub (5-10 min)
```
1. Vá para: Actions → "Conciliação diária Advbox x Asaas"
2. Clique: "Run workflow"
3. Deixe: dry_run=true (é um teste)
4. Espere o workflow terminar
5. Verifique: Não deve haver erro 401
```

### ✅ Passo 5: Rodar de Verdade (5 min)
```
1. Run workflow novamente
2. Mude: dry_run=false
3. Confirme que lançamentos aparecem no Advbox
```

## Se Algo Não Funcionar

### Erro 401 persiste?
```bash
# Teste manualmente
curl -H "access_token: seu_token" \
  "https://api.asaas.com/v3/financialTransactions?startDate=2026-09-28&limit=1"
```
Se retornar erro, o token ainda é inválido.

### Precisa entender mais?
```bash
cat RESUMO_CORRECOES.md          # Sumário executivo
cat DIAGNOSTICO_ERRO_401.md      # Guia completo
cat ANALISE_TECNICA.md           # Análise profunda
```

## Checklist Rápido

- [ ] Novo token obtido do Asaas
- [ ] Script `test_asaas_token.py` retornou sucesso
- [ ] GitHub Secrets foi atualizado
- [ ] Workflow testado (dry_run=true)
- [ ] Workflow executado (dry_run=false)
- [ ] Lançamentos aparecem no Advbox
- [ ] ✅ CONCLUÍDO!

---

**Tempo total: ~20 minutos**

**Dúvidas?** Leia os outros documentos .md - tudo está explicado!
