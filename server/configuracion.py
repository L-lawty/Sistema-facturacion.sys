"""
Configuración de conexión a MySQL, leída de variables de entorno.
Copia .env.example a .env y ajusta los valores para tu entorno.
"""
import os
from dotenv import load_dotenv

load_dotenv()

MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
MYSQL_PUERTO = int(os.environ.get("MYSQL_PUERTO", "3306"))
MYSQL_USUARIO = os.environ.get("MYSQL_USUARIO", "root")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
MYSQL_BASE_DATOS = os.environ.get("MYSQL_BASE_DATOS", "facturacion")

# Cuenta desde la que se envían los correos transaccionales (bienvenida,
# aviso de inicio de sesión). EMAIL_PASSWORD debe ser una "contraseña de
# aplicación" de Gmail, no la contraseña normal de la cuenta: Gmail ya no
# acepta la contraseña normal para SMTP. Se genera en la cuenta de Google,
# en Seguridad -> Verificación en 2 pasos (debe estar activada) -> Contraseñas
# de aplicaciones.
EMAIL_REMITENTE = os.environ.get("EMAIL_REMITENTE", "")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")