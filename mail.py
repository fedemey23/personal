"""Versión mail del termómetro: el mismo contenido que el artifact, con tablas y estilos en línea.

Los clientes de correo no muestran SVG ni JavaScript, así que el termómetro y las barras
se arman con celdas de tabla.
"""
from html import escape

ARTIFACT_URL = "https://claude.ai/artifact/BVkicQTuAconfx5Qs7pnj2"

C = {
    "bg": "#FAFBF9", "panel": "#FFFFFF", "side": "#F2F3F0", "ink": "#0A0A0B", "mu": "#5C5C5E", "bdr": "#E4E5E1",
    "logo": "#009444", "accent": "#E71CA2", "bar": "#CDD1CB", "google": "#4285F4", "meta": "#1877F2",
}
FILL = {"verde": "#59D7A2", "amarillo": "#FAB219", "rojo": "#D03B3B", "gris": "#B9BDB6"}
TAG = {"verde": ("#0E7A4E", "#E2F7EE"), "amarillo": ("#8A5A00", "#FDF0D5"),
       "rojo": ("#C2334D", "#F9E7EA"), "gris": ("#5C5C5E", "#EDEEEB")}
SHAPE = {"verde": "●", "amarillo": "◆", "rojo": "▲", "gris": "–"}
LABEL = {"verde": "Todo bien", "amarillo": "Atención", "rojo": "Revisar ya", "gris": "Sin lectura"}
CLIENT_LABEL = {"verde": "Bien", "amarillo": "Atención", "rojo": "Crítico"}
F_DISPLAY = "'Recoleta Alt',Recoleta,Georgia,'Times New Roman',serif"
F_BODY = "'Circular Std',-apple-system,'Segoe UI','Helvetica Neue',Arial,sans-serif"
F_MONO = "'SF Mono',Menlo,Consolas,monospace"


def esc(t):
    return escape(str(t), quote=True)


def ddmm(iso):
    return f"{iso[8:10]}/{iso[5:7]}"


def fmt(v):
    return f"{round(v):,}".replace(",", ".")


def dec(v):
    return f"{v:.1f}".rstrip("0").rstrip(".").replace(".", ",")


# Estilos que se repiten muchas veces: van como clases en <head> para que el mail pese poco.
STYLE = (
    f".t{{display:inline-block;font-family:{F_MONO};font-size:10px;letter-spacing:.08em;text-transform:uppercase;"
    "padding:3px 8px;border-radius:4px;font-weight:600;white-space:nowrap}"
    + "".join(f".t-{lvl}{{background:{bg};color:{fg}}}" for lvl, (fg, bg) in TAG.items())
    + f".p{{display:inline-block;font-size:12px;font-weight:700;padding:1px 10px;border:1.5px solid {C['bdr']};"
    "border-radius:100px;white-space:nowrap}"
    f".pg{{color:{C['google']}}}.pm{{color:{C['meta']}}}"
    ".b{width:22px;border-radius:3px 3px 0 0;font-size:0;line-height:0}.bc{padding:0 3px}"
    f".cv{{padding:16px 18px;border-top:1.5px solid {C['bdr']}}}"
    f".nm{{font-family:{F_MONO};font-size:13.5px;font-weight:600;word-break:break-word;margin-top:2px}}"
    f".sb{{font-size:12px;color:{C['mu']};word-break:break-word}}"
    f".wy{{font-size:13.5px;color:{C['mu']};margin-top:4px;word-break:break-word}}"
    f".vl{{font-family:{F_DISPLAY};font-size:20px;font-weight:700}}.sm{{font-size:11.5px;color:{C['mu']}}}"
    f".ax{{font-family:{F_MONO};font-size:10px;color:{C['mu']}}}"
    "@media (max-width:560px){.col{display:block!important;width:100%!important;padding-right:0!important}"
    ".spark{padding-top:10px!important}.pad{padding-left:12px!important;padding-right:12px!important}}"
)


def tag(level, text=None):
    return f'<span class="t t-{level}">{SHAPE[level]} {esc(text or LABEL[level])}</span>'


def plat(name):
    dot = "pm" if name == "Meta" else "pg"
    return f'<span class="p"><span class="{dot}">●</span> {esc(name)}</span>'


def thermo(level, temp):
    """Termómetro con celdas: la columna sube con la temperatura (marcas en 20% y 50%)."""
    tube = 96
    filled = max(8, round(tube * (0.08 + 0.92 * min(1, temp))))
    color = FILL[level]
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" align="center"><tr><td align="center">'
            f'<table role="presentation" cellpadding="0" cellspacing="0" style="border:2px solid {C["bdr"]};'
            f'border-bottom:0;border-radius:10px 10px 0 0;background:{C["panel"]}">'
            f'<tr><td style="width:10px;height:{tube - filled}px;font-size:0;line-height:0">&nbsp;</td></tr>'
            f'<tr><td style="width:10px;height:{filled}px;background:{color};font-size:0;line-height:0">&nbsp;</td></tr>'
            f'</table></td></tr><tr><td align="center">'
            f'<div style="width:28px;height:28px;border-radius:50%;background:{color};border:2px solid {C["bdr"]};'
            f'margin-top:-2px"></div></td></tr></table>')


def bars(item, level):
    weeks, h = item["weeks"], 40
    top = max(1, *weeks)
    cells = []
    for i, v in enumerate(weeks):
        last = i == len(weeks) - 1
        bh = max(3, round(v / top * h)) if v else 3
        color = (FILL[level] if last else C["bar"]) if v else C["bdr"]
        cells.append(f'<td class="bc" valign="bottom" height="{h}">'
                     f'<div class="b" style="height:{bh}px;background:{color}">&nbsp;</div></td>')
    return f'<table cellpadding="0" cellspacing="0"><tr>{"".join(cells)}</tr></table>'


def conv(item, week_starts, week):
    ref = (f"sem. anterior {fmt(item['prev'])}" if item["recent"]
           else f"prom. {fmt(item['weekly']) if item['weekly'] >= 1000 else dec(item['weekly'])}")
    note = f' <strong style="color:{C["ink"]};font-weight:600">{esc(item["note"])}</strong>' if item.get("note") else ""
    return (
        f'<tr><td class="cv">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
        f'<td class="col" valign="top" style="padding-right:14px">'
        f'<div style="line-height:2">{tag(item["level"], item["title"])} {plat(item["platform"])}</div>'
        f'<div class="nm">{esc(item["name"])}</div>'
        f'<div class="sb">{esc(item["group"])} · {esc(", ".join(item["campaigns"]))}</div>'
        f'<div class="wy">{esc(item["why"])}{note}</div></td>'
        f'<td class="col spark" valign="top" width="150" style="width:150px">'
        f'<div><span class="vl">{fmt(item["weeks"][-1])}</span>'
        f' <span class="sm">esta semana · {ref}</span></div>'
        f'{bars(item, item["level"])}'
        f'<div class="ax">{ddmm(week_starts[0])} → {ddmm(week[0])}</div>'
        f'</td></tr></table></td></tr>')


def client(c, week_starts, week):
    alerts = " ".join(tag(lvl, f"{sum(1 for i in c['items'] if i['level'] == lvl)} {LABEL[lvl].lower()}")
                      for lvl in ("rojo", "amarillo") if any(i["level"] == lvl for i in c["items"]))
    gray = sum(1 for i in c["items"] if i["level"] == "gris")
    return (
        f'<tr><td class="pad" style="padding:0 24px 16px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="background:{C["panel"]};border:1.5px solid {C["bdr"]};border-radius:20px;border-collapse:separate;overflow:hidden">'
        f'<tr><td style="background:{C["side"]};padding:18px">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
        f'<td width="44" valign="middle" style="width:44px">{thermo(c["level"], c["temp"])}</td>'
        f'<td valign="middle" style="padding-left:14px">'
        f'<div style="font-family:{F_DISPLAY};font-size:24px;font-weight:700;line-height:1.1">{esc(c["client"])}</div>'
        f'<div style="margin-top:6px;line-height:2">{tag(c["level"], CLIENT_LABEL[c["level"]])} {alerts}</div>'
        f'<div style="font-size:12.5px;color:{C["mu"]}"><strong style="color:{C["ink"]}">{c["healthy"]} de {c["readable"]}</strong>'
        f' funcionando bien{f" · {gray} sin lectura" if gray else ""}</div>'
        f'</td></tr></table></td></tr>'
        + "".join(conv(i, week_starts, week) for i in c["items"])
        + '</table></td></tr>')


def render(data):
    week, week_starts = data["week"], data["week_starts"]
    legend = "".join(
        f'<td class="col" valign="top" style="padding:0 4px 6px"><div style="border:1.5px solid {C["bdr"]};border-radius:14px;'
        f'background:{C["panel"]};padding:10px 12px">{tag(lvl)}<div style="font-size:12.5px;color:{C["mu"]};'
        f'margin-top:6px">{text}</div></div></td>'
        for lvl, text in (("verde", "En línea con su historial y su tráfico."),
                          ("amarillo", "Bajó bastante más que el tráfico."),
                          ("rojo", "En cero con tráfico: revisar el evento o el formulario.")))
    return (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>Termómetro de conversiones</title>'
        f'<style>{STYLE}</style></head>'
        f'<body style="margin:0;padding:0;background:{C["bg"]}">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{C["bg"]}">'
        '<tr><td align="center" style="padding:20px 8px">'
        f'<table role="presentation" width="680" cellpadding="0" cellspacing="0" style="width:100%;max-width:680px;'
        f'font-family:{F_BODY};color:{C["ink"]};font-size:14.5px;line-height:1.55">'
        '<tr><td style="padding:0 24px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="font-family:Montserrat,\'Helvetica Neue\',Arial,sans-serif;font-size:22px;letter-spacing:-.02em;color:{C["logo"]}">zenda.</td>'
        f'<td align="right" style="font-family:{F_MONO};font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:{C["mu"]}">auditoría semanal /</td>'
        f'</tr></table><div style="height:1.5px;background:{C["bdr"]};margin:14px 0 22px"></div></td></tr>'
        '<tr><td style="padding:0 24px 18px">'
        f'<div style="font-family:{F_MONO};font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:{C["mu"]}">'
        f'semana del {ddmm(week[0])} al {ddmm(week[1])} · próxima actualización: martes {ddmm(data["next"])}</div>'
        f'<h1 style="margin:6px 0 10px;font-family:{F_DISPLAY};font-size:36px;line-height:1.05;letter-spacing:-.03em;'
        f'font-weight:700">Termómetro de <span style="color:{C["accent"]}">conversiones</span></h1>'
        f'<p style="margin:0 0 14px;color:{C["mu"]}">Las conversiones por las que optimizan las campañas de cada cliente, '
        'revisadas una vez por semana para detectar caídas de medición o del sitio.</p>'
        f'<a href="{ARTIFACT_URL}" style="display:inline-block;background:{C["ink"]};color:{C["bg"]};text-decoration:none;'
        'font-weight:700;font-size:14px;padding:10px 22px;border-radius:100px">Abrir el termómetro</a></td></tr>'
        f'<tr><td style="padding:0 20px 14px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>{legend}</tr></table></td></tr>'
        f'<tr><td style="padding:0 24px 18px;font-size:12.5px;color:{C["mu"]}">El termómetro de cada cliente sube según qué '
        'parte de sus conversiones tiene alertas (rojo cuenta entera, amarillo media): hasta 20% queda en bien, hasta 50% '
        'en atención y arriba de eso en crítico. Las alertas se muestran siempre.</td></tr>'
        + "".join(client(c, week_starts, week) for c in data["clients"])
        + f'<tr><td style="padding:10px 24px 8px;font-size:12px;color:{C["mu"]}">Solo lectura: se consulta SeePM y no se '
        'modifica nada en las cuentas. Se compara la última semana (martes a lunes) con las 4 anteriores, ajustando por '
        'clics, y los últimos 3 días contra el resto de la semana. Gris: volumen demasiado bajo para leer.</td></tr>'
        '</table></td></tr></table></body></html>')
