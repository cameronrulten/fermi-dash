# debug/test_dark_export.py
import panel as pn
from panel.io.save import save as pn_save

print("Panel version:", pn.__version__)
pn.extension(theme="dark")  # global default for components

# --- Material (requires Theme class) ---
try:
    # Panel ≥1.0
    from panel.theme.material import MaterialDarkTheme
except Exception:
    # Fallback for some older builds
    from panel.template.material import MaterialDarkTheme

mat = pn.template.MaterialTemplate(
    title="Material Dark Test",
    theme=MaterialDarkTheme,   # ← Theme class, not "dark"
)
mat.main.append(pn.pane.Markdown("**Hello from Material DARK**"))
pn_save(mat, "debug_material_dark.html", resources="inline")

# --- FastList (also with a Theme class) ---
from panel.theme import DarkTheme
fast = pn.template.FastListTemplate(
    title="FastList Dark Test",
    main=[pn.pane.Markdown("**Hello from FastList DARK**")],
    theme=DarkTheme,
    theme_toggle=False,
)
pn_save(fast, "debug_fastlist_dark.html", resources="inline")

# --- Bootstrap (use BootstrapDarkTheme class) ---
from panel.theme.bootstrap import BootstrapDarkTheme
boot = pn.template.BootstrapTemplate(
    title="Bootstrap Dark Test",
    theme=BootstrapDarkTheme,  # ← NOT bootswatch_theme=
)
boot.main.append(pn.pane.Markdown("**Hello from Bootstrap DARK**"))
pn_save(boot, "debug_bootstrap_dark.html", resources="inline")

print("Wrote:", "debug_material_dark.html, debug_fastlist_dark.html, debug_bootstrap_dark.html")
