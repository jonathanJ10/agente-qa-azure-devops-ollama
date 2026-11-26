import json
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"


def preguntar_llm(
    prompt: str,
    system_prompt: str = "",
    modelo: str = "llama3",
    timeout: int = 600,
    num_ctx: int | None = None,
    num_predict: int | None = None,
    formato_json: bool = False,
) -> str:
    """Envia un prompt a Ollama i retorna el text net."""
    opciones: dict = {
        "temperature": 0.2,
    }
    if isinstance(num_ctx, int) and num_ctx > 0:
        opciones["num_ctx"] = num_ctx
    if isinstance(num_predict, int) and num_predict > 0:
        opciones["num_predict"] = num_predict

    payload: dict = {
        "model": modelo,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "options": opciones,
    }
    if formato_json:
        payload["format"] = "json"

    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except requests.exceptions.ConnectionError:
        return "ERROR_CONEXION: No se pudo conectar a Ollama. Verifica que esté ejecutándose en el puerto 11434."
    except requests.exceptions.Timeout:
        return "ERROR_TIMEOUT: El modelo tardó demasiado en responder."
    except Exception as e:
        return f"ERROR_LLM: {str(e)}"


def extraer_json(texto: str) -> dict | None:
    """Intenta extreure un objecte JSON fins i tot si el model afegeix text abans o després."""
    limpio = (texto or "").strip()
    if not limpio:
        return None

    try:
        parsed = json.loads(limpio)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    idx = 0
    while idx < len(limpio):
        pos_llave = limpio.find("{", idx)
        if pos_llave == -1:
            break
        try:
            obj, _ = decoder.raw_decode(limpio[pos_llave:])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
        idx = pos_llave + 1

    return None