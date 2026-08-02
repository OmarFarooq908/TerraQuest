"""adventurectl — local exploration CLI."""

from __future__ import annotations

import typer
from adventure_core.config import load_pack_manifest
from rich.console import Console
from rich.table import Table

from adventure_cli.pipeline import run_mission

app = typer.Typer(
    name="adventurectl",
    help="Adventure AI — missions, not itineraries.",
    no_args_is_help=True,
)
mission_app = typer.Typer(help="Mission commands")
pack_app = typer.Typer(help="Region Pack build & inspect")
app.add_typer(mission_app, name="mission")
app.add_typer(pack_app, name="pack")
console = Console()


def _print_pack_banner(pack: str) -> None:
    manifest, pack_dir = load_pack_manifest(pack)
    src = ", ".join(s.kind for s in manifest.sources) if manifest.sources else "unknown"
    if manifest.synthetic:
        console.print(
            "[bold red]SYNTHETIC PACK[/bold red] — fixture data for CI/tests only. "
            "Not real OSM/DEM. Build production: [cyan]adventurectl pack build --config skardu_v1[/cyan]"
        )
    else:
        console.print(
            f"[bold green]REAL PACK[/bold green] id={manifest.pack_id} "
            f"sources=\\[{src}\\] dir={pack_dir}"
        )
        if manifest.built_at:
            console.print(f"[dim]built_at={manifest.built_at} hash={manifest.content_hash}[/dim]")


def _print_intent(result) -> None:
    intent = result.request.intent
    c = intent.constraints
    console.print(
        f"Intent \\[{intent.source}\\]: origin={c.origin} vehicle={c.vehicle} ({c.vehicle_class}) "
        f"days={c.days} party={c.party_size} budget={c.budget_per_person} {c.currency or ''}"
    )
    active = intent.preferences.active()
    console.print(f"Preferences: {active or '{}'}")
    console.print(f"Goals: {intent.goals or []}")


def _print_coverage(result) -> None:
    console.print()
    console.print("[bold]Intent coverage[/bold]")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Field")
    table.add_column("Role")
    table.add_column("Value")
    table.add_column("Scoring")
    table.add_column("Reason")
    for f in result.coverage.fields:
        value = f.value
        if isinstance(value, dict):
            value = ", ".join(f"{k}={v}" for k, v in list(value.items())[:6])
        elif isinstance(value, list):
            value = ", ".join(str(v) for v in value) if value else "—"
        elif value is None:
            value = "—"
        style = {
            "used": "green",
            "partial": "yellow",
            "ignored": "red",
            "neutral": "dim",
        }.get(f.scoring, "white")
        table.add_row(
            f.field,
            f.role,
            str(value)[:52],
            f"[{style}]{f.scoring}[/{style}]",
            f.reason[:56],
        )
    console.print(table)


@pack_app.command("build")
def pack_build(
    config: str = typer.Option("skardu_v1", "--config", "-c", help="Pack config id or yaml path"),
    skip_dem: bool = typer.Option(
        False, "--skip-dem", help="OSM-only build (faster, less accurate)"
    ),
) -> None:
    """Build a production Region Pack from OSM (+ DEM). Requires network."""
    from adventure_packbuilder import build_pack, load_build_config

    cfg = load_build_config(config)
    console.print(f"Building pack [bold]{cfg.pack_id}[/bold] bbox={cfg.bbox} …")
    out = build_pack(cfg, skip_dem=skip_dem)
    console.print(f"[green]Built[/green] {out}")
    console.print("Run a mission with:")
    console.print(f'  adventurectl mission run --pack {cfg.pack_id} --interpreter rules -p "..."')


@pack_app.command("info")
def pack_info(
    pack: str = typer.Argument(..., help="Pack id or directory"),
) -> None:
    """Show pack manifest and honesty banner."""
    manifest, pack_dir = load_pack_manifest(pack)
    _print_pack_banner(pack)
    console.print(manifest.model_dump_json(indent=2))


@mission_app.command("run")
def mission_run(
    pack: str = typer.Option(
        "skardu_v1",
        "--pack",
        help="Pack id (skardu_v1) or fixtures/karakoram_mini for CI",
    ),
    mode: str = typer.Option("fearless_far", "--mode"),
    prompt: str = typer.Option(..., "--prompt", "-p"),
    max_results: int = typer.Option(5, "--max-results"),
    interpreter: str = typer.Option(
        "auto",
        "--interpreter",
        help="auto | rules | ollama",
    ),
    model: str = typer.Option("llama3.2", "--model", help="Ollama model for interpreter"),
    strict_llm: bool = typer.Option(
        False,
        "--strict-llm",
        help="With interpreter=auto, fail instead of falling back to rules",
    ),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Run a mission: interpret → GIS → preference-vector score."""
    _print_pack_banner(pack)
    result = run_mission(
        pack=pack,
        mode=mode,
        prompt=prompt,
        max_results=max_results,
        interpreter=interpreter,
        model=model,
        allow_rules_fallback=not strict_llm,
    )

    if json_out:
        console.print_json(result.model_dump_json(indent=2))
        return

    console.print(f"[bold]Mode[/bold]: {result.mode}  [bold]Pack[/bold]: {result.pack_id}")
    console.print(f"[dim]{result.request.prompt}[/dim]")
    _print_intent(result)
    console.print()

    table = Table(title="Ranked missions")
    table.add_column("#", justify="right")
    table.add_column("Name")
    table.add_column("Claim")
    table.add_column("Score", justify="right")
    table.add_column("Conf", justify="right")
    table.add_column("Evidence")

    for i, m in enumerate(result.missions, start=1):
        ev = (
            m.evidence.get("generator")
            or m.evidence.get("source")
            or m.evidence.get("osm_id")
            or "—"
        )
        table.add_row(
            str(i),
            m.name[:28],
            m.claim[:36],
            f"{m.score:.3f}",
            f"{m.confidence.value:.0%}",
            str(ev)[:20],
        )
    console.print(table)

    if result.missions:
        console.print()
        top = result.missions[0]
        console.print(f"[bold]Top evidence[/bold] ({top.candidate_id}):")
        for r in top.confidence.reasons:
            console.print(f"  • {r.code}: {r.detail}")
        if top.evidence:
            console.print(f"  • raw: { {k: top.evidence[k] for k in list(top.evidence)[:8]} }")

    _print_coverage(result)
    console.print()
    for note in result.notes:
        console.print(f"[dim]- {note}[/dim]")


@app.callback()
def main() -> None:
    """Adventure AI CLI."""


if __name__ == "__main__":
    app()
