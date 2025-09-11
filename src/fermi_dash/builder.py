from __future__ import annotations
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Dict, Any
import yaml
from rich import print as rprint
from rich.console import Console
from rich.table import Table
import panel as pn
from panel.io.save import save as pn_save
from panel.theme import DarkTheme

pn.extension("plotly") # harmless if unused; keeps template resources present

IMG_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg"}
HTML_EXTS = {".html"}
PDF_EXTS = {".pdf"}

# Require a decimal (e.g. 7.0, 180.25). Case-insensitive.
# Support BOTH “…_lightcurve_<days>days” and “…_lightcurve_data_<days>days”
LC_PATTERNS = [
    re.compile(r"_lightcurve_(?P<days>\d+\.\d+)days(?=\.)", re.IGNORECASE),
    re.compile(r"_lightcurve_data_(?P<days>\d+\.\d+)days(?=\.)", re.IGNORECASE),
]

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
    template_name: str = "material"  # "material" | "fastlist"

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

def discover_lightcurves(lc_dir: Path) -> Dict[float, Dict[str, Path]]:
    """
    Returns {days: {'.png': Path, '.html': Path, ...}} for visual files only.
    Days must include a decimal (e.g. 7.0, 180.25). Case-insensitive.
    """
    out: Dict[float, Dict[str, Path]] = {}
    if not lc_dir.exists():
        return out

    for p in lc_dir.iterdir():
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext not in (IMG_EXTS | HTML_EXTS):  # 🔒 ignore .txt/.json/etc.
            continue

        days_val = None
        for rx in LC_PATTERNS:
            m = rx.search(p.name)
            if m:
                days_val = float(m.group("days"))
                break
        if days_val is None:
            continue

        out.setdefault(days_val, {})[ext] = p

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
        # Raw HTML from Bokeh may include <script> tags; pn.pane.HTML will include them,
        # but some browsers are picky with file://. PNGs are safer for single-file dashboards.
        try:
            html = path.read_text(encoding="utf-8")
            return pn.pane.HTML(html, height=420, sizing_mode="stretch_width", margin=0)
        except Exception:
            pass
    # Fallback to image if available or if HTML disabled
    if ext == ".png":
        return pn.pane.PNG(str(path), height=360, sizing_mode="stretch_width", embed=True, margin=0)
    if ext in {".jpg", ".jpeg", ".gif", ".svg"}:
        return pn.pane.Image(str(path), height=360, sizing_mode="stretch_width", embed=True, margin=0)
    if ext in HTML_EXTS:
        # HTML present but prefer_html=False → link out
        return pn.pane.Markdown(f"[Open lightcurve HTML]({path.as_posix()})")
    
    return pn.pane.Markdown("*Lightcurve not available*")

def make_template(name: str, title: str, header, tabs):
    if name.lower() == "material":
        t = pn.template.MaterialTemplate(title=title) #, theme=DarkTheme)
        t.main.extend([header, tabs])
        return t
    # default to fastlist + forced CSS
    t = pn.template.FastListTemplate(title=title, main=[header, tabs], theme_toggle=False) #theme=DarkTheme
    t.config.raw_css = ["""...CSS from above..."""]
    return t

def build_dashboard(opts: BuildOptions) -> Path:
    summaries = []

    try:
        # Panel 1.x commonly exposes it here
        from panel.template import DarkTheme
    except Exception:
        # Fallback (covers some versions)
        from panel.theme import DarkTheme

    pn.extension(design="bootstrap")
    #pn.extension(design="material", theme="dark") # forces dark unless a template overrides it

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
            collapsible=False,
        )

        lc_dir = tdir / "lc_plots"
        found_map = discover_lightcurves(lc_dir)

        # which bins to include
        if opts.days:
            wanted_days = list(dict.fromkeys(opts.days))  # dedupe, preserve order
        else:
            wanted_days = sorted(found_map.keys())

        # choose best file per day
        pairs: list[tuple[float, Path]] = []
        for d in wanted_days:
            files = found_map.get(d, {})
            chosen: Path | None = None
            if opts.prefer_html and ".html" in files:
                chosen = files[".html"]
            else:
                for e in [".png", ".jpg", ".jpeg", ".gif", ".svg", ".html"]:
                    if e in files:
                        chosen = files[e]
                        break
            if chosen:
                pairs.append((d, chosen))

        # debug
        if pairs:
            console.print(f"[dim]{name}: chosen LC files → " +
                        ", ".join(f"{d:g}={p.suffix.lower()[1:]}" for d, p in pairs))
        else:
            console.print(f"[dim]{name}: chosen LC files → [none]")

        # build cards
        #shorter comprehension version
        # lc_cards: List[pn.Card] = [
        #     pn.Card(_lc_pane(p, opts.prefer_html), title=f"Lightcurve — {d:g} days", collapsible=False)
        #     for d, p in pairs
        # ]
        # lc_section = pn.Column(*lc_cards, sizing_mode="stretch_width") if lc_cards else pn.pane.Markdown("*No matching lightcurves found*")

        # expanded version of lc_cards comprehension
        lc_cards: List[pn.Card] = []
        for d, p in pairs:
            pane = _lc_pane(p, opts.prefer_html)
            lc_cards.append(pn.Card(pane, title=f"Lightcurve — {d:g} days", collapsible=False))

        lc_section: pn.viewable.Viewable
        if lc_cards:
            lc_section = pn.Column(*lc_cards, sizing_mode="stretch_width")
            # lc_section = pn.GridBox(*lc_cards, ncols=2, sizing_mode="stretch_both")
        else:
            lc_section = pn.pane.Markdown("*No matching lightcurves found*")

        content = pn.Column(sed_card, lc_section, sizing_mode="stretch_both")
        tabs.append((name, content))

        #per target summary
        sed_ok = sed_path is not None
        found_bins = sorted(d for d, _ in pairs) if pairs else []
        summaries.append((name, sed_ok, len(found_bins), found_bins))

    if not tabs:
        console.print("[bold red]No tabs to render (no targets found).[/bold red]")
        raise SystemExit(3)

    header = pn.Column(
        f"## {opts.title}",
        pn.pane.Markdown(opts.subtitle, styles={"color": "#94a3b8"}),
        pn.pane.Markdown(f"*Generated with fermi-dash*"),
        sizing_mode="stretch_width",
    )

    tabs_obj = pn.Tabs(*tabs, dynamic=False)

    template = make_template(opts.template_name, opts.title, header, tabs_obj)
    # template.main.append(header)
    # template.main.append(tabs_obj)

    console.print(f"[dim]Panel {pn.__version__} | Template={type(template).__name__} | theme param type={getattr(template, 'theme', None)}[/dim]")

    # pn.config.raw_css.append("""
    # :root { color-scheme: dark; }
    # html, body, .bk-root { background: #0b0d10 !important; color: #e7e9ea !important; }
    # .mdc-top-app-bar, .pnx-header { background: #0b0d10 !important; color: #e7e9ea !important; }
    # .bk-card, .mdc-card, .pn-card { background:#1a1c20 !important; border-color:#1f2328 !important; }
    # """)

    # pn.config.raw_css.append("""
    # :root{
    # /* ChatGPT-ish palette */
    # --bg:        #ffffff;  /* page */
    # --header-bg: #11161D;  /* top app bar / tab strip */
    # --surface:   #141922;  /* cards/panes */
    # --surface-2: #171E28;  /* deeper surfaces if needed */
    # --text:      #E6E9EE;  /* primary text */
    # --muted:     #A6AFBB;  /* secondary text */
    # --border:    #242B33;  /* subtle borders */
    # --accent:    #10A37F;  /* OpenAI/ChatGPT green */
    # --accent-2:  #2DC08D;  /* hover/active variant */
    # --focus:     #3AD2A1;  /* focus ring */
    # }

    # /* Base */
    # html, body, .bk-root{ background:var(--bg) !important; color:var(--text) !important; }
    # a, .markdown a{ color:var(--accent) !important; text-decoration:none; }
    # a:hover{ color:var(--accent-2) !important; }

    # /* Header / app bar */
    # .mdc-top-app-bar, .mdc-top-app-bar__row, .pnx-header{
    # background:var(--header-bg) !important; color:var(--text) !important;
    # }

    # /* Cards / panels */
    # .bk-card, .mdc-card, .pn-card{
    # background:var(--surface) !important; color:var(--text) !important;
    # border-color:var(--border) !important; box-shadow:none !important;
    # }
    # .bk-card .bk-header, .pn-card .bk-header{ background:transparent !important; color:var(--muted) !important; }

    # /* Bokeh Tabs (Panel Tabs) */
    # .bk-tabs-header{ background:var(--header-bg) !important; border-color:var(--border) !important; }
    # .bk-tabs-header .bk-tab{ color:var(--muted) !important; }
    # .bk-tabs-header .bk-tab.bk-active{ color:var(--accent) !important; border-color:var(--accent) !important; }

    # /* Material Tabs (if template renders MDC tabs anywhere) */
    # .mdc-tab{ color:var(--muted) !important; }
    # .mdc-tab.mdc-tab--active{ color:var(--accent) !important; }
    # .mdc-tab-indicator .mdc-tab-indicator__content{
    # background-color:var(--accent) !important; border-color:var(--accent) !important;
    # }

    # /* Tooltips, menus, small chrome */
    # .bk-tooltip, .bk-menu, .mdc-menu{ background:var(--surface-2) !important; color:var(--text) !important; border-color:var(--border) !important; }

    # /* Inputs / focus */
    # input, select, textarea{ background:var(--surface) !important; color:var(--text) !important; border-color:var(--border) !important; }
    # *:focus{ outline: 2px solid var(--focus) !important; outline-offset:2px; }

    # /* (Optional) softer scrollbars on Firefox/WebKit */
    # *{ scrollbar-color: var(--surface-2) transparent; }
    # ::-webkit-scrollbar{ height:10px; width:10px; }
    # ::-webkit-scrollbar-thumb{ background:var(--surface-2); border-radius:8px; }
    # """)


    # One-file export suitable for sharing
    #template.save(str(opts.outfile), embed=True)
    pn_save(template, str(opts.outfile), resources="inline")

    #print summary table
    table = Table(title="Dashboard build summary")
    table.add_column("Target")
    table.add_column("SED", justify="center")
    table.add_column("#LC bins", justify="right")
    table.add_column("Bins")
    for t, sed_ok, n, bins in summaries:
        table.add_row(t, "✅" if sed_ok else "❌",
                    str(n),
                    ", ".join(f"{b:g}" for b in bins) if bins else "—")
    console.print(table)

    console.print(f"[green]Saved[/green] {opts.outfile}")
    return opts.outfile