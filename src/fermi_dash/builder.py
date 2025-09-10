from __future__ import annotations
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Dict, Any
import yaml
from rich import print as rprint
from rich.console import Console
import panel as pn

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
return opts.outfile