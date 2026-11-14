import math
import unittest
from pathlib import Path

from alphaforge.engine import (
    apply_scenario,
    calculate_metrics,
    compare_case,
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


if __name__ == "__main__":
    unittest.main()
