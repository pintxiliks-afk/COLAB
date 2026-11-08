#!/usr/bin/env python3
"""Publica un agente Markdown (config_agente.md) en GitHub desde la terminal.

Actualiza SOLO ese archivo con la API de GitHub (sin git push --force).
El token se lee de la variable GITHUB_TOKEN o se pide sin mostrarlo en pantalla.

Ejemplo:
  export GITHUB_TOKEN="github_pat_..."        # o déjalo sin definir y te lo pedirá
  python3 publicar_agente.py --user TU_USUARIO --repo TU_REPO \
      --titulo "Asistente M.M.O." --cuerpo-archivo cuerpo.md
"""
import argparse, base64, getpass, os, re, sys, time, urllib.parse
import requests
import yaml

COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
API = "https://api.github.com"
PISTAS = {
    401: "El token no es válido o ha caducado. Genera uno nuevo.",
    403: "El token no tiene permiso «Contents: Read and write» en este repositorio, o has superado el límite de peticiones.",
    404: "No encuentro el repositorio, la rama o la ruta. Con tokens fine-grained también sale 404 si el token no tiene acceso a ese repo.",
    409: "El archivo cambió mientras se publicaba. Vuelve a ejecutar.",
    422: "GitHub rechazó los datos (a menudo, el archivo cambió justo antes). Vuelve a ejecutar.",
}
CUERPO_DEFECTO = """# Estado del Sistema: Óptimo

Contenido publicado desde la terminal.

- La web lo lee al cargar la página.
- Los parámetros de estilo vienen de la cabecera YAML.
"""


def salir(msg):
    print("ERROR:", msg, file=sys.stderr)
    sys.exit(1)


def parsear():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--user", required=True, help="usuario u organización de GitHub")
    p.add_argument("--repo", required=True)
    p.add_argument("--rama", default="main")
    p.add_argument("--ruta", default="config_agente.md", help="ruta del .md dentro del repo")
    p.add_argument("--mensaje", default=None, help="mensaje del commit")
    p.add_argument("--titulo", default="Asistente de Desarrollo M.M.O.")
    p.add_argument("--tema", default="cyberpunk")
    p.add_argument("--color-primario", default="#06b6d4")
    p.add_argument("--color-fondo", default="#09090b")
    p.add_argument("--modo-experto", action="store_true", help="activa modo_experto: true")
    p.add_argument("--cuerpo-archivo", help="archivo .md local con el cuerpo (sin cabecera)")
    p.add_argument("--simular", action="store_true", help="solo muestra el archivo; no publica")
    return p.parse_args()


def construir(a):
    errores = []
    if not a.titulo.strip():
        errores.append("--titulo está vacío.")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", a.tema):
        errores.append("--tema solo admite letras, números, guion y guion bajo.")
    for n, v in (("--color-primario", a.color_primario), ("--color-fondo", a.color_fondo)):
        if not COLOR_RE.match(v):
            errores.append(f"{n} debe ser un color hexadecimal como #06b6d4 (ahora: {v!r}).")
    if not a.ruta.endswith(".md") or a.ruta.startswith("/") or ".." in a.ruta.split("/"):
        errores.append("--ruta debe ser relativa, sin '..' y acabar en .md.")
    cuerpo = CUERPO_DEFECTO
    if a.cuerpo_archivo:
        try:
            with open(a.cuerpo_archivo, encoding="utf-8") as f:
                cuerpo = f.read()
        except OSError as e:
            errores.append(f"No puedo leer {a.cuerpo_archivo}: {e}")
    if len(cuerpo.encode("utf-8")) > 200_000:
        errores.append("El cuerpo supera los 200 KB.")
    if errores:
        salir("Corrige esto:\n - " + "\n - ".join(errores))
    meta = {"titulo": a.titulo.strip(), "tema": a.tema, "color_primario": a.color_primario,
            "color_fondo": a.color_fondo, "modo_experto": bool(a.modo_experto)}
    cab = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{cab}\n---\n\n{cuerpo.strip()}\n"


def falla(r):
    try:
        detalle = r.json().get("message", "")
    except ValueError:
        detalle = ""
    salir(f"GitHub respondió {r.status_code} {detalle}. {PISTAS.get(r.status_code, '')}".strip())


def publicar(a, contenido, token, intentos=2):
    cab = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
           "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "terminal-agentes-markdown"}
    url = (f"{API}/repos/{urllib.parse.quote(a.user)}/{urllib.parse.quote(a.repo)}"
           f"/contents/{urllib.parse.quote(a.ruta)}")
    mensaje = a.mensaje or f"Actualizar {a.ruta} desde terminal"
    for intento in range(intentos):
        r = requests.get(url, headers=cab, params={"ref": a.rama}, timeout=30)
        sha = None
        if r.status_code == 200:
            actual = r.json()
            sha = actual["sha"]
            if base64.b64decode(actual["content"]).decode("utf-8") == contenido:
                return "sin_cambios", actual.get("html_url")
        elif r.status_code != 404:
            falla(r)
        datos = {"message": mensaje, "branch": a.rama,
                 "content": base64.b64encode(contenido.encode("utf-8")).decode("ascii")}
        if sha:
            datos["sha"] = sha
        p = requests.put(url, headers=cab, json=datos, timeout=30)
        if p.status_code in (200, 201):
            return ("creado" if p.status_code == 201 else "actualizado"), p.json()["commit"]["html_url"]
        if p.status_code in (409, 422) and intento + 1 < intentos:
            time.sleep(1)
            continue
        falla(p)


def main():
    a = parsear()
    contenido = construir(a)
    print(contenido)
    if a.simular:
        print("(simulación: no se ha publicado nada)")
        return
    token = os.environ.get("GITHUB_TOKEN") or getpass.getpass("Token de GitHub (no se muestra): ").strip()
    if not token:
        salir("Falta el token.")
    estado, enlace = publicar(a, contenido, token)
    print({"creado": "Archivo creado.", "actualizado": "Archivo actualizado.",
           "sin_cambios": "Sin cambios: el contenido ya era el mismo."}[estado])
    print("Ver en GitHub:", enlace)
    print("Tu web lo mostrará cuando se redespliegue (Cloudflare Pages / GitHub Pages: 1-2 min).")


if __name__ == "__main__":
    main()
