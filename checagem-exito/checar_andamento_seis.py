"""Leitura SOMENTE LEITURA dos processos vencidos (CONTADORIA, sem baixa) que têm
recebimento correspondente no Asaas, com valor menor.

Procura nas tarefas sinais de andamento: obrigação pendente, parcela, saldo, etc.
Imprime somente: máscara do processo, datas, palavras encontradas e valores em R$.
Não imprime texto das tarefas, nomes de clientes nem números completos de processo.
"""

import re
import sys
from collections import defaultdict

import conferir_pendentes as cp

ANDAMENTO = re.compile(
    r"andamento|aguard|pendent|requer|parcial|parcela|restante|saldo|falta|"
    r"intima|cumpriment|execu[çc]|recurso|dep[óo]sit|expedi|diferen|l[ií]quid|"
    r"reten[çc]|desconto|acordo|complementar|cobran[çc]a|boleto",
    re.IGNORECASE,
)
VALOR = re.compile(r"R\$\s?[\d\.\,]+")


def main() -> int:
    if not cp.ADVBOX_TOKEN or not cp.ASAAS_TOKEN:
        print("ERRO: tokens não configurados.")
        return 1

    lancs = cp.advbox_contadoria_sem_pagamento()
    vencidos = [l for l in lancs if (l.get("date_due") or "9999")[:10] < cp.HOJE]
    recebs = cp.recebimentos_asaas()

    por_digitos = defaultdict(list)
    for r in recebs:
        ref = cp.digitos(r.get("externalReference"))
        if len(ref) >= 15:
            por_digitos[ref].append(r)

    alvo = []
    for l in vencidos:
        proc = cp.digitos(l.get("process_number"))
        if len(proc) < 15:
            continue
        casados = [r for ref, rs in por_digitos.items()
                   if proc in ref or ref.endswith(proc) for r in rs]
        if casados:
            alvo.append((l, proc, casados))
    print(f"Processos com recebimento no Asaas (menor): {len(alvo)}")

    for l, proc, casados in alvo:
        lid = cp.id_processo(l)
        mascara = cp.mascarar(proc)
        print(f"\nPROCESSO {mascara} | Advbox {l.get('amount')} venc {str(l.get('date_due'))[:10]} | "
              f"Asaas {[(x.get('date'), x.get('value')) for x in casados][:3]}")
        if not lid:
            print("  sem id de processo no lançamento")
            continue
        itens = cp.ler_tarefas(lid)
        print(f"  itens lidos: {len(itens)}")
        for it in itens:
            txt = cp.texto_do_item(it)
            palavras = sorted({m.lower() for m in ANDAMENTO.findall(txt)})
            valores = VALOR.findall(txt)
            if palavras or valores:
                print(f"  TAREFA {cp.data_do_item(it)} | palavras: {palavras} | valores: {valores[:4]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
