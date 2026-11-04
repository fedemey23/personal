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


def client_temperature(items):
    """Temperatura del cliente: qué parte de sus conversiones tiene alertas (rojo pesa 1, amarillo 0,5).

    Hasta 20% el cliente queda verde aunque tenga alguna alerta, hasta 50% amarillo, arriba rojo.
    Las conversiones sin lectura no cuentan.
    """
    readable = [i for i in items if i["level"] != "gris"]
    reds = sum(1 for i in readable if i["level"] == "rojo")
    yellows = sum(1 for i in readable if i["level"] == "amarillo")
    temp = (reds + 0.5 * yellows) / len(readable) if readable else 0
    level = "verde" if temp < 0.2 else "amarillo" if temp < 0.5 else "rojo"
    return {"level": level, "temp": round(temp, 3), "healthy": len(readable) - reds - yellows, "readable": len(readable)}


MIN_SPEND = 10_000      # debajo de esto una campaña sin resultados no se marca
JUMP_MIN = 100_000      # diferencia mínima para marcar un salto de inversión


def money(v):
    return "$" + miles(v)


def evaluate_campaign(c, account_cpa, account_spend):
    """Pestaña de inversión: gasto sin resultados, costo disparado o salto de inversión."""
    prev_spend, spend = c["spend"]
    prev_res, res = c["results"]
    weekly = prev_spend / c["prev_weeks"] if c["prev_weeks"] else 0
    own_cpa = prev_spend / prev_res if prev_res else None
    cpa = spend / res if res else None
    flags = []

    if c["kind"] == "conv" and not c["new"]:
        if res == 0 and spend >= MIN_SPEND:
            if prev_res == 0:
                flags.append(("rojo", "Gasta sin resultados",
                              f"Sin resultados en 5 semanas con {money(prev_spend + spend)} invertidos ({money(spend)} esta semana)."))
            elif spend >= 2 * own_cpa:
                flags.append(("rojo", "Gasta sin resultados",
                              f"{money(spend)} esta semana y ningún resultado; su costo habitual es {money(own_cpa)} por resultado."))
        if cpa and own_cpa and prev_res >= 3 and cpa >= 3 * own_cpa:
            flags.append(("amarillo", f"Costo por resultado ×{n(cpa / own_cpa)}",
                          f"{money(cpa)} por resultado esta semana contra {money(own_cpa)} de su historial "
                          f"({n(res)} resultados con {money(spend)})."))
    if not c["new"] and c["prev_weeks"] >= 2 and spend >= 2 * weekly and spend - weekly >= JUMP_MIN:
        context = ""
        if c["kind"] == "conv" and cpa and account_cpa and cpa >= 3 * account_cpa:
            context = (f" Es el {round(spend / account_spend * 100)}% de la inversión de la cuenta y cuesta "
                       f"{money(cpa)} por resultado, {n(cpa / account_cpa)} veces el promedio de la cuenta.")
        flags.append(("amarillo", f"Inversión ×{n(spend / weekly)}",
                      f"{money(spend)} esta semana contra {money(weekly)} por semana en las anteriores." + context))

    level = min((f[0] for f in flags), key=LEVELS.index, default="verde")
    return {"name": c["name"], "platform": PLATFORM[c["platform"]], "account": c["account"], "kind": c["kind"],
            "new": c["new"], "spend": spend, "results": res, "cpa": cpa, "own_cpa": own_cpa, "level": level,
            "flags": [{"level": f[0], "title": f[1], "why": f[2]} for f in flags]}


def delivery(snap):
    camps = snap.get("campaigns", [])
    by_account = {}
    for c in camps:
        a = by_account.setdefault(c["account"], {"spend": 0, "prev": 0, "res": 0})
        a["spend"] += c["spend"][1]
        if c["kind"] == "conv" and not c["new"]:
            a["prev"] += c["spend"][0]
            a["res"] += c["results"][0]
    items = []
    for c in camps:
        a = by_account[c["account"]]
        items.append(evaluate_campaign(c, a["prev"] / a["res"] if a["res"] else None, a["spend"]))
    items.sort(key=lambda i: (LEVELS.index(i["level"]), -i["spend"]))
    flagged = [i for i in items if i["level"] in ("rojo", "amarillo")]
    return {"items": items, "no_delivery": snap.get("no_delivery", []),
            "spend": sum(i["spend"] for i in items), "flagged_spend": sum(i["spend"] for i in flagged),
            "reds": sum(1 for i in flagged if i["level"] == "rojo"),
            "yellows": sum(1 for i in flagged if i["level"] == "amarillo")}


def summary(clients):
    """Resumen ejecutivo de la pestaña de conversiones: una frase y una línea por alerta."""
    readable = sum(c["readable"] for c in clients)
    healthy = sum(c["healthy"] for c in clients)
    alerts = [(c["client"], i) for c in clients for i in c["items"] if i["level"] in ("rojo", "amarillo")]
    reds = sum(1 for _, i in alerts if i["level"] == "rojo")
    yellows = len(alerts) - reds
    if not alerts:
        head = f"Todo en orden: las {readable} conversiones funcionan bien."
    else:
        parts = [p for p in (f"{reds} para revisar ya" if reds else "",
                             f"{yellows} con atención" if yellows else "") if p]
        head = f"{healthy} de {readable} conversiones funcionan bien. " + " y ".join(parts).capitalize() + "."
    alerts.sort(key=lambda a: LEVELS.index(a[1]["level"]))
    lines = [{"level": i["level"], "client": cl, "name": i["name"], "platform": i["platform"],
              "text": i["title"] + (" · causa conocida" if i.get("note", "") and "Causa conocida" in i["note"] else "")}
             for cl, i in alerts]
    return {"head": head, "lines": lines}


def delivery_summary(clients):
    reds = sum(c["delivery"]["reds"] for c in clients)
    yellows = sum(c["delivery"]["yellows"] for c in clients)
    spend = sum(c["delivery"]["spend"] for c in clients)
    flagged = sum(c["delivery"]["flagged_spend"] for c in clients)
    idle = sum(len(c["delivery"]["no_delivery"]) for c in clients)
    if not reds and not yellows:
        head = f"Sin alertas de inversión: {money(spend)} invertidos en la semana."
    else:
        head = (f"{money(flagged)} de {money(spend)} invertidos esta semana están en campañas con alertas "
                f"({round(flagged / spend * 100)}%).")
    return {"head": head, "idle": idle}


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
        clients.append({"client": snap["client"], **client_temperature(items), "items": items,
                        "delivery": delivery(snap)})
    clients.sort(key=lambda c: (-c["temp"], c["client"]))
    week_starts = json.loads(paths[0].read_text()).get("week_starts", [])
    return {"week": week, "week_starts": week_starts, "next": (date.fromisoformat(week[1]) + timedelta(days=8)).isoformat(),
            "clients": clients, "summary": summary(clients), "delivery_summary": delivery_summary(clients)}


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

    print(data["summary"]["head"])
    print(data["delivery_summary"]["head"])
    for c in data["clients"]:
        print(f"{c['client']}: {c['level']}")
        for i in c["delivery"]["items"]:
            if i["flags"]:
                print(f"  [{i['level']:>8}] {i['name']} · " + " / ".join(f["title"] for f in i["flags"]))


if __name__ == "__main__":
    main()
