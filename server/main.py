import os
import secrets

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from db import inicializar_db
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