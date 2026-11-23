from pathlib import Path
from typing import Callable

from cache_qa import calcular_clave_cache, guardar_cache_qa, leer_cache_qa
from llm_resilience import ejecutar_llm_con_resiliencia

PROMPT_REFINAMIENTO = """
Eres un Analista Senior de QA especializado en refinamiento de requerimientos.
Analiza el contexto RAG y el requerimiento y responde ÚNICAMENTE con un JSON válido:
{
  "observaciones_criticas": ["..."],
  "preguntas_escalamiento": ["..."]
}
Sé concreto, técnico y accionable.
"""

PROMPT_HISTORIAS = """
Eres un Analista Senior de QA experto en redacción de historias de usuario.
Con base en el contexto RAG, el requerimiento y el refinamiento previo, responde ÚNICAMENTE con un JSON válido:
{
  "historias_de_usuario": [
    {
      "id": "HU-01",
      "titulo": "...",
      "descripcion": "Como [rol], quiero [acción], para [beneficio]",
      "criterios_aceptacion": ["..."]
    }
  ]
}
"""

PROMPT_CASOS = """
Eres un Arquitecto Senior de QA diseñando estrategias de prueba.
Responde ÚNICAMENTE con un JSON válido con esta estructura exacta:
{
  "casos_de_prueba": {
    "humo": [{"id": "SMK-01", "escenario": "...", "resultado_esperado": "..."}],
    "funcionales": [{"id": "FNC-01", "escenario": "...", "resultado_esperado": "..."}],
    "regresion": [{"id": "REG-01", "escenario": "...", "resultado_esperado": "..."}],
    "automatizacion": [{"id": "AUT-01", "escenario": "...", "candidato_porque": "...", "resultado_esperado": "..."}]
  }
}
Incluye un caso funcional por cada criterio o subopción relevante, 2-3 casos de humo, 2-3 de regresión y 2-3 de automatización con justificación técnica en "candidato_porque".
"""


def _ejecutar_etapa_con_cache(
    etapa: str,
    prompt_usuario: str,
    system_prompt: str,
    contexto_rag: str,
    modelo: str,
    carpeta_cache: Path,
    preguntar_fn: Callable[..., str],
    extraer_json_fn: Callable[[str], dict | None],
    modelo_fallback: str = "llama3.2:3b",
    timeout: int = 900,
) -> tuple[dict | None, str]:
    clave = calcular_clave_cache(
        contenido_req=f"[{etapa}]\n{prompt_usuario}",
        contexto_rag=contexto_rag,
        modelo=modelo,
    )
    cacheado = leer_cache_qa(carpeta_cache, clave)
    if isinstance(cacheado, dict) and cacheado:
        print(f"  [Subagente:{etapa}] Cache hit ({clave[:8]}...).")
        return cacheado, modelo

    print(f"  [Subagente:{etapa}] Ejecutando con {modelo}...")
    extraido, modelo_efectivo, info = ejecutar_llm_con_resiliencia(
        prompt=prompt_usuario,
        system_prompt=system_prompt,
        modelo_principal=modelo,
        preguntar_fn=preguntar_fn,
        extraer_json_fn=extraer_json_fn,
        modelo_fallback=modelo_fallback,
        timeout=timeout,
        max_reintentos_por_modelo=1,
    )
    if isinstance(extraido, dict) and extraido:
        guardar_cache_qa(carpeta_cache, clave, extraido)
        return extraido, modelo_efectivo

    print(f"  [Subagente:{etapa}] Sin resultado válido ({info.get('ultimo_error', '')}).")
    return None, modelo_efectivo


def ejecutar_orquestacion_subagentes_qa(
    contenido_req: str,
    contexto_rag: str,
    tipo_fuente: str,
    modelo_principal: str,
    modelo_rapido: str,
    carpeta_cache: Path,
    preguntar_fn: Callable[..., str],
    extraer_json_fn: Callable[[str], dict | None],
    timeout: int = 900,
) -> tuple[dict | None, str]:
    """Orquesta subagentes especializados por etapa y consolida la salida QA."""
    base_ctx = (
        f"POLÍTICAS INTERNAS DE QA (RAG):\n{contexto_rag}\n\n"
        f"REQUERIMIENTO ({tipo_fuente.upper()}):\n{contenido_req}"
    )

    ref_data, modelo_ref = _ejecutar_etapa_con_cache(
        etapa="refinamiento",
        prompt_usuario=base_ctx,
        system_prompt=PROMPT_REFINAMIENTO,
        contexto_rag=contexto_rag,
        modelo=modelo_rapido,
        carpeta_cache=carpeta_cache,
        preguntar_fn=preguntar_fn,
        extraer_json_fn=extraer_json_fn,
        modelo_fallback=modelo_principal,
        timeout=timeout,
    )

    ctx_con_ref = f"{base_ctx}\n\nREFINAMIENTO PREVIO:\n{ref_data or {}}"
    hu_data, modelo_hu = _ejecutar_etapa_con_cache(
        etapa="historias",
        prompt_usuario=ctx_con_ref,
        system_prompt=PROMPT_HISTORIAS,
        contexto_rag=contexto_rag,
        modelo=modelo_principal,
        carpeta_cache=carpeta_cache,
        preguntar_fn=preguntar_fn,
        extraer_json_fn=extraer_json_fn,
        modelo_fallback=modelo_rapido,
        timeout=timeout,
    )

    ctx_con_hu = f"{ctx_con_ref}\n\nHISTORIAS DE USUARIO:\n{hu_data or {}}"
    casos_data, modelo_casos = _ejecutar_etapa_con_cache(
        etapa="casos_prueba",
        prompt_usuario=ctx_con_hu,
        system_prompt=PROMPT_CASOS,
        contexto_rag=contexto_rag,
        modelo=modelo_principal,
        carpeta_cache=carpeta_cache,
        preguntar_fn=preguntar_fn,
        extraer_json_fn=extraer_json_fn,
        modelo_fallback=modelo_rapido,
        timeout=timeout,
    )

    if not any([ref_data, hu_data, casos_data]):
        return None, modelo_casos or modelo_hu or modelo_ref

    consolidado: dict = {
        "refinamiento": {
            "observaciones_criticas": (ref_data or {}).get("observaciones_criticas", []),
            "preguntas_escalamiento": (ref_data or {}).get("preguntas_escalamiento", []),
        },
        "historias_de_usuario": (hu_data or {}).get("historias_de_usuario", []),
        "casos_de_prueba": (casos_data or {}).get("casos_de_prueba", {}),
    }

    modelo_reportado = modelo_casos or modelo_hu or modelo_ref
    return consolidado, modelo_reportado