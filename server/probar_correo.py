"""
Prueba rápida de las credenciales de correo, sin necesidad de levantar
todo el servidor FastAPI. Uso:

    python probar_correo.py tu_correo_de_prueba@gmail.com

Lee EMAIL_REMITENTE y EMAIL_PASSWORD de tu .env (igual que el resto del
proyecto) e intenta enviar un correo de prueba a la dirección que le pases.
"""
import sys

from correo import enviar_bienvenida

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python probar_correo.py destinatario@gmail.com")
        sys.exit(1)

    destinatario = sys.argv[1]
    print(f"Enviando correo de prueba a {destinatario} ...")
    enviar_bienvenida(destinatario, "Usuario de prueba")
    print("Listo. Si no viste un error de [correo] arriba, revisa la bandeja de entrada (y spam).")
