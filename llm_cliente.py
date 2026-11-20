import json
import re
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"


def preguntar_llm(
    prompt: str,
    system_prompt: str = "",
    modelo: str = "llama3",
    timeout: int = 600,
) -> str:
    """Envía un prompt a Ollama y devuelve el texto limpio."""
    payload = {
        "model": modelo,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "options": {
            "temperature": 0.2  # Baja temperatura para respuestas más precisas y consistentes
        },
    }
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
    """Intenta extraer un objeto JSON incluso si el modelo agrega texto antes o después."""
    texto = texto.strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", texto, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
    return None