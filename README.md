# Monitor matinal de tráfico: Pozuelo → Calle Xaudaró

Proyecto Python listo para GitHub Actions que mide **siempre el mismo trazado** entre:

- **Origen:** Calle Zaragoza, 11, 28223 Pozuelo de Alarcón, Madrid
- **Destino:** Calle Xaudaró, 25, Madrid

## Qué hace

Cada mañana toma catas a las **06:30, 06:40, 06:50, 07:00, 07:10, 07:20 y 07:30** (zona `Europe/Madrid`).

- 06:30, 06:40 y 06:50 alimentan la tendencia inicial.
- Desde las **06:50** manda un email cada 10 minutos.
- En cada email muestra:
  - tiempo de viaje medido en ese momento;
  - **estimación del tiempo si sales a las 07:00**;
  - retraso por tráfico;
  - gradiente de empeoramiento;
  - tabla con todas las catas acumuladas de esa mañana.
- A las 07:00, la estimación de las 07:00 pasa a ser el valor observado real. Los emails de 07:10–07:30 conservan ese dato y siguen mostrando cómo evoluciona el tráfico actual.
- Guarda CSV y JSON diarios en `output/` para poder analizar históricos después.

## Gradiente

Se calcula con la pendiente de las últimas tres catas, expresada como **minutos adicionales de viaje por cada 10 minutos de reloj**:

| Pendiente | Estado |
|---|---|
| ≤ +0,5 min/10 min | estable |
| > +0,5 y ≤ +1,5 | creciente moderado |
| > +1,5 y ≤ +3,0 | creciente rápido |
| > +3,0 | creciente extremo |

Los umbrales son configurables por variables de entorno.

## Por qué TomTom

La API de Routing permite guardar la polilínea de una ruta y después reconstruirla. Este proyecto crea una **ruta de referencia** una sola vez y las catas posteriores recalculan el tiempo sobre esa geometría usando `reconstructionMode=strict`, evitando que el motor cambie a otra alternativa cuando aparece tráfico.

## 1. Crear la API key de TomTom y la ruta fija (solo una vez)

1. Entra en el **TomTom Developer Portal** y crea/inicia sesión en una cuenta personal.
2. Abre **Dashboard** y crea una clave con **Add New Key** (en algunas cuentas TomTom ya muestra una primera clave en el Dashboard).
3. Asegúrate de que la clave tenga acceso a **Routing API** y **Search API**: el proyecto usa Search para geocodificar las direcciones y Routing para medir/reconstruir el trayecto.
4. Copia la clave. No la subas nunca a Git.

Después exporta la clave y genera la ruta de referencia:

```bash
export TOMTOM_API_KEY="PEGA_AQUI_TU_CLAVE_TOMTOM"
export DRY_RUN=true
python -m pip install -r requirements.txt
python -m commute_monitor.reference_route
```

Se generará:

```text
state/reference_route.json
```

**Commit ese fichero al repositorio.** A partir de ahí todos los días se comparará el mismo trazado. Si quieres fijar otra ruta, borra/regenera ese archivo en el momento en que TomTom esté eligiendo el recorrido que quieres conservar.

## 2. Probar una medición local

```bash
cp .env.example .env
# Carga las variables de .env con tu método preferido o expórtalas en la shell.
python -m commute_monitor --once
```

Para probar también el email, usa `--send`. Con `DRY_RUN=true` el correo se imprime y no se envía.

## 3. Gmail ya configurado para este proyecto

El proyecto queda preconfigurado con:

```text
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USERNAME=javier.garrido.pino@gmail.com
SMTP_FROM=javier.garrido.pino@gmail.com
EMAIL_TO=javier.garrido.pino@gmail.com
SMTP_STARTTLS=false
```

El puerto 465 usa SMTP sobre SSL. La contraseña normal de Gmail **no debe utilizarse**. Para este script crea una **contraseña de aplicación** de Google:

1. En tu cuenta de Google abre **Seguridad e inicio de sesión**.
2. Activa **Verificación en dos pasos** si todavía no está activa.
3. Abre **Contraseñas de aplicaciones**.
4. Crea una con un nombre como `GitHub Traffic Monitor`.
5. Google mostrará una contraseña de 16 caracteres. Cópiala; será el valor de `SMTP_PASSWORD`.

> Si no aparece "Contraseñas de aplicaciones", Google indica que puede ocurrir en cuentas con Protección Avanzada, cuentas de organización o configuraciones que solo usan llaves de seguridad para la verificación en dos pasos.

### Secrets que debes crear en GitHub

En tu repositorio de GitHub ve a **Settings → Secrets and variables → Actions → New repository secret** y crea:

- `TOMTOM_API_KEY` = tu clave de TomTom.
- `SMTP_PASSWORD` = la contraseña de aplicación de Google de 16 caracteres.

No necesitas crear `DRY_RUN`: el workflow ya lo fija a `false`. GitHub cifra los repository secrets y solo se exponen al workflow cuando este los referencia.

Los demás parámetros de Gmail ya tienen valores por defecto en el código y aparecen también en `.env.example`. Puedes sobreescribirlos en el workflow si algún día quieres enviar a otra cuenta.

No guardes `TOMTOM_API_KEY` ni `SMTP_PASSWORD` en el repositorio.

## 4. Automatización con GitHub Actions

El repositorio incluye `.github/workflows/commute-monitor.yml`. GitHub Actions lo ejecutará automáticamente de lunes a viernes a las **06:15, hora Europe/Madrid**:

```yaml
on:
  schedule:
    - cron: "15 6 * * 1-5"
      timezone: "Europe/Madrid"
```

Se arranca a las 06:15 para dejar margen antes de la primera cata de las 06:30. El proceso queda vivo y toma las catas internamente a las 06:30, 06:40, 06:50, 07:00, 07:10, 07:20 y 07:30.

También incorpora `workflow_dispatch`, de modo que puedes lanzarlo manualmente desde **Actions → Morning commute traffic monitor → Run workflow** para hacer pruebas.

Los workflows programados se ejecutan sobre el último commit de la rama por defecto. Si el repositorio es público y queda sin actividad durante un periodo prolongado, GitHub puede desactivar temporalmente los schedules; basta reactivarlos desde Actions.

Los CSV y JSON generados se suben al final de cada ejecución como **GitHub Actions artifacts** durante 30 días.

Si también quieres fines de semana, cambia el cron del workflow a:

```text
15 6 * * *
```

## 5. Cómo se calcula la previsión de las 07:00

- A las 06:50: regresión lineal con 06:30 + 06:40 + 06:50 y extrapolación a 07:00.
- A las 07:00: se sustituye por el tiempo real observado a las 07:00.
- A las 07:10, 07:20 y 07:30: se mantiene el observado de las 07:00 como referencia, mientras el email sigue mostrando el tiempo actual y el gradiente.

Esto hace que la previsión se vaya alimentando con las catas, sin mezclar rutas distintas.

## Estructura

```text
commute_monitor/
  analytics.py       # tendencia, gradiente y previsión
  config.py          # variables de entorno
  emailer.py         # email texto + HTML
  monitor.py         # reloj de catas 06:30–07:30
  reference_route.py # genera la ruta fija
  storage.py         # CSV/JSON diario
  tomtom.py          # geocoding + Routing API
.github/workflows/commute-monitor.yml
.env.example
requirements.txt
```

## Nota operativa

Los workflows programados de GitHub Actions pueden sufrir retrasos de cola. Por eso el proyecto usa **un solo job largo** y temporiza las catas dentro del propio proceso. Si el job llega a una cata con más de 180 segundos de retraso, esa cata se omite en vez de etiquetar una medición tardía como si fuera puntual. El límite se cambia con `MAX_SAMPLE_LATENESS_SECONDS`.
