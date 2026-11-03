#!/usr/bin/env python3
"""Auditoría semanal de conversiones: arma el termómetro de cada cliente.

Uso:
  python3 pulso.py data/<cliente>/<fecha>.json [más clientes...] -o out/auditoria.html

Cada snapshot trae 5 semanas por conversión (4 de referencia + la última) y, si se
leyó, el detalle diario de la última semana. No se conecta a ninguna plataforma.
"""
import argparse
import json
from datetime import date, timedelta
from pathlib import Path

LEVELS = ["rojo", "amarillo", "verde", "gris"]
PLATFORM = {"google_ads": "Google Ads", "meta_ads": "Meta"}
HERE = Path(__file__).parent


def n(x):
    return f"{x:.1f}".rstrip("0").rstrip(".").replace(".", ",")


def miles(k):
    return f"{round(k):,}".replace(",", ".")


def ddmm(iso):
    d = date.fromisoformat(iso)
    return f"{d.day:02d}/{d.month:02d}"


def evaluate(item, week_start):
    """Devuelve el nivel del termómetro y una explicación corta."""
    conv, clicks = item["weeks"], item["clicks"]
    last, last_clicks = conv[-1], clicks[-1]
    base = [(c, k) for c, k in zip(conv[:-1], clicks[:-1]) if k]
    base_conv = sum(c for c, _ in base)
    base_clicks = sum(k for _, k in base)
    weekly = base_conv / len(base) if base else 0
    cvr = base_conv / base_clicks if base_clicks else None
    since = item.get("since")
    recent = bool(since) and date.fromisoformat(since) > week_start - timedelta(days=7)

    def res(level, title, why):
        return {"level": level, "title": title, "why": why, "weekly": round(weekly, 1), "recent": recent,
                "prev": conv[-2]}

    if last == 0:
        if base_conv == 0:
            total = base_clicks + last_clicks
            if total >= 100:
                return res("rojo", "En cero con tráfico",
                           f"Ninguna conversión en 5 semanas con {miles(total)} clics. Revisar si el evento se "
                           "dispara: completar el formulario o el flujo y ver si llega.")
            return res("gris", "Sin lectura", f"Sin conversiones, pero con solo {miles(total)} clics en 5 semanas.")
        expected = cvr * last_clicks if cvr else 0
        if expected >= 2.5:
            return res("rojo", "En cero esta semana",
                       f"Cero conversiones con {miles(last_clicks)} clics; con su tasa habitual se esperaban "
                       f"unas {n(expected)}. Revisar el tag o el formulario.")
        return res("gris", "Sin lectura", f"Cero esta semana, pero con su volumen se esperaban menos de 3 "
                                          f"({n(weekly)} por semana de promedio).")

    daily = item.get("daily")
    if daily:
        c4, k4 = sum(daily["conv"][:4]), sum(daily["clicks"][:4])
        c3, k3 = sum(daily["conv"][4:]), sum(daily["clicks"][4:])
        expected3 = c4 / k4 * k3 if k4 else 0
        if expected3 >= 10 and c3 < 0.4 * expected3:
            return res("amarillo", "Cayó en los últimos 3 días",
                       f"Venía en {miles(c4 / 4)} por día y en los últimos 3 días bajó a {miles(c3 / 3)}, "
                       f"con los clics estables ({miles(k4 / 4)} → {miles(k3 / 3)} por día). Puede ser demora en "
                       "el reporte del evento o una rotura: si sigue así el miércoles, revisar.")

    if not recent and cvr:
        expected = cvr * last_clicks
        if expected >= 5 and last / expected < 0.6:
            return res("amarillo", f"{round((1 - last / expected) * 100)}% debajo de lo esperado",
                       f"{miles(last)} conversiones con {miles(last_clicks)} clics; con su tasa habitual se "
                       f"esperaban unas {n(expected)}.")

    if recent:
        return res("verde", "Nueva y midiendo",
                   f"Arrancó el {ddmm(since)}. {miles(last)} conversiones con {miles(last_clicks)} clics esta "
                   "semana; desde la próxima se compara con su historial.")
    return res("verde", "En línea", f"{miles(last)} esta semana contra {n(weekly)} de promedio.")


def build(paths):
    clients, week = [], None
    for path in paths:
        snap = json.loads(path.read_text())
        week = snap["week"]
        start = date.fromisoformat(week[0])
        items = [{"name": i["name"], "platform": PLATFORM[i["platform"]], "group": i["group"],
                  "campaigns": i["campaigns"], "weeks": i["weeks"], "clicks": i["clicks"], "note": i.get("note"),
                  **evaluate(i, start)}
                 for i in snap["conversions"]]
        items.sort(key=lambda i: (LEVELS.index(i["level"]), i["platform"], i["group"]))
        clients.append({"client": snap["client"], "level": items[0]["level"], "items": items})
    clients.sort(key=lambda c: (LEVELS.index(c["level"]), c["client"]))
    week_starts = json.loads(paths[0].read_text()).get("week_starts", [])
    return {"week": week, "week_starts": week_starts, "next": (date.fromisoformat(week[1]) + timedelta(days=8)).isoformat(),
            "clients": clients}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("snapshots", nargs="+", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("out/auditoria.html"))
    args = ap.parse_args()

    data = build(args.snapshots)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = ((HERE / "template.html").read_text()
            .replace("/*__FONTS__*/", (HERE / "assets/zenda-fonts.css").read_text())
            .replace("/*__DATA__*/null", payload))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html)

    for c in data["clients"]:
        print(f"{c['client']}: {c['level']}")
        for i in c["items"]:
            print(f"  [{i['level']:>8}] {i['name']} · {i['title']}")


if __name__ == "__main__":
    main()
