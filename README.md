# Pulso de conversiones

Monitor de solo lectura para detectar caídas en la medición (o en el sitio) de las conversiones principales de Google Ads y Meta, separado por cliente.

No ejecuta cambios en las cuentas. Lee los datos a través de SeePM, calcula un estado por conversión y arma un panel HTML.

## Cómo funciona

1. **Lectura** (la hace Claude con SeePM, ver [RUTINA.md](RUTINA.md)): por cada cliente de `clients.json` detecta las conversiones principales y baja 38 días de conversiones y clics por día. El resultado es un snapshot en `data/<cliente>/<fecha>.json`.
2. **Cálculo** (`pulso.py`, sin dependencias): compara los últimos 7 días con las 4 semanas anteriores, teniendo en cuenta el tráfico.
3. **Panel** (`template.html` → `out/pulso.html`): estado, explicación y gráfico de actividad diaria de cada conversión.

```bash
python3 pulso.py data/pickit/2026-10-26.json -o out/pulso.html
```

## Qué es una conversión principal

- **Google Ads:** acción primaria cuya meta (categoría + origen) usan para ofertar las campañas activas.
- **Meta:** evento de optimización de los conjuntos de anuncios activos.

## Estados

| Estado | Cuándo |
|---|---|
| Caída | Con el tráfico que hubo se esperaban 4 o más conversiones y llegaron cero, o llegó menos del 40% de lo esperado. |
| Revisar | Lo mismo con umbrales más bajos, o un evento que nunca se registró con 100 clics o más. |
| OK | En línea con su tasa habitual, o bajó en la misma proporción que el tráfico. |
| Nueva | Menos de 7 días de historia. |
| Poco volumen | Convierte tan poco que un cero no indica nada. |
| Sin entrega | La campaña figura activa pero no tuvo clics en 7 días. |

"Lo esperado" es la tasa de conversión sobre clics de las 4 semanas anteriores aplicada a los clics de los días evaluados. Así, una baja de tráfico no se confunde con una rotura de medición.

## Formato del snapshot

```json
{
  "client": "Pickit",
  "ref_date": "2026-10-26",
  "dates": ["2026-09-19", "...", "2026-10-26"],
  "notes": ["texto libre que se muestra bajo el cliente"],
  "conversions": [
    {
      "id": "7732517673",
      "name": "AR - Sellers - Lead Calificado",
      "platform": "google_ads",
      "account_id": "6727245662",
      "account_name": "Pickit - AR",
      "group": "B2B Sellers · AR",
      "why": "por qué es principal",
      "since": "2026-10-06",
      "last_seen": "2026-09-10",
      "conv": [0, 1, 0],
      "clicks": [40, 52, 38]
    }
  ]
}
```

`conv` y `clicks` van alineados con `dates`. `since` (fecha de inicio de la campaña, si empezó dentro de la ventana) y `last_seen` (última conversión conocida antes de la ventana) son opcionales.

## Solo lectura

`.claude/settings.json` bloquea todas las herramientas de SeePM que escriben (cambios en plataformas, brain, clientes, alertas). Cualquier sesión de Claude que trabaje en este repo queda limitada a leer.

## Agregar un cliente

Sumarlo a `clients.json` con su id de SeePM y las cuentas a monitorear. La rutina diaria lo toma desde la próxima corrida.
