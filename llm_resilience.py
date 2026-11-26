import json
import re
import time
from typing import Callable


def _rescate_json_basico(texto: str) -> dict | None:
    """Intenta recuperar un objeto JSON delimitado por llaves si el extractor principal falla."""
    if not texto or "{" not in texto or "}" not in texto:
        return None
    inicio = texto.find("{")
    fin = texto.rfind("}")
    if fin <= inicio:
        return None
    fragmento = texto[inicio : fin + 1]
    fragmento_limpio = re.sub(r",\s*([}\]])", r"\1", fragmento)
    try:
        parsed = json.loads(fragmento_limpio)
        return parsed if isinstance(parsed, dict) and parsed else None
    except Exception:
        return None


def ejecutar_llm_con_resiliencia(
    prompt: str,
    system_prompt: str,
    modelo_principal: str,
    preguntar_fn: Callable[..., str],
    extraer_json_fn: Callable[[str], dict | None],
    modelo_fallback: str | None = "llama3.2:3b",
    timeout: int = 900,
    max_reintentos_por_modelo: int = 1,
    timeout_fallback: int | None = 300,
) -> tuple[dict | None, str, dict]:
    """Ejecuta el LLM con reintentos y fallback automático si falla o no da JSON válido.

    Retorna: (json_extraido_o_none, modelo_efectivo_usado, info_resiliencia)
    """
    t_inicio = time.perf_counter()
    modelos_a_intentar: list[str] = [modelo_principal]
    if modelo_fallback and modelo_fallback != modelo_principal:
        modelos_a_intentar.append(modelo_fallback)

    info = {
        "intentos_totales": 0,
        "fallback_activado": False,
        "modelo_final": modelo_principal,
        "ultimo_error": "",
        "timeout_efectivo": timeout,
        "duracion_total_s": 0.0,
    }

    for idx_modelo, modelo_actual in enumerate(modelos_a_intentar):
        if idx_modelo > 0:
            info["fallback_activado"] = True
            print(
                f"[Resiliencia] Activando fallback hacia modelo local '{modelo_actual}'..."
            )

        timeout_actual = timeout
        if idx_modelo > 0 and timeout_fallback is not None:
            timeout_actual = min(timeout, timeout_fallback)
        elif ":3b" in modelo_actual or ":1b" in modelo_actual:
            timeout_actual = min(timeout, 360)

        info["timeout_efectivo"] = timeout_actual

        for intento in range(1, max_reintentos_por_modelo + 2):
            info["intentos_totales"] += 1
            if intento > 1:
                print(
                    f"[Resiliencia] Reintento #{intento - 1} con modelo '{modelo_actual}'..."
                )

            respuesta_cruda = preguntar_fn(
                prompt=prompt,
                system_prompt=system_prompt,
                modelo=modelo_actual,
                timeout=timeout_actual,
            )

            if not respuesta_cruda or respuesta_cruda.startswith("ERROR_"):
                info["ultimo_error"] = respuesta_cruda or "Respuesta vacía"
                print(
                    f"[Resiliencia] Fallo en '{modelo_actual}' (intento {intento}): {info['ultimo_error']}"
                )
                continue

            extraido = extraer_json_fn(respuesta_cruda)
            if not (isinstance(extraido, dict) and extraido):
                extraido = _rescate_json_basico(respuesta_cruda)

            if isinstance(extraido, dict) and extraido:
                info["modelo_final"] = modelo_actual
                info["duracion_total_s"] = round(time.perf_counter() - t_inicio, 2)
                return extraido, modelo_actual, info

            info["ultimo_error"] = "No se pudo extraer un JSON válido"
            print(
                f"[Resiliencia] Respuesta sin JSON válido en '{modelo_actual}' (intento {intento})."
            )

    info["duracion_total_s"] = round(time.perf_counter() - t_inicio, 2)
    return None, info["modelo_final"], info