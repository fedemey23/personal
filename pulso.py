#!/usr/bin/env python3
"""Pulso semanal: evalúa las conversiones por las que optimizan las campañas y arma el mail.

Uso:
  python3 pulso.py data/<cliente>/<fecha>.json [más clientes...] [-o mail.md]

Cada snapshot trae 5 semanas por conversión (4 de referencia + la última). Si existe un
snapshot anterior del mismo cliente en su carpeta, marca qué alertas son nuevas.
No se conecta a ninguna plataforma.
"""
import argparse
import json
from datetime import date, timedelta
from pathlib import Path

ORDER = ["caida", "revisar", "ok", "nueva", "poco_volumen"]
ICON = {"caida": "🔴", "revisar": "🟡", "ok": "🟢", "nueva": "🔵", "poco_volumen": "⚪"}
LABEL = {"caida": "Caída", "revisar": "Revisar", "ok": "OK", "nueva": "Nueva", "poco_volumen": "Poco volumen"}
PLATFORM = {"google_ads": "Google Ads", "meta_ads": "Meta"}


def n(x):
    return f"{x:.1f}".rstrip("0").rstrip(".").replace(".", ",")


def miles(k):
    return f"{k:,}".replace(",", ".")


def ddmm(iso):
    d = date.fromisoformat(iso)
    return f"{d.day:02d}/{d.month:02d}"


def evaluate(item, week_start):
    conv, clicks = item["weeks"], item["clicks"]
    last, last_clicks = conv[-1], clicks[-1]
    base = [(c, k) for c, k in zip(conv[:-1], clicks[:-1]) if k]
    base_conv = sum(c for c, _ in base)
    base_clicks = sum(k for _, k in base)
    weekly = base_conv / len(base) if base else 0
    out = {"last": last, "last_clicks": last_clicks, "weekly": weekly}

    def res(status, why):
        return {**out, "status": status, "why": why}

    since = item.get("since")
    if since and date.fromisoformat(since) > week_start - timedelta(days=7):
        return res("nueva", f"Arrancó el {ddmm(since)}. {last} conversiones con {miles(last_clicks)} clics; "
                            "se compara desde la próxima semana.")

    if base_conv == 0 and last == 0:
        total = base_clicks + last_clicks
        seen = f" La última fue el {ddmm(item['last_seen'])}." if item.get("last_seen") else ""
        if total >= 100:
            return res("revisar", f"Ninguna conversión en 5 semanas con {miles(total)} clics.{seen} "
                                  "Puede ser la campaña o el evento: conviene completar el formulario y ver si llega.")
        return res("poco_volumen", f"Sin conversiones en 5 semanas, pero con solo {total} clics.{seen}")

    expected = base_conv / base_clicks * last_clicks if base_clicks else 0
    if last == 0 and expected >= 2.5:
        status = "caida" if expected >= 4 else "revisar"
        return res(status, f"Cero conversiones con {miles(last_clicks)} clics; con su tasa habitual se esperaban "
                           f"unas {n(expected)}. Si el tráfico es normal, revisar el tag o el formulario.")
    if expected >= 5 and last / expected < 0.6:
        status = "caida" if last / expected < 0.4 else "revisar"
        return res(status, f"{last} conversiones con {miles(last_clicks)} clics; se esperaban unas {n(expected)} "
                           f"({round((1 - last / expected) * 100)}% menos).")
    if weekly < 1 and last == 0:
        return res("poco_volumen", f"Convierte menos de una vez por semana ({n(weekly)} de promedio).")
    return res("ok", "")


def previous_alerts(path):
    snaps = sorted(p for p in path.parent.glob("*.json") if p.name < path.name)
    if not snaps:
        return None
    prev = json.loads(snaps[-1].read_text())
    start = date.fromisoformat(prev["week"][0])
    return {i["id"] for i in prev["conversions"] if evaluate(i, start)["status"] in ("caida", "revisar")}


def render(snap, prev_alerts):
    week_start = date.fromisoformat(snap["week"][0])
    items = [{**i, **evaluate(i, week_start)} for i in snap["conversions"]]
    items.sort(key=lambda i: (ORDER.index(i["status"]), i["platform"], i["group"]))
    alerts = [i for i in items if i["status"] in ("caida", "revisar")]
    ok = [i for i in items if i["status"] == "ok"]
    rest = [i for i in items if i["status"] in ("nueva", "poco_volumen")]

    lines = [f"## {snap['client']}"]
    if not alerts:
        lines.append(f"🟢 Sin alertas. Las {len(items)} conversiones de optimización registran actividad normal.")
    for i in alerts:
        tag = ""
        if prev_alerts is not None:
            tag = " · **nueva alerta**" if i["id"] not in prev_alerts else " · sigue desde la semana pasada"
        lines += ["", f"{ICON[i['status']]} **{LABEL[i['status']]}: {i['name']}** ({PLATFORM[i['platform']]} · "
                      f"{i['group']}){tag}", f"{i['why']}", f"Campañas: {', '.join(i['campaigns'])}"]
    if ok:
        lines += ["", "| Conversión | Plataforma | Semana | Prom. 4 sem. | Clics |", "|---|---|--:|--:|--:|"]
        for i in ok:
            lines.append(f"| 🟢 {i['name']} | {PLATFORM[i['platform']]} | {i['last']} | {n(i['weekly'])} "
                         f"| {miles(i['last_clicks'])} |")
    for i in rest:
        lines += ["", f"{ICON[i['status']]} {LABEL[i['status']]}: **{i['name']}** ({PLATFORM[i['platform']]}). {i['why']}"]
    return items, "\n".join(lines)


# Estética Zenda (de la skill reportes-paid-media), con estilos en línea para clientes de correo.
Z = {
    "bg": "#FAFBF9", "card": "#FFFFFF", "ink": "#0A0A0B", "mu": "#5C5C5E", "bdr": "#E4E5E1",
    "logo": "#009444", "g_ink": "#0E7A4E", "m": "#E71CA2", "m_ink": "#B0157C",
    "display": "'Recoleta Alt', Recoleta, Georgia, 'Times New Roman', serif",
    "body": "'Circular Std', -apple-system, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif",
    "mono": "'SF Mono', 'Fira Code', Menlo, Consolas, monospace",
    "logo_font": "Montserrat, 'Helvetica Neue', Arial, sans-serif",
}
TAG_COLORS = {
    "caida": ("#C2334D", "#F9E7EA"), "revisar": (Z["m_ink"], "#FCE8F5"), "ok": (Z["g_ink"], "#E2F7EE"),
    "nueva": ("#1A6A8A", "#EAF6FA"), "poco_volumen": (Z["mu"], "#EDEEEB"),
}


def esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def tag(status, text=None):
    fg, bg = TAG_COLORS[status]
    return (f'<span style="display:inline-block;font-family:{Z["mono"]};font-size:10px;letter-spacing:.08em;'
            f'text-transform:uppercase;padding:3px 8px;border-radius:4px;background:{bg};color:{fg};'
            f'font-weight:600;white-space:nowrap">{esc(text or LABEL[status])}</span>')


def mono(text):
    return (f'<span style="font-family:{Z["mono"]};font-size:11px;letter-spacing:.1em;text-transform:uppercase;'
            f'color:{Z["mu"]}">{esc(text)}</span>')


def html_client(snap, items, prev):
    alerts = [i for i in items if i["status"] in ("caida", "revisar")]
    ok = [i for i in items if i["status"] == "ok"]
    rest = [i for i in items if i["status"] in ("nueva", "poco_volumen")]
    cell = f"padding:10px 12px;border-top:1px solid {Z['bdr']}"
    out = [f'<tr><td style="padding:36px 32px 0">',
           f'<h2 style="margin:0 0 14px;font-family:{Z["display"]};font-size:26px;letter-spacing:-.02em;'
           f'font-weight:700">{esc(snap["client"])}</h2>']
    if not alerts:
        out.append(f'<p style="margin:0 0 14px;color:{Z["mu"]}">Sin alertas: las {len(items)} conversiones '
                   'de optimización registran actividad normal.</p>')
    for i in alerts:
        note = ""
        if prev is not None:
            note = "&nbsp;" + (tag("revisar", "nueva alerta") if i["id"] not in prev
                               else tag("poco_volumen", "sigue de la semana pasada"))
        out.append(
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{Z["card"]};'
            f'border:1.5px solid {Z["bdr"]};border-radius:16px;margin-bottom:12px"><tr><td style="padding:18px 20px">'
            f'<div>{tag(i["status"])}{note}&nbsp; {mono(PLATFORM[i["platform"]] + " · " + i["group"])}</div>'
            f'<div style="font-family:{Z["mono"]};font-size:15px;font-weight:600;margin:10px 0 4px;'
            f'word-break:break-word">{esc(i["name"])}</div>'
            f'<p style="margin:0 0 8px;color:{Z["mu"]}">{esc(i["why"])}</p>'
            f'<div style="font-size:12.5px;color:{Z["mu"]}"><strong style="color:{Z["ink"]}">Campañas:</strong> '
            f'{esc(", ".join(i["campaigns"]))}</div></td></tr></table>')
    if ok:
        th = (f'padding:10px 12px;font-family:{Z["mono"]};font-size:10px;letter-spacing:.08em;'
              f'text-transform:uppercase;color:{Z["mu"]};font-weight:500')
        out.append(f'<div style="margin:18px 0 8px">{tag("ok", f"{len(ok)} en orden")}</div>'
                   f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:'
                   f'{Z["card"]};border:1.5px solid {Z["bdr"]};border-radius:16px;font-size:13px"><tr>'
                   f'<td style="{th};text-align:left">Conversión</td><td style="{th};text-align:right">Semana</td>'
                   f'<td style="{th};text-align:right">Prom. 4 sem.</td><td style="{th};text-align:right">Clics</td></tr>')
        for i in ok:
            out.append(
                f'<tr><td style="{cell}"><div style="font-family:{Z["mono"]};font-size:12.5px;word-break:break-word">'
                f'{esc(i["name"])}</div><div style="font-size:11.5px;color:{Z["mu"]}">{PLATFORM[i["platform"]]} · '
                f'{esc(i["group"])}</div></td>'
                f'<td style="{cell};text-align:right;font-weight:700">{i["last"]}</td>'
                f'<td style="{cell};text-align:right;color:{Z["mu"]}">{n(i["weekly"])}</td>'
                f'<td style="{cell};text-align:right;color:{Z["mu"]}">{miles(i["last_clicks"])}</td></tr>')
        out.append("</table>")
    for i in rest:
        out.append(f'<p style="margin:14px 0 0;font-size:13.5px;color:{Z["mu"]}">{tag(i["status"])}&nbsp; '
                   f'<span style="font-family:{Z["mono"]};color:{Z["ink"]}">{esc(i["name"])}</span> '
                   f'({PLATFORM[i["platform"]]}). {esc(i["why"])}</p>')
    out.append("</td></tr>")
    return "".join(out)


def render_html(clients, week, counts):
    alerts = counts["caida"] + counts["revisar"]
    if alerts:
        word = "conversión" if alerts == 1 else "conversiones"
        head = f'{alerts} {word} para <span style="color:{Z["m"]}">revisar</span>'
    else:
        head = f'Todo en <span style="color:{Z["g_ink"]}">orden</span>'
    chips = " ".join(tag(s, f"{counts[s]} {LABEL[s]}") for s in ORDER if counts[s])
    rule = f'<div style="height:1px;background:{Z["bdr"]}"></div>'
    return "".join([
        '<!doctype html><html lang="es"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        '<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400&display=swap" rel="stylesheet">',
        f'<title>Pulso semanal</title></head><body style="margin:0;padding:0;background:{Z["bg"]}">',
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{Z["bg"]}">',
        '<tr><td align="center" style="padding:24px 12px">',
        f'<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;'
        f'font-family:{Z["body"]};color:{Z["ink"]};font-size:14.5px;line-height:1.6">',
        '<tr><td style="padding:0 32px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>',
        f'<td style="font-family:{Z["logo_font"]};font-size:22px;letter-spacing:-.02em;color:{Z["logo"]}">zenda.</td>',
        f'<td align="right">{mono("pulso semanal /")}</td></tr></table></td></tr>',
        f'<tr><td style="padding:14px 32px 28px">{rule}</td></tr>',
        f'<tr><td style="padding:0 32px">{mono(f"semana del {ddmm(week[0])} al {ddmm(week[1])}")}',
        f'<h1 style="margin:6px 0 14px;font-family:{Z["display"]};font-size:34px;line-height:1.08;'
        f'letter-spacing:-.03em;font-weight:700">{head}</h1><div style="line-height:2">{chips}</div></td></tr>',
        *(html_client(*c) for c in clients),
        f'<tr><td style="padding:36px 32px 8px">{rule}<p style="margin:14px 0 0;font-size:12px;color:{Z["mu"]}">',
        'Solo se revisan los eventos por los que optimizan las campañas con entrega en la semana. Se compara la última '
        'semana (martes a lunes) con las 4 anteriores, ajustando por clics. Google cuenta por fecha de conversión y los '
        'últimos días todavía pueden sumar. Revisión de solo lectura: no se modificó nada en las cuentas.</p></td></tr>',
        '</table></td></tr></table></body></html>',
    ])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("snapshots", nargs="+", type=Path)
    ap.add_argument("-o", "--out", type=Path)
    ap.add_argument("--html", type=Path, help="también guarda el mail en HTML con la estética de Zenda")
    args = ap.parse_args()

    blocks, clients, counts, week = [], [], {s: 0 for s in ORDER}, None
    for path in args.snapshots:
        snap = json.loads(path.read_text())
        week = snap["week"]
        prev = previous_alerts(path)
        items, text = render(snap, prev)
        for i in items:
            counts[i["status"]] += 1
        worst = min(ORDER.index(i["status"]) for i in items)
        blocks.append((worst, text))
        clients.append((worst, snap, items, prev))
    blocks.sort(key=lambda b: b[0])
    clients.sort(key=lambda c: c[0])

    alerts = counts["caida"] + counts["revisar"]
    subject = (f"Pulso semanal {ddmm(week[0])} al {ddmm(week[1])}: "
               + (f"{alerts} {'conversión para revisar' if alerts == 1 else 'conversiones para revisar'}"
                  if alerts else "todo en orden"))
    summary = " · ".join(f"{ICON[s]} {counts[s]} {LABEL[s]}" for s in ORDER if counts[s])
    mail = "\n\n".join([f"**Asunto:** {subject}", summary] + [t for _, t in blocks] + [
        "---",
        "Solo se revisan los eventos por los que optimizan las campañas con entrega en la semana. "
        "Se compara la última semana (martes a lunes) con las 4 anteriores, ajustando por clics. "
        "Google cuenta por fecha de conversión y los últimos días todavía pueden sumar.",
    ])
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(mail + "\n")
    if args.html:
        args.html.parent.mkdir(parents=True, exist_ok=True)
        args.html.write_text(render_html([c[1:] for c in clients], week, counts))
    print(mail)


if __name__ == "__main__":
    main()
