#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script: Listar categorias disponíveis no Advbox
"""

import os
import sys
import requests

ADVBOX_BASE = "https://app.advbox.com.br/api/v1"
ADVBOX_TOKEN = os.environ.get("ADVBOX_TOKEN", "")

ADVBOX_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

if not ADVBOX_TOKEN:
    print("❌ ADVBOX_TOKEN not set")
    sys.exit(1)

print("📋 Listando categorias do Advbox")
print("=" * 80)

headers = {
    "Authorization": f"Bearer {ADVBOX_TOKEN}",
    "User-Agent": ADVBOX_USER_AGENT,
    "Accept": "application/json",
    "Content-Type": "application/json"
}

def main():
    try:
        print(f"Token length: {len(ADVBOX_TOKEN)}")
        print(f"Token (first 10 chars): {ADVBOX_TOKEN[:10]}...")
        print(f"Headers: Authorization={headers['Authorization'][:20]}...")

        resp = requests.get(
            f"{ADVBOX_BASE}/categories",
            headers=headers,
            timeout=30
        )

        print(f"Status: {resp.status_code}\n")

        if resp.status_code == 200:
            data = resp.json()
            categories = data.get("data", [])

            if categories:
                print(f"✅ Encontradas {len(categories)} categorias:\n")
                for cat in categories[:30]:  # Show first 30
                    cat_id = cat.get("id")
                    name = cat.get("name", "(sem nome)")
                    print(f"  ID: {cat_id:>6} | Nome: {name}")

                # Save to file for easy reference
                print("\n📁 Salvando categorias em categorias_list.json...")
                import json
                with open("categorias_list.json", "w") as f:
                    json.dump(categories, f, indent=2, ensure_ascii=False)
                print("✅ Salvo em categorias_list.json")
            else:
                print("❌ Nenhuma categoria encontrada")
                print(f"Response: {data}")
        else:
            print(f"⚠️  Erro {resp.status_code}")
            print(f"Full response text:\n{resp.text}")
            try:
                print("\nResponse JSON:")
                print(resp.json())
            except:
                pass

    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()

    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
