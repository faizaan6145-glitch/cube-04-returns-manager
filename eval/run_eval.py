"""Run the real Returns Manager pipeline over eval/manifest.csv and score it
against eval/labels_A.csv (ground truth) and eval/labels_B.csv (second human,
used only to measure inter-rater agreement). See eval/README.md for setup.

Usage:
    python eval/run_eval.py

Writes eval/results.csv (raw agent output per unit) and eval/EVAL_SUMMARY.md
(the report table), and prints the same summary to the terminal.

This calls the real Gemini API once per unit (one batched call each, per
RULES.md Engineering Rule 2) -- it costs a little quota and takes a while for
50 units. It will not silently skip a unit that errors: a failed call still
produces a pending_review row, same as production (fail open).
"""
from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.catalog import load_catalog  # noqa: E402
from app.config import load_settings  # noqa: E402
from app.pipeline import process_return  # noqa: E402
from eval.metrics import (  # noqa: E402
    cohens_kappa,
    confusion_counts,
    confusion_matrix,
    exact_match_accuracy,
    latency_stats,
    uncertain_rate,
)

EVAL_DIR = ROOT / "eval"
FIXTURES_DIR = EVAL_DIR / "fixtures"

RESULT_FIELDS = [
    "unit_id", "record_id", "status",
    "identity_verdict", "identity_confidence", "identity_latency_ms",
    "completeness_verdict", "completeness_confidence",
    "condition_verdict", "condition_confidence", "condition_grade",
    "disposition",
]


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def run_agent_on_manifest() -> list[dict]:
    manifest = read_csv(EVAL_DIR / "manifest.csv")
    if not manifest:
        print(f"No rows in {EVAL_DIR / 'manifest.csv'}. Copy manifest_template.csv "
              "and add your eval units first. See eval/README.md.")
        return []

    settings = load_settings()
    catalog = load_catalog(settings.catalog_path)
    results = []

    for i, row in enumerate(manifest, 1):
        unit_dir = FIXTURES_DIR / row["unit_id"]
        filenames = [f for f in row["image_files"].split(";") if f]
        image_bytes = []
        for fname in filenames:
            fpath = unit_dir / fname
            if fpath.exists():
                image_bytes.append(fpath.read_bytes())
            else:
                print(f"  ! missing image {fpath}, skipping it")

        print(f"[{i}/{len(manifest)}] {row['unit_id']} ({len(image_bytes)} images)...", end=" ", flush=True)
        start = time.monotonic()
        record = process_return(
            settings=settings,
            catalog=catalog,
            organization_id=row["org_id"],
            client_id="eval-runner",
            operator_label="eval",
            unit_id=row["unit_id"],
            order_id=row["order_id"],
            ordered_sku=row["ordered_sku"],
            ordered_asin=row["ordered_asin"],
            image_bytes=image_bytes,
            image_paths=[],
        )
        print(f"{record.status} / {record.outcome.disposition} ({time.monotonic() - start:.1f}s)")

        by_key = {c.check_key: c for c in record.checks}
        results.append({
            "unit_id": row["unit_id"],
            "record_id": record.record_id,
            "status": record.status,
            "identity_verdict": by_key["identity"].verdict,
            "identity_confidence": by_key["identity"].confidence,
            "identity_latency_ms": by_key["identity"].latency_ms,
            "completeness_verdict": by_key["completeness"].verdict,
            "completeness_confidence": by_key["completeness"].confidence,
            "condition_verdict": by_key["condition"].verdict,
            "condition_confidence": by_key["condition"].confidence,
            "condition_grade": record.outcome.condition_grade or "",
            "disposition": record.outcome.disposition,
        })

    with open(EVAL_DIR / "results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(results)

    return results


def build_report(results: list[dict], labels_a: list[dict], labels_b: list[dict]) -> str:
    a_by_unit = {r["unit_id"]: r for r in labels_a}
    b_by_unit = {r["unit_id"]: r for r in labels_b}
    lines: list[str] = []

    def p(line: str = "") -> None:
        lines.append(line)

    scored = [r for r in results if r["unit_id"] in a_by_unit]
    skipped = len(results) - len(scored)
    p(f"# Evaluation summary\n")
    p(f"Units run: {len(results)}. Scored against labels_A: {len(scored)}"
      f"{f' ({skipped} unlabeled, excluded)' if skipped else ''}.\n")

    if not scored:
        p("No labelled units to score yet -- fill in eval/labels_A.csv.")
        return "\n".join(lines)

    # --- Identity ---
    pred = [r["identity_verdict"] for r in scored]
    truth_raw = [a_by_unit[r["unit_id"]]["identity_match"] for r in scored]
    truth = ["PASS" if t == "yes" else "FAIL" if t == "no" else "UNCERTAIN" for t in truth_raw]
    c = confusion_counts(pred, truth, positive="PASS")
    p("## Identity")
    p(f"- Accuracy (incl. UNCERTAIN as its own class): {c['accuracy']:.1%} (n={c['n']})")
    p(f"- False positives (agent PASS, human said no): {c['fp']}")
    p(f"- False negatives (agent FAIL, human said yes): {c['fn']}")
    p(f"- UNCERTAIN rate: {uncertain_rate(pred):.1%}")
    p()

    # --- Completeness ---
    pred = [r["completeness_verdict"] for r in scored]
    truth = [
        "FAIL" if (a_by_unit[r["unit_id"]].get("parts_missing") or "").strip() else "PASS"
        for r in scored
    ]
    c = confusion_counts(pred, truth, positive="PASS")
    p("## Completeness")
    p(f"- Accuracy: {c['accuracy']:.1%} (n={c['n']})")
    p(f"- False positives (agent says complete, human found missing parts): {c['fp']}")
    p(f"- False negatives (agent says missing, human says complete): {c['fn']}")
    p(f"- UNCERTAIN rate: {uncertain_rate(pred):.1%}")
    p()

    # --- Condition ---
    graded = [r for r in scored if r["condition_grade"]]
    pred = [r["condition_grade"] for r in graded]
    truth = [a_by_unit[r["unit_id"]]["condition_grade"] for r in graded]
    p("## Condition grade")
    p(f"- Exact-grade accuracy: {exact_match_accuracy(pred, truth):.1%} (n={len(graded)})")
    p(f"- UNCERTAIN rate (not graded at all): "
      f"{uncertain_rate([r['condition_verdict'] for r in scored]):.1%}")
    cm = confusion_matrix(pred, truth)
    if cm:
        p("- Confusion (truth -> agent, top mismatches):")
        for (truth_g, pred_g), n in sorted(cm.items(), key=lambda kv: -kv[1]):
            if truth_g != pred_g:
                p(f"  - {truth_g} -> {pred_g}: {n}")
    p()

    # --- Disposition ---
    pred = [r["disposition"] for r in scored]
    truth = [a_by_unit[r["unit_id"]]["disposition"] for r in scored]
    p("## Disposition")
    p(f"- Exact-match accuracy: {exact_match_accuracy(pred, truth):.1%} (n={len(pred)})")
    false_restock = sum(1 for p_, t_ in zip(pred, truth) if p_ == "restock" and t_ != "restock")
    missed_restock = sum(1 for p_, t_ in zip(pred, truth) if p_ != "restock" and t_ == "restock")
    p(f"- **False restocks** (agent said restock, human disagreed) — costliest error: {false_restock}")
    p(f"- Missed restocks (human said restock, agent didn't): {missed_restock}")
    p(f"- pending_review rate: {sum(p_ == 'pending_review' for p_ in pred) / len(pred):.1%}")
    p()

    # --- Human agreement (labels_A vs labels_B) ---
    both = [u for u in a_by_unit if u in b_by_unit]
    p("## Human label agreement (labels_A vs labels_B)")
    if both:
        for field in ("identity_match", "condition_grade", "disposition"):
            a_vals = [a_by_unit[u][field] for u in both]
            b_vals = [b_by_unit[u][field] for u in both]
            k = cohens_kappa(a_vals, b_vals)
            agree = sum(x == y for x, y in zip(a_vals, b_vals)) / len(both)
            p(f"- {field}: {agree:.1%} raw agreement, Cohen's kappa = {k:.2f} (n={len(both)})")
    else:
        p("- No units labelled by both A and B yet.")
    p()

    # --- Latency ---
    lat = latency_stats([r["identity_latency_ms"] for r in scored])
    p("## Latency (per unit, one batched call)")
    p(f"- mean {lat['mean_ms']}ms, median {lat['median_ms']}ms, "
      f"p95 {lat['p95_ms']}ms, max {lat['max_ms']}ms")
    p()

    error_units = [r["unit_id"] for r in results if r["status"] == "error"]
    if error_units:
        p("## Model/dependency failures (fail-open, preserved as pending_review)")
        p(f"- {len(error_units)} unit(s): {', '.join(error_units)}")

    return "\n".join(lines)


def main() -> None:
    results = run_agent_on_manifest()
    if not results:
        return
    labels_a = read_csv(EVAL_DIR / "labels_A.csv")
    labels_b = read_csv(EVAL_DIR / "labels_B.csv")
    report = build_report(results, labels_a, labels_b)
    (EVAL_DIR / "EVAL_SUMMARY.md").write_text(report, encoding="utf-8")
    print("\n" + report)
    print(f"\nWrote eval/results.csv and eval/EVAL_SUMMARY.md")


if __name__ == "__main__":
    main()
