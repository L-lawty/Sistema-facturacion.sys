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