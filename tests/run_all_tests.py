"""Script pour exécuter tous les tests et générer un rapport détaillé.

Usage:
    python tests/run_all_tests.py
    python tests/run_all_tests.py --verbose
    python tests/run_all_tests.py --report report.html
"""

import sys
import unittest
import argparse
from pathlib import Path
from datetime import datetime
import json


# Ajouter le répertoire parent au path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def discover_and_run_tests(verbose=False, pattern="test_*.py"):
    """Découvrir et exécuter tous les tests."""
    loader = unittest.TestLoader()
    start_dir = Path(__file__).parent
    suite = loader.discover(start_dir, pattern=pattern)

    verbosity = 2 if verbose else 1
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)

    return result


def generate_report(result, output_file=None):
    """Générer un rapport détaillé des tests."""
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_tests": result.testsRun,
        "successes": result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "success_rate": (result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100 if result.testsRun > 0 else 0,
        "failures_details": [
            {
                "test": str(test),
                "traceback": traceback
            }
            for test, traceback in result.failures
        ],
        "errors_details": [
            {
                "test": str(test),
                "traceback": traceback
            }
            for test, traceback in result.errors
        ]
    }

    # Afficher le résumé
    print("\n" + "=" * 70)
    print("RÉSUMÉ DES TESTS")
    print("=" * 70)
    print(f"Date: {report['timestamp']}")
    print(f"Total de tests exécutés: {report['total_tests']}")
    print(f"✅ Succès: {report['successes']}")
    print(f"❌ Échecs: {report['failures']}")
    print(f"⚠️  Erreurs: {report['errors']}")
    print(f"⏭️  Ignorés: {report['skipped']}")
    print(f"📊 Taux de réussite: {report['success_rate']:.2f}%")
    print("=" * 70)

    if report['failures'] > 0:
        print("\n❌ ÉCHECS:")
        for failure in report['failures_details']:
            print(f"\n  Test: {failure['test']}")
            print(f"  {failure['traceback'][:200]}...")

    if report['errors'] > 0:
        print("\n⚠️  ERREURS:")
        for error in report['errors_details']:
            print(f"\n  Test: {error['test']}")
            print(f"  {error['traceback'][:200]}...")

    # Sauvegarder le rapport JSON
    if output_file:
        output_path = Path(output_file)
        if output_path.suffix == ".json":
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"\n📄 Rapport JSON sauvegardé: {output_path}")
        elif output_path.suffix == ".html":
            generate_html_report(report, output_path)
            print(f"\n📄 Rapport HTML sauvegardé: {output_path}")

    return report


def generate_html_report(report, output_path):
    """Générer un rapport HTML."""
    html = f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rapport de Tests - AlphaForge</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .stat-value {{
            font-size: 32px;
            font-weight: bold;
            margin: 10px 0;
        }}
        .success {{ color: #10b981; }}
        .failure {{ color: #ef4444; }}
        .error {{ color: #f59e0b; }}
        .skipped {{ color: #6b7280; }}
        .details {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-top: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .test-item {{
            border-left: 4px solid #ef4444;
            padding: 10px;
            margin: 10px 0;
            background: #fef2f2;
        }}
        pre {{
            background: #1f2937;
            color: #f3f4f6;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Rapport de Tests AlphaForge</h1>
        <p>Généré le {report['timestamp']}</p>
    </div>

    <div class="stats">
        <div class="stat-card">
            <div>Total de tests</div>
            <div class="stat-value">{report['total_tests']}</div>
        </div>
        <div class="stat-card">
            <div>Succès</div>
            <div class="stat-value success">✅ {report['successes']}</div>
        </div>
        <div class="stat-card">
            <div>Échecs</div>
            <div class="stat-value failure">❌ {report['failures']}</div>
        </div>
        <div class="stat-card">
            <div>Erreurs</div>
            <div class="stat-value error">⚠️ {report['errors']}</div>
        </div>
        <div class="stat-card">
            <div>Taux de réussite</div>
            <div class="stat-value">{report['success_rate']:.1f}%</div>
        </div>
    </div>
"""

    if report['failures_details']:
        html += """
    <div class="details">
        <h2>❌ Échecs détaillés</h2>
"""
        for failure in report['failures_details']:
            html += f"""
        <div class="test-item">
            <strong>{failure['test']}</strong>
            <pre>{failure['traceback']}</pre>
        </div>
"""
        html += "    </div>"

    if report['errors_details']:
        html += """
    <div class="details">
        <h2>⚠️ Erreurs détaillées</h2>
"""
        for error in report['errors_details']:
            html += f"""
        <div class="test-item">
            <strong>{error['test']}</strong>
            <pre>{error['traceback']}</pre>
        </div>
"""
        html += "    </div>"

    html += """
</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    parser = argparse.ArgumentParser(description="Exécuter tous les tests AlphaForge")
    parser.add_argument("-v", "--verbose", action="store_true", help="Mode verbeux")
    parser.add_argument("-p", "--pattern", default="test_*.py", help="Pattern de fichiers de test")
    parser.add_argument("-r", "--report", help="Fichier de rapport (.json ou .html)")
    parser.add_argument("--custom-only", action="store_true", help="Exécuter seulement les tests du portefeuille personnalisé")
    parser.add_argument("--explanation-only", action="store_true", help="Exécuter seulement les tests d'explication")

    args = parser.parse_args()

    # Choisir le pattern selon les arguments
    if args.custom_only:
        pattern = "test_custom_portfolio.py"
    elif args.explanation_only:
        pattern = "test_explanation_robustness.py"
    else:
        pattern = args.pattern

    print("=" * 70)
    print("EXÉCUTION DES TESTS ALPHAFORGE")
    print("=" * 70)
    print(f"Pattern: {pattern}")
    print(f"Mode verbeux: {args.verbose}")
    print("=" * 70 + "\n")

    result = discover_and_run_tests(args.verbose, pattern)
    report = generate_report(result, args.report)

    # Code de sortie
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
