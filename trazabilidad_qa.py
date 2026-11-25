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


def _canonizar_token(token: str) -> str:
    """Normaliza plurales simples en español sin perder raíces técnicas."""
    tok = token.strip().lower()
    if len(tok) > 4 and tok.endswith("es") and not tok.endswith(("res", "ses", "ces")):
        candidato = tok[:-2]
        if len(candidato) >= 3:
            return candidato
    if len(tok) > 3 and tok.endswith("s") and not tok.endswith(("ss", "us", "is")):
        candidato = tok[:-1]
        if len(candidato) >= 3:
            return candidato
    return tok


def _tokens_relevantes(texto: str) -> set[str]:
    palabras = _normalizar_texto(texto).split()
    return {
        _canonizar_token(p)
        for p in palabras
        if len(_canonizar_token(p)) >= 3 and p not in _STOPWORDS and _canonizar_token(p) not in _STOPWORDS
    }


def _criterio_cubierto_en_texto(
    criterio: str, texto_casos_norm: str, tokens_casos: set[str]
) -> tuple[bool, set[str]]:
    criterio_norm = _normalizar_texto(criterio)
    if not criterio_norm:
        return False, set()

    tokens_crit = _tokens_relevantes(criterio)
    if not tokens_crit:
        return False, set()

    coincidencias = tokens_crit.intersection(tokens_casos)

    # 1. Coincidencia directa normalizada
    if criterio_norm in texto_casos_norm:
        return True, coincidencias or tokens_crit

    # 2. Coincidencia por tokens clave (al menos 60% o mínimo 2 tokens relevantes)
    if len(tokens_crit) <= 2:
        umbral = max(1, min(2, len(tokens_crit)))
    else:
        umbral = max(2, int(len(tokens_crit) * 0.6))

    return len(coincidencias) >= umbral, coincidencias


def _buscar_casos_asociados(
    tokens_crit: set[str], casos_tokenizados: list[tuple[str, str, set[str]]]
) -> list[str]:
    if not tokens_crit:
        return []
    asociados: list[str] = []
    for caso_id, texto_norm, tokens_caso in casos_tokenizados:
        if not caso_id:
            continue
        inter = tokens_crit.intersection(tokens_caso)
        if inter and (len(inter) >= 1 and any(tok in texto_norm for tok in inter)):
            asociados.append(caso_id)
    return asociados


def construir_matriz_trazabilidad(
    datos_qa: dict, subopciones_detectadas: list[tuple[str, str]]
) -> dict:
    """Construye la matriz de trazabilidad entre criterios/subopciones y casos funcionales."""
    casos_qa = (datos_qa or {}).get("casos_de_prueba", {}) or {}
    funcionales = casos_qa.get("funcionales", []) or []

    textos_func: list[str] = []
    casos_tokenizados: list[tuple[str, str, set[str]]] = []

    for idx_c, c in enumerate(funcionales, start=1):
        if not isinstance(c, dict):
            continue
        caso_id = str(c.get("id") or f"FNC-{idx_c:02d}").strip()
        texto_completo = f"{caso_id} {c.get('escenario', '')} {c.get('resultado_esperado', '')}"
        textos_func.append(texto_completo)
        casos_tokenizados.append(
            (caso_id, _normalizar_texto(texto_completo), _tokens_relevantes(texto_completo))
        )

    texto_casos_norm = " | ".join(_normalizar_texto(t) for t in textos_func)
    tokens_casos = _tokens_relevantes(" ".join(textos_func))

    lista_sub = list(subopciones_detectadas or [])
    total = len(lista_sub)
    cubiertos = 0
    detalle: list[dict] = []

    for idx, item in enumerate(lista_sub, start=1):
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        categoria, criterio = str(item[0] or ""), str(item[1] or "")
        esta_cubierto, _ = _criterio_cubierto_en_texto(
            criterio, texto_casos_norm, tokens_casos
        )
        if esta_cubierto:
            cubiertos += 1

        casos_asoc = (
            _buscar_casos_asociados(_tokens_relevantes(criterio), casos_tokenizados)
            if esta_cubierto
            else []
        )

        detalle.append(
            {
                "indice": idx,
                "categoria": categoria or "General",
                "criterio": criterio,
                "cubierto": esta_cubierto,
                "casos_asociados": casos_asoc,
            }
        )

    porcentaje = round((cubiertos / total) * 100.0, 1) if total > 0 else 100.0

    return {
        "total_criterios_detectados": total,
        "criterios_cubiertos": cubiertos,
        "porcentaje_trazabilidad": porcentaje,
        "detalle": detalle,
    }