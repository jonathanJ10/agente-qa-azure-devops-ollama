from pathlib import Path


def normalizar_y_validar_qa(datos: dict | None) -> dict:
    """Valida y normaliza la estructura JSON generada por el LLM antes de exportar."""
    if not isinstance(datos, dict):
        datos = {}

    refinamiento = datos.get("refinamiento")
    if not isinstance(refinamiento, dict):
        refinamiento = {}

    obs = refinamiento.get("observaciones_criticas")
    if not isinstance(obs, list):
        obs = [str(obs)] if obs else []
    obs_limpias = [str(x).strip() for x in obs if str(x).strip()]

    pregs = refinamiento.get("preguntas_escalamiento")
    if not isinstance(pregs, list):
        pregs = [str(pregs)] if pregs else []
    pregs_limpias = [str(x).strip() for x in pregs if str(x).strip()]

    hus_raw = datos.get("historias_de_usuario")
    if not isinstance(hus_raw, list):
        hus_raw = []
    hus_limpias: list[dict] = []
    for idx, hu in enumerate(hus_raw, start=1):
        if not isinstance(hu, dict):
            continue
        ca_raw = hu.get("criterios_aceptacion", [])
        if not isinstance(ca_raw, list):
            ca_raw = [str(ca_raw)] if ca_raw else []
        hus_limpias.append(
            {
                "id": str(hu.get("id") or f"HU-{idx:02d}").strip(),
                "titulo": str(hu.get("titulo") or "Historia de Usuario sin título").strip(),
                "descripcion": str(hu.get("descripcion") or "").strip(),
                "criterios_aceptacion": [
                    str(c).strip() for c in ca_raw if str(c).strip()
                ],
            }
        )

    casos_raw = datos.get("casos_de_prueba")
    if not isinstance(casos_raw, dict):
        casos_raw = {}

    def _normalizar_lista_casos(
        lista_entrada: object, prefijo: str, incluir_auto: bool = False
    ) -> list[dict]:
        if not isinstance(lista_entrada, list):
            return []
        salida: list[dict] = []
        for idx, item in enumerate(lista_entrada, start=1):
            if not isinstance(item, dict):
                continue
            escenario = str(item.get("escenario") or "").strip()
            resultado = str(item.get("resultado_esperado") or "").strip()
            if not escenario and not resultado:
                continue
            caso: dict[str, str] = {
                "id": str(item.get("id") or f"{prefijo}-{idx:02d}").strip(),
                "escenario": escenario,
                "resultado_esperado": resultado,
            }
            if incluir_auto:
                caso["candidato_porque"] = str(
                    item.get("candidato_porque")
                    or "Prueba repetitiva o crítica candidata a automatización."
                ).strip()
            salida.append(caso)
        return salida

    return {
        "refinamiento": {
            "observaciones_criticas": obs_limpias,
            "preguntas_escalamiento": pregs_limpias,
        },
        "historias_de_usuario": hus_limpias,
        "casos_de_prueba": {
            "humo": _normalizar_lista_casos(casos_raw.get("humo"), "SMK"),
            "funcionales": _normalizar_lista_casos(casos_raw.get("funcionales"), "FNC"),
            "regresion": _normalizar_lista_casos(casos_raw.get("regresion"), "REG"),
            "automatizacion": _normalizar_lista_casos(
                casos_raw.get("automatizacion"), "AUT", incluir_auto=True
            ),
        },
    }


def guardar_docx_seguro(
    datos_estructurados: dict, ruta_docx: Path, exportador_fn
) -> Path | None:
    """Guarda el .docx y, si está bloqueado por Word, lo guarda con un nombre alternativo."""
    try:
        exportador_fn(datos_estructurados, str(ruta_docx))
        return ruta_docx
    except PermissionError:
        ruta_alternativa = ruta_docx.with_name(f"{ruta_docx.stem}_nuevo.docx")
        print(
            f"Aviso: '{ruta_docx.name}' está abierto o bloqueado. "
            f"Guardando en '{ruta_alternativa.name}'..."
        )
        try:
            exportador_fn(datos_estructurados, str(ruta_alternativa))
            return ruta_alternativa
        except Exception as exc:
            print(f"No se pudo guardar el documento Word: {exc}")
            return None