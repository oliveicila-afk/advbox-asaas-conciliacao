# Diagnóstico: Erro 401 - Falha na Conciliação Asaas/Advbox

## Status do Problema

**Data de início:** 2026-09-26
**Última falha:** 2026-09-28 às 14:56:43 UTC (5 tentativas, todas retornando 401)
**Impacto:** Nenhum lançamento está sendo emitido no Advbox porque o script `conciliar.py` falha ao autenticar na API do Asaas.

## Causa Raiz Identificada

O workflow GitHub Actions `conciliacao-diaria.yml` está falhando ao chamar o endpoint `/financialTransactions` da API Asaas com erro **HTTP 401 (Não Autorizado)**.

### Sequência de erro no workflow:
```
[2026-09-28T14:56:43Z] Asaas: buscando /financialTransactions…
[2026-09-28T14:56:43Z] Asaas /financialTransactions -> status 401 (tentativa 1/5)
[2026-09-28T14:56:45Z] Asaas /financialTransactions -> status 401 (tentativa 2/5)
[2026-09-28T14:56:49Z] Asaas /financialTransactions -> status 401 (tentativa 3/5)
[2026-09-28T14:56:57Z] Asaas /financialTransactions -> status 401 (tentativa 4/5)
[2026-09-28T14:57:13Z] Asaas /financialTransactions -> status 401 (tentativa 5/5)
RuntimeError: Falha ao consultar Asaas /financialTransactions após 5 tentativas
```

## Possíveis Causas

### 1. **Token Expirado ou Revogado** ⚠️ MAIS PROVÁVEL
- O token no GitHub Secret `ASAAS_TOKEN` pode ter sido invalidado
- Tokens Asaas podem expirar após um período de inatividade
- O token pode ter sido manualmente revogado no dashboard do Asaas

### 2. **Token Incorreto**
- O token em GitHub Secrets pode ser diferente do que estava em `analise_completa.py`
- O token pode ter sido truncado ou corrompido

### 3. **Mudança na API do Asaas**
- A API pode ter mudado o formato de autenticação
- Pode ser necessário usar Bearer token em vez de header `access_token`

### 4. **Problema de Rede/Proxy**
- Menos provável, mas possível se o IP do GitHub Actions foi bloqueado

## Dados de Segurança

### ⚠️ Credencial Exposta Encontrada

**Arquivo:** `analise_completa.py` (linha 30)  
**Token exposto:** `$aact_prod_000MzkwODA2MWY2OGM3MWRlMDU2NWM3MzJlNzZmNGZhZGY6OmRjNTA3MGI0LWU2NjAtNDYxZS04MTRiLTkwMDdhZWZkNWM4ODo6JGFhY2hfMTIyYzZhY2ItMmFhYi00M2ZiLTgwMmUtZWUyNmQ0MmE4YTg5`  
**Status:** ✓ CORRIGIDO - Token removido e código atualizado para usar variáveis de ambiente

**Ação tomada:**
- Removido token hardcoded de `analise_completa.py`
- Script atualizado para ler de `os.environ.get("ASAAS_TOKEN", "")`
- Agora funciona da mesma forma que `conciliar.py` (seguro)

## Solução

### Passo 1: Validar o Token Atual

Execute o script de teste para diagnosticar se o token está funcionando:

```bash
# No seu ambiente local ou no Actions
ASAAS_TOKEN="seu_token_aqui" python test_asaas_token.py
```

Este script irá:
- ✓ Verificar se a variável está configurada
- ✓ Tentar chamar a API Asaas
- ✓ Mostrar exatamente qual é o erro
- ✓ Sugerir ações corretivas

### Passo 2: Se o Token Estiver Inválido

Se o script de teste retornar **401**, você precisa gerar um novo token:

1. **Acesse o Dashboard do Asaas**
   - URL: https://www.asaas.com/login
   - Faça login com sua conta

2. **Gere um novo API Token**
   - Vá para: Configurações → Integrações → API
   - Clique em "Gerar Nova Chave de API"
   - Copie o novo token gerado (começa com `$aact_prod_...`)

3. **Atualize o Secret no GitHub**
   - Vá para: Seu Repositório → Settings → Secrets and variables → Actions
   - Procure por `ASAAS_TOKEN`
   - Clique em "Update secret"
   - Cole o novo token
   - Clique em "Update secret"

### Passo 3: Validar a Correção

Após atualizar o token no GitHub:

```bash
# Opção A: Executar o teste localmente
ASAAS_TOKEN="seu_novo_token" python test_asaas_token.py

# Opção B: Disparar manualmente o workflow no GitHub
# Vá para: Actions → Conciliação diária Advbox x Asaas → Run workflow
# (deixar configurações padrão: dry_run=true)
```

Se o teste retornar **✓ SUCESSO**, o workflow deve funcionar novamente.

### Passo 4: Executar a Conciliação

```bash
# Uma vez validado, disparar a conciliação real
cd /caminho/para/o/repositorio

# Localmente (opcional):
ADVBOX_TOKEN="..." ASAAS_TOKEN="seu_novo_token" python conciliar.py

# Ou via GitHub Actions (automático ou manual):
# - Actions → Conciliação diária Advbox x Asaas → Run workflow
# - Usar dry_run=false para executar de verdade
```

## Verificação Checklist

Antes de considerar o problema resolvido:

- [ ] Script `test_asaas_token.py` retorna **✓ SUCESSO**
- [ ] Token no GitHub Secrets foi atualizado
- [ ] Workflow `conciliacao-diaria.yml` foi executado com sucesso
- [ ] PDF de reconciliação foi gerado
- [ ] Lançamentos (links) estão sendo emitidos no Advbox novamente
- [ ] Não há mais erros 401 nos logs do GitHub Actions

## Mudanças de Código Realizadas

### ✓ Corrigido: `analise_completa.py`

**Antes:**
```python
ADVBOX_TOKEN = "FN01fkXyKtolS8GJMdtUiNQJfM6CWtRm7gxe2ZGacA6LGlsDOMMSvTmDo8Vn"
ASAAS_TOKEN = "$aact_prod_000MzkwODA2MWY2OGM3MWRlMDU2NWM3MzJlNzZmNGZhZGY6OmRjNTA3MGI0LWU2NjAtNDYxZS04MTRiLTkwMDdhZWZkNWM4ODo6JGFhY2hfMTIyYzZhY2ItMmFhYi00M2ZiLTgwMmUtZWUyNmQ0MmE4YTg5"
```

**Depois:**
```python
import os

ADVBOX_TOKEN = os.environ.get("ADVBOX_TOKEN", "")
ASAAS_TOKEN = os.environ.get("ASAAS_TOKEN", "")
```

## Próximos Passos (Se a Solução Não Funcionar)

Se após seguir todos esses passos o problema persistir:

1. **Verificar logs detalhados do GitHub**
   - Actions → Workflow que falhou → Ver logs completos
   - Procurar por mensagens de erro específicas

2. **Testar endpoint Asaas manualmente**
   ```bash
   curl -H "access_token: seu_token" \
     "https://api.asaas.com/v3/financialTransactions?startDate=2026-09-28&finishDate=2026-09-28&limit=1"
   ```

3. **Verificar se a API Asaas está funcionando**
   - Status page: https://status.asaas.com/

4. **Contatar suporte Asaas**
   - Se o token está válido mas ainda retorna 401
   - Fornecer o token e a timestamp do erro

## Referências

- [Documentação API Asaas](https://docs.asaas.com/)
- [GitHub Actions Secrets](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions)
- [Workflow: conciliacao-diaria.yml](./.github/workflows/conciliacao-diaria.yml)
- [Script de teste: test_asaas_token.py](./test_asaas_token.py)
