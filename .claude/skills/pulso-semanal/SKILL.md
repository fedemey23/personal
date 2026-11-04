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

## Pestaña Inversión y entrega (por cuenta)

- **Google Ads:** tres consultas por cuenta, todas con `campaign.status = 'ENABLED'` (sin segmentar por fecha, así también vuelven las campañas con cero impresiones):
  1. Última semana: `campaign.id, campaign.name, campaign.advertising_channel_type, metrics.cost_micros, metrics.impressions, metrics.conversions`.
  2. Las 4 semanas anteriores: `campaign.id, metrics.cost_micros, metrics.conversions`.
  3. Semanas con gasto en esas 4 semanas: `segments.week, campaign.id, metrics.cost_micros` con `metrics.cost_micros > 0`. Sirve para no comparar contra un promedio inflado en campañas nuevas.
- **Meta:** la misma llamada semanal a nivel campaña de la pestaña de conversiones, sumando `spend,impressions` a los `fields`. Para las activas sin entrega: `graph_api_request` GET `act_<id>/adsets` con `filtering` `effective_status IN [ACTIVE]` y `fields=id,name,campaign{name}`; las campañas con conjuntos activos y sin impresiones en la semana van a `no_delivery`.
- Guardar en el snapshot `campaigns` (nombre, plataforma, cuenta, `kind` `conv` o `awareness`, `spend` y `results` como [4 semanas previas, semana], `prev_weeks`, `new`) y `no_delivery`. Alcance, tráfico, video, interacciones y teasers van como `awareness`.
- Ojo: `campaign_conversion_goal` solo devuelve las campañas con metas propias. Las que usan las metas de la cuenta (por ejemplo Hogar, Moto y Salud Segura Max en Sancor Productos) también optimizan por las primarias de la cuenta: revisarlas en la pestaña de conversiones.

## Salida

1. Guardar `data/<cliente>/<fecha de hoy>.json` con el formato del README (5 semanas por conversión, `daily` de la última semana si se leyó, `since` si la campaña arrancó en las últimas 2 semanas).
2. `python3 pulso.py data/*/<fecha de hoy>.json -o out/auditoria.html`
3. Republicar `out/auditoria.html` en el mismo artifact, https://claude.ai/artifact/BVkicQTuAconfx5Qs7pnj2 (pasar esa URL como `url`; no crear uno nuevo).
4. Commit y push de `data/` en la rama de trabajo.
5. Responder con una línea por cliente: su color y, si no es verde, qué conversión lo explica.
