import json
from pathlib import Path
from typing import Callable

from cache_qa import calcular_clave_cache, guardar_cache_qa, leer_cache_qa
from llm_resilience import ejecutar_llm_con_resiliencia

PROMPT_REFINAMIENTO = """
Eres un Analista Senior de QA enfocado exclusivamente en refinamiento de requerimientos.
Identifica riesgos, ambigüedades, reglas de negocio incompletas y preguntas de escalamiento.
No redactes historias de usuario ni casos de prueba.

Responde ÚNICAMENTE con un JSON válido (sin markdown ni texto extra) con esta estructura:
{
  "observaciones_criticas": ["máximo 4 puntos concretos"],
  "preguntas_escalamiento": ["máximo 4 preguntas puntuales"]
}
"""

PROMPT_HISTORIAS = """
Eres un Analista Senior de QA enfocado exclusivamente en redactar historias de usuario.
A partir del requerimiento y del refinamiento previo, redacta historias claras y trazables.
No generes casos de prueba.

Responde ÚNICAMENTE con un JSON válido (sin markdown ni texto extra) con esta estructura:
{
  "historias_de_usuario": [
    {
      "id": "HU-01",
      "titulo": "Título breve",
      "descripcion": "Como [rol], quiero [acción], para [beneficio]",
      "criterios_aceptacion": ["criterio o subopción clara"]
    }
  ]
}
"""

PROMPT_CASOS = """
Eres un Arquitecto Senior de QA enfocado exclusivamente en diseñar casos de prueba.
Genera casos concisos, claros y accionables alineados con las historias y criterios recibidos:
- "humo": 2 a 3 casos de disponibilidad, acceso y carga inicial sin errores.
- "funcionales": 1 caso por cada criterio o subopción relevante, redactado de forma clara y verificable.
- "regresion": 2 a 3 casos de no afectación a módulos relacionados o consistencia de datos.
- "automatizacion": 2 a 3 casos repetitivos o críticos, indicando en "candidato_porque" el motivo técnico breve.

Responde ÚNICAMENTE con un JSON válido (sin markdown ni texto extra) con esta estructura:
{
  "casos_de_prueba": {
    "humo": [{"id": "SMK-01", "escenario": "...", "resultado_esperado": "..."}],
    "funcionales": [{"id": "FNC-01", "escenario": "...", "resultado_esperado": "..."}],
    "regresion": [{"id": "REG-01", "escenario": "...", "resultado_esperado": "..."}],
    "automatizacion": [
      {"id": "AUT-01", "escenario": "...", "candidato_porque": "...", "resultado_esperado": "..."}
    ]
  }
}
"""


def _resumir_contexto_compacto(texto: str, max_chars: int = 2200) -> str:
    """Recorta textos auxiliares para evitar prompts pesados en modelos locales."""
    limpio = (texto or "").strip()
    if len(limpio) <= max_chars:
        return limpio
    return limpio[:max_chars].rstrip() + "\n...[contexto acotado para eficiencia]..."


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
    """Orquesta subagentes especializados con contexto acotado y consolida la salida QA."""
    req_compacto = _resumir_contexto_compacto(contenido_req, max_chars=4500)
    rag_compacto = _resumir_contexto_compacto(contexto_rag, max_chars=1800)

    # 1. Subagente de Refinamiento (ligero, ideal para modelo rápido)
    prompt_ref = (
        f"POLÍTICAS QA:\n{rag_compacto}\n\n"
        f"REQUERIMIENTO ({tipo_fuente.upper()}):\n{req_compacto}"
    )
    ref_data, modelo_ref = _ejecutar_etapa_con_cache(
        etapa="refinamiento",
        prompt_usuario=prompt_ref,
        system_prompt=PROMPT_REFINAMIENTO,
        contexto_rag=rag_compacto,
        modelo=modelo_rapido,
        carpeta_cache=carpeta_cache,
        preguntar_fn=preguntar_fn,
        extraer_json_fn=extraer_json_fn,
        modelo_fallback=modelo_principal,
        timeout=timeout,
    )

    ref_json_compacto = _resumir_contexto_compacto(
        json.dumps(ref_data or {}, ensure_ascii=False), max_chars=1200
    )

    # 2. Subagente de Historias de Usuario
    prompt_hu = (
        f"POLÍTICAS QA:\n{rag_compacto}\n\n"
        f"REQUERIMIENTO ({tipo_fuente.upper()}):\n{req_compacto}\n\n"
        f"REFINAMIENTO:\n{ref_json_compacto}"
    )
    hu_data, modelo_hu = _ejecutar_etapa_con_cache(
        etapa="historias",
        prompt_usuario=prompt_hu,
        system_prompt=PROMPT_HISTORIAS,
        contexto_rag=rag_compacto,
        modelo=modelo_principal,
        carpeta_cache=carpeta_cache,
        preguntar_fn=preguntar_fn,
        extraer_json_fn=extraer_json_fn,
        modelo_fallback=modelo_rapido,
        timeout=timeout,
    )

    hu_compacto = _resumir_contexto_compacto(
        json.dumps((hu_data or {}).get("historias_de_usuario", []), ensure_ascii=False),
        max_chars=1800,
    )

    # 3. Subagente de Casos de Prueba
    prompt_casos = (
        f"REQUERIMIENTO ({tipo_fuente.upper()}):\n{req_compacto}\n\n"
        f"HISTORIAS Y CRITERIOS:\n{hu_compacto}"
    )
    casos_data, modelo_casos = _ejecutar_etapa_con_cache(
        etapa="casos_prueba",
        prompt_usuario=prompt_casos,
        system_prompt=PROMPT_CASOS,
        contexto_rag=rag_compacto,
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