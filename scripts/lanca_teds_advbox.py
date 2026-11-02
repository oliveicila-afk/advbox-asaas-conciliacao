#!/usr/bin/env python3
"""
Script para lançar as 10 TEDs recebidas do ASAAS no Advbox
Período: 01-10 de outubro de 2026
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Optional

# Dados das TEDs a lançar
TEDS = [
      {"numero_fatura": "924908121", "valor": 27214.78, "data": "2026-10-01"},
      {"numero_fatura": "925258116", "valor": 6293.97, "data": "2026-10-02"},
      {"numero_fatura": "926476598", "valor": 8969.79, "data": "2026-10-03"},
      {"numero_fatura": "928586680", "valor": 20808.16, "data": "2026-10-04"},
      {"numero_fatura": "928874986", "valor": 7239.30, "data": "2026-10-05"},
      {"numero_fatura": "929562005", "valor": 9600.96, "data": "2026-10-06"},
      {"numero_fatura": "929696991", "valor": 8789.85, "data": "2026-10-07"},
      {"numero_fatura": "929718746", "valor": 17463.23, "data": "2026-10-08"},
      {"numero_fatura": "930023237", "valor": 11988.57, "data": "2026-10-09"},
      {"numero_fatura": "932787371", "valor": 4363.11, "data": "2026-10-10"},
]

class AdvboxAPI:
      """Cliente para a API do Advbox"""

    BASE_URL = "https://api.advbox.com.br/v1"

    def __init__(self, api_key: str):
              """
                      Inicializa o cliente da API do Advbox

                              Args:
                                          api_key: Chave de API do Advbox (obtida em Settings > Integrações)
                                                  """
              self.api_key = api_key
              self.session = requests.Session()
              self.session.headers.update({
                  "Authorization": f"Bearer {api_key}",
                  "Content-Type": "application/json"
              })

    def criar_receita(
              self,
              valor: float,
              data_pagamento: str,
              numero_referencia: str,
              conta_id: int = 193264,
              categoria_id: Optional[int] = None,
              descricao: str = "TED recebida"
    ) -> Dict:
              """
                      Cria um lançamento de receita no Advbox

                              Args:
                                          valor: Valor da receita
                                                      data_pagamento: Data do pagamento (YYYY-MM-DD)
                                                                  numero_referencia: Número da fatura/referência
                                                                              conta_id: ID da conta (padrão: ASAAS)
                                                                                          categoria_id: ID da categoria (opcional)
                                                                                                      descricao: Descrição do lançamento
                                                                                                      
                                                                                                              Returns:
                                                                                                                          Resposta da API
                                                                                                                                  """
              payload = {
                  "tipo": 2,
                  "valor": valor,
                  "data_pagamento": data_pagamento,
                  "descricao": f"{descricao} - Fatura {numero_referencia}",
                  "numero_referencia": numero_referencia,
                  "conta_id": conta_id,
              }

        if categoria_id:
                      payload["categoria_id"] = categoria_id

        response = self.session.post(
                      f"{self.BASE_URL}/transactions",
                      json=payload
        )

        return {
                      "status_code": response.status_code,
                      "success": response.status_code in [200, 201],
                      "data": response.json() if response.text else {},
                      "error": response.text if response.status_code not in [200, 201] else None
        }

    def listar_contas(self) -> Dict:
              """Lista as contas cadastradas no Advbox"""
              response = self.session.get(f"{self.BASE_URL}/accounts")
              return {
                  "status_code": response.status_code,
                  "data": response.json() if response.text else []
              }

    def listar_categorias(self) -> Dict:
              """Lista as categorias cadastradas no Advbox"""
              response = self.session.get(f"{self.BASE_URL}/categories")
              return {
                  "status_code": response.status_code,
                  "data": response.json() if response.text else []
              }


def lançar_teds(api_key: str) -> None:
      """
          Lança todas as 10 TEDs no Advbox

              Args:
                      api_key: Chave de API do Advbox
                          """
      print("=" * 60)
      print("LANÇAMENTO DE TEDs NO ADVBOX")
      print("=" * 60)
      print(f"Total de TEDs: {len(TEDS)}")
      print(f"Período: 01-10 de outubro de 2026")
      print(f"Total a lançar: R$ {sum(ted['valor'] for ted in TEDS):,.2f}")
      print("=" * 60)

    api = AdvboxAPI(api_key)

    resultados = {
              "sucesso": [],
              "erro": []
    }

    for i, ted in enumerate(TEDS, 1):
              print(f"\n[{i}/{len(TEDS)}] Lançando TED {ted['numero_fatura']}...")
              print(f"  Valor: R$ {ted['valor']:,.2f}")
              print(f"  Data: {ted['data']}")

        resultado = api.criar_receita(
                      valor=ted['valor'],
                      data_pagamento=ted['data'],
                      numero_referencia=ted['numero_fatura'],
                      descricao="TED recebida"
        )

        if resultado['success']:
                      print(f"  Sucesso!")
                      resultados['sucesso'].append(ted)
else:
              print(f"  Erro: {resultado['error']}")
              resultados['erro'].append({
                  **ted,
                  "erro": resultado['error']
              })

    # Resumo final
      print("\n" + "=" * 60)
    print("RESUMO DO LANÇAMENTO")
    print("=" * 60)
    print(f"Lançados com sucesso: {len(resultados['sucesso'])}")
    print(f"Com erro: {len(resultados['erro'])}")

    if resultados['erro']:
              print("\nTEDs com erro:")
              for ted in resultados['erro']:
                            print(f"  - {ted['numero_fatura']}: {ted['erro']}")

          print("\n" + "=" * 60)


if __name__ == "__main__":
      import sys

    # Obter a chave de API
      if len(sys.argv) > 1:
                api_key = sys.argv[1]
else:
          api_key = input("Digite a chave de API do Advbox (obtida em Settings > Integrações): ")

    if not api_key:
              print("Erro: Chave de API não fornecida")
              sys.exit(1)

    try:
              lançar_teds(api_key)
except Exception as e:
          print(f"\nErro ao executar script: {e}")
          sys.exit(1)
