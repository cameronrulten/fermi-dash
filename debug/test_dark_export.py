# debug/test_dark_export.py
import panel as pn
from panel.io.save import save as pn_save

pn.extension(theme="dark")

# 1) Material + MaterialDarkTheme
try:
    from panel.theme.material import MaterialDarkTheme
except Exception:
    from panel.template.material import MaterialDarkTheme

mat = pn.template.MaterialTemplate(title="Material Dark Test", theme=MaterialDarkTheme)
mat.main.append(pn.pane.Markdown("**Hello from Material DARK**"))
pn_save(mat, "debug_material_dark.html", resources="inline")

# 2) FastList + DarkTheme
from panel.theme import DarkTheme
fast = pn.template.FastListTemplate(title="FastList Dark Test", main=[pn.pane.Markdown("**Hello from FastList DARK**")], theme=DarkTheme, theme_toggle=False)
pn_save(fast, "debug_fastlist_dark.html", resources="inline")

# 3) Bootstrap darkly (control)
boot = pn.template.BootstrapTemplate(title="Bootstrap Darkly Test", bootswatch_theme="darkly")
boot.main.append(pn.pane.Markdown("**Hello from Bootstrap DARKLY**"))
pn_save(boot, "debug_bootstrap_dark.html", resources="inline")

print("Panel version:", pn.__version__)
print("Wrote:", "debug_material_dark.html, debug_fastlist_dark.html, debug_bootstrap_dark.html")
