"""Lance une comparaison historique pour un persona."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from alphaforge.engine import compare_case, write_result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--persona", default="amira")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    result = compare_case(root, args.persona)
    if args.output:
        output_path = args.output if args.output.is_absolute() else root / args.output
        write_result(result, output_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
