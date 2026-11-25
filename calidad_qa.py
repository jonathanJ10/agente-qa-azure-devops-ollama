def evaluar_calidad_artefactos(datos_qa: dict) -> dict:
    """Evalúa completitud, estructura y rigor QA de los artefactos generados (puntaje 0-100)."""
    if not isinstance(datos_qa, dict):
        return {
            "puntaje": 0,
            "aprobado": False,
            "advertencias": ["La estructura de datos QA no es un diccionario válido."],
            "hallazgos_detalle": ["estructura_invalida"],
        }

    advertencias: list[str] = []
    hallazgos: list[str] = []
    puntaje = 100

    refinamiento = datos_qa.get("refinamiento", {})
    obs = refinamiento.get("observaciones_criticas", []) if isinstance(refinamiento, dict) else []
    pregs = refinamiento.get("preguntas_escalamiento", []) if isinstance(refinamiento, dict) else []
    if not obs and not pregs:
        puntaje -= 15
        advertencias.append("Sin observaciones críticas ni preguntas de escalamiento.")
        hallazgos.append("refinamiento_vacio")

    historias = datos_qa.get("historias_de_usuario", [])
    if not isinstance(historias, list) or len(historias) == 0:
        puntaje -= 25
        advertencias.append("No se generaron historias de usuario.")
        hallazgos.append("historias_faltantes")
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
            hallazgos.append("formato_hu_incompleto")

        sin_gherkin = 0
        for h in historias:
            if not isinstance(h, dict):
                continue
            crits = h.get("criterios_aceptacion", [])
            texto_crits = " ".join(str(c).lower() for c in crits) if isinstance(crits, list) else ""
            if not ("dado" in texto_crits and "cuando" in texto_crits and "entonces" in texto_crits):
                sin_gherkin += 1
        if sin_gherkin > 0:
            puntaje -= 5
            advertencias.append(
                f"{sin_gherkin} historia(s) sin criterios Gherkin completos (Dado/Cuando/Entonces)."
            )
            hallazgos.append("criterios_sin_gherkin")

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
        hallazgos.append("funcionales_faltantes")
    else:
        funcionales_incompletos = sum(
            1
            for f in funcionales
            if not isinstance(f, dict)
            or not str(f.get("escenario", "")).strip()
            or not str(f.get("resultado_esperado", "")).strip()
        )
        if funcionales_incompletos > 0:
            puntaje -= 10
            advertencias.append(
                f"{funcionales_incompletos} caso(s) funcional(es) sin escenario o resultado esperado."
            )
            hallazgos.append("funcionales_incompletos")

    if len(humo) < 2:
        puntaje -= 10
        advertencias.append(f"Pocos casos de humo ({len(humo)} encontrados, se sugieren >= 2).")
        hallazgos.append("humo_insuficiente")

    if len(regresion) < 2:
        puntaje -= 10
        advertencias.append(
            f"Pocos casos de regresión ({len(regresion)} encontrados, se sugieren >= 2)."
        )
        hallazgos.append("regresion_insuficiente")

    if len(automatizacion) < 2:
        puntaje -= 10
        advertencias.append(
            f"Pocos casos de automatización ({len(automatizacion)} encontrados, se sugieren >= 2)."
        )
        hallazgos.append("automatizacion_insuficiente")
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
            hallazgos.append("automatizacion_sin_motivo")

    puntaje_final = max(0, puntaje)
    return {
        "puntaje": puntaje_final,
        "aprobado": puntaje_final >= 70,
        "advertencias": advertencias,
        "hallazgos_detalle": hallazgos,
    }