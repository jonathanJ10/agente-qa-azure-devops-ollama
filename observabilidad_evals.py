import json
import re
import time
import unicodedata
from pathlib import Path

_STOPWORDS_COBERTURA = {
    "para",
    "cuando",
    "donde",
    "desde",
    "hasta",
    "sobre",
    "entre",
    "segun",
    "según",
    "como",
    "debe",
    "deben",
    "deberia",
    "debería",
    "sistema",
    "usuario",
    "modulo",
    "módulo",
    "caso",
    "casos",
    "prueba",
    "validacion",
    "validación",
    "datos",
    "estado",
    "estados",
    "con",
    "sin",
    "por",
    "las",
    "los",
    "del",
    "una",
    "uno",
    "que",
}


def _normalizar_texto_eval(texto: str) -> str:
    sin_tildes = "".join(
        c
        for c in unicodedata.normalize("NFD", str(texto or "").lower())
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", sin_tildes).strip()


def _tokens_relevantes(texto: str) -> set[str]:
    limpio = re.sub(r"[^a-z0-9\s]", " ", _normalizar_texto_eval(texto))
    return {
        tok
        for tok in limpio.split()
        if len(tok) >= 4 and tok not in _STOPWORDS_COBERTURA
    }


class TimerEjecucion:
    """Mide la duración en segundos de una ejecución del pipeline."""

    def __init__(self) -> None:
        self._inicio = time.perf_counter()

    def elapsed_seg(self) -> float:
        return round(time.perf_counter() - self._inicio, 2)


def evaluar_cobertura_criterios(
    datos_qa: dict, subopciones_esperadas: list[tuple[str, str]]
) -> dict:
    """Evalúa cuántos ítems de criterios de aceptación quedaron cubiertos en funcionales."""
    funcionales = datos_qa.get("casos_de_prueba", {}).get("funcionales", [])
    texto_funcionales_raw = " ".join(
        f"{c.get('escenario', '')} {c.get('resultado_esperado', '')}"
        for c in funcionales
        if isinstance(c, dict)
    )
    texto_funcionales_norm = _normalizar_texto_eval(texto_funcionales_raw)
    tokens_funcionales = _tokens_relevantes(texto_funcionales_raw)

    if not subopciones_esperadas:
        return {
            "total_subopciones": 0,
            "cubiertas": 0,
            "faltantes": [],
            "porcentaje_cobertura": 100.0,
        }

    cubiertas = 0
    faltantes: list[str] = []

    for categoria, subopcion in subopciones_esperadas:
        etiqueta = f"{categoria}: {subopcion}" if categoria else subopcion
        sub_norm = _normalizar_texto_eval(subopcion)
        tokens_sub = _tokens_relevantes(subopcion)

        coincide_directo = bool(sub_norm and sub_norm in texto_funcionales_norm)
        coincide_tokens = False
        if not coincide_directo and tokens_sub:
            interseccion = len(tokens_sub & tokens_funcionales)
            umbral = max(1, (len(tokens_sub) + 1) // 2)
            coincide_tokens = interseccion >= umbral

        if coincide_directo or coincide_tokens:
            cubiertas += 1
        else:
            faltantes.append(etiqueta)

    porcentaje = round((cubiertas / len(subopciones_esperadas)) * 100, 1)
    return {
        "total_subopciones": len(subopciones_esperadas),
        "cubiertas": cubiertas,
        "faltantes": faltantes,
        "porcentaje_cobertura": porcentaje,
    }


def registrar_metricas_ejecucion(
    carpeta_salidas: Path,
    nombre_salida: str,
    tipo_fuente: str,
    modelo: str,
    desde_cache: bool,
    duracion_seg: float,
    datos_qa: dict,
    eval_cobertura: dict,
) -> Path:
    """Guarda un resumen JSON de observabilidad y evals en salidas/metricas_qa.jsonl."""
    carpeta_salidas.mkdir(parents=True, exist_ok=True)
    casos = datos_qa.get("casos_de_prueba", {}) if isinstance(datos_qa, dict) else {}
    telemetria_sub = (
        datos_qa.get("_telemetria_subagentes")
        if isinstance(datos_qa, dict)
        and isinstance(datos_qa.get("_telemetria_subagentes"), dict)
        else None
    )

    resumen: dict = {
        "salida": nombre_salida,
        "fuente": tipo_fuente,
        "modelo": modelo,
        "desde_cache": desde_cache,
        "duracion_seg": duracion_seg,
        "historias_usuario": len(datos_qa.get("historias_de_usuario", []))
        if isinstance(datos_qa, dict)
        else 0,
        "conteo_casos": {
            "humo": len(casos.get("humo", [])) if isinstance(casos, dict) else 0,
            "funcionales": len(casos.get("funcionales", [])) if isinstance(casos, dict) else 0,
            "regresion": len(casos.get("regresion", [])) if isinstance(casos, dict) else 0,
            "automatizacion": (
                len(casos.get("automatizacion", [])) if isinstance(casos, dict) else 0
            ),
        },
        "eval_cobertura_criterios": eval_cobertura,
    }
    if telemetria_sub is not None:
        resumen["telemetria_subagentes"] = telemetria_sub

    ruta_log = carpeta_salidas / "metricas_qa.jsonl"
    with ruta_log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(resumen, ensure_ascii=False) + "\n")

    extra_cache = ""
    if telemetria_sub and telemetria_sub.get("estado_cache"):
        extra_cache = (
            f" ({telemetria_sub['estado_cache']} "
            f"{telemetria_sub.get('cache_hits', 0)}/{telemetria_sub.get('total_etapas', 0)})"
        )

    print(
        f"[Métricas/Eval] Tiempo: {duracion_seg}s | Cache: {desde_cache}{extra_cache} | "
        f"Funcionales: {resumen['conteo_casos']['funcionales']} | "
        f"Cobertura CA: {eval_cobertura['porcentaje_cobertura']}% "
        f"({eval_cobertura['cubiertas']}/{eval_cobertura['total_subopciones']})"
    )
    return ruta_log