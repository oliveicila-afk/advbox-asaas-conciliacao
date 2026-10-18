"""Somente leitura: procura no histórico e nas tarefas do processo do lançamento sinais de pagamento
em atraso (datas, palavras de pagamento, valores). Não imprime texto das tarefas, nomes nem número de processo."""
import re
import sys

import conferir_pendentes as cp
import aplicar_regra_liquido as a

TX = "15193032"
PALAVRAS = re.compile(r"pag[oa]|pagament|recebid|caiu|baixa|atras|vencid|quitad|dep[óo]sit|honor[áa]ri", re.IGNORECASE)
DATA = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
VALOR = re.compile(r"R\$\s?[\d\.\,]+")


def main() -> int:
    det = a.detalhe(TX)
    print(f"Lançamento: venc {str(det.get('date_due'))[:10]} | pag {str(det.get('date_payment'))[:10]} "
          f"| valor {det.get('amount')}")
    lid = cp.id_processo(det)
    if not lid:
        print("sem id de processo")
        return 0
    itens = cp.ler_tarefas(lid)
    print(f"itens lidos: {len(itens)}")
    for it in sorted(itens, key=lambda x: str(x.get("created_at") or x.get("date") or "")):
        txt = cp.texto_do_item(it)
        palavras = sorted({m.lower() for m in PALAVRAS.findall(txt)})
        datas = DATA.findall(txt)
        valores = VALOR.findall(txt)
        if palavras or valores:
            print(f"  {cp.data_do_item(it)} | palavras: {palavras} | datas no texto: {datas[:4]} | valores: {valores[:4]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
