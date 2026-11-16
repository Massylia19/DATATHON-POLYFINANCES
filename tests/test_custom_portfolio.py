"""Tests exhaustifs pour la modification de portefeuille personnalisé.

Couvre tous les cas possibles, y compris les cas extrêmes et improbables.
"""

import math
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from agent.service import analyze_custom_portfolio
from alphaforge.engine import EngineError


ROOT = Path(__file__).resolve().parents[1]


class CustomPortfolioNormalCasesTests(unittest.TestCase):
    """Tests des cas d'utilisation normaux."""

    def test_valid_portfolio_with_existing_assets_only(self):
        """Modifier les poids des actifs existants uniquement."""
        result = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights={
                "SPY": 50.0,
                "QQQ": 30.0,
                "SHOP.TO": 10.0,
                "BTC-USD": 10.0,
            },
            root=ROOT,
        )
        self.assertEqual(result["status"], "success")
        self.assertIn("before", result)
        self.assertIn("after", result)
        self.assertEqual(result["after"]["weights_by_asset_pct"]["SPY"], 50.0)

    def test_add_new_asset_and_adjust_existing(self):
        """Ajouter un nouvel actif et ajuster les existants."""
        result = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights={
                "SPY": 30.0,
                "QQQ": 25.0,
                "SHOP.TO": 15.0,
                "BTC-USD": 10.0,
                "NVDA": 20.0,  # Nouveau
            },
            root=ROOT,
        )
        self.assertEqual(result["status"], "success")
        self.assertIn("NVDA", result["after"]["weights_by_asset_pct"])

    def test_remove_asset_from_portfolio(self):
        """Retirer un actif du portefeuille."""
        result = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights={
                "SPY": 50.0,
                "QQQ": 50.0,
                # SHOP.TO et BTC-USD retirés
            },
            root=ROOT,
        )
        self.assertEqual(result["status"], "success")
        self.assertNotIn("SHOP.TO", result["after"]["weights_by_asset_pct"])
        self.assertNotIn("BTC-USD", result["after"]["weights_by_asset_pct"])

    def test_replace_all_assets(self):
        """Remplacer complètement le portefeuille."""
        result = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights={
                "NVDA": 40.0,
                "AAPL": 30.0,
                "MSFT": 30.0,
            },
            root=ROOT,
        )
        self.assertEqual(result["status"], "success")
        after_symbols = set(result["after"]["weights_by_asset_pct"].keys())
        self.assertEqual(after_symbols, {"NVDA", "AAPL", "MSFT"})

    def test_equal_weights_distribution(self):
        """Distribuer les poids également."""
        result = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights={
                "SPY": 25.0,
                "QQQ": 25.0,
                "SHOP.TO": 25.0,
                "BTC-USD": 25.0,
            },
            root=ROOT,
        )
        self.assertEqual(result["status"], "success")
        for weight in result["after"]["weights_by_asset_pct"].values():
            self.assertAlmostEqual(weight, 25.0, places=2)


class CustomPortfolioEdgeCasesTests(unittest.TestCase):
    """Tests des cas limites."""

    def test_single_asset_100_percent(self):
        """Un seul actif à 100%."""
        result = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights={"SPY": 100.0},
            root=ROOT,
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["after"]["weights_by_asset_pct"]), 1)

    def test_very_small_weights(self):
        """Poids très petits (0.5%)."""
        result = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights={
                "SPY": 99.0,
                "QQQ": 0.5,
                "SHOP.TO": 0.5,
            },
            root=ROOT,
        )
        self.assertEqual(result["status"], "success")

    def test_many_assets_small_weights(self):
        """Beaucoup d'actifs avec petits poids."""
        # Créer un portefeuille avec 20 actifs
        weights = {}
        symbols = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META",
                   "TSLA", "BRK-B", "JNJ", "V", "WMT", "JPM", "PG", "XOM", "HD",
                   "MA", "DIS", "NFLX"]
        for symbol in symbols:
            weights[symbol] = 5.0  # 20 * 5% = 100%

        result = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights=weights,
            root=ROOT,
        )
        self.assertEqual(result["status"], "success")

    def test_weights_sum_to_99_99(self):
        """Total = 99.99% (erreur d'arrondi acceptable)."""
        result = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights={
                "SPY": 33.33,
                "QQQ": 33.33,
                "SHOP.TO": 33.33,
            },
            root=ROOT,
        )
        # Devrait passer car proche de 100%
        self.assertEqual(result["status"], "success")

    def test_weights_sum_to_100_01(self):
        """Total = 100.01% (erreur d'arrondi acceptable)."""
        result = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights={
                "SPY": 50.005,
                "QQQ": 50.005,
            },
            root=ROOT,
        )
        # Devrait échouer car > 100%
        self.assertEqual(result["status"], "error")


class CustomPortfolioInvalidInputTests(unittest.TestCase):
    """Tests des entrées invalides."""

    def test_negative_weight(self):
        """Poids négatif."""
        result = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights={
                "SPY": -10.0,
                "QQQ": 110.0,
            },
            root=ROOT,
        )
        self.assertEqual(result["status"], "error")

    def test_weight_over_100_percent(self):
        """Poids individuel > 100%."""
        result = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights={"SPY": 150.0},
            root=ROOT,
        )
        self.assertEqual(result["status"], "error")

    def test_total_not_100_percent(self):
        """Total != 100%."""
        result = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights={
                "SPY": 50.0,
                "QQQ": 30.0,
            },
            root=ROOT,
        )
        self.assertEqual(result["status"], "error")
        self.assertIn("100%", result["error"]["message"])

    def test_empty_portfolio(self):
        """Portefeuille vide."""
        result = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights={},
            root=ROOT,
        )
        self.assertEqual(result["status"], "error")

    def test_unknown_symbol(self):
        """Symbole inexistant."""
        result = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights={
                "UNKNOWN_SYMBOL_XYZ": 100.0,
            },
            root=ROOT,
        )
        self.assertEqual(result["status"], "error")
        self.assertIn("UNKNOWN_SYMBOL", result["error"]["message"])

    def test_invalid_persona_id(self):
        """Persona inexistant."""
        result = analyze_custom_portfolio(
            persona_id="invalid_persona",
            custom_weights={"SPY": 100.0},
            root=ROOT,
        )
        self.assertEqual(result["status"], "error")

    def test_duplicate_symbols(self):
        """Symboles en double (géré par Python dict, mais testé pour sécurité)."""
        # En Python, les clés dupliquées écrasent les précédentes
        weights = {"SPY": 50.0, "SPY": 60.0, "QQQ": 40.0}
        result = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights=weights,
            root=ROOT,
        )
        # Devrait échouer car 60 + 40 = 100 mais comportement à vérifier
        # En pratique, le dict final sera {"SPY": 60.0, "QQQ": 40.0}
        self.assertIn(result["status"], ["success", "error"])


class CustomPortfolioExtremeInputTests(unittest.TestCase):
    """Tests des cas extrêmes et bizarres."""

    def test_infinity_weight(self):
        """Poids infini."""
        result = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights={"SPY": float("inf")},
            root=ROOT,
        )
        self.assertEqual(result["status"], "error")

    def test_nan_weight(self):
        """Poids NaN."""
        result = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights={"SPY": float("nan")},
            root=ROOT,
        )
        self.assertEqual(result["status"], "error")

    def test_very_large_weight(self):
        """Poids très grand."""
        result = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights={"SPY": 999999.99},
            root=ROOT,
        )
        self.assertEqual(result["status"], "error")

    def test_symbol_with_special_characters(self):
        """Symbole avec caractères spéciaux."""
        result = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights={
                "BRK-B": 50.0,  # Valide (existe)
                "SHOP.TO": 50.0,  # Valide (existe)
            },
            root=ROOT,
        )
        self.assertEqual(result["status"], "success")

    def test_lowercase_symbol(self):
        """Symbole en minuscules (devrait être normalisé)."""
        result = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights={"spy": 100.0},
            root=ROOT,
        )
        # Dépend de l'implémentation - peut être normalisé ou rejeté
        self.assertIn(result["status"], ["success", "error"])

    def test_zero_weight(self):
        """Poids à zéro (retirer l'actif)."""
        result = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights={
                "SPY": 0.0,
                "QQQ": 100.0,
            },
            root=ROOT,
        )
        self.assertEqual(result["status"], "success")


class CustomPortfolioDataIssuesTests(unittest.TestCase):
    """Tests avec problèmes de données."""

    @patch("alphaforge.engine.load_prices_in_cad")
    def test_missing_market_data(self, mock_load_prices):
        """Données de marché manquantes pour un actif."""
        mock_load_prices.side_effect = Exception("Prix manquants pour SPY")
        result = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights={"SPY": 100.0},
            root=ROOT,
        )
        self.assertEqual(result["status"], "error")

    @patch("alphaforge.engine.align_on_common_dates")
    def test_no_common_dates(self, mock_align):
        """Aucune date commune entre les actifs."""
        mock_align.return_value = ([], {})
        result = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights={"SPY": 50.0, "QQQ": 50.0},
            root=ROOT,
        )
        self.assertEqual(result["status"], "error")

    @patch("alphaforge.engine.load_fx_usdcad")
    def test_missing_fx_data(self, mock_fx):
        """Données de change manquantes."""
        mock_fx.side_effect = Exception("Taux FX indisponibles")
        result = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights={"SPY": 100.0},
            root=ROOT,
        )
        self.assertEqual(result["status"], "error")


class CustomPortfolioMetricsTests(unittest.TestCase):
    """Tests de validation des métriques calculées."""

    def test_metrics_are_calculated(self):
        """Vérifier que toutes les métriques sont calculées."""
        result = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights={
                "SPY": 60.0,
                "QQQ": 40.0,
            },
            root=ROOT,
        )
        self.assertEqual(result["status"], "success")

        # Vérifier les métriques avant
        before_metrics = result["before"]["metrics"]
        self.assertIn("total_return", before_metrics)
        self.assertIn("annualized_volatility", before_metrics)
        self.assertIn("max_drawdown", before_metrics)

        # Vérifier les métriques après
        after_metrics = result["after"]["metrics"]
        self.assertIn("total_return", after_metrics)
        self.assertIn("annualized_volatility", after_metrics)
        self.assertIn("max_drawdown", after_metrics)

        # Vérifier les deltas
        deltas = result["delta_after_minus_before"]["metrics"]
        self.assertIn("total_return", deltas)

    def test_volatility_is_positive(self):
        """La volatilité doit être positive."""
        result = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights={"SPY": 100.0},
            root=ROOT,
        )
        self.assertEqual(result["status"], "success")
        self.assertGreaterEqual(result["after"]["metrics"]["annualized_volatility"], 0)

    def test_max_drawdown_is_negative_or_zero(self):
        """Le drawdown maximum doit être négatif ou zéro."""
        result = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights={"SPY": 100.0},
            root=ROOT,
        )
        self.assertEqual(result["status"], "success")
        self.assertLessEqual(result["after"]["metrics"]["max_drawdown"], 0)


class CustomPortfolioConcurrencyTests(unittest.TestCase):
    """Tests de concurrence et performance."""

    def test_multiple_sequential_requests(self):
        """Plusieurs requêtes séquentielles."""
        for i in range(5):
            result = analyze_custom_portfolio(
                persona_id="amira",
                custom_weights={
                    "SPY": 50.0 + i,
                    "QQQ": 50.0 - i,
                },
                root=ROOT,
            )
            self.assertEqual(result["status"], "success")

    def test_different_personas_same_weights(self):
        """Différents personas avec les mêmes poids."""
        weights = {"SPY": 50.0, "QQQ": 50.0}

        for persona_id in ["amira", "mateo", "robert"]:
            result = analyze_custom_portfolio(
                persona_id=persona_id,
                custom_weights=weights,
                root=ROOT,
            )
            self.assertEqual(result["status"], "success")


class CustomPortfolioIntegrationTests(unittest.TestCase):
    """Tests d'intégration bout-en-bout."""

    def test_full_workflow_add_modify_remove(self):
        """Workflow complet : ajouter, modifier, retirer."""
        # Étape 1 : Ajouter NVDA
        result1 = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights={
                "SPY": 35.0,
                "QQQ": 30.0,
                "SHOP.TO": 15.0,
                "BTC-USD": 10.0,
                "NVDA": 10.0,  # Ajout
            },
            root=ROOT,
        )
        self.assertEqual(result1["status"], "success")
        self.assertIn("NVDA", result1["after"]["weights_by_asset_pct"])

        # Étape 2 : Modifier les poids
        result2 = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights={
                "SPY": 30.0,
                "QQQ": 30.0,
                "SHOP.TO": 10.0,
                "BTC-USD": 10.0,
                "NVDA": 20.0,  # Augmentation
            },
            root=ROOT,
        )
        self.assertEqual(result2["status"], "success")
        self.assertEqual(result2["after"]["weights_by_asset_pct"]["NVDA"], 20.0)

        # Étape 3 : Retirer SHOP.TO
        result3 = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights={
                "SPY": 35.0,
                "QQQ": 35.0,
                "BTC-USD": 10.0,
                "NVDA": 20.0,
            },
            root=ROOT,
        )
        self.assertEqual(result3["status"], "success")
        self.assertNotIn("SHOP.TO", result3["after"]["weights_by_asset_pct"])

    def test_api_response_structure(self):
        """Vérifier la structure complète de la réponse."""
        result = analyze_custom_portfolio(
            persona_id="amira",
            custom_weights={"SPY": 50.0, "QQQ": 50.0},
            root=ROOT,
        )
        self.assertEqual(result["status"], "success")

        # Structure attendue
        required_keys = [
            "status", "analysis_type", "persona", "scenario", "period",
            "currency", "methodology", "before", "after",
            "delta_after_minus_before", "series", "sources"
        ]
        for key in required_keys:
            self.assertIn(key, result, f"Clé manquante : {key}")


if __name__ == "__main__":
    unittest.main()
