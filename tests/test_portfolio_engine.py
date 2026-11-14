import math
import unittest
from pathlib import Path

from alphaforge.engine import (
    EngineError,
    apply_scenario,
    calculate_metrics,
    compare_case,
    run_analysis,
    simulate_buy_and_hold,
)


ROOT = Path(__file__).resolve().parents[1]


class ApplyScenarioTests(unittest.TestCase):
    def test_amira_weights_are_scaled_and_total_100(self):
        portfolio = {
            "persona_id": "amira",
            "positions": [
                {"symbol": "SPY", "weight_pct": 40},
                {"symbol": "QQQ", "weight_pct": 30},
                {"symbol": "SHOP.TO", "weight_pct": 15},
                {"symbol": "BTC-USD", "weight_pct": 15},
            ],
        }
        scenario = {
            "persona_id": "amira",
            "scenario_id": "amira_add_nvda",
            "symbol": "NVDA",
            "target_weight_pct": 10,
        }

        result = apply_scenario(portfolio, scenario)
        weights = {item["symbol"]: item["weight_pct"] for item in result["positions"]}

        self.assertEqual(weights["SPY"], 36)
        self.assertEqual(weights["QQQ"], 27)
        self.assertEqual(weights["SHOP.TO"], 13.5)
        self.assertEqual(weights["BTC-USD"], 13.5)
        self.assertEqual(weights["NVDA"], 10)
        self.assertTrue(math.isclose(sum(weights.values()), 100.0))

    def test_existing_symbol_is_rejected(self):
        portfolio = {
            "persona_id": "amira",
            "positions": [{"symbol": "SPY", "weight_pct": 100}],
        }
        scenario = {
            "persona_id": "amira",
            "symbol": "SPY",
            "target_weight_pct": 10,
        }
        with self.assertRaises(ValueError):
            apply_scenario(portfolio, scenario)


class SimulationTests(unittest.TestCase):
    def test_buy_and_hold_uses_fixed_shares(self):
        values = simulate_buy_and_hold(
            {"A": 50, "B": 50},
            {"A": [10, 20, 10], "B": [20, 20, 10]},
        )
        self.assertEqual(values, [1.0, 1.5, 0.75])
        metrics = calculate_metrics(values)
        self.assertAlmostEqual(metrics["total_return"], -0.25)
        self.assertAlmostEqual(metrics["max_drawdown"], -0.5)


class IntegrationTests(unittest.TestCase):
    def test_amira_comparison_is_complete(self):
        result = compare_case(ROOT, "amira")
        self.assertEqual(result["currency"], "CAD")
        self.assertEqual(result["scenario"]["added_symbol"], "NVDA")
        self.assertEqual(result["after"]["weights_by_asset_pct"]["NVDA"], 10)
        self.assertEqual(result["period"]["start"], "2021-11-12")
        self.assertEqual(result["period"]["end"], "2026-11-12")
        self.assertGreater(result["period"]["common_observations"], 1000)
        self.assertEqual(
            set(result["before"]["metrics"]),
            {"total_return", "annualized_volatility", "max_drawdown"},
        )

    def test_three_documented_scenarios_and_series_contract(self):
        cases = (
            ("amira", "NVDA", 10),
            ("mateo", "XOM", 10),
            ("robert", "TSLA", 5),
        )
        for persona_id, symbol, weight in cases:
            with self.subTest(persona_id=persona_id):
                result = run_analysis(persona_id, symbol, weight, root=ROOT)
                self.assertEqual(result["scenario"]["added_symbol"], symbol)
                self.assertEqual(result["scenario"]["target_weight_pct"], weight)
                self.assertAlmostEqual(
                    sum(result["before"]["weights_by_asset_pct"].values()), 100.0
                )
                self.assertAlmostEqual(
                    sum(result["after"]["weights_by_asset_pct"].values()), 100.0
                )
                series = result["series"]
                self.assertEqual(series["before"][0], 100.0)
                self.assertEqual(series["after"][0], 100.0)
                self.assertEqual(len(series["dates"]), len(series["before"]))
                self.assertEqual(len(series["dates"]), len(series["after"]))
                self.assertEqual(
                    len(series["dates"]), result["period"]["common_observations"]
                )

    def test_custom_amira_weights_are_used(self):
        for weight in (5, 20):
            with self.subTest(weight=weight):
                result = run_analysis("amira", "NVDA", weight, root=ROOT)
                self.assertEqual(
                    result["after"]["weights_by_asset_pct"]["NVDA"], weight
                )
                self.assertAlmostEqual(
                    sum(result["after"]["weights_by_asset_pct"].values()), 100.0
                )

    def test_invalid_inputs_are_rejected_with_codes(self):
        cases = (
            (("unknown", "NVDA", 10), "INVALID_PERSONA"),
            (("amira", "NOT-A-SYMBOL", 10), "UNKNOWN_SYMBOL"),
            (("amira", "NVDA", 0), "INVALID_WEIGHT"),
            (("amira", "NVDA", 100), "INVALID_WEIGHT"),
            (("amira", "NVDA", float("nan")), "INVALID_WEIGHT"),
            (("amira", "SPY", 10), "ASSET_ALREADY_HELD"),
        )
        for arguments, expected_code in cases:
            with self.subTest(arguments=arguments):
                with self.assertRaises(EngineError) as caught:
                    run_analysis(*arguments, root=ROOT)
                self.assertEqual(caught.exception.code, expected_code)


if __name__ == "__main__":
    unittest.main()
