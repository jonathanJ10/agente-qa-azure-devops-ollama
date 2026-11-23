def evaluar_calidad_artefactos(datos_qa: dict) -> dict:
    """Evalúa completitud y estructura de los artefactos QA generados (puntaje 0-100)."""
    if not isinstance(datos_qa, dict):
        return {
            "puntaje": 0,
            "aprobado": False,
            "advertencias": ["La estructura de datos QA no es un diccionario válido."],
        }

    advertencias: list[str] = []
    puntaje = 100

    refinamiento = datos_qa.get("refinamiento", {})
    obs = refinamiento.get("observaciones_criticas", []) if isinstance(refinamiento, dict) else []
    pregs = refinamiento.get("preguntas_escalamiento", []) if isinstance(refinamiento, dict) else []
    if not obs and not pregs:
        puntaje -= 15
        advertencias.append("Sin observaciones críticas ni preguntas de escalamiento.")

    historias = datos_qa.get("historias_de_usuario", [])
    if not isinstance(historias, list) or len(historias) == 0:
        puntaje -= 25
        advertencias.append("No se generaron historias de usuario.")
    else:
        sin_formato = sum(
            1
            for h in historias
            if not isinstance(h, dict)
            or "quiero" not in str(h.get("descripcion", "")).lower()
        )
        if sin_formato > 0:
            puntaje -= 10
            advertencias.append(
                f"{sin_formato} historia(s) sin estructura 'Como..., quiero..., para...'."
            )

    casos = datos_qa.get("casos_de_prueba", {})
    if not isinstance(casos, dict):
        casos = {}

    funcionales = casos.get("funcionales", []) if isinstance(casos.get("funcionales"), list) else []
    humo = casos.get("humo", []) if isinstance(casos.get("humo"), list) else []
    regresion = casos.get("regresion", []) if isinstance(casos.get("regresion"), list) else []
    automatizacion = (
        casos.get("automatizacion", [])
        if isinstance(casos.get("automatizacion"), list)
        else []
    )

    if len(funcionales) == 0:
        puntaje -= 25
        advertencias.append("No hay casos funcionales generados.")

    if len(humo) < 2:
        puntaje -= 10
        advertencias.append(f"Pocos casos de humo ({len(humo)} encontrados, se sugieren >= 2).")

    if len(regresion) < 2:
        puntaje -= 10
        advertencias.append(
            f"Pocos casos de regresión ({len(regresion)} encontrados, se sugieren >= 2)."
        )

    if len(automatizacion) < 2:
        puntaje -= 10
        advertencias.append(
            f"Pocos casos de automatización ({len(automatizacion)} encontrados, se sugieren >= 2)."
        )
    else:
        sin_motivo = sum(
            1
            for a in automatizacion
            if not isinstance(a, dict) or not str(a.get("candidato_porque", "")).strip()
        )
        if sin_motivo > 0:
            puntaje -= 5
            advertencias.append(
                f"{sin_motivo} caso(s) de automatización sin 'candidato_porque'."
            )

    puntaje_final = max(0, puntaje)
    return {
        "puntaje": puntaje_final,
        "aprobado": puntaje_final >= 70,
        "advertencias": advertencias,
    }