---
name: pulso-semanal
description: Revisión semanal de solo lectura de las conversiones por las que optimizan las campañas de Google Ads y Meta de cada cliente en clients.json, para detectar caídas de medición o del sitio. Lee por SeePM, arma un snapshot y devuelve el mail semanal. Usar cuando pidan el pulso semanal, revisar si se rompió alguna conversión o correr el control de conversiones.
---

# Pulso semanal de conversiones

Solo lectura. Usar únicamente `list_accounts`, `brain_read`, `get_client_card` y `read_platform_data` de SeePM. Nunca `change_platform`, `run_seepm_change` ni `brain_write`: `.claude/settings.json` las bloquea igual.

## Alcance

Solo las conversiones **por las que optimizan las campañas con entrega en la semana**. Nada de pasos intermedios del embudo ni leads generales si la campaña optimiza por el calificado.

- **Meta:** el evento de `results` de cada campaña o conjunto con clics en la semana. Es exactamente lo que optimiza.
- **Google Ads:** las primarias cuya meta (categoría + origen) usan las campañas activas. Si en una misma meta hay varias primarias (por ejemplo "AR - Sellers - Lead" y "AR - Sellers - Lead Calificado"), quedarse con la que el brain del cliente marca como la que importa (en Pickit, la que dice "Calificado"). Anotar en `clients.json` qué acción se eligió por meta para no volver a decidirlo.

## Ventana

La semana va de martes a lunes y termina ayer. El mail compara esa semana contra las 4 anteriores, así que se leen 5 semanas.

## Lecturas por cuenta (presupuesto: 3 consultas en Google y 1 o 2 en Meta)

### Google Ads

1. Metas de las campañas activas:
   `SELECT campaign.id, campaign.name, campaign_conversion_goal.category, campaign_conversion_goal.origin FROM campaign_conversion_goal WHERE campaign.status = 'ENABLED' AND campaign_conversion_goal.biddable = TRUE`
   Si las metas no cambiaron respecto a `clients.json`, usar las acciones ya elegidas ahí. Si cambiaron, consultar las primarias (`conversion_action.primary_for_goal = TRUE`) y elegir de nuevo.
2. Conversiones diarias solo de las acciones elegidas (el segmento filtrado tiene que estar en el SELECT):
   `SELECT segments.date, segments.conversion_action, metrics.all_conversions_by_conversion_date FROM customer WHERE segments.date BETWEEN '<inicio>' AND '<ayer>' AND segments.conversion_action IN ('customers/<id>/conversionActions/<acción>', ...)`
3. Clics diarios de esas campañas:
   `SELECT segments.date, campaign.id, metrics.clicks FROM campaign WHERE segments.date BETWEEN '<inicio>' AND '<ayer>' AND campaign.id IN (...)`

Sumar por semana de martes a lunes. Los clics de cada acción son los de las campañas que la tienen como meta.

### Meta

1. `get_insights` sobre la cuenta, `level: "campaign"`, `time_range: {since: <inicio>, until: <ayer>}`, `time_increment: "7"`, `fields: "results,clicks"`. Con `since` en martes, cada fila es una semana. Agrupar por evento de `results`.
2. Solo si una campaña devuelve `indicator: "mixed"` (optimiza por eventos distintos en cada conjunto): repetir esa cuenta con `level: "adset"` para las 2 últimas semanas.

Si Meta limita la cuenta, no reintentar: armar el mail con lo que haya y decirlo en una línea.

## Salida

1. Guardar `data/<cliente>/<fecha de hoy>.json` con el formato del README (5 semanas por conversión; `since` si la campaña arrancó en las últimas 2 semanas).
2. `python3 pulso.py data/*/<fecha de hoy>.json -o ejemplos/ultimo-mail.md --html ejemplos/ultimo-mail.html` (la versión HTML tiene la estética de Zenda, para mandarla por un conector de correo)
3. Commit y push de `data/` en la rama de trabajo, para que la semana siguiente marque qué alertas son nuevas.
4. Responder **solo con el texto del mail** que imprime el script. Ese mensaje es el que llega por correo.
