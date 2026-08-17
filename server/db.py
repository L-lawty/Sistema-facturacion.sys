"""
Capa mínima de acceso a datos (MySQL) para usuarios.
Se amplía luego con tablas de productos y facturas.
"""
from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor

from configuracion import (
    MYSQL_HOST,
    MYSQL_PUERTO,
    MYSQL_USUARIO,
    MYSQL_PASSWORD,
    MYSQL_BASE_DATOS,
)


def inicializar_db():
    """Crea la base de datos (si no existe) y la tabla de usuarios."""
    conexion_inicial = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PUERTO,
        user=MYSQL_USUARIO,
        password=MYSQL_PASSWORD,
        charset="utf8mb4",
    )
    try:
        with conexion_inicial.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS {MYSQL_BASE_DATOS} "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conexion_inicial.commit()
    finally:
        conexion_inicial.close()

    with obtener_conexion() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nombre VARCHAR(100) UNIQUE NOT NULL,
                    email VARCHAR(255) NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    email_verificado TINYINT(1) NOT NULL DEFAULT 0,
                    codigo_verificacion VARCHAR(6) NULL,
                    codigo_expira TIMESTAMP NULL,
                    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB CHARACTER SET utf8mb4
            """)
            # Migración: si la tabla ya existía de antes de pedir correo,
            # se agrega la columna aparte. Nullable porque las cuentas viejas
            # no tienen correo guardado (simplemente no reciben avisos hasta
            # que alguien las actualice a mano en la base de datos).
            try:
                cursor.execute(
                    "ALTER TABLE usuarios ADD COLUMN email VARCHAR(255) NULL"
                )
            except pymysql.err.OperationalError as error:
                if error.args[0] != 1060:  # 1060 = Duplicate column name
                    raise
            try:
                cursor.execute(
                    "ALTER TABLE usuarios ADD CONSTRAINT uq_usuarios_email UNIQUE (email)"
                )
            except (pymysql.err.OperationalError, pymysql.err.IntegrityError) as error:
                if error.args[0] not in (1061, 1557, 1826):  # el índice/constraint ya existe
                    raise
            # Migración: verificación de correo por código de 6 dígitos.
            # Las cuentas viejas (creadas antes de este cambio) quedarían con
            # email_verificado = 0 y sin poder entrar; como ya existían de
            # buena fe, se marcan como verificadas de una vez.
            try:
                cursor.execute(
                    "ALTER TABLE usuarios ADD COLUMN email_verificado TINYINT(1) NOT NULL DEFAULT 0"
                )
                cursor.execute(
                    "UPDATE usuarios SET email_verificado = 1 WHERE creado_en < NOW()"
                )
            except pymysql.err.OperationalError as error:
                if error.args[0] != 1060:
                    raise
            try:
                cursor.execute(
                    "ALTER TABLE usuarios ADD COLUMN codigo_verificacion VARCHAR(6) NULL"
                )
            except pymysql.err.OperationalError as error:
                if error.args[0] != 1060:
                    raise
            try:
                cursor.execute(
                    "ALTER TABLE usuarios ADD COLUMN codigo_expira TIMESTAMP NULL"
                )
            except pymysql.err.OperationalError as error:
                if error.args[0] != 1060:
                    raise
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS productos (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    usuario_id INT NOT NULL,
                    nombre VARCHAR(150) NOT NULL,
                    categoria VARCHAR(50) NOT NULL DEFAULT 'General',
                    precio DECIMAL(10,2) NOT NULL,
                    stock INT NOT NULL DEFAULT 0,
                    activo TINYINT(1) NOT NULL DEFAULT 1,
                    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
                ) ENGINE=InnoDB CHARACTER SET utf8mb4
            """)
            # Si la tabla ya existía de antes de agregar el borrado lógico,
            # la columna no estará ahí: se agrega aparte y se ignora el
            # error si ya existe (por ejemplo en instalaciones previas).
            try:
                cursor.execute(
                    "ALTER TABLE productos ADD COLUMN activo TINYINT(1) NOT NULL DEFAULT 1"
                )
            except pymysql.err.OperationalError as error:
                if error.args[0] != 1060:  # 1060 = Duplicate column name
                    raise
            # Migración: si la tabla ya existía de antes de aislar el stock
            # por usuario, no tenía usuario_id. Como los productos de esa
            # etapa eran solo datos de prueba (compartidos entre cuentas,
            # sin dueño real), se eliminan junto con su detalle de factura
            # asociado y se agrega la columna limpia.
            #
            # Nota: no todos los MySQL están en modo estricto. Si no lo
            # está, "ADD COLUMN ... NOT NULL" sin DEFAULT no falla como
            # se esperaría: rellena las filas existentes con 0 en silencio.
            # Por eso se verifica la columna contra information_schema en
            # vez de confiar en que la ALTER lance un error, y además se
            # limpia de nuevo si la llave foránea falla por datos huérfanos
            # (usuario_id=0) que hayan quedado de un intento anterior.
            cursor.execute(
                """SELECT COUNT(*) AS cantidad FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'productos'
                   AND COLUMN_NAME = 'usuario_id'""",
                (MYSQL_BASE_DATOS,),
            )
            columna_existe = cursor.fetchone()["cantidad"] > 0
            if not columna_existe:
                cursor.execute("DELETE FROM factura_detalle")
                cursor.execute("DELETE FROM facturas")
                cursor.execute("DELETE FROM productos")
                cursor.execute("ALTER TABLE productos ADD COLUMN usuario_id INT NOT NULL")

            def _agregar_fk_productos_usuario():
                cursor.execute(
                    "ALTER TABLE productos ADD CONSTRAINT fk_productos_usuario "
                    "FOREIGN KEY (usuario_id) REFERENCES usuarios(id)"
                )

            try:
                _agregar_fk_productos_usuario()
            except pymysql.err.IntegrityError as error:
                if error.args[0] == 1452:  # filas huérfanas (usuario_id sin dueño real)
                    cursor.execute("DELETE FROM factura_detalle")
                    cursor.execute("DELETE FROM facturas")
                    cursor.execute("DELETE FROM productos")
                    _agregar_fk_productos_usuario()
                else:
                    raise
            except (pymysql.err.OperationalError, pymysql.err.InternalError) as error:
                if error.args[0] not in (1826, 1005):  # la llave foránea ya existe
                    raise
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS facturas (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    usuario_id INT NOT NULL,
                    cliente_nombre VARCHAR(150) NOT NULL,
                    total DECIMAL(10,2) NOT NULL,
                    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
                ) ENGINE=InnoDB CHARACTER SET utf8mb4
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS factura_detalle (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    factura_id INT NOT NULL,
                    producto_id INT NOT NULL,
                    nombre_producto VARCHAR(150) NOT NULL,
                    cantidad INT NOT NULL,
                    precio_unitario DECIMAL(10,2) NOT NULL,
                    subtotal DECIMAL(10,2) NOT NULL,
                    FOREIGN KEY (factura_id) REFERENCES facturas(id),
                    FOREIGN KEY (producto_id) REFERENCES productos(id)
                ) ENGINE=InnoDB CHARACTER SET utf8mb4
            """)
        conexion.commit()


@contextmanager
def obtener_conexion():
    conexion = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PUERTO,
        user=MYSQL_USUARIO,
        password=MYSQL_PASSWORD,
        database=MYSQL_BASE_DATOS,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )
    try:
        yield conexion
    finally:
        conexion.close()


def obtener_usuario_por_nombre(nombre: str):
    with obtener_conexion() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM usuarios WHERE nombre = %s", (nombre,)
            )
            return cursor.fetchone()


def obtener_usuario_por_id(usuario_id: int):
    with obtener_conexion() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT * FROM usuarios WHERE id = %s", (usuario_id,))
            return cursor.fetchone()


def obtener_usuario_por_correo(email: str):
    with obtener_conexion() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM usuarios WHERE email = %s", (email,)
            )
            return cursor.fetchone()


def crear_usuario(nombre: str, email: str, password_hash: str) -> int:
    """Devuelve el id del usuario recién creado (todavía sin verificar)."""
    with obtener_conexion() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                "INSERT INTO usuarios (nombre, email, password_hash) VALUES (%s, %s, %s)",
                (nombre, email, password_hash),
            )
            usuario_id = cursor.lastrowid
        conexion.commit()
    return usuario_id


def establecer_codigo_verificacion(usuario_id: int, codigo: str, minutos_expira: int = 15):
    with obtener_conexion() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                """UPDATE usuarios
                   SET codigo_verificacion = %s, codigo_expira = DATE_ADD(NOW(), INTERVAL %s MINUTE)
                   WHERE id = %s""",
                (codigo, minutos_expira, usuario_id),
            )
        conexion.commit()


def confirmar_correo(usuario_id: int, codigo: str) -> bool:
    """Marca el correo como verificado si el código coincide y no ha expirado."""
    with obtener_conexion() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                """SELECT id FROM usuarios
                   WHERE id = %s AND codigo_verificacion = %s AND codigo_expira > NOW()""",
                (usuario_id, codigo),
            )
            if cursor.fetchone() is None:
                return False
            cursor.execute(
                """UPDATE usuarios
                   SET email_verificado = 1, codigo_verificacion = NULL, codigo_expira = NULL
                   WHERE id = %s""",
                (usuario_id,),
            )
        conexion.commit()
    return True


# ---------- Productos (aislados por usuario) ----------

def listar_productos(usuario_id: int):
    with obtener_conexion() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM productos WHERE usuario_id = %s AND stock > 0 AND activo = 1 ORDER BY nombre",
                (usuario_id,),
            )
            return cursor.fetchall()


def obtener_producto(producto_id: int, usuario_id: int):
    with obtener_conexion() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM productos WHERE id = %s AND usuario_id = %s",
                (producto_id, usuario_id),
            )
            return cursor.fetchone()


def crear_producto(usuario_id: int, nombre: str, categoria: str, precio: float, stock: int):
    with obtener_conexion() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                "INSERT INTO productos (usuario_id, nombre, categoria, precio, stock) VALUES (%s, %s, %s, %s, %s)",
                (usuario_id, nombre, categoria, precio, stock),
            )
        conexion.commit()


def listar_todos_productos(usuario_id: int):
    """A diferencia de listar_productos(), incluye también los que están en 0
    y los productos archivados (se muestran al final)."""
    with obtener_conexion() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM productos WHERE usuario_id = %s ORDER BY activo DESC, nombre",
                (usuario_id,),
            )
            return cursor.fetchall()


def contar_productos_por_categoria(usuario_id: int):
    """Solo cuenta productos activos, para reflejar el inventario vigente."""
    with obtener_conexion() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                """SELECT categoria, COUNT(*) AS cantidad
                   FROM productos
                   WHERE activo = 1 AND usuario_id = %s
                   GROUP BY categoria
                   ORDER BY categoria""",
                (usuario_id,),
            )
            return cursor.fetchall()


def actualizar_producto(producto_id: int, usuario_id: int, nombre: str, categoria: str, precio: float, stock: int):
    with obtener_conexion() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                """UPDATE productos
                   SET nombre = %s, categoria = %s, precio = %s, stock = %s
                   WHERE id = %s AND usuario_id = %s""",
                (nombre, categoria, precio, stock, producto_id, usuario_id),
            )
        conexion.commit()


def archivar_producto(producto_id: int, usuario_id: int):
    """Borrado lógico: oculta el producto de facturación sin perder su historial
    en facturas ya emitidas."""
    with obtener_conexion() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE productos SET activo = 0 WHERE id = %s AND usuario_id = %s",
                (producto_id, usuario_id),
            )
        conexion.commit()


def reactivar_producto(producto_id: int, usuario_id: int):
    with obtener_conexion() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE productos SET activo = 1 WHERE id = %s AND usuario_id = %s",
                (producto_id, usuario_id),
            )
        conexion.commit()


# ---------- Facturación ----------

def crear_factura(usuario_id: int, cliente_nombre: str, items: list):
    """
    items: lista de dicts con producto_id, nombre, precio_unitario, cantidad, subtotal.
    Inserta la factura y su detalle, y descuenta el stock, todo en una transacción.
    Solo descuenta stock de productos que pertenezcan al usuario_id (defensa
    extra por si el carrito llega manipulado).
    """
    total = sum(item["subtotal"] for item in items)
    with obtener_conexion() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                "INSERT INTO facturas (usuario_id, cliente_nombre, total) VALUES (%s, %s, %s)",
                (usuario_id, cliente_nombre, total),
            )
            factura_id = cursor.lastrowid

            for item in items:
                cursor.execute(
                    """INSERT INTO factura_detalle
                       (factura_id, producto_id, nombre_producto, cantidad, precio_unitario, subtotal)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (
                        factura_id,
                        item["producto_id"],
                        item["nombre"],
                        item["cantidad"],
                        item["precio_unitario"],
                        item["subtotal"],
                    ),
                )
                cursor.execute(
                    "UPDATE productos SET stock = stock - %s WHERE id = %s AND usuario_id = %s",
                    (item["cantidad"], item["producto_id"], usuario_id),
                )
        conexion.commit()
    return factura_id, total


def obtener_factura(factura_id: int, usuario_id: int):
    """Devuelve (None, None) si la factura no existe o no pertenece al usuario."""
    with obtener_conexion() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM facturas WHERE id = %s AND usuario_id = %s",
                (factura_id, usuario_id),
            )
            factura = cursor.fetchone()
            if factura is None:
                return None, None
            cursor.execute(
                "SELECT * FROM factura_detalle WHERE factura_id = %s", (factura_id,)
            )
            detalle = cursor.fetchall()
    return factura, detalle


def listar_facturas_usuario(usuario_id: int):
    with obtener_conexion() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM facturas WHERE usuario_id = %s ORDER BY creado_en DESC",
                (usuario_id,),
            )
            return cursor.fetchall()