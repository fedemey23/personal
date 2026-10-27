#!/usr/bin/env python3
"""Pulso de conversiones: calcula el estado de cada conversión principal y arma el panel.

Uso:
  python3 pulso.py data/<cliente>/<fecha>.json [más snapshots...] -o out/pulso.html

Lee snapshots (ver README.md para el formato), no se conecta a ninguna plataforma
y no modifica nada fuera del archivo de salida.
"""
import argparse
import json
from datetime import date
from pathlib import Path

RECENT_DAYS = 7
BASE_DAYS = 28
MIN_HISTORY = 7

ORDER = ["caida", "atencion", "ok", "nueva", "sin_senal", "sin_entrega"]
LABELS = {
    "caida": "Caída",
    "atencion": "Revisar",
    "ok": "OK",
    "nueva": "Nueva",
    "sin_senal": "Poco volumen",
    "sin_entrega": "Sin entrega",
}


def fmt_n(x):
    return f"{x:.1f}".rstrip("0").rstrip(".").replace(".", ",")


def fmt_date(iso):
    d = date.fromisoformat(iso)
    return f"{d.day:02d}/{d.month:02d}"


def first_active(conv, clicks, since_idx):
    if since_idx is not None:
        return since_idx
    for i, (c, k) in enumerate(zip(conv, clicks)):
        if c or k:
            return i
    return len(conv)


def evaluate(item, dates):
    conv, clicks = item["conv"], item["clicks"]
    n = len(dates)
    since_idx = dates.index(item["since"]) if item.get("since") in dates else None
    start = first_active(conv, clicks, since_idx)

    rec = range(max(start, n - RECENT_DAYS), n)
    base = range(max(start, n - RECENT_DAYS - BASE_DAYS), n - RECENT_DAYS)
    rec_conv = sum(conv[i] for i in rec)
    rec_clicks = sum(clicks[i] for i in rec)
    base_conv = sum(conv[i] for i in base)
    base_clicks = sum(clicks[i] for i in base)
    history_days = n - start

    last_idx = max((i for i, c in enumerate(conv) if c), default=None)
    if last_idx is not None:
        last_seen = dates[last_idx]
        silent = range(last_idx + 1, n)
    else:
        last_seen = item.get("last_seen")
        silent = range(start, n)
    silent_days = len(silent)
    silent_clicks = sum(clicks[i] for i in silent)

    cvr = base_conv / base_clicks if base_clicks else None
    weekly_base = base_conv / len(base) * 7 if len(base) else None

    stats = {
        "rec_conv": rec_conv,
        "rec_clicks": rec_clicks,
        "base_weekly": round(weekly_base, 1) if weekly_base is not None else None,
        "last_seen": last_seen,
        "silent_days": silent_days,
        "history_days": history_days,
    }

    def result(status, headline, detail):
        return {"status": status, "label": LABELS[status], "headline": headline, "detail": detail, **stats}

    if rec_clicks == 0:
        return result(
            "sin_entrega",
            "La campaña no está entregando",
            f"Sin clics en los últimos {RECENT_DAYS} días. Los conjuntos figuran activos pero no gastan, "
            "así que no hay nada que medir. No es un problema de medición.",
        )

    if history_days < MIN_HISTORY:
        return result(
            "nueva",
            f"Empezó el {fmt_date(dates[start])}",
            f"Lleva {history_days} {'día' if history_days == 1 else 'días'} con {sum(conv[start:])} conversiones. "
            "Hace falta una semana de historia para compararla.",
        )

    if base_conv == 0 and rec_conv == 0:
        last_txt = f"La última fue el {fmt_date(last_seen)}." if last_seen else ""
        if silent_clicks >= 100:
            return result(
                "atencion",
                f"{silent_days} días sin conversiones con tráfico",
                f"{silent_clicks} clics desde el {fmt_date(dates[start])} y ninguna conversión. " + (f"{last_txt} " if last_txt else "")
                + "Puede ser la campaña o la medición: "
                "conviene completar el formulario de prueba y ver si el evento llega.",
            )
        return result(
            "sin_senal",
            "Volumen demasiado bajo para evaluar",
            f"{silent_clicks} clics desde el {fmt_date(dates[start])} y ninguna conversión. {last_txt} "
            "Con tan poco tráfico un cero no indica una rotura.",
        )

    if cvr and silent_days:
        expected_silent = cvr * silent_clicks
        if expected_silent >= 4 or (expected_silent >= 2.5 and silent_days >= 3):
            status = "caida" if expected_silent >= 4 else "atencion"
            return result(
                status,
                f"{silent_days} días sin conversiones",
                f"Desde el {fmt_date(last_seen)} hubo {silent_clicks} clics y ninguna conversión. "
                f"Con su tasa habitual se esperaban unas {fmt_n(expected_silent)}. "
                "Si el tráfico sigue normal, revisar el tag o el formulario.",
            )

    if cvr:
        expected_rec = cvr * rec_clicks
        if expected_rec >= 5:
            ratio = rec_conv / expected_rec
            if ratio < 0.6:
                status = "caida" if ratio < 0.4 else "atencion"
                return result(
                    status,
                    f"Convierte {round((1 - ratio) * 100)}% menos de lo esperado",
                    f"{rec_conv} conversiones en los últimos {RECENT_DAYS} días con {rec_clicks} clics. "
                    f"Con su tasa habitual se esperaban unas {fmt_n(expected_rec)}.",
                )

    if weekly_base is not None and weekly_base < 1 and rec_conv == 0:
        return result(
            "sin_senal",
            "Convierte menos de una vez por semana",
            f"Última conversión el {fmt_date(last_seen)}, con {silent_clicks} clics desde entonces. "
            "Con este volumen una semana en cero es normal.",
        )

    base_clicks_weekly = base_clicks / len(base) * 7 if len(base) else 0
    if weekly_base and rec_conv < 0.6 * weekly_base and rec_clicks < 0.7 * base_clicks_weekly:
        return result(
            "ok",
            "Bajó junto con el tráfico",
            f"{rec_conv} esta semana contra {fmt_n(weekly_base)} por semana antes, pero los clics también bajaron "
            f"({rec_clicks} contra {round(base_clicks_weekly)}). La medición acompaña al tráfico.",
        )

    return result(
        "ok",
        "En línea con su historial",
        f"{rec_conv} en los últimos {RECENT_DAYS} días contra {fmt_n(weekly_base)} por semana en las 4 anteriores"
        + (f". Última el {fmt_date(last_seen)}." if last_seen else "."),
    )


def build(snapshots):
    clients = []
    for snap in snapshots:
        dates = snap["dates"]
        items = []
        for item in snap["conversions"]:
            ev = evaluate(item, dates)
            items.append({k: item.get(k) for k in
                          ("id", "name", "group", "why", "platform", "account_id", "account_name", "since")}
                         | {"conv": item["conv"], "clicks": item["clicks"]} | ev)
        items.sort(key=lambda x: (ORDER.index(x["status"]), x["platform"], x["group"]))
        counts = {s: sum(1 for i in items if i["status"] == s) for s in ORDER}
        clients.append({
            "client": snap["client"],
            "ref_date": snap["ref_date"],
            "generated_at": snap.get("generated_at"),
            "dates": dates,
            "notes": snap.get("notes", []),
            "counts": counts,
            "worst": next(s for s in ORDER if counts[s]) if items else "ok",
            "items": items,
        })
    clients.sort(key=lambda c: (ORDER.index(c["worst"]), c["client"]))
    return {"clients": clients, "labels": LABELS, "order": ORDER}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("snapshots", nargs="+", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("out/pulso.html"))
    ap.add_argument("--template", type=Path, default=Path(__file__).with_name("template.html"))
    args = ap.parse_args()

    data = build([json.loads(p.read_text()) for p in args.snapshots])
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = args.template.read_text().replace("/*__PULSO_DATA__*/null", payload)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html)

    for c in data["clients"]:
        print(f"{c['client']} ({c['ref_date']}):")
        for i in c["items"]:
            print(f"  [{i['label']:>12}] {i['name']} · {i['headline']}")


if __name__ == "__main__":
    main()
