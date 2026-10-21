from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.table import Table


@dataclass(frozen=True)
class Run:
    dataset_name: str
    dataset_path: str
    results: dict[str, dict]


@dataclass(frozen=True)
class ComparisonRow:
    query: str
    rows_a: int | None
    rows_b: int | None
    median_seconds_a: float
    median_seconds_b: float
    delta_percent: float
    speedup: float
    rows_mismatch: bool


class RunLoadError(Exception):
    pass


def load_run(path: Path) -> Run:
    run_file = path / "run.json" if path.is_dir() else path
    if not run_file.exists():
        raise RunLoadError(f"no run.json found at {run_file}")
    payload = json.loads(run_file.read_text())
    try:
        results = {result["query"]: result for result in payload["results"]}
        return Run(
            dataset_name=payload["dataset_name"],
            dataset_path=payload["dataset_path"],
            results=results,
        )
    except KeyError as e:
        raise RunLoadError(f"{run_file} is not a valid run.json (missing {e})") from e


def compare(run_a: Run, run_b: Run) -> tuple[list[ComparisonRow], list[str]]:
    shared = sorted(set(run_a.results) & set(run_b.results))
    skipped = sorted(set(run_a.results) ^ set(run_b.results))
    rows = []
    for name in shared:
        result_a = run_a.results[name]
        result_b = run_b.results[name]
        median_a = result_a["median_seconds"]
        median_b = result_b["median_seconds"]
        delta_percent = ((median_b - median_a) / median_a) * 100 if median_a else 0.0
        speedup = median_a / median_b if median_b else float("inf")
        rows.append(
            ComparisonRow(
                query=name,
                rows_a=result_a["rows"],
                rows_b=result_b["rows"],
                median_seconds_a=median_a,
                median_seconds_b=median_b,
                delta_percent=delta_percent,
                speedup=speedup,
                rows_mismatch=result_a["rows"] != result_b["rows"],
            )
        )
    return rows, skipped


def render_table(run_a: Run, run_b: Run, rows: list[ComparisonRow]) -> Table:
    table = Table(title=f"{run_a.dataset_name} vs {run_b.dataset_name}")
    table.add_column("query")
    table.add_column(f"{run_a.dataset_name} rows", justify="right")
    table.add_column(f"{run_b.dataset_name} rows", justify="right")
    table.add_column(f"{run_a.dataset_name} median (s)", justify="right")
    table.add_column(f"{run_b.dataset_name} median (s)", justify="right")
    table.add_column("delta median %", justify="right")
    table.add_column("speedup", justify="right")
    for row in rows:
        query_label = f"{row.query} ⚠" if row.rows_mismatch else row.query
        table.add_row(
            query_label,
            str(row.rows_a),
            str(row.rows_b),
            f"{row.median_seconds_a:.4f}",
            f"{row.median_seconds_b:.4f}",
            f"{row.delta_percent:+.1f}%",
            f"{row.speedup:.2f}x",
        )
    return table


def print_comparison(
    run_a: Run, run_b: Run, rows: list[ComparisonRow], skipped: list[str]
) -> None:
    console = Console(width=200)
    console.print(render_table(run_a, run_b, rows))
    if skipped:
        console.print(f"skipped (present in only one run): {', '.join(skipped)}")


def write_markdown(
    run_a: Run, run_b: Run, rows: list[ComparisonRow], outfile: Path
) -> None:
    lines = [
        (
            f"| query | {run_a.dataset_name} rows | {run_b.dataset_name} rows | "
            f"{run_a.dataset_name} median (s) | {run_b.dataset_name} median (s) | "
            f"delta median % | speedup |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        query_label = f"{row.query} ⚠" if row.rows_mismatch else row.query
        lines.append(
            f"| {query_label} | {row.rows_a} | {row.rows_b} | {row.median_seconds_a:.4f} | "
            f"{row.median_seconds_b:.4f} | {row.delta_percent:+.1f}% | {row.speedup:.2f}x |"
        )
    outfile.write_text("\n".join(lines) + "\n")


def write_csv(run_a: Run, run_b: Run, rows: list[ComparisonRow], outfile: Path) -> None:
    with outfile.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "query",
                f"{run_a.dataset_name}_rows",
                f"{run_b.dataset_name}_rows",
                f"{run_a.dataset_name}_median_seconds",
                f"{run_b.dataset_name}_median_seconds",
                "delta_median_percent",
                "speedup",
                "rows_mismatch",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.query,
                    row.rows_a,
                    row.rows_b,
                    row.median_seconds_a,
                    row.median_seconds_b,
                    f"{row.delta_percent:.1f}",
                    f"{row.speedup:.2f}",
                    row.rows_mismatch,
                ]
            )
