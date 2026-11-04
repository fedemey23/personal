# Auditoría semanal de conversiones

Revisión semanal de solo lectura de las conversiones por las que optimizan las campañas de Google Ads y Meta, separada por cliente. Sirve para detectar caídas de medición o del sitio sin revisar las cuentas todos los días.

No ejecuta cambios en las cuentas. Lee los datos a través de SeePM y actualiza una página con un termómetro por cliente: [Termómetro de conversiones](https://claude.ai/artifact/BVkicQTuAconfx5Qs7pnj2).

## Cómo funciona

1. **Lectura**: la skill [`termometro-conversiones`](.claude/skills/termometro-conversiones/SKILL.md) recorre los clientes de `clients.json`, toma solo los eventos de optimización de las campañas con entrega (o los que el equipo fijó para ese cliente) y baja 5 semanas de conversiones y clics, más el detalle diario de la última. Guarda un snapshot en `data/<cliente>/<fecha>.json`.
2. **Termómetro** (`pulso.py` + `template.html`, sin dependencias): evalúa cada conversión y arma `out/auditoria.html` con la estética de Zenda (tipografías en `assets/zenda-fonts.css`). La skill la republica en el mismo artifact todos los martes.

```bash
python3 pulso.py data/pickit/2026-11-03.json data/banco-del-sol/2026-11-03.json -o out/auditoria.html
```

## Colores

| Color | Cuándo |
|---|---|
| Rojo · revisar ya | En cero esta semana cuando con sus clics se esperaban 2,5 o más, o sin ninguna conversión en 5 semanas con 100 clics o más. |
| Amarillo · atención | Menos del 60% de lo esperado para su tráfico, o una caída fuerte en los últimos 3 días con los clics estables. |
| Verde · todo bien | En línea con su historial, o nueva y registrando conversiones. |
| Gris · sin lectura | Convierte tan poco que un cero no indica nada. |

"Lo esperado" es la tasa de conversión sobre clics de las 4 semanas anteriores aplicada a los clics de la última. Así una baja de tráfico no se confunde con una rotura de medición. El termómetro de cada cliente mide qué parte de sus conversiones tiene alertas (rojo cuenta 1, amarillo 0,5; las grises no cuentan): hasta 20% queda en bien, hasta 50% en atención y arriba en crítico. Cada conversión muestra su plataforma.

## Pods

La página tiene una pestaña por pod (Ari - Milly y Mate - Lu), cada una con un resumen ejecutivo de una frase y una línea por alerta. El pod de cada cliente se define en `clients.json` y viaja en el campo `pod` del snapshot.

Cuando el tráfico de la semana más que duplica el habitual (por ejemplo, un Cyber), la tasa de conversión deja de ser comparable y el termómetro compara el volumen bruto.

## Formato del snapshot

```json
{
  "client": "Pickit",
  "week": ["2026-10-27", "2026-11-02"],
  "conversions": [
    {
      "id": "gads:7732517673",
      "name": "AR - Sellers - Lead Calificado",
      "label": "Lead calificado de sellers · Argentina",
      "platform": "google_ads",
      "account_id": "6727245662",
      "group": "B2B Sellers AR",
      "pod": "Ari - Milly",
      "campaigns": ["AR_Flex_SameDay"],
      "weeks": [3, 0, 4, 5, 4],
      "clicks": [422, 119, 267, 448, 218],
      "daily": {"conv": [1, 0, 0, 2, 0, 0, 1], "clicks": [44, 34, 33, 31, 33, 32, 21]},
      "since": "2026-10-26",
      "last_seen": "2026-09-10"
    }
  ]
}
```

`weeks` y `clicks` van de la semana más vieja a la última. `daily` (conversiones y clics por día de la última semana), `since` (inicio de la campaña, si es reciente) y `last_seen` (última conversión antes de la ventana) son opcionales.

## Solo lectura

`.claude/settings.json` bloquea todas las herramientas de SeePM que escriben (cambios en plataformas, brain, clientes, alertas). Cualquier sesión de Claude que trabaje en este repo queda limitada a leer.

## Agregar un cliente

Sumarlo a `clients.json` con su id de SeePM y las cuentas a revisar. La skill lo toma desde la próxima corrida.
