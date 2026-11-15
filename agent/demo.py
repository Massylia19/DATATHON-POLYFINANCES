"""Commande de démonstration du service AlphaForge Bedrock."""

from __future__ import annotations

import argparse
import json
from typing import Any

from agent.service import analyze_request


def _print_result(result: dict[str, Any]) -> None:
    print(f"Statut global : {result['status']}")
    analysis = result.get("analysis")
    if analysis:
        period = analysis["period"]
        print(
            "Période : "
            f"{period['start']} au {period['end']} "
            f"({period['common_observations']} observations, {analysis['currency']})"
        )
        for label, section in (("Avant", "before"), ("Après", "after")):
            metrics = analysis[section]["metrics"]
            print(
                f"{label} : rendement={metrics['total_return']:.2%}, "
                f"volatilité={metrics['annualized_volatility']:.2%}, "
                f"baisse maximale={metrics['max_drawdown']:.2%}"
            )

    checks = result.get("checks") or []
    print("Contrôles :")
    for check in checks:
        print(f"- {check['id']} : {check['status']} — {check['message']}")

    explanation = result.get("explanation")
    if explanation:
        print("Explication :")
        print(explanation["summary"])
        trace = explanation.get("tool_trace", result.get("tool_trace", []))
    else:
        print("Explication : indisponible")
        trace = result.get("tool_trace", [])

    warnings = result.get("warnings", [])
    if warnings:
        print("Avertissements et diagnostics :")
        for warning in warnings:
            print(f"- {warning}")
    if result.get("error"):
        print("Erreur : " + json.dumps(result["error"], ensure_ascii=False))

    print("Traces factuelles des outils :")
    for entry in trace:
        print(
            f"- {entry['tool']} : {entry['status']} "
            f"({entry.get('execution_origin', 'non précisé')})"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--persona", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--weight", required=True, type=float)
    args = parser.parse_args()

    result = analyze_request(args.persona, args.symbol, args.weight)
    _print_result(result)
    return {"success": 0, "partial": 2, "error": 1}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
