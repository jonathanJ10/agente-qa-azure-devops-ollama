import re


def seleccionar_modelo_qa(
    contenido_req: str,
    cantidad_subopciones: int = 0,
    modelo_base: str = "llama3",
    modelo_rapido: str | None = None,
    modelo_complejo: str | None = None,
    umbral_subopciones_complejo: int = 10,
    umbral_chars_complejo: int = 6000,
) -> tuple[str, str]:
    """Selecciona el modelo de Ollama según la complejidad del requerimiento.

    Retorna una tupla: (modelo_elegido, motivo_enrutamiento).
    """
    texto = contenido_req or ""
    longitud = len(texto)
    multiples_items = len(re.findall(r"\n\s*---\s*\n", texto)) >= 1

    if (
        cantidad_subopciones >= umbral_subopciones_complejo
        or longitud >= umbral_chars_complejo
        or multiples_items
    ):
        elegido = modelo_complejo or modelo_base
        motivo = (
            f"alta complejidad (subopciones={cantidad_subopciones}, "
            f"chars={longitud}, multi_item={multiples_items})"
        )
        return elegido, motivo

    if modelo_rapido and longitud < 2500 and cantidad_subopciones <= 4 and not multiples_items:
        motivo = (
            f"requerimiento corto/moderado (subopciones={cantidad_subopciones}, "
            f"chars={longitud})"
        )
        return modelo_rapido, motivo

    motivo = (
        f"complejidad estándar (subopciones={cantidad_subopciones}, "
        f"chars={longitud})"
    )
    return modelo_base, motivo