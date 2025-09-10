from __future__ import annotations
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Dict, Any
import yaml
from rich import print as rprint
from rich.console import Console
import panel as pn
from panel.io import save as pn_save

pn.extension("plotly") # harmless if unused; keeps template resources present

IMG_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg"}
HTML_EXTS = {".html"}
PDF_EXTS = {".pdf"}

console = Console()

@dataclass
class BuildOptions:
    root: Path
    config_yaml: Path
    title: str = "Fermi-LAT Dashboard"
    subtitle: str = "Auto-generated"
    outfile: Path = Path("fermi_dashboard.html")
    days: Optional[List[float]] = None # e.g., [7.0, 30.0]
    prefer_html: bool = False # use HTML lightcurves if available
    allow_pdf: bool = False # try to embed PDF SEDs (off by default)

# ------------------ YAML parsing ------------------

def _walk_names(obj: Any, out: List[str]) -> None:
    """Recursively collect values of keys named 'name'."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "name" and isinstance(v, (str, int, float)):
                out.append(str(v))
            else:
                _walk_names(v, out)
    elif isinstance(obj, list):
        for item in obj:
            _walk_names(item, out)


def load_target_names(config_yaml: Path) -> List[str]:
    data = yaml.safe_load(config_yaml.read_text())
    found: List[str] = []
    _walk_names(data, found)
    # dedupe, preserve order
    seen = set()
    names = []
    for n in found:
        if n not in seen:
            seen.add(n)
            names.append(n)
    return names

# ------------------ File discovery helpers ------------------

def find_sed_path(target_dir: Path, allow_pdf: bool) -> Optional[Path]:
    """Return SED image path for the target, prefer PNG over others.
    Looks for 'sed_plot.<ext>' inside target_dir.
    """
    candidates = list(target_dir.glob("sed_plot.*"))
    if not candidates:
        return None
    # Prefer PNG/JPG/SVG
    for p in candidates:
        if p.suffix.lower() in IMG_EXTS:
            return p
    # Fallback to PDF if allowed
    if allow_pdf:
        for p in candidates:
            if p.suffix.lower() in PDF_EXTS:
                return p
    return None

LC_RE = re.compile(r"^(?P<name>.+?)_lightcurve_data_(?P<days>[0-9]+(?:\.[0-9]+)?)days\.(?P<ext>[a-zA-Z0-9]+)$")

def discover_lightcurves(lc_dir: Path, name: str) -> Dict[float, Path]:
    """Return mapping {days: path} discovered under lc_dir for a given name."""
    out: Dict[float, Path] = {}
    if not lc_dir.exists():
        return out
    for p in lc_dir.iterdir():
        if not p.is_file():
            continue
        m = LC_RE.match(p.name)
        if not m:
            continue
        if m.group("name") != name:
            continue
        try:
            days = float(m.group("days"))
        except ValueError:
            continue
        out[days] = p
    return out

# ------------------ Panel UI builders ------------------

def _sed_pane(path: Path) -> pn.viewable.Viewable:
    ext = path.suffix.lower()
    if ext in IMG_EXTS:
        return pn.pane.Image(
            str(path), height=420, sizing_mode="stretch_width", embed=True, margin=0
        )
    if ext in PDF_EXTS:
        # Lightweight fallback to show a link rather than embedding heavy PDFJS
        return pn.pane.Markdown(f"[Open SED PDF]({path.as_posix()})")
    return pn.pane.Markdown("*SED not available*")

def _lc_pane(path: Path, prefer_html: bool) -> pn.viewable.Viewable:
    ext = path.suffix.lower()
    if prefer_html and ext in HTML_EXTS:
        try:
            html = path.read_text(encoding="utf-8")
            return pn.pane.HTML(html, height=420, sizing_mode="stretch_width", margin=0)
        except Exception:
            pass
    # Fallback to image if available or if HTML disabled
    if ext in IMG_EXTS:
        return pn.pane.Image(
            str(path), height=360, sizing_mode="stretch_width", embed=True, margin=0
        )
    if ext in HTML_EXTS:
        # HTML present but prefer_html=False → link out
        return pn.pane.Markdown(f"[Open lightcurve HTML]({path.as_posix()})")
    return pn.pane.Markdown("*Lightcurve not available*")

def build_dashboard(opts: BuildOptions) -> Path:
    names = load_target_names(opts.config_yaml)
    if not names:
        console.print("[bold red]No target names found in YAML.[/bold red]")
        raise SystemExit(2)

    tabs = []
    for name in names:
        tdir = opts.root / name
        if not tdir.exists():
            console.print(f"[yellow]Warning:[/] target dir not found: {tdir}")
            continue

        sed_path = find_sed_path(tdir, opts.allow_pdf)
        sed_card = pn.Card(
            _sed_pane(sed_path) if sed_path else pn.pane.Markdown("*No SED found*"),
            title=f"SED — {name}",
        )

        lc_dir = tdir / "lc_plots"
        discovered = discover_lightcurves(lc_dir, name)
        if opts.days:
            # filter to requested bins if present
            pairs = [(d, discovered.get(d)) for d in opts.days]
            pairs = [(d, p) for d, p in pairs if p is not None]
        else:
            pairs = sorted(discovered.items(), key=lambda kv: kv[0])

        lc_cards: List[pn.Card] = []
        for d, p in pairs:
            pane = _lc_pane(p, opts.prefer_html)
            lc_cards.append(pn.Card(pane, title=f"Lightcurve — {d:g} days"))

        lc_section: pn.viewable.Viewable
        if lc_cards:
            lc_section = pn.GridBox(*lc_cards, ncols=2, sizing_mode="stretch_both")
        else:
            lc_section = pn.pane.Markdown("*No matching lightcurves found*")

        content = pn.Column(sed_card, lc_section, sizing_mode="stretch_both")
        tabs.append((name, content))

    if not tabs:
        console.print("[bold red]No tabs to render (no targets found).[/bold red]")
        raise SystemExit(3)

    header = pn.Column(
        f"## {opts.title}",
        pn.pane.Markdown(opts.subtitle, styles={"color": "#94a3b8"}),
        pn.pane.Markdown(f"*Generated with fermi-dash*"),
        sizing_mode="stretch_width",
    )

    tabs_obj = pn.Tabs(*tabs, dynamic=True)

    template = pn.template.FastListTemplate(
        title=opts.title,
        main=[header, tabs_obj],
        theme="dark",
    )

    # One-file export suitable for sharing
    #template.save(str(opts.outfile), embed=True)
    pn_save(template, str(opts.outfile), resources="inline")
    console.print(f"[green]Saved[/green] {opts.outfile}")
    return opts.outfile