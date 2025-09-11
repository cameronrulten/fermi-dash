# scripts/debug_discover.py
from pathlib import Path
import re
import sys

IMG_EXTS  = {".png", ".jpg", ".jpeg", ".gif", ".svg"}
HTML_EXTS = {".html"}
RX = re.compile(r"_lightcurve_data_(\d+\.\d+)days(?=\.)", re.IGNORECASE)  # requires a decimal: 7.0, 180.25

def main(lc_dir: str):
    pdir = Path(lc_dir)
    print(f"Scanning: {pdir}")
    for p in sorted(pdir.iterdir()):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        vis = ext in (IMG_EXTS | HTML_EXTS)
        m = RX.search(p.name)
        days = m.group(1) if m else None
        print(f"{'VIS ' if vis else 'SKIP'}  {'HIT ' if m else 'MISS'}  ext={ext:<5} days={str(days):<6}  {p.name}")

if __name__ == "__main__":
    main(sys.argv[1])
