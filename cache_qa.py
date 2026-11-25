import hashlib
import json
from pathlib import Path

CACHE_SCHEMA_VERSION = "v2.1"


def calcular_clave_cache(
    contenido_req: str,
    contexto_rag: str,
    modelo: str,
    version_esquema: str = CACHE_SCHEMA_VERSION,
) -> str:
    """Genera un hash SHA-256 incluyendo la versión de esquema para evitar caché obsoleta."""
    carga = json.dumps(
        {
            "schema_version": version_esquema,
            "modelo": str(modelo or "").strip(),
            "contenido_req": str(contenido_req or ""),
            "contexto_rag": str(contexto_rag or ""),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(carga.encode("utf-8")).hexdigest()


def leer_cache_qa(carpeta_cache: Path, clave: str) -> dict | None:
    ruta = carpeta_cache / f"{clave}.json"
    if not ruta.exists():
        return None
    try:
        data = json.loads(ruta.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def guardar_cache_qa(carpeta_cache: Path, clave: str, datos: dict) -> Path:
    carpeta_cache.mkdir(parents=True, exist_ok=True)
    ruta = carpeta_cache / f"{clave}.json"
    ruta.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return ruta