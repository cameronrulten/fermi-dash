from __future__ import annotations
from pathlib import Path
from typing import List, Optional
import typer
from rich import print as rprint
from .builder import BuildOptions, build_dashboard

app = typer.Typer(add_completion=False, help="Build a static HTML dashboard of SED and lightcurves.")

@app.command()
def main(
root: Path = typer.Option(..., exists=True, file_okay=False, dir_okay=True, readable=True, help="Analysis root directory"),
config: Path = typer.Option(..., exists=True, file_okay=True, dir_okay=False, readable=True, help="YAML listing targets with 'name' keys"),
outfile: Path = typer.Option(Path("fermi_dashboard.html"), help="Output HTML file path"),
title: str = typer.Option("Fermi-LAT Dashboard", help="Dashboard title"),
subtitle: str = typer.Option("Auto-generated", help="Subtitle"),
days: Optional[List[float]] = typer.Option(None, help="Lightcurve bin sizes to include, e.g. --days 7 30 365"),
prefer_html: bool = typer.Option(False, help="Prefer embedding HTML lightcurves if available (Bokeh)"),
allow_pdf: bool = typer.Option(False, help="Attempt to link/embed PDF SEDs if PNG not found"),
):
"""Create a single-file HTML dashboard from a typical Fermi-LAT analysis folder.

Example:
fermi-dash --root ./analysis --config analysis.yaml --days 7 30 --outfile dash.html
"""
opts = BuildOptions(
root=root,
config_yaml=config,
title=title,
subtitle=subtitle,
outfile=outfile,
days=days,
prefer_html=prefer_html,
allow_pdf=allow_pdf,
)
build_dashboard(opts)

if __name__ == "__main__":
app()