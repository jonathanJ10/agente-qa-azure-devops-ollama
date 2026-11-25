from pathlib import Path
from typing import Callable


def _a_lista_strings(valor: object) -> list[str]:
    if isinstance(valor, list):
        return [str(x).strip() for x in valor if str(x).strip()]
    if isinstance(valor, str) and valor.strip():
        return [valor.strip()]
    return []


def normalizar_y_validar_qa(datos: dict | None) -> dict:
    """Normaliza la estructura QA garantizando claves, IDs y campos mínimos."""
    base = datos if isinstance(datos, dict) else {}

    refinamiento_raw = base.get("refinamiento")
    refinamiento_dict = refinamiento_raw if isinstance(refinamiento_raw, dict) else {}

    refinamiento = {
        "observaciones_criticas": _a_lista_strings(
            refinamiento_dict.get("observaciones_criticas")
        ),
        "preguntas_escalamiento": _a_lista_strings(
            refinamiento_dict.get("preguntas_escalamiento")
        ),
    }

    hus_raw = base.get("historias_de_usuario")
    hus_list = hus_raw if isinstance(hus_raw, list) else []
    historias_normalizadas: list[dict] = []

    for idx, hu in enumerate(hus_list, start=1):
        if not isinstance(hu, dict):
            continue
        hu_id = str(hu.get("id") or f"HU-{idx:02d}").strip()
        titulo = str(hu.get("titulo") or f"Historia de usuario {idx}").strip()
        descripcion = str(
            hu.get("descripcion")
            or "Como usuario del sistema, quiero ejecutar el flujo requerido, para cumplir el objetivo del negocio."
        ).strip()
        criterios = _a_lista_strings(hu.get("criterios_aceptacion"))
        historias_normalizadas.append(
            {
                "id": hu_id,
                "titulo": titulo,
                "descripcion": descripcion,
                "criterios_aceptacion": criterios,
            }
        )

    if not historias_normalizadas:
        historias_normalizadas.append(
            {
                "id": "HU-01",
                "titulo": "Flujo principal del requerimiento",
                "descripcion": "Como analista u operador del sistema, quiero procesar el requerimiento según sus reglas de negocio, para garantizar una operación confiable y trazable.",
                "criterios_aceptacion": [
                    "Dado un usuario autorizado, cuando ejecuta el flujo principal con datos válidos, entonces el sistema procesa la operación y registra trazabilidad.",
                    "Dado datos inválidos o fuera de regla, cuando intenta procesar la operación, entonces el sistema bloquea el flujo y muestra un mensaje controlado.",
                ],
            }
        )

    casos_raw = base.get("casos_de_prueba")
    casos_dict = casos_raw if isinstance(casos_raw, dict) else {}

    def _normalizar_lista_casos(
        items: object, prefijo: str, incluir_motivo_auto: bool = False
    ) -> list[dict]:
        lista_in = items if isinstance(items, list) else []
        salida: list[dict] = []
        for idx, item in enumerate(lista_in, start=1):
            if not isinstance(item, dict):
                continue
            escenario = str(item.get("escenario") or "").strip()
            resultado = str(item.get("resultado_esperado") or "").strip()
            if not escenario and not resultado:
                continue
            caso = {
                "id": str(item.get("id") or f"{prefijo}-{idx:02d}").strip(),
                "escenario": escenario or "Validar escenario del requerimiento.",
                "resultado_esperado": resultado
                or "El sistema responde conforme a la regla esperada sin errores.",
            }
            if incluir_motivo_auto:
                caso["candidato_porque"] = str(
                    item.get("candidato_porque")
                    or "Alta repetitividad y valor para regresión continua."
                ).strip()
            salida.append(caso)
        return salida

    humo_normalizado = _normalizar_lista_casos(casos_dict.get("humo"), "SMK")
    if len(humo_normalizado) < 2:
        humo_base = [
            {
                "id": "SMK-01",
                "escenario": "Verificar acceso autenticado y disponibilidad del módulo principal del requerimiento.",
                "resultado_esperado": "El módulo carga correctamente sin errores HTTP ni bloqueos de sesión.",
            },
            {
                "id": "SMK-02",
                "escenario": "Verificar consulta o carga inicial de datos del requerimiento en estado operativo normal.",
                "resultado_esperado": "La información se presenta de forma coherente y sin fallos críticos.",
            },
        ]
        ids_existentes = {c["id"] for c in humo_normalizado}
        for base_caso in humo_base:
            if len(humo_normalizado) >= 2:
                break
            if base_caso["id"] not in ids_existentes:
                humo_normalizado.append(base_caso)

    casos_normalizados = {
        "humo": humo_normalizado,
        "funcionales": _normalizar_lista_casos(casos_dict.get("funcionales"), "FNC"),
        "regresion": _normalizar_lista_casos(casos_dict.get("regresion"), "REG"),
        "automatizacion": _normalizar_lista_casos(
            casos_dict.get("automatizacion"), "AUT", incluir_motivo_auto=True
        ),
    }

    return {
        "refinamiento": refinamiento,
        "historias_de_usuario": historias_normalizadas,
        "casos_de_prueba": casos_normalizados,
    }


def guardar_docx_seguro(
    datos_qa: dict,
    ruta_docx: Path,
    exportar_fn: Callable[[dict, str], None],
) -> Path | None:
    """Exporta el Word de forma segura y evita fallos si el archivo está abierto."""
    ruta_docx.parent.mkdir(parents=True, exist_ok=True)
    try:
        exportar_fn(datos_qa, str(ruta_docx))
        return ruta_docx
    except PermissionError:
        ruta_alterna = ruta_docx.with_name(f"{ruta_docx.stem}_nuevo{ruta_docx.suffix}")
        exportar_fn(datos_qa, str(ruta_alterna))
        return ruta_alterna