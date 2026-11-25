import re
import unicodedata

_STOPWORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al",
    "en", "por", "para", "con", "sin", "que", "y", "o", "u", "se", "su", "sus",
    "a", "ante", "bajo", "desde", "hasta", "sobre", "entre", "como", "cuando",
    "si", "no", "es", "son", "ser", "estar", "valide", "validar", "verificar",
    "debe", "deben", "sistema", "usuario", "caso", "prueba", "funcional",
}


def _normalizar_texto(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto or "")
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    limpio = re.sub(r"[^a-zA-Z0-9\s]", " ", sin_tildes.lower())
    return re.sub(r"\s+", " ", limpio).strip()


def _tokens_relevantes(texto: str) -> set[str]:
    palabras = _normalizar_texto(texto).split()
    return {p for p in palabras if len(p) >= 3 and p not in _STOPWORDS}


def _criterio_cubierto_en_texto(criterio: str, texto_casos_norm: str, tokens_casos: set[str]) -> bool:
    criterio_norm = _normalizar_texto(criterio)
    if not criterio_norm:
        return False

    # 1. Coincidencia directa normalizada
    if criterio_norm in texto_casos_norm:
        return True

    # 2. Coincidencia por tokens clave (al menos 60% o mínimo 2 tokens relevantes)
    tokens_crit = _tokens_relevantes(criterio)
    if not tokens_crit:
        return False

    coincidencias = tokens_crit.intersection(tokens_casos)
    umbral = max(1, min(2, len(tokens_crit))) if len(tokens_crit) <= 2 else max(2, int(len(tokens_crit) * 0.6))
    return len(coincidencias) >= umbral


def construir_matriz_trazabilidad(
    datos_qa: dict, subopciones_detectadas: list[tuple[str, str]]
) -> dict:
    """Construye la matriz de trazabilidad entre criterios/subopciones y casos funcionales."""
    casos_qa = (datos_qa or {}).get("casos_de_prueba", {}) or {}
    funcionales = casos_qa.get("funcionales", []) or []

    textos_func = [
        f"{c.get('id', '')} {c.get('escenario', '')} {c.get('resultado_esperado', '')}"
        for c in funcionales
        if isinstance(c, dict)
    ]
    texto_casos_norm = " | ".join(_normalizar_texto(t) for t in textos_func)
    tokens_casos = _tokens_relevantes(" ".join(textos_func))

    total = len(subopciones_detectadas)
    cubiertos = 0
    detalle: list[dict] = []

    for idx, (categoria, criterio) in enumerate(subopciones_detectadas, start=1):
        esta_cubierto = _criterio_cubierto_en_texto(
            criterio, texto_casos_norm, tokens_casos
        )
        if esta_cubierto:
            cubiertos += 1
        detalle.append(
            {
                "indice": idx,
                "categoria": categoria or "General",
                "criterio": criterio,
                "cubierto": esta_cubierto,
            }
        )

    porcentaje = round((cubiertos / total) * 100.0, 1) if total > 0 else 100.0

    return {
        "total_criterios_detectados": total,
        "criterios_cubiertos": cubiertos,
        "porcentaje_trazabilidad": porcentaje,
        "detalle": detalle,
    }