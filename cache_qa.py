import hashlib
import json
import os
import re
from pathlib import Path

CACHE_SCHEMA_VERSION = "v2.1"


def _sanitizar_clave_cache(clave: str) -> str:
    limpia = re.sub(r"[^A-Fa-f0-9_-]", "", str(clave or "").strip())
    if not limpia:
        raise ValueError("La clave de caché no es válida.")
    return limpia


def calcular_clave_cache(
    contenido_req: str,
    contexto_rag: str,
    modelo: str,
    version_esquema: str = CACHE_SCHEMA_VERSION,
) -> str:
    """Genera un hash SHA-256 incluyendo la versión de esquema para evitar caché obsoleta."""
    carga = json.dumps(
        {
            "schema_version": str(version_esquema or CACHE_SCHEMA_VERSION).strip(),
            "modelo": str(modelo or "").strip(),
            "contenido_req": str(contenido_req or ""),
            "contexto_rag": str(contexto_rag or ""),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(carga.encode("utf-8")).hexdigest()


def leer_cache_qa(carpeta_cache: Path, clave: str) -> dict | None:
    clave_segura = _sanitizar_clave_cache(clave)
    ruta = carpeta_cache / f"{clave_segura}.json"
    if not ruta.exists():
        return None
    try:
        data = json.loads(ruta.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        try:
            ruta.unlink(missing_ok=True)
        except Exception:
            pass
        return None


def guardar_cache_qa(carpeta_cache: Path, clave: str, datos: dict) -> Path:
    if not isinstance(datos, dict):
        raise TypeError("Los datos a guardar en caché deben ser un diccionario.")

    clave_segura = _sanitizar_clave_cache(clave)
    carpeta_cache.mkdir(parents=True, exist_ok=True)

    ruta_final = carpeta_cache / f"{clave_segura}.json"
    ruta_temporal = carpeta_cache / f".{clave_segura}.{os.getpid()}.tmp"

    contenido = json.dumps(datos, ensure_ascii=False, indent=2)
    try:
        ruta_temporal.write_text(contenido, encoding="utf-8")
        os.replace(ruta_temporal, ruta_final)
    finally:
        if ruta_temporal.exists():
            try:
                ruta_temporal.unlink(missing_ok=True)
            except Exception:
                pass

    return ruta_final