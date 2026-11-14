
"""Lance une comparaison historique et valide le profil d'un persona."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from alphaforge.engine import compare_case, write_result, load_case
from alphaforge.profile_checks import validate_profile


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--persona", default="amira")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    data_dir = root / "data"

    # 1. Comparaison historique
    result = compare_case(root, args.persona)

    # 2. Chargement du profil et du scénario
    profile, portfolio, scenario = load_case(data_dir, args.persona)

    # 3. Validation du profil
    findings = validate_profile(
        profile,
        scenario,
        result,
        data_dir
    )

    # 4. Ajout des constats au résultat
    result["profile_findings"] = findings

    # 5. Sauvegarde facultative
    if args.output:
        output_path = (
            args.output
            if args.output.is_absolute()
            else root / args.output
        )
        write_result(result, output_path)

    # 6. Affichage du résultat complet
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
