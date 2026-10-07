"""Size a local pre-period store pilot; never uploads baseline sales."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from pilot_core import synthetic_pilot
from pilot_design import DESIGN_FIELDS, baseline_rows_to_csv, plan_pilot
from scenario_core import SYNTHETIC_EXAMPLE, break_even_lift


def run() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Generate and size an invented pre-period baseline")
    demo.add_argument("--output-dir", type=Path, default=Path("outputs/pilot_design_demo"))
    local = commands.add_parser("plan", help="Size from a local pre-period CSV")
    local.add_argument("csv_path", type=Path)
    local.add_argument("--break-even-lift", type=float, required=True,
                       help="Contribution break-even unit lift as a decimal, e.g. 0.225")
    local.add_argument("--target-lift", type=float, required=True,
                       help="Assumed true average lift to detect, as a decimal")
    local.add_argument("--pre-weeks", type=int, default=6)
    local.add_argument("--post-weeks", type=int, default=6)
    local.add_argument("--heterogeneity-sd", type=float, default=0.08)
    local.add_argument("--power", type=float, default=0.80)
    local.add_argument("--output-dir", type=Path, default=Path("outputs/pilot_design_local"))
    args = parser.parse_args()

    if args.command == "demo":
        rows, _ = synthetic_pilot()
        rows = [row for row in rows if row["period"] == "pre"]
        csv_text = baseline_rows_to_csv(rows)
        hurdle = break_even_lift(SYNTHETIC_EXAMPLE)
        kwargs = {"break_even_lift": hurdle, "target_lift": 0.30}
        label = "SYNTHETIC PRE-PERIOD DESIGN DEMO"
    else:
        with args.csv_path.open(newline="", encoding="utf-8-sig") as source:
            reader = csv.DictReader(source)
            if not reader.fieldnames or set(DESIGN_FIELDS) - set(reader.fieldnames):
                parser.error("CSV must contain every field in docs/PILOT_DESIGN.md")
            rows = list(reader)
        csv_text = None
        kwargs = {"break_even_lift": args.break_even_lift,
                  "target_lift": args.target_lift,
                  "planned_pre_weeks": args.pre_weeks,
                  "planned_post_weeks": args.post_weeks,
                  "heterogeneity_sd": args.heterogeneity_sd,
                  "target_power": args.power}
        label = "USER-SUPPLIED LOCAL PRE-PERIOD BASELINE"
    try:
        result = plan_pilot(rows, as_of=datetime.now(timezone.utc), **kwargs)
    except ValueError as exc:
        parser.error(str(exc))
    report = json.dumps({"data_label": label, **result}, indent=2) + "\n"
    files = {"pilot_design.json": report}
    if csv_text is not None:
        files["synthetic_baseline.csv"] = csv_text
    for filename in files:
        if (args.output_dir / filename).exists():
            parser.error(f"Refusing to overwrite {args.output_dir / filename}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in files.items():
        (args.output_dir / filename).write_text(content, encoding="utf-8")
    print(f"Artifacts: {args.output_dir.resolve()}")
    print("Illustrative matched pairs: " +
          (str(result["required_pairs"]) if result["required_pairs"] is not None
           else "none within 200"))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
