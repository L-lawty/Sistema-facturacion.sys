"""
Rutas del inventario (CRUD de productos). Es el mismo stock que después
aparece disponible para facturar: listar_productos() (usado en /facturacion)
solo trae los que tienen existencias; aquí se listan todos, incluyendo
los que están en 0, para poder reponerlos.

Todo el inventario es individual por usuario: cada consulta y cada
modificación va filtrada/validada contra el usuario_id de la sesión activa.
"""
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from db import (
    listar_todos_productos,
    obtener_producto,
    crear_producto,
    actualizar_producto,
    archivar_producto,
    reactivar_producto,
    contar_productos_por_categoria,
)

router = APIRouter()
plantillas = Jinja2Templates(directory="../frontend/plantillas/logica_jinja")

# Lista fija de categorías: se elige de un select en vez de escribirla a mano.
CATEGORIAS = [
    "Alimentos",
    "Bebidas",
    "Limpieza",
    "Electrónica",
    "Ferretería",
    "Papelería",
    "Ropa y calzado",
    "Salud y belleza",
    "Hogar",
    "General",
    "Otros",
]


def _sesion_activa(request: Request):
    return request.session.get("usuario_id")


def _respuesta_redirigir_login():
    respuesta = HTMLResponse(content="", status_code=200)
    respuesta.headers["HX-Redirect"] = "/login"
    return respuesta


def _validar_producto(nombre: str, categoria: str, precio: float, stock: int):
    if len(nombre) < 2:
        return "El nombre debe tener al menos 2 caracteres"
    if not categoria:
        return "La categoría es obligatoria"
    if precio <= 0:
        return "El precio debe ser mayor a 0"
    if stock < 0:
        return "El stock no puede ser negativo"
    return None


def _tabla_respuesta(request: Request, usuario_id: int, editar_id=None, error=None):
    productos = listar_todos_productos(usuario_id)
    return plantillas.TemplateResponse(
        request,
        "_tabla_stock.html",
        {
            "productos": productos,
            "editar_id": editar_id,
            "error": error,
            "categorias": CATEGORIAS,
            "resumen": contar_productos_por_categoria(usuario_id),
        },
    )


# ---------- Vista principal ----------

@router.get("/stock", response_class=HTMLResponse)
def vista_stock(request: Request):
    usuario_id = _sesion_activa(request)
    if not usuario_id:
        return RedirectResponse("/login", status_code=303)

    productos = listar_todos_productos(usuario_id)
    return plantillas.TemplateResponse(
        request,
        "stock.html",
        {
            "productos": productos,
            "editar_id": None,
            "error": None,
            "categorias": CATEGORIAS,
            "resumen": contar_productos_por_categoria(usuario_id),
            "usuario_nombre": request.session.get("usuario_nombre"),
        },
    )


# ---------- Acciones (POST/GET, llamadas por htmx) ----------

@router.get("/stock/tabla", response_class=HTMLResponse)
def tabla_stock(request: Request):
    """Usada para volver al modo lectura (botón Cancelar de una edición)."""
    usuario_id = _sesion_activa(request)
    if not usuario_id:
        return _respuesta_redirigir_login()
    return _tabla_respuesta(request, usuario_id)


@router.post("/stock/crear", response_class=HTMLResponse)
def crear_producto_ruta(
    request: Request,
    nombre: str = Form(...),
    categoria: str = Form(...),
    precio: float = Form(...),
    stock: int = Form(...),
):
    usuario_id = _sesion_activa(request)
    if not usuario_id:
        return _respuesta_redirigir_login()

    nombre = nombre.strip()
    categoria = categoria.strip()
    error = _validar_producto(nombre, categoria, precio, stock)

    if error is None:
        crear_producto(usuario_id, nombre, categoria, precio, stock)

    return _tabla_respuesta(request, usuario_id, error=error)


@router.get("/stock/editar/{producto_id}", response_class=HTMLResponse)
def editar_producto_form(request: Request, producto_id: int):
    usuario_id = _sesion_activa(request)
    if not usuario_id:
        return _respuesta_redirigir_login()

    producto = obtener_producto(producto_id, usuario_id)
    if producto is None:
        return _tabla_respuesta(request, usuario_id, error="Ese producto ya no existe")
    if not producto["activo"]:
        return _tabla_respuesta(request, usuario_id, error="Reactiva el producto antes de editarlo")

    return _tabla_respuesta(request, usuario_id, editar_id=producto_id)


@router.post("/stock/actualizar/{producto_id}", response_class=HTMLResponse)
def actualizar_producto_ruta(
    request: Request,
    producto_id: int,
    nombre: str = Form(...),
    categoria: str = Form(...),
    precio: float = Form(...),
    stock: int = Form(...),
):
    usuario_id = _sesion_activa(request)
    if not usuario_id:
        return _respuesta_redirigir_login()

    if obtener_producto(producto_id, usuario_id) is None:
        return _tabla_respuesta(request, usuario_id, error="Ese producto ya no existe")

    nombre = nombre.strip()
    categoria = categoria.strip()
    error = _validar_producto(nombre, categoria, precio, stock)

    if error is None:
        actualizar_producto(producto_id, usuario_id, nombre, categoria, precio, stock)
        return _tabla_respuesta(request, usuario_id)

    # Si hubo error, se queda en modo edición mostrando el mensaje.
    return _tabla_respuesta(request, usuario_id, editar_id=producto_id, error=error)


@router.post("/stock/archivar/{producto_id}", response_class=HTMLResponse)
def archivar_producto_ruta(request: Request, producto_id: int):
    usuario_id = _sesion_activa(request)
    if not usuario_id:
        return _respuesta_redirigir_login()

    if obtener_producto(producto_id, usuario_id) is None:
        return _tabla_respuesta(request, usuario_id, error="Ese producto ya no existe")

    archivar_producto(producto_id, usuario_id)
    return _tabla_respuesta(request, usuario_id)


@router.post("/stock/reactivar/{producto_id}", response_class=HTMLResponse)
def reactivar_producto_ruta(request: Request, producto_id: int):
    usuario_id = _sesion_activa(request)
    if not usuario_id:
        return _respuesta_redirigir_login()

    if obtener_producto(producto_id, usuario_id) is None:
        return _tabla_respuesta(request, usuario_id, error="Ese producto ya no existe")

    reactivar_producto(producto_id, usuario_id)
    return _tabla_respuesta(request, usuario_id)