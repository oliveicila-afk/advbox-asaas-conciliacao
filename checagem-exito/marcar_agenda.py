"""Cria a tarefa de cobrança do caso pendente com 'mostrar na agenda' (a antiga já foi apagada manualmente)."""
import time
import requests
import aplicar_regra_liquido as a
import conferir_pendentes as cp

TX = "16912661"
det = a.detalhe(TX)
lid = cp.id_processo(det)
comentario = (
    "Pagamento recebido em 17/09/2026 com valor a menor. "
    "Valor bruto no Advbox: R$ 2640,05. "
    "Valor recebido: R$ 2541,36. "
    "Processo com movimentação após o pagamento. Verificar se falta valor a receber, "
    "a previsão de data e a possível incidência de juros e multa."
)
payload = {
    "from": a.PRISCILA_ID,
    "guests": [a.GABI_ID],
    "tasks_id": a.TIPO_TAREFA_COBRANCA_EXITO,
    "lawsuits_id": lid,
    "start_date": "2026-11-17",
    "comments": comentario,
    "important": True,
    "urgent": False,
    "display_schedule": True,
}
r = requests.post(f"{cp.ADVBOX_BASE}/posts", headers=a.headers(), json=payload, timeout=30)
print(f"NOVA tarefa com agenda: status {r.status_code} | {r.text[:200]}")
time.sleep(2.2)
