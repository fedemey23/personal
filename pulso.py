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


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("snapshots", nargs="+", type=Path)
    ap.add_argument("-o", "--out", type=Path)
    args = ap.parse_args()

    blocks, counts, week = [], {s: 0 for s in ORDER}, None
    for path in args.snapshots:
        snap = json.loads(path.read_text())
        week = snap["week"]
        items, text = render(snap, previous_alerts(path))
        for i in items:
            counts[i["status"]] += 1
        blocks.append((min(ORDER.index(i["status"]) for i in items), text))
    blocks.sort(key=lambda b: b[0])

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
    print(mail)


if __name__ == "__main__":
    main()
