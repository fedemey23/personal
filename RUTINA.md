# Rutina diaria del Pulso

Instrucciones para la sesión de Claude que corre el Pulso cada mañana. Se usan como prompt de la tarea programada.

**Regla principal: solo lectura.** Usar únicamente `list_clients`, `list_accounts`, `brain_read`, `list_platform_tools` y `read_platform_data` de SeePM. Nunca `change_platform`, `run_seepm_change` ni `brain_write`. El archivo `.claude/settings.json` las bloquea igual.

## Pasos por cliente (`clients.json`)

Ventana: desde 38 días antes de ayer hasta ayer (zona horaria de la cuenta).

### Google Ads (por cuenta)

1. Metas que usan las campañas activas:
   ```sql
   SELECT campaign.id, campaign.name, campaign_conversion_goal.category, campaign_conversion_goal.origin
   FROM campaign_conversion_goal
   WHERE campaign.status = 'ENABLED' AND campaign_conversion_goal.biddable = TRUE
   ```
2. Acciones primarias habilitadas:
   ```sql
   SELECT conversion_action.id, conversion_action.name, conversion_action.category, conversion_action.type
   FROM conversion_action
   WHERE conversion_action.status = 'ENABLED' AND conversion_action.primary_for_goal = TRUE
   ```
   Conversión principal = primaria cuya categoría y origen (WEBPAGE ↔ WEBSITE) coinciden con una meta del paso 1. Sus clics son los de las campañas que tienen esa meta.
3. Conversiones por día y acción (por fecha de conversión):
   ```sql
   SELECT segments.date, segments.conversion_action, metrics.all_conversions_by_conversion_date
   FROM customer WHERE segments.date BETWEEN '<desde>' AND '<hasta>'
   ```
4. Clics por día y campaña:
   ```sql
   SELECT segments.date, campaign.id, metrics.clicks FROM campaign
   WHERE segments.date BETWEEN '<desde>' AND '<hasta>' AND metrics.clicks > 0
   ```

### Meta (por cuenta)

1. `get_insights` con `level: "adset"`, `time_range: "last_7d"`, `fields: "results,clicks"`. El campo `results` trae el evento de optimización de cada conjunto (por ejemplo `offsite_conversion.fb_pixel_custom.lead_calificado_puntos_ar`). Cada evento distinto es una conversión principal.
2. Para cada campaña que optimiza por ese evento: `get_insights` con `object_id` de la campaña, `time_increment: "1"`, `fields: "results,clicks"` y la ventana completa. Una llamada por campaña es más compacta que pedir todo el nivel adset por día.
3. Sumar por evento. Si una campaña empezó dentro de la ventana, poner su primer día en `since`.

Meta limita las consultas por cuenta. No repetir llamadas; si una cuenta queda limitada, armar el snapshot con lo que haya y dejarlo anotado en `notes`.

## Salida

1. Guardar `data/<slug>/<fecha>.json` con el formato del README.
2. `python3 pulso.py data/*/<fecha>.json -o out/pulso.html`
3. Republicar `out/pulso.html` en el mismo Artifact (no crear uno nuevo).
4. Commit y push de `data/` en la rama de trabajo.
5. Si algún cliente tiene una conversión en **Caída** o **Revisar** que ayer no tenía, mencionarlo en el resumen final de la corrida (es lo que llega por mail).
