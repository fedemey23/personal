# Pulso de conversiones

Revisión semanal de solo lectura de las conversiones por las que optimizan las campañas de Google Ads y Meta, separada por cliente. Sirve para detectar caídas de medición o del sitio sin revisar las cuentas todos los días.

No ejecuta cambios en las cuentas. Lee los datos a través de SeePM y devuelve un mail.

## Cómo funciona

1. **Lectura**: la skill [`pulso-semanal`](.claude/skills/pulso-semanal/SKILL.md) recorre los clientes de `clients.json`, toma solo los eventos de optimización de las campañas con entrega y baja 5 semanas de conversiones y clics. Son unas 3 consultas por cuenta de Google y 1 o 2 por cuenta de Meta. Guarda un snapshot en `data/<cliente>/<fecha>.json`.
2. **Evaluación y mail** (`pulso.py`, sin dependencias): compara la última semana con las 4 anteriores ajustando por clics y arma el mail. Si hay un snapshot de la semana anterior, marca qué alertas son nuevas.

```bash
python3 pulso.py data/pickit/2026-11-03.json
```

Ejemplo de salida: [ejemplos/mail-2026-11-03.md](ejemplos/mail-2026-11-03.md).

## Estados

| Estado | Cuándo |
|---|---|
| 🔴 Caída | Con los clics de la semana se esperaban 4 o más conversiones y llegaron cero, o llegó menos del 40% de lo esperado. |
| 🟡 Revisar | Lo mismo con umbrales más bajos, o un evento sin ninguna conversión en 5 semanas con 100 clics o más. |
| 🟢 OK | En línea con su tasa habitual. |
| 🔵 Nueva | La campaña arrancó en las últimas 2 semanas. |
| ⚪ Poco volumen | Convierte tan poco que una semana en cero no indica nada. |

"Lo esperado" es la tasa de conversión sobre clics de las 4 semanas anteriores aplicada a los clics de la última. Así una baja de tráfico no se confunde con una rotura de medición.

## Formato del snapshot

```json
{
  "client": "Pickit",
  "week": ["2026-10-27", "2026-11-02"],
  "conversions": [
    {
      "id": "gads:7732517673",
      "name": "AR - Sellers - Lead Calificado",
      "platform": "google_ads",
      "account_id": "6727245662",
      "group": "B2B Sellers AR",
      "campaigns": ["AR_Flex_SameDay"],
      "weeks": [3, 0, 4, 5, 4],
      "clicks": [422, 119, 267, 448, 218],
      "since": "2026-10-26",
      "last_seen": "2026-09-10"
    }
  ]
}
```

`weeks` y `clicks` van de la semana más vieja a la última. `since` (inicio de la campaña, si es reciente) y `last_seen` (última conversión antes de la ventana) son opcionales.

## Solo lectura

`.claude/settings.json` bloquea todas las herramientas de SeePM que escriben (cambios en plataformas, brain, clientes, alertas). Cualquier sesión de Claude que trabaje en este repo queda limitada a leer.

## Agregar un cliente

Sumarlo a `clients.json` con su id de SeePM y las cuentas a revisar. La skill lo toma desde la próxima corrida.
