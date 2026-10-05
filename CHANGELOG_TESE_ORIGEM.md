# Changelog: Resolução de Centro de Custo por TESE + ORIGEM

## Data: 2026-10-04

### Problema
Receitas de honorário não estavam sendo auto-postadas porque o centro de custo não era identificado. O código anterior apenas tentava sugerir centro de custo por origem do cliente, o que era insuficiente porque:

1. A estrutura de centros de custo no Advbox é **GRUPO-CANAL** (ex: "CONSUMIDOR-INSTAGRAM / MÍDIA SOCIAL", "RMC-ESCRITÓRIO / DIRETA")
2. O campo `origin` do cliente contém apenas o CANAL (ex: "INSTAGRAM", "ESCRITÓRIO")
3. Sem o GRUPO, não era possível montar o nome correto do centro de custo

**Exemplo concreto:**
- Receita R$ 1.588,73 no dia 28/09
- Cliente com `origin="ESCRITÓRIO"`
- Lawsuit com `type_lawsuit_id=1` (tese "RMC")
- Antes: não conseguia encontrar o centro de custo porque procurava por "ESCRITÓRIO" apenas
- Esperado: encontrar "RMC-ESCRITÓRIO / DIRETA" (GRUPO="RMC" + CANAL="ESCRITÓRIO")

### Solução Implementada

#### 1. Nova Função: `_mapa_tese_grupo()`
Constrói um mapeamento **TESE → GRUPO** observando os nomes dos centros de custo disponíveis em `/settings.financial.cost_centers`.

```python
_mapa_tese_grupo() → {"RMC": "RMC", "CONSUMIDOR": "CONSUMIDOR", ...}
```

Exemplo: Se existe centro de custo "CONSUMIDOR-INSTAGRAM", mapeia "CONSUMIDOR" → "CONSUMIDOR".

#### 2. Nova Função: `resolver_centro_custo_por_tese_e_origem(tese, origem_cliente)`
Resolve o nome completo do centro de custo combinando:
- `tese`: a tese/grupo do processo (ex: "RMC", "CONSUMIDOR")
- `origem_cliente`: a origem/canal do cliente (ex: "INSTAGRAM", "ESCRITÓRIO")

Resultado: nome do centro de custo como "GRUPO-CANAL" (ex: "RMC-ESCRITÓRIO / DIRETA")

O matching é feito em dois níveis:
1. **Exato**: procura "TESE-ORIGEM" no nome (ex: "RMC-INSTAGRAM" dentro de "RMC-INSTAGRAM / MÍDIA SOCIAL")
2. **Fuzzy**: se não encontrar exato, procura por palavras-chave parciais (fallback para variações)

#### 3. Modificação: `enriquecer_receita_faltando_com_processo()`
Adicionada **CAMADA 4B** de resolução de centro de custo, após ler a tese:

```
CAMADA 1: Precedente (se houver lançamento anterior do mesmo processo)
CAMADA 2: Análise de tarefas/descrições (se não houver precedente)
CAMADA 3: Validação de juros/multas
CAMADA 4: Sugestão por origem (usando sugerir_centro_custo_por_origem)
CAMADA 4B: [NOVO] Resolução por TESE + ORIGEM  ← implementado aqui
```

Quando não consegue resolver em CAMADA 1 (precedente) mas tem TESE e ORIGEM disponíveis, agora tenta:
```python
if not centro_custo_sugerido and tese and origem_cliente:
    centro_custo_sugerido = resolver_centro_custo_por_tese_e_origem(tese, origem_cliente)
```

### Impacto Esperado

#### Antes (status em 28/09)
- R$ 9.351,31: ✓ Postada (tinha precedente)
- R$ 1.588,73: ✗ Não postada (faltava centro de custo)
- R$ 3.608,27: ✗ Não postada (regex não parseou o protocolo)

#### Depois (com CAMADA 4B)
- R$ 1.588,73: ✓ Deve ser postada agora (tese="RMC" + origem="ESCRITÓRIO" → "RMC-ESCRITÓRIO / DIRETA")
- R$ 3.608,27: ainda precisa ajuste nos regex patterns

### Validação

O arquivo `test_tese_origem_mapping.py` contém testes unitários que validam:
- ✓ RMC + INSTAGRAM → RMC-INSTAGRAM / MÍDIA SOCIAL
- ✓ RMC + ESCRITÓRIO → RMC-ESCRITÓRIO / DIRETA
- ✓ CONSUMIDOR + INSTAGRAM → CONSUMIDOR-INSTAGRAM / MÍDIA SOCIAL
- ✓ CONSUMIDOR + ESCRITÓRIO → CONSUMIDOR-ESCRITÓRIO / DIRETA
- ✓ RMC + TRÁFEGO → RMC-TRÁFEGO / MÍDIA PAGA
- ✓ CONCURSO + INDICAÇÃO → CONCURSO-INDICAÇÃO / INDICAÇÃO

Todos os 10 testes passaram ✓

### Como Testar

1. **Teste local (sem APIs reais):**
   ```bash
   python3 test_tese_origem_mapping.py
   ```

2. **Teste em produção (com dados reais):**
   ```bash
   # No GitHub Actions, trigger manualmente:
   - Target Date: 2026-09-28
   - DRY_RUN: true (pra não gravar nada)
   ```

   Ou via linha de comando (precisa das variáveis de ambiente ADVBOX_TOKEN, ASAAS_TOKEN):
   ```bash
   TARGET_DATE=2026-09-28 DRY_RUN=true python3 conciliar_v2.py
   ```

3. **Verificar no diagnóstico:**
   O script `diagnostico_advbox.py` mostra todos os centros de custo disponíveis, ajudando a validar o mapeamento.

### Próximos Passos

1. **Ajustar regex do protocolo** para a receita R$ 3.608,27 (seção 5 do diagnóstico mostrou que o protocolo tem um formato diferente)
2. **Testar no contexto real** com as credenciais do Advbox/Asaas
3. **Monitorar a execução** no dia seguinte pra validar que as receitas são postadas corretamente

### Notas Técnicas

- Usa `@lru_cache` pra cache das funções de mapeamento (evita múltiplas chamadas a `/settings`)
- A lógica de fallback (fuzzy matching) é robusta a variações de caso/acentuação
- As receitas ainda têm as travas de segurança:
  - Precisa de categoria_id E centro_custo_id
  - Se o protocolo informar um valor creditado diferente do que caiu, rejeita (manual)

