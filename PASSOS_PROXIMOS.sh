#!/bin/bash
# Script helper para completar a solução do erro 401

set -e

echo "=========================================="
echo "SOLUÇÃO: Erro 401 - Conciliação Asaas"
echo "=========================================="
echo ""

# Step 1: Verificar se há commit pendente
echo "📝 Status do repositório:"
git status

echo ""
echo "📦 Commit preparado (ready to push):"
git log -1 --oneline

echo ""
echo "=========================================="
echo "✅ PRÓXIMOS PASSOS (você precisa fazer):"
echo "=========================================="
echo ""
echo "1️⃣  Obter novo token do Asaas:"
echo "   • Acesse: https://www.asaas.com/login"
echo "   • Vá para: Configurações → Integrações → API"
echo "   • Gere um novo token (começa com \$aact_prod_)"
echo ""

echo "2️⃣  Validar o token localmente:"
echo "   export ASAAS_TOKEN='seu_token_aqui'"
echo "   python test_asaas_token.py"
echo ""

echo "3️⃣  Atualizar GitHub Secrets:"
echo "   • Settings → Secrets and variables → Actions"
echo "   • Atualize ASAAS_TOKEN"
echo ""

echo "4️⃣  Push das mudanças:"
echo "   git push origin main"
echo ""

echo "5️⃣  Testar workflow no GitHub:"
echo "   • Actions → Conciliação diária Advbox x Asaas"
echo "   • Run workflow (dry_run=true)"
echo "   • Verificar se não há mais erros 401"
echo ""

echo "6️⃣  Se teste passou, rodar de verdade:"
echo "   • Run workflow novamente (dry_run=false)"
echo "   • Verificar se lançamentos aparecem no Advbox"
echo ""

echo "=========================================="
echo "📚 Documentação:"
echo "=========================================="
echo "   • RESUMO_CORRECOES.md"
echo "   • DIAGNOSTICO_ERRO_401.md"
echo "   • test_asaas_token.py"
echo ""

echo "Tempo estimado: ~20 minutos"
echo ""
