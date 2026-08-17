
import random
import re

import bcrypt
from fastapi import APIRouter, BackgroundTasks, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from db import (
    obtener_usuario_por_nombre,
    obtener_usuario_por_correo,
    obtener_usuario_por_id,
    crear_usuario,
    establecer_codigo_verificacion,
    confirmar_correo,
)
from correo import enviar_bienvenida, enviar_alerta_inicio_sesion, enviar_codigo_verificacion

router = APIRouter()
plantillas = Jinja2Templates(directory="../frontend/plantillas/logica_jinja")

PATRON_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def hashear_password(password: str) -> str:
    sal = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), sal).decode("utf-8")


def verificar_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def _generar_codigo() -> str:
    return f"{random.randint(0, 999999):06d}"


def _enviar_codigo_a(usuario_id: int, email: str, nombre: str, background_tasks: BackgroundTasks):
    codigo = _generar_codigo()
    establecer_codigo_verificacion(usuario_id, codigo)
    background_tasks.add_task(enviar_codigo_verificacion, email, nombre, codigo)


# ---------- Vistas (GET) ----------

@router.get("/login", response_class=HTMLResponse)
def vista_login(request: Request):
    if request.session.get("usuario_id"):
        return RedirectResponse("/", status_code=303)
    return plantillas.TemplateResponse(request, "login.html")


@router.get("/registro", response_class=HTMLResponse)
def vista_registro(request: Request):
    if request.session.get("usuario_id"):
        return RedirectResponse("/", status_code=303)
    return plantillas.TemplateResponse(request, "registro.html")


@router.get("/verificar", response_class=HTMLResponse)
def vista_verificar(request: Request):
    if request.session.get("usuario_id"):
        return RedirectResponse("/", status_code=303)
    usuario_pendiente_id = request.session.get("usuario_pendiente_id")
    if not usuario_pendiente_id:
        return RedirectResponse("/login", status_code=303)

    usuario = obtener_usuario_por_id(usuario_pendiente_id)
    if usuario is None:
        request.session.pop("usuario_pendiente_id", None)
        return RedirectResponse("/login", status_code=303)

    return plantillas.TemplateResponse(
        request, "verificar.html", {"correo": usuario["email"], "error": None}
    )


# ---------- Acciones (POST, llamadas por htmx) ----------

@router.post("/login", response_class=HTMLResponse)
def procesar_login(
    request: Request,
    background_tasks: BackgroundTasks,
    nombre: str = Form(...),
    contrasena: str = Form(...),
):
    usuario = obtener_usuario_por_nombre(nombre.strip())

    if usuario is None or not verificar_password(contrasena, usuario["password_hash"]):
        return plantillas.TemplateResponse(
            request,
            "_fragmento_error.html",
            {"error": "Nombre de usuario o contraseña incorrectos"},
        )

    if not usuario["email_verificado"]:
        # Cuenta válida pero correo sin confirmar: se manda a verificar en
        # vez de dejarla entrar. Se reenvía un código nuevo por si el
        # primero ya expiró.
        _enviar_codigo_a(usuario["id"], usuario["email"], usuario["nombre"], background_tasks)
        request.session["usuario_pendiente_id"] = usuario["id"]
        respuesta = HTMLResponse(content="", status_code=200)
        respuesta.headers["HX-Redirect"] = "/verificar"
        return respuesta

    request.session["usuario_id"] = usuario["id"]
    request.session["usuario_nombre"] = usuario["nombre"]

    if usuario.get("email"):
        background_tasks.add_task(enviar_alerta_inicio_sesion, usuario["email"], usuario["nombre"])

    respuesta = HTMLResponse(content="", status_code=200)
    respuesta.headers["HX-Redirect"] = "/"
    return respuesta


@router.post("/registro", response_class=HTMLResponse)
def procesar_registro(
    request: Request,
    background_tasks: BackgroundTasks,
    nombre: str = Form(...),
    correo: str = Form(...),
    contrasena: str = Form(...),
    confirmar_contrasena: str = Form(...),
):
    nombre = nombre.strip()
    correo = correo.strip().lower()

    if len(nombre) < 3:
        error = "El nombre debe tener al menos 3 caracteres"
    elif not PATRON_EMAIL.match(correo):
        error = "Escribe un correo válido"
    elif len(contrasena) < 8:
        error = "La contraseña debe tener al menos 8 caracteres"
    elif contrasena != confirmar_contrasena:
        error = "Las contraseñas no coinciden"
    elif obtener_usuario_por_nombre(nombre) is not None:
        error = "Ese nombre de usuario ya existe"
    elif obtener_usuario_por_correo(correo) is not None:
        error = "Ese correo ya está registrado"
    else:
        error = None

    if error:
        return plantillas.TemplateResponse(
            request, "_fragmento_error.html", {"error": error}
        )

    usuario_id = crear_usuario(nombre, correo, hashear_password(contrasena))
    _enviar_codigo_a(usuario_id, correo, nombre, background_tasks)
    request.session["usuario_pendiente_id"] = usuario_id

    respuesta = HTMLResponse(content="", status_code=200)
    respuesta.headers["HX-Redirect"] = "/verificar"
    return respuesta


@router.post("/verificar/codigo", response_class=HTMLResponse)
def procesar_verificacion(
    request: Request,
    background_tasks: BackgroundTasks,
    codigo: str = Form(...),
):
    usuario_pendiente_id = request.session.get("usuario_pendiente_id")
    if not usuario_pendiente_id:
        return _respuesta_redirigir_login()

    if not confirmar_correo(usuario_pendiente_id, codigo.strip()):
        return plantillas.TemplateResponse(
            request,
            "_fragmento_error.html",
            {"error": "Código incorrecto o vencido. Puedes pedir uno nuevo abajo."},
        )

    usuario = obtener_usuario_por_id(usuario_pendiente_id)
    request.session.pop("usuario_pendiente_id", None)
    request.session["usuario_id"] = usuario["id"]
    request.session["usuario_nombre"] = usuario["nombre"]

    background_tasks.add_task(enviar_bienvenida, usuario["email"], usuario["nombre"])

    respuesta = HTMLResponse(content="", status_code=200)
    respuesta.headers["HX-Redirect"] = "/"
    return respuesta


@router.post("/verificar/reenviar", response_class=HTMLResponse)
def reenviar_codigo(request: Request, background_tasks: BackgroundTasks):
    usuario_pendiente_id = request.session.get("usuario_pendiente_id")
    if not usuario_pendiente_id:
        return _respuesta_redirigir_login()

    usuario = obtener_usuario_por_id(usuario_pendiente_id)
    if usuario is None:
        request.session.pop("usuario_pendiente_id", None)
        return _respuesta_redirigir_login()

    _enviar_codigo_a(usuario["id"], usuario["email"], usuario["nombre"], background_tasks)

    return plantillas.TemplateResponse(
        request,
        "_fragmento_error.html",
        {"error": None, "aviso": "Te reenviamos un código nuevo a tu correo."},
    )


@router.post("/salir")
def cerrar_sesion(request: Request):
    request.session.clear()
    respuesta = HTMLResponse(content="", status_code=200)
    respuesta.headers["HX-Redirect"] = "/login"
    return respuesta


def _respuesta_redirigir_login():
    respuesta = HTMLResponse(content="", status_code=200)
    respuesta.headers["HX-Redirect"] = "/login"
    return respuesta
