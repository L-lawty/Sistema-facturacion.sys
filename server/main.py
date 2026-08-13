import os
import secrets

from fastapi import FastAPI, Request, status
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from db import inicializar_db, obtener_conexion
from autenticacion import router as router_autenticacion
from facturacion import router as router_facturacion
from stock import router as router_stock

app = FastAPI(title="Sistema de facturación")

# Clave de sesión: en producción se define por variable de entorno.
CLAVE_SESION = os.environ.get("CLAVE_SESION", secrets.token_hex(32))
app.add_middleware(SessionMiddleware, secret_key=CLAVE_SESION, same_site="lax")

app.mount("/static", StaticFiles(directory="../frontend"), name="static")

app.include_router(router_autenticacion)
app.include_router(router_facturacion)
app.include_router(router_stock)


@app.on_event("startup")
def al_iniciar():
    inicializar_db()


@app.get("/")
def raiz(request: Request):
    if not request.session.get("usuario_id"):
        return RedirectResponse("/login", status_code=303)
    return RedirectResponse("/facturacion", status_code=303)


@app.get("/MantenerVivo")
def mantener_viva_db():
    """Ping simple para evitar que Render/Aiven se duerman por inactividad."""
    try:
        with obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        return {"status": status.HTTP_200_OK, "mensaje": "Servicios hosting despiertos"}
    except Exception as e:
        return {"Error": type(e).__name__, "detalle": str(e)}