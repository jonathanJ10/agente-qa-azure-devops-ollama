import re


def seleccionar_modelo_qa(
    contenido_req: str,
    cantidad_subopciones: int = 0,
    modelo_base: str = "llama3",
    modelo_rapido: str | None = None,
    modelo_complejo: str | None = None,
) -> tuple[str, str]:
    """Selecciona el modelo de Ollama según la complejidad del requerimiento.

    Retorna una tupla: (modelo_elegido, motivo_enrutamiento).
    """
    longitud = len(contenido_req or "")
    multiples_items = len(re.findall(r"\n\s*---\s*\n", contenido_req or "")) >= 1

    if cantidad_subopciones >= 10 or longitud >= 6000 or multiples_items:
        elegido = modelo_complejo or modelo_base
        motivo = (
            f"alta complejidad (subopciones={cantidad_subopciones}, "
            f"chars={longitud}, multi_item={multiples_items})"
        )
        return elegido, motivo

    if modelo_rapido and longitud < 1800 and cantidad_subopciones <= 3:
        motivo = (
            f"requerimiento corto (subopciones={cantidad_subopciones}, "
            f"chars={longitud})"
        )
        return modelo_rapido, motivo

    motivo = (
        f"complejidad estándar (subopciones={cantidad_subopciones}, "
        f"chars={longitud})"
    )
    return modelo_base, motivo