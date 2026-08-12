
import bcrypt
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from db import obtener_usuario_por_nombre, crear_usuario

router = APIRouter()
plantillas = Jinja2Templates(directory="../frontend/plantillas/logica_jinja")


def hashear_password(password: str) -> str:
    sal = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), sal).decode("utf-8")


def verificar_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


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


# ---------- Acciones (POST, llamadas por htmx) ----------

@router.post("/login", response_class=HTMLResponse)
def procesar_login(request: Request, nombre: str = Form(...), contrasena: str = Form(...)):
    usuario = obtener_usuario_por_nombre(nombre.strip())

    if usuario is None or not verificar_password(contrasena, usuario["password_hash"]):
        return plantillas.TemplateResponse(
            request,
            "_fragmento_error.html",
            {"error": "Nombre de usuario o contraseña incorrectos"},
        )

    request.session["usuario_id"] = usuario["id"]
    request.session["usuario_nombre"] = usuario["nombre"]

    respuesta = HTMLResponse(content="", status_code=200)
    respuesta.headers["HX-Redirect"] = "/"
    return respuesta


@router.post("/registro", response_class=HTMLResponse)
def procesar_registro(
    request: Request,
    nombre: str = Form(...),
    contrasena: str = Form(...),
    confirmar_contrasena: str = Form(...),
):
    nombre = nombre.strip()

    if len(nombre) < 3:
        error = "El nombre debe tener al menos 3 caracteres"
    elif len(contrasena) < 8:
        error = "La contraseña debe tener al menos 8 caracteres"
    elif contrasena != confirmar_contrasena:
        error = "Las contraseñas no coinciden"
    elif obtener_usuario_por_nombre(nombre) is not None:
        error = "Ese nombre de usuario ya existe"
    else:
        error = None

    if error:
        return plantillas.TemplateResponse(
            request, "_fragmento_error.html", {"error": error}
        )

    crear_usuario(nombre, hashear_password(contrasena))
    respuesta = HTMLResponse(content="", status_code=200)
    respuesta.headers["HX-Redirect"] = "/login"
    return respuesta


@router.post("/salir")
def cerrar_sesion(request: Request):
    request.session.clear()
    respuesta = HTMLResponse(content="", status_code=200)
    respuesta.headers["HX-Redirect"] = "/login"
    return respuesta