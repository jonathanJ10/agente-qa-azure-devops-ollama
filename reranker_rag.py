import re

TERMINOS_QA_CLAVE = {
    "criterio",
    "criterios",
    "aceptacion",
    "aceptación",
    "prueba",
    "pruebas",
    "humo",
    "smoke",
    "funcional",
    "funcionales",
    "regresion",
    "regresión",
    "automatizacion",
    "automatización",
    "escalamiento",
    "refinamiento",
    "historia",
    "usuario",
    "reporte",
    "modulo",
    "módulo",
    "validacion",
    "validación",
}


def _tokenizar(texto: str) -> set[str]:
    palabras = re.findall(r"[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ0-9_]+", texto.lower())
    return {p for p in palabras if len(p) > 2}


def rerank_fragmentos_rag(
    consulta: str, fragmentos: list[str] | str, top_k: int = 3
) -> str:
    """Reordena fragmentos del RAG según relevancia con la consulta y términos QA."""
    if isinstance(fragmentos, str):
        lista_frag = [
            bloque.strip()
            for bloque in re.split(r"\n\s*---\s*\n|\n{2,}", fragmentos)
            if bloque.strip()
        ]
    else:
        lista_frag = [f.strip() for f in fragmentos if isinstance(f, str) and f.strip()]

    if not lista_frag:
        return ""

    tokens_consulta = _tokenizar(consulta)
    puntuados: list[tuple[float, int, str]] = []

    for idx, frag in enumerate(lista_frag):
        tokens_frag = _tokenizar(frag)
        coincidencias = len(tokens_consulta.intersection(tokens_frag))
        boost_qa = sum(1 for t in tokens_frag if t in TERMINOS_QA_CLAVE)
        longitud_normalizada = min(len(frag) / 500.0, 2.0)
        score = (coincidencias * 2.0) + (boost_qa * 0.5) + (longitud_normalizada * 0.25)
        puntuados.append((score, idx, frag))

    puntuados.sort(key=lambda x: (-x[0], x[1]))
    seleccionados = [frag for _, _, frag in puntuados[:top_k]]
    return "\n\n---\n\n".join(seleccionados)


def preparar_texto_por_secciones(texto: str, max_chars: int = 12000) -> str:
    """Recorta priorizando el inicio y los bloques de Criterios de aceptación."""
    if len(texto) <= max_chars:
        return texto

    bloques = re.split(r"\n\s*---\s*\n", texto)
    bloques_priorizados: list[str] = []

    for bloque in bloques:
        if "criterios de aceptación" in bloque.lower() or "descripción" in bloque.lower():
            bloques_priorizados.append(bloque.strip())
        else:
            bloques_priorizados.append(bloque.strip())

    resultado: list[str] = []
    acumulado = 0
    for b in bloques_priorizados:
        sep = "\n\n---\n\n" if resultado else ""
        if acumulado + len(sep) + len(b) <= max_chars:
            resultado.append(b)
            acumulado += len(sep) + len(b)
        else:
            restante = max_chars - acumulado - len(sep)
            if restante > 300:
                resultado.append(b[:restante])
            break

    return "\n\n---\n\n".join(resultado)