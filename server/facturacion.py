"""
Rutas de facturación. El carrito vive en la sesión del usuario (no en la
base de datos) mientras arma la factura; solo se persiste cuando confirma
con 'Generar factura', momento en que se descuenta el stock.
"""
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from db import (
    listar_productos,
    obtener_producto,
    crear_factura,
    obtener_factura,
    listar_facturas_usuario,
)

router = APIRouter()
plantillas = Jinja2Templates(directory="../frontend/plantillas/logica_jinja")


def _sesion_activa(request: Request):
    return request.session.get("usuario_id")


def _respuesta_redirigir_login():
    respuesta = HTMLResponse(content="", status_code=200)
    respuesta.headers["HX-Redirect"] = "/login"
    return respuesta


def _total_carrito(carrito: list) -> float:
    return round(sum(item["subtotal"] for item in carrito), 2)


# ---------- Vista principal ----------

@router.get("/facturacion", response_class=HTMLResponse)
def vista_facturacion(request: Request):
    if not _sesion_activa(request):
        return RedirectResponse("/login", status_code=303)

    productos = listar_productos(request.session["usuario_id"])
    carrito = request.session.get("carrito", [])
    return plantillas.TemplateResponse(
        request,
        "facturacion.html",
        {
            "productos": productos,
            "carrito": carrito,
            "total": _total_carrito(carrito),
            "usuario_nombre": request.session.get("usuario_nombre"),
        },
    )


# ---------- Acciones del carrito (htmx) ----------

@router.post("/facturacion/agregar", response_class=HTMLResponse)
def agregar_producto(request: Request, producto_id: int = Form(...), cantidad: int = Form(...)):
    if not _sesion_activa(request):
        return _respuesta_redirigir_login()

    carrito = request.session.get("carrito", [])
    producto = obtener_producto(producto_id, request.session["usuario_id"])
    error = None

    if producto is None:
        error = "Ese producto ya no existe"
    elif cantidad < 1:
        error = "La cantidad debe ser al menos 1"
    else:
        ya_reservado = sum(item["cantidad"] for item in carrito if item["producto_id"] == producto_id)
        if ya_reservado + cantidad > producto["stock"]:
            error = f"Solo hay {producto['stock']} unidades disponibles de {producto['nombre']}"

    if error is None:
        for item in carrito:
            if item["producto_id"] == producto_id:
                item["cantidad"] += cantidad
                item["subtotal"] = round(item["cantidad"] * item["precio_unitario"], 2)
                break
        else:
            precio_unitario = float(producto["precio"])
            carrito.append({
                "producto_id": producto["id"],
                "nombre": producto["nombre"],
                "precio_unitario": precio_unitario,
                "cantidad": cantidad,
                "subtotal": round(cantidad * precio_unitario, 2),
            })
        request.session["carrito"] = carrito

    return plantillas.TemplateResponse(
        request,
        "_carrito.html",
        {"carrito": carrito, "total": _total_carrito(carrito), "error": error},
    )


@router.post("/facturacion/quitar/{producto_id}", response_class=HTMLResponse)
def quitar_producto(request: Request, producto_id: int):
    if not _sesion_activa(request):
        return _respuesta_redirigir_login()

    carrito = request.session.get("carrito", [])
    carrito = [item for item in carrito if item["producto_id"] != producto_id]
    request.session["carrito"] = carrito

    return plantillas.TemplateResponse(
        request,
        "_carrito.html",
        {"carrito": carrito, "total": _total_carrito(carrito), "error": None},
    )


@router.post("/facturacion/generar", response_class=HTMLResponse)
def generar_factura(request: Request, cliente_nombre: str = Form(...)):
    if not _sesion_activa(request):
        return _respuesta_redirigir_login()

    carrito = request.session.get("carrito", [])

    if not carrito:
        return plantillas.TemplateResponse(
            request,
            "_carrito.html",
            {"carrito": carrito, "total": 0, "error": "Agrega al menos un producto antes de generar la factura"},
        )

    if not cliente_nombre.strip():
        return plantillas.TemplateResponse(
            request,
            "_carrito.html",
            {"carrito": carrito, "total": _total_carrito(carrito), "error": "Escribe el nombre del cliente"},
        )

    factura_id, _total = crear_factura(request.session["usuario_id"], cliente_nombre.strip(), carrito)
    request.session["carrito"] = []

    respuesta = HTMLResponse(content="", status_code=200)
    respuesta.headers["HX-Redirect"] = f"/facturacion/{factura_id}"
    return respuesta


# ---------- Factura generada ----------

@router.get("/facturacion/{factura_id}", response_class=HTMLResponse)
def vista_factura_generada(request: Request, factura_id: int):
    if not _sesion_activa(request):
        return RedirectResponse("/login", status_code=303)

    factura, detalle = obtener_factura(factura_id, request.session["usuario_id"])
    if factura is None:
        return RedirectResponse("/historial", status_code=303)

    return plantillas.TemplateResponse(
        request, "factura_generada.html", {"factura": factura, "detalle": detalle}
    )


# ---------- Historial ----------

@router.get("/historial", response_class=HTMLResponse)
def vista_historial(request: Request):
    if not _sesion_activa(request):
        return RedirectResponse("/login", status_code=303)

    facturas = listar_facturas_usuario(request.session["usuario_id"])
    return plantillas.TemplateResponse(
        request,
        "historial.html",
        {
            "facturas": facturas,
            "usuario_nombre": request.session.get("usuario_nombre"),
        },
    )