# fermi-dash

Static HTML dashboard generator for Fermi-LAT SED and lightcurve plots using Panel.

## Install
```bash
uv sync
```

## Usage
```bash
uv run fermi-dash --root /path/to/analysis --config analysis.yaml --outfile dash.html
```

### Options
--days 7 30 365 — filter which lightcurve bins to include.
--prefer-html — embed Bokeh HTML lightcurves when present; otherwise uses PNG.
--allow-pdf — if sed_plot.png missing, link to PDF.
Folder expectations
analysis.yaml contains objects with name keys (any nesting), e.g.:

```
- name: 3C_454.3
- name: PKS_1510-089
```

Per-target folder under the root with sed_plot.png and lc_plots/.

## Output
A single file like fermi_dashboard.html you can email or share. Open in any browser.

