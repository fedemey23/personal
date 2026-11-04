---
name: pulso-semanal
description: Revisión semanal de solo lectura de las conversiones por las que optimizan las campañas de Google Ads y Meta de cada cliente en clients.json, para detectar caídas de medición o del sitio. Lee por SeePM, arma un snapshot y actualiza el termómetro de conversiones (artifact). Usar cuando pidan la auditoría semanal, el termómetro, revisar si se rompió alguna conversión o correr el control de conversiones.
---

# Auditoría semanal de conversiones

Solo lectura. Usar únicamente `list_accounts`, `brain_read`, `get_client_card` y `read_platform_data` de SeePM. Nunca `change_platform`, `run_seepm_change` ni `brain_write`: `.claude/settings.json` las bloquea igual.

## Alcance

Solo las conversiones **por las que optimizan las campañas con entrega en la semana**. Nada de pasos intermedios del embudo ni leads generales si la campaña optimiza por el calificado.

- **Meta:** el evento de `results` de cada campaña o conjunto con clics en la semana. Es exactamente lo que optimiza.
- **Conversiones fijadas por el equipo:** si el cliente tiene `conversions` en `clients.json` (por ejemplo Banco del Sol), revisar exactamente esas y no buscar otras.
- **Google Ads:** las primarias cuya meta (categoría + origen) usan las campañas activas. Si en una misma meta hay varias primarias (por ejemplo "AR - Sellers - Lead" y "AR - Sellers - Lead Calificado"), quedarse con la que el brain del cliente marca como la que importa (en Pickit, la que dice "Calificado"). Anotar en `clients.json` qué acción se eligió por meta para no volver a decidirlo.

## Ventana

La semana va de martes a lunes y termina ayer. El termómetro compara esa semana contra las 4 anteriores, así que se leen 5 semanas. Además guarda el detalle diario de la última semana (conversiones y clics), que sirve para detectar caídas de los últimos 3 días.

## Lecturas por cuenta (presupuesto: 3 consultas en Google y 1 o 2 en Meta)

### Google Ads

Forma recomendada (detecta también las campañas que usan las metas generales de la cuenta):

- `SELECT segments.date, segments.conversion_action_name, metrics.conversions FROM customer WHERE segments.date BETWEEN '<inicio>' AND '<ayer>' AND metrics.conversions > 0`. `metrics.conversions` solo cuenta las acciones por las que ofertan las campañas: esas son las candidatas. Si hay varias del mismo embudo (Lead y Apertura Completada, Compra y Page view), quedarse con la del final, como indica `clients.json`.
- Clics diarios de la cuenta: `SELECT segments.date, metrics.clicks FROM customer WHERE segments.date BETWEEN '<inicio>' AND '<ayer>'`.

Forma anterior, usada en Pickit, Banco del Sol y Sancor (puede dejar afuera campañas sin metas propias):

1. Metas de las campañas activas:
   `SELECT campaign.id, campaign.name, campaign_conversion_goal.category, campaign_conversion_goal.origin FROM campaign_conversion_goal WHERE campaign.status = 'ENABLED' AND campaign_conversion_goal.biddable = TRUE`
   Si las metas no cambiaron respecto a `clients.json`, usar las acciones ya elegidas ahí. Si cambiaron, consultar las primarias (`conversion_action.primary_for_goal = TRUE`) y elegir de nuevo.
2. Conversiones diarias solo de las acciones elegidas (el segmento filtrado tiene que estar en el SELECT):
   `SELECT segments.date, segments.conversion_action, metrics.all_conversions_by_conversion_date FROM customer WHERE segments.date BETWEEN '<inicio>' AND '<ayer>' AND segments.conversion_action IN ('customers/<id>/conversionActions/<acción>', ...)`
   Si las acciones las administra otro MCC (Banco del Sol), el resource name no sirve: filtrar con `segments.conversion_action_name LIKE '%...%'` como indica `clients.json`.
3. Clics diarios de esas campañas:
   `SELECT segments.date, campaign.id, metrics.clicks FROM campaign WHERE segments.date BETWEEN '<inicio>' AND '<ayer>' AND campaign.id IN (...)`

Sumar por semana de martes a lunes. Los clics de cada acción son los de las campañas que la tienen como meta.

### Meta

1. `get_insights` sobre la cuenta, `level: "campaign"`, `time_range: {since: <inicio>, until: <ayer>}`, `time_increment: "7"`, `fields: "results,clicks"`. Con `since` en martes, cada fila es una semana. Agrupar por evento de `results`.
2. Detalle diario de la última semana: la misma llamada a nivel campaña con `time_range` de los últimos 7 días y `time_increment: "1"`, solo para las campañas con conversiones de optimización.
3. Solo si una campaña devuelve `indicator: "mixed"` (optimiza por eventos distintos en cada conjunto): repetir esa cuenta con `level: "adset"` para las 2 últimas semanas.

Si Meta limita la cuenta, no reintentar: armar el termómetro con lo que haya y anotarlo en la respuesta.

## Pods

Cada cliente de `clients.json` tiene un `pod` y el snapshot lo lleva en `pod`. El termómetro arma una pestaña por pod, con su resumen ejecutivo:
- **Ari - Milly:** Banco del Sol, Sancor Seguros (con Prevención Salud y Prevención Retiro), Pickit y Chubb.
- **Mate - Lu:** PPI, Tai Loy y Almarena.

## Salida

1. Guardar `data/<cliente>/<fecha de hoy>.json` con el formato del README (5 semanas por conversión, `daily` de la última semana si se leyó, `since` si la campaña arrancó en las últimas 2 semanas).
2. `python3 pulso.py data/*/<fecha de hoy>.json -o out/auditoria.html`
3. Republicar `out/auditoria.html` en el mismo artifact, https://claude.ai/artifact/BVkicQTuAconfx5Qs7pnj2 (pasar esa URL como `url`; no crear uno nuevo).
4. Commit y push de `data/` en la rama de trabajo.
5. Responder con una línea por cliente: su color y, si no es verde, qué conversión lo explica.
