import json
import time
from pathlib import Path


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
    texto_funcionales = " ".join(
        f"{c.get('escenario', '')} {c.get('resultado_esperado', '')}".lower()
        for c in funcionales
    )

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
        if subopcion.lower() in texto_funcionales:
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
    casos = datos_qa.get("casos_de_prueba", {})
    resumen = {
        "salida": nombre_salida,
        "fuente": tipo_fuente,
        "modelo": modelo,
        "desde_cache": desde_cache,
        "duracion_seg": duracion_seg,
        "historias_usuario": len(datos_qa.get("historias_de_usuario", [])),
        "conteo_casos": {
            "humo": len(casos.get("humo", [])),
            "funcionales": len(casos.get("funcionales", [])),
            "regresion": len(casos.get("regresion", [])),
            "automatizacion": len(casos.get("automatizacion", [])),
        },
        "eval_cobertura_criterios": eval_cobertura,
    }

    ruta_log = carpeta_salidas / "metricas_qa.jsonl"
    with ruta_log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(resumen, ensure_ascii=False) + "\n")

    print(
        f"[Métricas/Eval] Tiempo: {duracion_seg}s | Cache: {desde_cache} | "
        f"Funcionales: {resumen['conteo_casos']['funcionales']} | "
        f"Cobertura CA: {eval_cobertura['porcentaje_cobertura']}% "
        f"({eval_cobertura['cubiertas']}/{eval_cobertura['total_subopciones']})"
    )
    return ruta_log