import unittest
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import analise_por_data_valor
import conciliar_v2
import criar_lancamentos
from period_reconciliation import date_range, plan_daily_movements


class PeriodReconciliationTests(unittest.TestCase):
    def test_date_range_is_inclusive(self):
        self.assertEqual(
            date_range("2026-09-01", "2026-09-03"),
            ["2026-09-01", "2026-09-02", "2026-09-03"],
        )

    def test_rejects_reversed_date_range(self):
        with self.assertRaises(ValueError):
            date_range("2026-09-03", "2026-09-01")

    def test_matches_by_direction_date_and_cents_and_preserves_duplicates(self):
        asaas = [
            {"id": "asaas-1", "date": "2026-09-01", "type": "PAYMENT_RECEIVED", "value": 100},
            {"id": "asaas-2", "date": "2026-09-01", "type": "PAYMENT_RECEIVED", "value": 100},
            {"id": "asaas-other-day", "date": "2026-09-02", "type": "PAYMENT_RECEIVED", "value": 40},
        ]
        advbox = [
            {"id": 1, "date_payment": "2026-09-01", "entry_type": "income", "amount": 100},
            {"id": 2, "date_payment": "2026-09-01", "entry_type": "expense", "amount": 100},
            {"id": 3, "date_payment": "2026-09-01", "entry_type": "income", "amount": 50},
        ]

        plan = plan_daily_movements(
            asaas,
            advbox,
            "2026-09-01",
            income_types={"PAYMENT_RECEIVED"},
            expense_types={"PAYMENT_FEE"},
            ignored_types=set(),
            consolidated_expense_categories={},
        )

        self.assertTrue(plan["safe_to_mutate"])
        self.assertEqual([item["id"] for item in plan["asaas_faltando"]], ["asaas-2"])
        self.assertEqual([item["id"] for item in plan["advbox_fantasmas"]], [2, 3])

    def test_unknown_asaas_type_blocks_deletion(self):
        plan = plan_daily_movements(
            [{"id": "unknown", "date": "2026-09-01", "type": "NEW_TYPE", "value": 100}],
            [{"id": 1, "date_payment": "2026-09-01", "entry_type": "income", "amount": 50}],
            "2026-09-01",
            income_types={"PAYMENT_RECEIVED"},
            expense_types=set(),
            ignored_types=set(),
            consolidated_expense_categories={},
        )

        self.assertFalse(plan["safe_to_mutate"])
        self.assertEqual(plan["unsupported_asaas_types"], ["NEW_TYPE"])
        self.assertEqual(plan["advbox_fantasmas"], [])

    def test_daily_fee_is_matched_as_a_category_total(self):
        plan = plan_daily_movements(
            [
                {"id": "fee-1", "date": "2026-09-01", "type": "INSTANT_TEXT_MESSAGE_FEE", "value": 2},
                {"id": "fee-2", "date": "2026-09-01", "type": "INSTANT_TEXT_MESSAGE_FEE", "value": 3},
            ],
            [{
                "id": 1,
                "date_payment": "2026-09-01",
                "entry_type": "expense",
                "amount": 5,
                "category": "TAXA DE COMUNICAÇÃO",
            }],
            "2026-09-01",
            income_types=set(),
            expense_types=set(),
            ignored_types=set(),
            consolidated_expense_categories={
                "INSTANT_TEXT_MESSAGE_FEE": "Taxa de Comunicação",
            },
        )

        self.assertTrue(plan["safe_to_mutate"])
        self.assertEqual(plan["expected_expense_cents"], 500)
        self.assertEqual(plan["actual_expense_cents"], 500)
        self.assertEqual(plan["advbox_fantasmas"], [])

    def test_parses_brazilian_and_us_amount_strings_and_accent_variants(self):
        plan = plan_daily_movements(
            [{
                "date": "2026-09-01",
                "type": "INSTANT_TEXT_MESSAGE_FEE",
                "value": "1.234,56",
            }],
            [{
                "id": 1,
                "date_payment": "2026-09-01",
                "entry_type": "expense",
                "amount": "1,234.56",
                "category": "Taxa de Comunicacao",
            }],
            "2026-09-01",
            income_types=set(),
            expense_types=set(),
            ignored_types=set(),
            consolidated_expense_categories={
                "INSTANT_TEXT_MESSAGE_FEE": "TAXA DE COMUNICAÇÃO",
            },
        )

        self.assertTrue(plan["safe_to_mutate"])
        self.assertEqual(plan["expected_expense_cents"], 123456)
        self.assertEqual(plan["actual_expense_cents"], 123456)

    def test_overposted_daily_fee_blocks_deletion(self):
        plan = plan_daily_movements(
            [{"date": "2026-09-01", "type": "INSTANT_TEXT_MESSAGE_FEE", "value": 5}],
            [{
                "id": 1,
                "date_payment": "2026-09-01",
                "entry_type": "expense",
                "amount": 10,
                "category": "TAXA DE COMUNICAÇÃO",
            }],
            "2026-09-01",
            income_types=set(),
            expense_types=set(),
            ignored_types=set(),
            consolidated_expense_categories={
                "INSTANT_TEXT_MESSAGE_FEE": "TAXA DE COMUNICAÇÃO",
            },
        )

        self.assertFalse(plan["safe_to_mutate"])
        self.assertEqual(len(plan["daily_category_overages"]), 1)
        self.assertEqual(plan["advbox_fantasmas"], [])

    def test_analysis_writes_fresh_per_day_plan_for_the_requested_range(self):
        advbox_items = [{
            "id": 1,
            "date_payment": "2026-09-01",
            "entry_type": "income",
            "amount": 50,
        }]
        asaas_items = [
            {"id": "receipt-1", "date": "2026-09-01", "type": "PAYMENT_RECEIVED", "value": 100},
            {"id": "receipt-2", "date": "2026-09-02", "type": "PAYMENT_RECEIVED", "value": 75},
        ]

        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "fresh-report.json"
            env = {
                "ADVBOX_TOKEN": "test",
                "ASAAS_TOKEN": "test",
                "START_DATE": "2026-09-01",
                "END_DATE": "2026-09-02",
                "ANALYSIS_FILE": str(report_path),
            }
            report_stub = {
                "receita_data_errada": [],
                "taxa_bancaria_data_errada": [],
                "receita_faltando": [],
                "taxa_bancaria_faltando": [],
                "taxas_diarias_info": {},
            }
            with patch.dict(os.environ, env, clear=False), \
                    patch.object(analise_por_data_valor, "advbox_get_all_transactions", return_value=advbox_items), \
                    patch.object(analise_por_data_valor, "asaas_get_financial_transactions_do_dia", side_effect=[
                        [asaas_items[0]], [asaas_items[1]],
                    ]), \
                    patch.object(analise_por_data_valor, "montar_relatorio", return_value=report_stub):
                self.assertEqual(analise_por_data_valor.main(), 0)

            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(report["schema_version"], 1)
        self.assertEqual([day["data"] for day in report["days"]], ["2026-09-01", "2026-09-02"])
        self.assertEqual([item["id"] for item in report["days"][0]["movements"]["asaas_faltando"]], ["receipt-1"])
        self.assertEqual([item["id"] for item in report["days"][0]["movements"]["advbox_fantasmas"]], [1])
        self.assertEqual([item["id"] for item in report["days"][1]["movements"]["asaas_faltando"]], ["receipt-2"])

    def test_launcher_rejects_missing_current_report_instead_of_using_old_analysis_json(self):
        with tempfile.TemporaryDirectory() as directory:
            missing_report = Path(directory) / "missing.json"
            with self.assertRaises(FileNotFoundError):
                criar_lancamentos.load_analysis(missing_report)

    def test_launcher_only_posts_asaas_items_missing_from_daily_movements(self):
        report = {
            "receita_faltando": [{"id": "matched"}, {"id": "missing"}],
            "taxa_bancaria_faltando": [{"id": "fee-matched"}, {"id": "fee-missing"}],
        }
        missing = [{"id": "missing"}, {"id": "fee-missing"}]

        criar_lancamentos._filter_report_to_missing_movements(report, missing)

        self.assertEqual(report["receita_faltando"], [{"id": "missing"}])
        self.assertEqual(report["taxa_bancaria_faltando"], [{"id": "fee-missing"}])

    def test_missing_customer_bank_fee_stays_manual(self):
        errors = criar_lancamentos._preflight_analysis({
            "days": [{
                "data": "2026-09-01",
                "movements": {
                    "safe_to_mutate": True,
                    "asaas_faltando": [{
                        "id": "bank-fee",
                        "type": conciliar_v2.TIPO_TAXA_BANCARIA_CLIENTE,
                    }],
                    "advbox_fantasmas": [],
                },
            }],
        })

        self.assertTrue(any("tipos sem regra de inclusão automática" in error for error in errors))

    def test_category_id_is_resolved_from_advbox_settings_not_a_constant(self):
        settings = {
            "financial": {
                "categories": [{"id": 99123, "category": "TAXA DE COMUNICACAO"}],
                "cost_centers": [{"id": 88442, "cost_center": "DESPESAS FINANCEIRAS GERAL"}],
            }
        }
        with patch.object(conciliar_v2, "advbox_get_settings", return_value=settings):
            conciliar_v2._mapa_categorias.cache_clear()
            conciliar_v2._mapa_centros_custo.cache_clear()
            self.assertEqual(conciliar_v2.resolver_categoria_id("Taxa de Comunicação"), 99123)
            self.assertEqual(
                conciliar_v2.resolver_centro_custo_id("Despesas Financeiras Geral"),
                88442,
            )
            self.assertIsNone(conciliar_v2.resolver_categoria_id("CATEGORIA INEXISTENTE"))
        conciliar_v2._mapa_categorias.cache_clear()
        conciliar_v2._mapa_centros_custo.cache_clear()

    def test_dry_run_uses_only_preflighted_phantom_ids(self):
        analysis = {
            "schema_version": 1,
            "days": [{
                "data": "2026-09-01",
                "report": {"taxas_diarias_info": {}},
                "movements": {
                    "safe_to_mutate": True,
                    "asaas_faltando": [],
                    "advbox_fantasmas": [{"id": 123}],
                },
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "analysis_report.json"
            report_path.write_text(json.dumps(analysis), encoding="utf-8")
            env = {"ADVBOX_TOKEN": "test", "ASAAS_TOKEN": "test"}
            with patch.dict(os.environ, env, clear=False), \
                    patch.object(criar_lancamentos, "ANALYSIS_FILE", report_path), \
                    patch.object(criar_lancamentos, "DRY_RUN", True), \
                    patch.object(criar_lancamentos, "aplicar_correcoes", return_value={
                        "aplicadas": [], "falhas": [], "pendentes": [],
                    }), \
                    patch.object(criar_lancamentos, "advbox_put", return_value=True) as put:
                self.assertEqual(criar_lancamentos.main(), 0)

        put.assert_called_once_with("123", {"status": "deleted"})

    def test_unsafe_plan_stops_before_any_advbox_mutation(self):
        analysis = {
            "schema_version": 1,
            "days": [{
                "data": "2026-09-01",
                "report": {"taxas_diarias_info": {}},
                "movements": {
                    "safe_to_mutate": False,
                    "unsupported_asaas_types": ["UNKNOWN"],
                    "unsupported_advbox_ids": [],
                    "daily_category_overages": [],
                    "asaas_faltando": [],
                    "advbox_fantasmas": [],
                },
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "analysis_report.json"
            report_path.write_text(json.dumps(analysis), encoding="utf-8")
            env = {"ADVBOX_TOKEN": "test", "ASAAS_TOKEN": "test"}
            with patch.dict(os.environ, env, clear=False), \
                    patch.object(criar_lancamentos, "ANALYSIS_FILE", report_path), \
                    patch.object(criar_lancamentos, "aplicar_correcoes") as apply, \
                    patch.object(criar_lancamentos, "advbox_put") as put:
                self.assertEqual(criar_lancamentos.main(), 1)

        apply.assert_not_called()
        put.assert_not_called()


if __name__ == "__main__":
    unittest.main()
