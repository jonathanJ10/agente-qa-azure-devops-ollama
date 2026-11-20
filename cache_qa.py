import hashlib
import json
from pathlib import Path


def calcular_clave_cache(
    contenido_req: str, contexto_rag: str, modelo: str
) -> str:
    """Genera un hash SHA-256 único según requerimiento, contexto RAG y modelo."""
    payload = f"{modelo}\n---\n{contexto_rag}\n---\n{contenido_req}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def leer_cache_qa(carpeta_cache: Path, clave: str) -> dict | None:
    """Devuelve los datos cacheados si existen y son un JSON válido."""
    ruta = carpeta_cache / f"{clave}.json"
    if not ruta.exists():
        return None
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return datos if isinstance(datos, dict) else None
    except Exception:
        return None


def guardar_cache_qa(carpeta_cache: Path, clave: str, datos: dict) -> Path:
    """Guarda el resultado estructurado en caché."""
    carpeta_cache.mkdir(parents=True, exist_ok=True)
    ruta = carpeta_cache / f"{clave}.json"
    ruta.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return ruta