import time
import requests
import aplicar_regra_liquido as a
import conferir_pendentes as cp

POST = 288487801
for metodo in ("patch", "put"):
    resp = getattr(requests, metodo)(f"{cp.ADVBOX_BASE}/posts/{POST}", headers=a.headers(),
                                     json={"display_schedule": True}, timeout=30)
    print(f"EDICAO {metodo.upper()} /posts/{POST}: status {resp.status_code}")
    time.sleep(2.2)
