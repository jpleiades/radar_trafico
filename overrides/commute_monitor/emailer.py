from __future__ import annotations

import html
import smtplib
from email.message import EmailMessage

from .analytics import ForecastResult, TrendResult
from .config import Settings
from .models import TrafficSample


def _fmt_minutes(seconds: int | None) -> str:
    if seconds is None:
        return "—"
    return f"{seconds / 60:.1f} min"


def _subject(sample: TrafficSample, forecast: ForecastResult, trend: TrendResult) -> str:
    # El asunto prioriza lo que está ocurriendo AHORA: duración observada en la
    # cata y ritmo de deterioro estimado por cada 10 minutos. El forecast sigue
    # apareciendo en el cuerpo del mensaje.
    state_labels = {
        "estable": "estable",
        "creciente moderado": "crecimiento moderado",
        "creciente rápido": "CRECIMIENTO RÁPIDO",
        "creciente extremo": "CRECIMIENTO EXTREMO",
    }
    state = state_labels.get(trend.label, trend.label)
    delta = trend.slope_minutes_per_10

    if trend.label == "creciente extremo":
        marker = "🚨"
    elif trend.label == "creciente rápido":
        marker = "⚠️"
    else:
        marker = "🚗"

    subject = (
        f"{marker} {sample.scheduled_time} · {sample.duration_minutes:.0f} min · "
        f"{delta:+.1f} min/10 min - {state}"
    )
    if trend.label in {"creciente rápido", "creciente extremo"}:
        subject += f" {marker}"
    return subject


def build_email(
    settings: Settings,
    samples: list[TrafficSample],
    forecast: ForecastResult,
    trend: TrendResult,
) -> EmailMessage:
    current = samples[-1]
    msg = EmailMessage()
    msg["Subject"] = _subject(current, forecast, trend)
    msg["From"] = settings.smtp_from or "traffic-monitor@example.invalid"
    msg["To"] = ", ".join(settings.email_to) if settings.email_to else "dry-run@example.invalid"

    lines = [
        f"Trayecto: {settings.origin_address} → {settings.destination_address}",
        f"Cata actual ({current.scheduled_time}): {current.duration_minutes:.1f} min",
        f"Estimación si sales a las {forecast.target_time}: {forecast.estimated_minutes:.1f} min",
        f"Gradiente: {trend.label} ({trend.slope_minutes_per_10:+.2f} min por cada 10 min)",
        f"Retraso por tráfico actual: {_fmt_minutes(current.traffic_delay_seconds)}",
        f"Método de previsión: {forecast.method}",
        "",
        "Histórico de la mañana:",
    ]
    for s in samples:
        lines.append(
            f"- {s.scheduled_time}: {s.duration_minutes:.1f} min "
            f"(retraso {_fmt_minutes(s.traffic_delay_seconds)})"
        )
    msg.set_content("\n".join(lines))

    rows = "".join(
        "<tr>"
        f"<td>{html.escape(s.scheduled_time)}</td>"
        f"<td>{s.duration_minutes:.1f} min</td>"
        f"<td>{_fmt_minutes(s.traffic_delay_seconds)}</td>"
        f"<td>{_fmt_minutes(s.no_traffic_seconds)}</td>"
        "</tr>"
        for s in samples
    )
    html_body = f"""
    <html><body style="font-family:Arial,sans-serif;line-height:1.4">
      <h2>Estado del tráfico — {html.escape(current.scheduled_time)}</h2>
      <p><strong>Trayecto:</strong><br>{html.escape(settings.origin_address)}<br>→ {html.escape(settings.destination_address)}</p>
      <table cellpadding="8" cellspacing="0" border="1" style="border-collapse:collapse">
        <tr><td><strong>Tiempo actual</strong></td><td>{current.duration_minutes:.1f} min</td></tr>
        <tr><td><strong>Estimación salida {html.escape(forecast.target_time)}</strong></td><td>{forecast.estimated_minutes:.1f} min</td></tr>
        <tr><td><strong>Gradiente</strong></td><td>{html.escape(trend.label)} ({trend.slope_minutes_per_10:+.2f} min/10 min)</td></tr>
        <tr><td><strong>Retraso actual</strong></td><td>{_fmt_minutes(current.traffic_delay_seconds)}</td></tr>
      </table>
      <p style="color:#555">Previsión: {html.escape(forecast.method)}. Todas las mediciones se recalculan sobre la misma ruta de referencia.</p>
      <h3>Catas de la mañana</h3>
      <table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse">
        <tr><th>Hora</th><th>Tiempo</th><th>Retraso</th><th>Sin tráfico</th></tr>
        {rows}
      </table>
    </body></html>
    """
    msg.add_alternative(html_body, subtype="html")
    return msg


def send_email(settings: Settings, message: EmailMessage) -> None:
    if settings.dry_run:
        print("\n--- EMAIL DRY RUN ---")
        print(message)
        print("--- END EMAIL ---\n")
        return

    if settings.smtp_port == 465 and not settings.smtp_starttls:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
        return

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
        smtp.ehlo()
        if settings.smtp_starttls:
            smtp.starttls()
            smtp.ehlo()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)
