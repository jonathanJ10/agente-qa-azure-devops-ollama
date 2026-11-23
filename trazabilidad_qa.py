import re


def _palabras_clave(texto: str) -> set[str]:
    tokens = re.findall(r"[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ0-9]+", texto.lower())
    return {t for t in tokens if len(t) > 3}


def construir_matriz_trazabilidad(
    datos_qa: dict, subopciones_ca: list[tuple[str, str]]
) -> dict:
    """Construye una matriz de trazabilidad entre criterios/subopciones y casos funcionales."""
    casos = datos_qa.get("casos_de_prueba", {}) if isinstance(datos_qa, dict) else {}
    funcionales = casos.get("funcionales", []) if isinstance(casos.get("funcionales"), list) else []

    matriz: list[dict] = []
    cubiertos = 0

    for idx, (categoria, subopcion) in enumerate(subopciones_ca, start=1):
        sub_lower = subopcion.lower()
        claves = _palabras_clave(subopcion)
        casos_asociados: list[str] = []

        for caso in funcionales:
            if not isinstance(caso, dict):
                continue
            caso_id = str(caso.get("id", "")).strip()
            texto_caso = (
                f"{caso.get('escenario', '')} {caso.get('resultado_esperado', '')}"
            ).lower()

            coincidencia_directa = sub_lower in texto_caso
            coincidencia_claves = len(claves) > 0 and (
                len(claves.intersection(_palabras_clave(texto_caso))) / len(claves) >= 0.6
            )

            if coincidencia_directa or coincidencia_claves:
                if caso_id and caso_id not in casos_asociados:
                    casos_asociados.append(caso_id)

        cubierto = len(casos_asociados) > 0
        if cubierto:
            cubiertos += 1

        matriz.append(
            {
                "item_id": f"CA-{idx:02d}",
                "categoria": categoria or "General",
                "criterio_o_subopcion": subopcion,
                "cubierto": cubierto,
                "casos_funcionales_asociados": casos_asociados,
            }
        )

    total = len(subopciones_ca)
    porcentaje = round((cubiertos / total) * 100, 1) if total > 0 else 100.0

    return {
        "total_criterios_detectados": total,
        "criterios_cubiertos": cubiertos,
        "porcentaje_trazabilidad": porcentaje,
        "matriz": matriz,
    }