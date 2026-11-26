from pathlib import Path
from typing import Callable


def _a_lista_strings(valor: object) -> list[str]:
    if isinstance(valor, list):
        return [str(x).strip() for x in valor if str(x).strip()]
    if isinstance(valor, str) and valor.strip():
        return [valor.strip()]
    return []


def _formatear_criterio_gherkin(criterio: str, titulo_hu: str) -> str:
    """Garantiza que un criterio de aceptación contenga estructura Dado/Cuando/Entonces."""
    limpio = criterio.strip()
    baja = limpio.lower()
    tiene_dado = "dado" in baja
    tiene_cuando = "cuando" in baja
    tiene_entonces = "entonces" in baja

    if tiene_dado and tiene_cuando and tiene_entonces:
        return limpio

    contexto = f"el contexto de '{titulo_hu}'" if titulo_hu else "las condiciones previas del flujo"
    if not tiene_dado and not tiene_cuando and not tiene_entonces:
        return (
            f"Dado {contexto}, cuando se evalúa '{limpio}', "
            f"entonces el sistema cumple la condición esperada de forma trazable."
        )

    partes: list[str] = []
    if not tiene_dado:
        partes.append(f"Dado {contexto}")
    partes.append(limpio)
    if not tiene_cuando:
        partes.append("cuando se ejecuta la acción correspondiente")
    if not tiene_entonces:
        partes.append("entonces el sistema valida y registra el resultado esperado")
    return ", ".join(partes) + ("." if not limpio.endswith(".") else "")


def _asegurar_criterios_gherkin(criterios: list[str], titulo_hu: str) -> list[str]:
    if not criterios:
        base_titulo = titulo_hu or "el flujo solicitado"
        return [
            f"Dado un usuario autorizado en {base_titulo}, cuando ejecuta el flujo con datos válidos, entonces el sistema procesa la operación y registra trazabilidad.",
            f"Dado datos inválidos o fuera de regla en {base_titulo}, cuando intenta procesar la operación, entonces el sistema rechaza la solicitud de forma controlada.",
        ]
    return [_formatear_criterio_gherkin(c, titulo_hu) for c in criterios]


def _completar_cobertura_istqb_funcional(funcionales: list[dict]) -> list[dict]:
    """Completa de forma determinista huecos ISTQB críticos sin alterar casos existentes."""
    salida = list(funcionales)
    texto_existente = " ".join(
        f"{c.get('escenario', '')} {c.get('resultado_esperado', '')}".lower()
        for c in salida
    )
    ids_existentes = {str(c.get("id", "")).strip() for c in salida}

    def _siguiente_id_fnc() -> str:
        n = len(salida) + 1
        while f"FNC-{n:02d}" in ids_existentes:
            n += 1
        ids_existentes.add(f"FNC-{n:02d}")
        return f"FNC-{n:02d}"

    # 1. Partición de equivalencia negativa / excepción controlada
    palabras_negativas = (
        "inválid",
        "invalido",
        "rechaz",
        "error",
        "excep",
        "bloque",
        "vencid",
        "no existe",
        "inexistente",
    )
    if salida and not any(p in texto_existente for p in palabras_negativas):
        salida.append(
            {
                "id": _siguiente_id_fnc(),
                "escenario": (
                    "Partición inválida / excepción: ejecutar el flujo con datos fuera de regla, "
                    "estado no permitido o referencia inexistente."
                ),
                "resultado_esperado": (
                    "El sistema rechaza la operación de forma controlada, no altera el estado "
                    "y registra el motivo de rechazo."
                ),
            }
        )

    # 2. Análisis de valores límite / frontera (montos, fechas, plazos o cantidades)
    palabras_limite = (
        "límite",
        "limite",
        "frontera",
        "mínimo",
        "minimo",
        "máximo",
        "maximo",
        "plazo",
        "vigencia",
        "monto",
        "cuota",
        "cero",
    )
    if salida and not any(p in texto_existente for p in palabras_limite):
        salida.append(
            {
                "id": _siguiente_id_fnc(),
                "escenario": (
                    "Valores límite / frontera: evaluar el comportamiento en los bordes permitidos "
                    "y justo fuera de ellos (montos, fechas/vigencias o plazos de convenio)."
                ),
                "resultado_esperado": (
                    "Los valores dentro del límite válido son aceptados y los valores en el borde "
                    "inválido o vencido son controlados según regla de negocio."
                ),
            }
        )

    # 3. Autorización / control de acceso por rol
    palabras_rol = (
        "rol",
        "permiso",
        "autoriz",
        "acceso",
        "no autorizado",
        "privilegio",
        "auditor",
    )
    if salida and not any(p in texto_existente for p in palabras_rol):
        salida.append(
            {
                "id": _siguiente_id_fnc(),
                "escenario": (
                    "Autorización por rol: validar que un usuario sin permisos suficientes intente "
                    "ejecutar o modificar una operación restringida del flujo."
                ),
                "resultado_esperado": (
                    "El sistema deniega el acceso por falta de permisos y deja registro de "
                    "auditoría sin ejecutar la acción."
                ),
            }
        )

    return salida


def normalizar_y_validar_qa(datos: dict | None) -> dict:
    """Normaliza la estructura QA garantizando claves, IDs, campos mínimos y cobertura ISTQB."""
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
        criterios_raw = _a_lista_strings(hu.get("criterios_aceptacion"))
        criterios = _asegurar_criterios_gherkin(criterios_raw, titulo)
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

    funcionales_normalizados = _completar_cobertura_istqb_funcional(
        _normalizar_lista_casos(casos_dict.get("funcionales"), "FNC")
    )

    casos_normalizados = {
        "humo": humo_normalizado,
        "funcionales": funcionales_normalizados,
        "regresion": _normalizar_lista_casos(casos_dict.get("regresion"), "REG"),
        "automatizacion": _normalizar_lista_casos(
            casos_dict.get("automatizacion"), "AUT", incluir_motivo_auto=True
        ),
    }

    resultado_final: dict = {
        "refinamiento": refinamiento,
        "historias_de_usuario": historias_normalizadas,
        "casos_de_prueba": casos_normalizados,
    }
    if "_telemetria_subagentes" in base and isinstance(base["_telemetria_subagentes"], dict):
        resultado_final["_telemetria_subagentes"] = base["_telemetria_subagentes"]

    return resultado_final


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