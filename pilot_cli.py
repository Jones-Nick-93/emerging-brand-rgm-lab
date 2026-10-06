"""Generate a synthetic pilot or audit and analyze a local pilot CSV."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from pilot_core import FIELDS, analyze_pilot, rows_to_csv, synthetic_pilot, validate_pilot


def run() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    demo = subparsers.add_parser("demo", help="Generate the fixed synthetic randomized pilot")
    demo.add_argument("--output-dir", type=Path, default=Path("outputs/pilot_demo"))
    local = subparsers.add_parser("analyze", help="Analyze a local CSV; no upload or network use")
    local.add_argument("csv_path", type=Path)
    local.add_argument("--output-dir", type=Path, default=Path("outputs/pilot_local"))
    args = parser.parse_args()

    if args.command == "demo":
        rows, truth = synthetic_pilot()
        csv_text = rows_to_csv(rows)
        label = "SYNTHETIC RANDOMIZED DEMO"
    else:
        with args.csv_path.open(newline="", encoding="utf-8-sig") as source:
            reader = csv.DictReader(source)
            if not reader.fieldnames or set(FIELDS) - set(reader.fieldnames):
                parser.error("CSV must contain every field in docs/PILOT_DATA_CONTRACT.md")
            rows = list(reader)
        truth = None
        csv_text = None
        label = "USER-SUPPLIED LOCAL PILOT; RANDOMIZATION NOT VERIFIED"

    as_of = datetime.now(timezone.utc)
    quality = validate_pilot(rows, as_of=as_of)
    files = {"quality_report.json": json.dumps({"data_label": label, **quality.to_dict()}, indent=2)}
    if csv_text is not None:
        files["synthetic_pilot.csv"] = csv_text
    if quality.ready:
        estimate = analyze_pilot(rows, as_of=as_of)
        files["pilot_estimate.json"] = json.dumps(
            {"data_label": label, "synthetic_truth": truth, **estimate}, indent=2)
    for filename in files:
        if (args.output_dir / filename).exists():
            parser.error(f"Refusing to overwrite {args.output_dir / filename}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for filename, contents in files.items():
        (args.output_dir / filename).write_text(contents + ("" if contents.endswith("\n") else "\n"),
                                                encoding="utf-8")
    print(f"Quality: {'READY FOR ESTIMATION' if quality.ready else 'BLOCKED'}")
    print(f"Artifacts: {args.output_dir.resolve()}")
    if not quality.ready:
        print("Blockers: " + "; ".join(quality.blockers[:5]))
        return 2
    print(f"Pooled lift: {estimate['pooled_lift']:.1%}; approximate 90% interval: "
          f"{estimate['interval_90'][0]:.1%} to {estimate['interval_90'][1]:.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
