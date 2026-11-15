import csv
import json
import math
import tempfile
import unittest
from datetime import date
from pathlib import Path

from alphaforge.engine import (
    PROJECT_ROOT,
    EngineError,
    align_on_common_dates,
    calculate_metrics,
    compare_case,
    load_case,
    load_persona_and_portfolio,
    load_prices_in_cad,
    run_analysis,
    write_result,
)


SCENARIOS = [
    ("amira", "NVDA", 10),
    ("mateo", "XOM", 10),
    ("robert", "TSLA", 5),
]

INITIAL_WEIGHTS = {
    "amira": {"SPY": 40, "QQQ": 30, "SHOP.TO": 15, "BTC-USD": 15},
    "mateo": {"ESGV": 40, "XBB.TO": 30, "FTS.TO": 15, "GLD": 15},
    "robert": {"ZST.TO": 40, "XBB.TO": 30, "GLD": 15, "XIU.TO": 15},
}

CONTRACT_SECTIONS = {
    "analysis_type",
    "persona",
    "scenario",
    "period",
    "currency",
    "before",
    "after",
    "delta_after_minus_before",
    "series",
    "methodology",
    "sources",
    "limitations",
}

SOURCE_IDS = {
    "src_assets_universe",
    "src_prices_daily",
    "src_fx_usdcad",
    "src_personas",
    "src_portfolios",
}

METRICS = {"total_return", "annualized_volatility", "max_drawdown"}


class ScenarioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = {
            persona: run_analysis(persona, symbol, weight)
            for persona, symbol, weight in SCENARIOS
        }

    def test_structure_matches_contract(self):
        for persona, _, _ in SCENARIOS:
            with self.subTest(persona=persona):
                result = self.results[persona]
                self.assertEqual(set(result), CONTRACT_SECTIONS)
                self.assertEqual(result["analysis_type"], "hypothetical_historical_comparison")
                self.assertEqual(result["currency"], "CAD")
                self.assertEqual(set(result["before"]["metrics"]), METRICS)
                self.assertEqual(set(result["after"]["metrics"]), METRICS)

    def test_added_asset_has_target_weight(self):
        for persona, symbol, weight in SCENARIOS:
            with self.subTest(persona=persona):
                result = self.results[persona]
                self.assertEqual(result["scenario"]["added_symbol"], symbol)
                self.assertEqual(result["scenario"]["target_weight_pct"], weight)
                self.assertEqual(result["scenario"]["funding_rule"], "proportional_reduction")
                self.assertEqual(result["after"]["weights_by_asset_pct"][symbol], weight)
                self.assertNotIn(symbol, result["before"]["weights_by_asset_pct"])

    def test_existing_weights_are_scaled_proportionally(self):
        for persona, _, weight in SCENARIOS:
            with self.subTest(persona=persona):
                after = self.results[persona]["after"]["weights_by_asset_pct"]
                scale = 1 - weight / 100
                for symbol, initial in INITIAL_WEIGHTS[persona].items():
                    self.assertAlmostEqual(after[symbol], initial * scale)

    def test_robert_weights_by_hand(self):
        after = self.results["robert"]["after"]["weights_by_asset_pct"]
        self.assertAlmostEqual(after["ZST.TO"], 38)
        self.assertAlmostEqual(after["XBB.TO"], 28.5)
        self.assertAlmostEqual(after["GLD"], 14.25)
        self.assertAlmostEqual(after["XIU.TO"], 14.25)
        self.assertAlmostEqual(after["TSLA"], 5)

    def test_weights_total_100(self):
        for persona, _, _ in SCENARIOS:
            with self.subTest(persona=persona):
                result = self.results[persona]
                for side in ("before", "after"):
                    self.assertAlmostEqual(sum(result[side]["weights_by_asset_pct"].values()), 100)
                    self.assertAlmostEqual(sum(result[side]["weights_by_class_pct"].values()), 100)

    def test_deltas_are_after_minus_before(self):
        for persona, _, _ in SCENARIOS:
            with self.subTest(persona=persona):
                result = self.results[persona]
                delta = result["delta_after_minus_before"]
                for metric in METRICS:
                    expected = result["after"]["metrics"][metric] - result["before"]["metrics"][metric]
                    self.assertAlmostEqual(delta["metrics"][metric], expected, places=9)
                before = result["before"]["weights_by_asset_pct"]
                after = result["after"]["weights_by_asset_pct"]
                for symbol, value in delta["weights_by_asset_pct"].items():
                    self.assertAlmostEqual(value, after.get(symbol, 0) - before.get(symbol, 0), places=9)

    def test_series_are_consistent(self):
        for persona, _, _ in SCENARIOS:
            with self.subTest(persona=persona):
                result = self.results[persona]
                series = result["series"]
                count = result["period"]["common_observations"]
                self.assertEqual(len(series["dates"]), count)
                self.assertEqual(len(series["before"]), count)
                self.assertEqual(len(series["after"]), count)
                self.assertEqual(series["before"][0], 100.0)
                self.assertEqual(series["after"][0], 100.0)
                self.assertEqual(series["dates"][0], result["period"]["start"])
                self.assertEqual(series["dates"][-1], result["period"]["end"])
                self.assertEqual(series["dates"], sorted(series["dates"]))
                self.assertEqual(len(set(series["dates"])), count)

    def test_series_match_total_return(self):
        for persona, _, _ in SCENARIOS:
            with self.subTest(persona=persona):
                result = self.results[persona]
                for side in ("before", "after"):
                    implied = result["series"][side][-1] / 100 - 1
                    self.assertAlmostEqual(implied, result[side]["metrics"]["total_return"], places=9)

    def test_full_persona_is_returned(self):
        for persona, _, _ in SCENARIOS:
            with self.subTest(persona=persona):
                profile = self.results[persona]["persona"]
                self.assertEqual(profile["id"], persona)
                for key in ("name", "risk_level", "objective", "preferences", "horizon_years_min", "horizon_years_max"):
                    self.assertIn(key, profile)
                self.assertEqual(
                    set(profile["missing_information"]),
                    {"loss_absorption_capacity", "liquidity_needs", "planned_withdrawals"},
                )
        self.assertIsNone(self.results["amira"]["persona"]["horizon_years_max"])
        self.assertEqual(self.results["robert"]["persona"]["horizon_years_min"], 3)
        self.assertEqual(self.results["robert"]["persona"]["horizon_years_max"], 5)

    def test_sources_have_stable_ids(self):
        for persona, _, _ in SCENARIOS:
            with self.subTest(persona=persona):
                ids = [source["id"] for source in self.results[persona]["sources"]]
                self.assertEqual(set(ids), SOURCE_IDS)
                self.assertEqual(len(ids), len(set(ids)))

    def test_methodology_and_limitations_mention_costs(self):
        for persona, _, _ in SCENARIOS:
            with self.subTest(persona=persona):
                result = self.results[persona]
                for key in ("funding", "series_base", "annualization_note", "max_drawdown", "weights_shown", "costs"):
                    self.assertIn(key, result["methodology"])
                self.assertTrue(any("Frais" in item for item in result["limitations"]))

    def test_result_is_valid_json_without_nan(self):
        for persona, _, _ in SCENARIOS:
            with self.subTest(persona=persona):
                json.dumps(self.results[persona], allow_nan=False)


class ConsistencyTests(unittest.TestCase):
    def test_run_analysis_matches_compare_case(self):
        for persona, symbol, weight in SCENARIOS:
            with self.subTest(persona=persona):
                self.assertEqual(
                    run_analysis(persona, symbol, weight),
                    compare_case(PROJECT_ROOT, persona),
                )

    def test_symbol_is_stripped_and_uppercased(self):
        result = run_analysis("amira", "  nvda ", 10)
        self.assertEqual(result["scenario"]["added_symbol"], "NVDA")
        self.assertEqual(result["scenario"]["scenario_id"], "amira_add_nvda")
        self.assertIn("NVDA", result["after"]["weights_by_asset_pct"])


class ErrorCodeTests(unittest.TestCase):
    def assert_code(self, code, persona_id, symbol, weight):
        with self.assertRaises(EngineError) as context:
            run_analysis(persona_id, symbol, weight)
        self.assertEqual(context.exception.code, code)
        self.assertTrue(context.exception.message)

    def test_engine_error_is_a_value_error(self):
        self.assertTrue(issubclass(EngineError, ValueError))

    def test_invalid_persona(self):
        for persona_id in ("bob", "", None, 7):
            with self.subTest(persona_id=persona_id):
                self.assert_code("INVALID_PERSONA", persona_id, "NVDA", 10)

    def test_invalid_persona_in_saved_scenario(self):
        for persona_id in ("bob", ""):
            with self.subTest(persona_id=persona_id):
                with self.assertRaises(EngineError) as context:
                    compare_case(PROJECT_ROOT, persona_id)
                self.assertEqual(context.exception.code, "INVALID_PERSONA")

    def test_missing_portfolio_or_scenario_stays_value_error(self):
        persona = {"personas": [{"id": "zoe"}]}
        cases = {
            "portfolio": ({"portfolios": []}, {"scenarios": [{"persona_id": "zoe"}]}),
            "scenario": ({"portfolios": [{"persona_id": "zoe"}]}, {"scenarios": []}),
        }
        for missing, (portfolios, scenarios) in cases.items():
            with self.subTest(missing=missing):
                directory = tempfile.TemporaryDirectory()
                self.addCleanup(directory.cleanup)
                data_dir = Path(directory.name)
                for name, content in (
                    ("personas.json", persona),
                    ("portfolios.json", portfolios),
                    ("scenarios.json", scenarios),
                ):
                    (data_dir / name).write_text(json.dumps(content), encoding="utf-8")
                with self.assertRaises(ValueError) as context:
                    load_case(data_dir, "zoe")
                self.assertNotIsInstance(context.exception, EngineError)

    def test_duplicate_persona_stays_value_error(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        data_dir = Path(directory.name)
        for name, content in (
            ("personas.json", {"personas": [{"id": "zoe"}, {"id": "zoe"}]}),
            ("portfolios.json", {"portfolios": [{"persona_id": "zoe"}]}),
            ("scenarios.json", {"scenarios": [{"persona_id": "zoe"}]}),
        ):
            (data_dir / name).write_text(json.dumps(content), encoding="utf-8")
        for loader in (load_persona_and_portfolio, load_case):
            with self.subTest(loader=loader.__name__):
                with self.assertRaises(ValueError) as context:
                    loader(data_dir, "zoe")
                self.assertNotIsInstance(context.exception, EngineError)

    def test_unknown_symbol(self):
        for symbol in ("APPLE", "", "   ", None, 123):
            with self.subTest(symbol=symbol):
                self.assert_code("UNKNOWN_SYMBOL", "amira", symbol, 10)

    def test_invalid_weight(self):
        for weight in (0, 100, -5, 150, "10", True, False, None, math.nan, math.inf, -math.inf):
            with self.subTest(weight=weight):
                self.assert_code("INVALID_WEIGHT", "amira", "NVDA", weight)

    def test_valid_decimal_weight_is_accepted(self):
        result = run_analysis("mateo", "XOM", 7.5)
        self.assertEqual(result["after"]["weights_by_asset_pct"]["XOM"], 7.5)

    def test_asset_already_held(self):
        for symbol in ("SPY", " spy ", "BTC-USD"):
            with self.subTest(symbol=symbol):
                self.assert_code("ASSET_ALREADY_HELD", "amira", symbol, 10)

    def test_insufficient_data(self):
        series = {
            "A": {date(2022, 1, 3): 1.0, date(2022, 1, 4): 1.0},
            "B": {date(2022, 1, 5): 1.0, date(2022, 1, 6): 1.0},
        }
        with self.assertRaises(EngineError) as context:
            align_on_common_dates(series)
        self.assertEqual(context.exception.code, "INSUFFICIENT_DATA")

    def test_single_common_date_is_insufficient(self):
        series = {
            "A": {date(2022, 1, 3): 1.0, date(2022, 1, 4): 1.0},
            "B": {date(2022, 1, 4): 1.0, date(2022, 1, 5): 1.0},
        }
        with self.assertRaises(EngineError) as context:
            align_on_common_dates(series)
        self.assertEqual(context.exception.code, "INSUFFICIENT_DATA")


class HandCalculatedTests(unittest.TestCase):
    ASSETS = {
        "USDX": {"ticker": "USDX", "currency": "USD", "asset_class": "equity"},
        "CADX": {"ticker": "CADX", "currency": "CAD", "asset_class": "equity"},
    }
    FX_DATES = [date(2022, 1, 3), date(2022, 1, 5)]
    FX_RATES = [1.25, 1.30]

    def write_prices(self, rows):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "prices.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["date", "ticker", "adj_close", "currency"])
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_fx_uses_same_day_rate(self):
        path = self.write_prices([
            {"date": "2022-01-03", "ticker": "USDX", "adj_close": "10", "currency": "USD"},
            {"date": "2022-01-05", "ticker": "USDX", "adj_close": "10", "currency": "USD"},
        ])
        prices = load_prices_in_cad(path, ["USDX"], self.ASSETS, self.FX_DATES, self.FX_RATES)
        self.assertAlmostEqual(prices["USDX"][date(2022, 1, 3)], 12.5)
        self.assertAlmostEqual(prices["USDX"][date(2022, 1, 5)], 13.0)

    def test_fx_uses_previous_rate_never_future(self):
        path = self.write_prices([
            {"date": "2022-01-04", "ticker": "USDX", "adj_close": "10", "currency": "USD"},
        ])
        prices = load_prices_in_cad(path, ["USDX"], self.ASSETS, self.FX_DATES, self.FX_RATES)
        self.assertAlmostEqual(prices["USDX"][date(2022, 1, 4)], 12.5)
        self.assertNotAlmostEqual(prices["USDX"][date(2022, 1, 4)], 13.0)

    def test_fx_missing_before_first_rate_raises(self):
        path = self.write_prices([
            {"date": "2022-01-02", "ticker": "USDX", "adj_close": "10", "currency": "USD"},
        ])
        with self.assertRaises(ValueError):
            load_prices_in_cad(path, ["USDX"], self.ASSETS, self.FX_DATES, self.FX_RATES)

    def test_cad_prices_are_not_converted(self):
        path = self.write_prices([
            {"date": "2022-01-04", "ticker": "CADX", "adj_close": "10", "currency": "CAD"},
        ])
        prices = load_prices_in_cad(path, ["CADX"], self.ASSETS, self.FX_DATES, self.FX_RATES)
        self.assertEqual(prices["CADX"][date(2022, 1, 4)], 10.0)

    def test_metrics_by_hand(self):
        metrics = calculate_metrics([100, 110, 99])
        self.assertAlmostEqual(metrics["total_return"], -0.01)
        self.assertAlmostEqual(metrics["max_drawdown"], -0.10)
        self.assertAlmostEqual(metrics["annualized_volatility"], math.sqrt(0.02) * math.sqrt(252))

    def test_alignment_keeps_only_common_dates(self):
        series = {
            "A": {date(2022, 1, 3): 1.0, date(2022, 1, 4): 2.0, date(2022, 1, 5): 3.0},
            "B": {date(2022, 1, 4): 20.0, date(2022, 1, 5): 30.0, date(2022, 1, 6): 40.0},
        }
        dates, prices = align_on_common_dates(series)
        self.assertEqual(dates, [date(2022, 1, 4), date(2022, 1, 5)])
        self.assertEqual(prices, {"A": [2.0, 3.0], "B": [20.0, 30.0]})


class WriteResultTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)

    def test_result_round_trips(self):
        result = run_analysis("robert", "TSLA", 5)
        path = self.directory / "robert.json"
        write_result(result, path)
        with path.open(encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), result)

    def test_nan_is_refused_and_no_file_written(self):
        path = self.directory / "nan.json"
        with self.assertRaises(ValueError):
            write_result({"value": math.nan}, path)
        self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
