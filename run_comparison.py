"""Lance une comparaison historique et valide le profil d'un persona."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from alphaforge.engine import EngineError, compare_case, run_analysis, write_result
from alphaforge.profile_checks import validate_profile


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
PERSONAS = ("amira", "mateo", "robert")
METRIC_LABELS = (
    ("total_return", "Total return"),
    ("annualized_volatility", "Volatility"),
    ("max_drawdown", "Max drop"),
)


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _pp(value: float) -> str:
    return f"{value * 100:+.1f} pp"


def add_profile_findings(result: dict[str, Any]) -> dict[str, Any]:
    scenario = {
        "symbol": result["scenario"]["added_symbol"],
        "target_weight_pct": result["scenario"]["target_weight_pct"],
    }
    result["profile_findings"] = validate_profile(
        result["persona"], scenario, result, DATA_DIR
    )
    return result


def format_summary(result: dict[str, Any]) -> str:
    scenario = result["scenario"]
    period = result["period"]
    lines = [
        f"{result['persona']['id']} + {scenario['added_symbol']} {scenario['target_weight_pct']:g}%"
        f" | {period['start']} → {period['end']}"
        f" | {period['common_observations']} dates | {result['currency']}",
        f"{'':<20}{'before':>10}{'after':>10}{'delta':>12}",
    ]
    for key, label in METRIC_LABELS:
        before = result["before"]["metrics"][key]
        after = result["after"]["metrics"][key]
        delta = result["delta_after_minus_before"]["metrics"][key]
        lines.append(f"{label:<20}{_pct(before):>10}{_pct(after):>10}{_pp(delta):>12}")
    for finding in result.get("profile_findings", []):
        lines.append(f"[{finding['status']}] {finding['title']}")
    return "\n".join(lines)


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--persona")
    parser.add_argument("--symbol")
    parser.add_argument("--weight", type=float)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def _run_all(as_json: bool) -> None:
    results = {}
    for persona in PERSONAS:
        result = add_profile_findings(compare_case(ROOT, persona))
        output_path = ROOT / "results" / f"{persona}_comparison.json"
        write_result(result, output_path)
        results[persona] = result
        if not as_json:
            print(format_summary(result))
            print(f"→ {output_path.relative_to(ROOT)}\n")
    if as_json:
        print(json.dumps(results, ensure_ascii=False, indent=2, allow_nan=False))


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.all:
        if args.persona or args.symbol or args.weight is not None or args.output:
            parser.error("--all ne se combine pas avec --persona, --symbol, --weight ou --output")
        _run_all(args.json)
        return

    if (args.symbol is None) != (args.weight is None):
        parser.error("Donner --symbol et --weight ensemble")

    persona = args.persona or "amira"
    try:
        if args.symbol is not None:
            result = run_analysis(persona, args.symbol, args.weight, root=ROOT)
        else:
            result = compare_case(ROOT, persona)
    except EngineError as error:
        payload = {"status": "error", "error": {"code": error.code, "message": error.message}}
        print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)

    add_profile_findings(result)

    if args.output:
        write_result(result, _resolve(args.output))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    else:
        print(format_summary(result))
        if args.output:
            print(f"→ {args.output}")


if __name__ == "__main__":
    main()
