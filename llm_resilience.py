from typing import Callable


def ejecutar_llm_con_resiliencia(
    prompt: str,
    system_prompt: str,
    modelo_principal: str,
    preguntar_fn: Callable[..., str],
    extraer_json_fn: Callable[[str], dict | None],
    modelo_fallback: str | None = "llama3.2:3b",
    timeout: int = 900,
    max_reintentos_por_modelo: int = 1,
) -> tuple[dict | None, str, dict]:
    """Ejecuta el LLM con reintentos y fallback automático si falla o no da JSON válido.

    Retorna: (json_extraido_o_none, modelo_efectivo_usado, info_resiliencia)
    """
    modelos_a_intentar: list[str] = [modelo_principal]
    if modelo_fallback and modelo_fallback != modelo_principal:
        modelos_a_intentar.append(modelo_fallback)

    info = {
        "intentos_totales": 0,
        "fallback_activado": False,
        "modelo_final": modelo_principal,
        "ultimo_error": "",
    }

    for idx_modelo, modelo_actual in enumerate(modelos_a_intentar):
        if idx_modelo > 0:
            info["fallback_activado"] = True
            print(
                f"[Resiliencia] Activando fallback hacia modelo local '{modelo_actual}'..."
            )

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
                timeout=timeout,
            )

            if not respuesta_cruda or respuesta_cruda.startswith("ERROR_"):
                info["ultimo_error"] = respuesta_cruda or "Respuesta vacía"
                print(
                    f"[Resiliencia] Fallo en '{modelo_actual}' (intento {intento}): {info['ultimo_error']}"
                )
                continue

            extraido = extraer_json_fn(respuesta_cruda)
            if isinstance(extraido, dict) and extraido:
                info["modelo_final"] = modelo_actual
                return extraido, modelo_actual, info

            info["ultimo_error"] = "No se pudo extraer un JSON válido"
            print(
                f"[Resiliencia] Respuesta sin JSON válido en '{modelo_actual}' (intento {intento})."
            )

    return None, info["modelo_final"], info