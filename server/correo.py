"""
Envío de correos transaccionales (bienvenida al registrarse, aviso de
inicio de sesión) usando SMTP de Gmail.

Las credenciales del remitente se leen de variables de entorno
(configuracion.py) y nunca deben quedar escritas en el código fuente.

Si el envío falla (credenciales inválidas, sin internet, etc.) no se
interrumpe el registro/login del usuario: el error solo se imprime en
consola para depurar.
"""
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from configuracion import EMAIL_REMITENTE, EMAIL_PASSWORD

SERVIDOR_SMTP = "smtp.gmail.com"
PUERTO_SMTP = 465
NOMBRE_REMITENTE = "facturación .sys"


def _plantilla_html(titulo: str, saludo: str, cuerpo: str, html_extra: str = "") -> str:
    """Plantilla base minimalista para los correos, en HTML con estilos
    en línea (los clientes de correo ignoran hojas de estilo externas)."""
    return f"""\
<!DOCTYPE html>
<html lang="es">
<body style="margin:0; padding:0; background-color:#f4f4f5; font-family: Helvetica, Arial, sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f5; padding:32px 16px;">
        <tr>
            <td align="center">
                <table role="presentation" width="480" cellpadding="0" cellspacing="0" style="background-color:#ffffff; border-radius:8px; overflow:hidden; border:1px solid #e4e4e7;">
                    <tr>
                        <td style="background-color:#0a0a0a; padding:24px 32px;">
                            <span style="color:#ededed; font-size:16px; letter-spacing:1px; font-weight:bold;">facturación <span style="color:#8a8a8a; font-weight:normal;">.sys</span></span>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:32px;">
                            <h1 style="margin:0 0 16px 0; font-size:20px; color:#0a0a0a;">{titulo}</h1>
                            <p style="margin:0 0 12px 0; font-size:14px; line-height:1.6; color:#3f3f46;">{saludo}</p>
                            <p style="margin:0; font-size:14px; line-height:1.6; color:#3f3f46;">{cuerpo}</p>
                            {html_extra}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:20px 32px; background-color:#fafafa; border-top:1px solid #e4e4e7;">
                            <p style="margin:0; font-size:11px; color:#a1a1aa;">Este es un correo automático de facturación.sys, no es necesario responderlo.</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def _enviar(destinatario: str, asunto: str, cuerpo_html: str):
    if not EMAIL_REMITENTE or not EMAIL_PASSWORD:
        print("[correo] EMAIL_REMITENTE/EMAIL_PASSWORD no configurados; no se envía nada.")
        return
    if not destinatario:
        return

    mensaje = MIMEMultipart("alternative")
    mensaje["Subject"] = asunto
    mensaje["From"] = f"{NOMBRE_REMITENTE} <{EMAIL_REMITENTE}>"
    mensaje["To"] = destinatario
    mensaje.attach(MIMEText(cuerpo_html, "html"))

    try:
        contexto = ssl.create_default_context()
        with smtplib.SMTP_SSL(SERVIDOR_SMTP, PUERTO_SMTP, context=contexto) as servidor:
            servidor.login(EMAIL_REMITENTE, EMAIL_PASSWORD)
            servidor.sendmail(EMAIL_REMITENTE, destinatario, mensaje.as_string())
    except Exception as error:
        print(f"[correo] No se pudo enviar a {destinatario}: {error}")


def enviar_codigo_verificacion(destinatario: str, nombre_usuario: str, codigo: str):
    caja_codigo = f"""\
            <div style="margin:20px 0; padding:16px; background-color:#f4f4f5; border-radius:8px; text-align:center;">
                <span style="font-family: 'Courier New', monospace; font-size:28px; letter-spacing:6px; font-weight:bold; color:#0a0a0a;">{codigo}</span>
            </div>
            <p style="margin:0; font-size:12px; color:#a1a1aa;">Este código vence en 15 minutos. Si no fuiste tú, ignora este correo.</p>"""
    cuerpo_html = _plantilla_html(
        titulo="Confirma tu correo",
        saludo=f"Hola <strong>{nombre_usuario}</strong>, usa este código para confirmar tu correo y activar tu cuenta en facturación.sys:",
        cuerpo="",
        html_extra=caja_codigo,
    )
    _enviar(destinatario, "Tu código de verificación · facturación.sys", cuerpo_html)


def enviar_bienvenida(destinatario: str, nombre_usuario: str):
    cuerpo_html = _plantilla_html(
        titulo="¡Gracias por registrarte!",
        saludo=f"Hola <strong>{nombre_usuario}</strong>, tu cuenta en facturación.sys se creó correctamente.",
        cuerpo="Ya puedes iniciar sesión y empezar a controlar tu inventario y tus facturas.",
    )
    _enviar(destinatario, "Bienvenido a facturación.sys", cuerpo_html)


def enviar_alerta_inicio_sesion(destinatario: str, nombre_usuario: str):
    fecha = datetime.now().strftime("%d/%m/%Y a las %H:%M")
    cuerpo_html = _plantilla_html(
        titulo="Nuevo inicio de sesión",
        saludo=f"Hola <strong>{nombre_usuario}</strong>, se inició sesión en tu cuenta de facturación.sys el {fecha}.",
        cuerpo="Si fuiste tú, no necesitas hacer nada. Si no reconoces este acceso, te recomendamos cambiar tu contraseña.",
    )
    _enviar(destinatario, "Inicio de sesión en facturación.sys", cuerpo_html)
