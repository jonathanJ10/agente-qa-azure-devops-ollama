from pathlib import Path
from seguridad_qa import sanitizar_con_auditoria


def construir_bloque_auditoria_dlp(texto_fuente: str) -> dict:
    """Genera un resumen de auditoría DLP sin revelar valores sensibles originales."""
    _, conteo = sanitizar_con_auditoria(texto_fuente or "")
    total_ocultos = sum(conteo.values())
    desglose = {k: v for k, v in conteo.items() if v > 0}
    return {
        "total_elementos_enmascarados": total_ocultos,
        "desglose_por_categoria": desglose,
        "resumen_linea": (
            f"Auditoría DLP: {total_ocultos} elemento(s) sensible(s) enmascarado(s) "
            f"({', '.join(f'{k}={v}' for k, v in desglose.items()) if desglose else 'sin hallazgos'})."
        ),
    }


def generar_resumen_ejecutivo_md(
    datos_qa: dict,
    nombre_salida: str,
    carpeta_salidas: Path,
    modelo_usado: str,
    eval_calidad: dict | None = None,
    trazabilidad: dict | None = None,
) -> Path:
    """Genera un reporte ejecutivo en Markdown en salidas/ y devuelve su ruta."""
    refinamiento = datos_qa.get("refinamiento", {}) if isinstance(datos_qa, dict) else {}
    obs = refinamiento.get("observaciones_criticas", []) if isinstance(refinamiento, dict) else []
    pregs = refinamiento.get("preguntas_escalamiento", []) if isinstance(refinamiento, dict) else []

    historias = datos_qa.get("historias_de_usuario", []) if isinstance(datos_qa, dict) else []
    casos = datos_qa.get("casos_de_prueba", {}) if isinstance(datos_qa, dict) else {}

    humo = casos.get("humo", []) if isinstance(casos, dict) else []
    funcionales = casos.get("funcionales", []) if isinstance(casos, dict) else []
    regresion = casos.get("regresion", []) if isinstance(casos, dict) else []
    automatizacion = casos.get("automatizacion", []) if isinstance(casos, dict) else []

    lineas: list[str] = [
        f"# Resumen Ejecutivo QA — {nombre_salida}",
        "",
        f"- **Modelo utilizado:** `{modelo_usado}`",
        f"- **Historias de usuario:** {len(historias)}",
        f"- **Casos de prueba:** {len(humo) + len(funcionales) + len(regresion) + len(automatizacion)} "
        f"(Humo: {len(humo)} | Funcionales: {len(funcionales)} | "
        f"Regresión: {len(regresion)} | Automatización: {len(automatizacion)})",
    ]

    if isinstance(eval_calidad, dict):
        lineas.append(
            f"- **Calidad QA:** {eval_calidad.get('puntaje', 'N/A')}/100 "
            f"(Aprobado: {eval_calidad.get('aprobado', 'N/A')})"
        )

    if isinstance(trazabilidad, dict):
        lineas.append(
            f"- **Trazabilidad CA:** {trazabilidad.get('criterios_cubiertos', 0)}/"
            f"{trazabilidad.get('total_criterios_detectados', 0)} "
            f"({trazabilidad.get('porcentaje_trazabilidad', 0)}%)"
        )

    lineas.extend(["", "## Observaciones críticas de refinamiento"])
    if obs:
        for item in obs:
            lineas.append(f"- {item}")
    else:
        lineas.append("- Sin observaciones críticas registradas.")

    lineas.extend(["", "## Preguntas de escalamiento"])
    if pregs:
        for item in pregs:
            lineas.append(f"- {item}")
    else:
        lineas.append("- Sin preguntas de escalamiento registradas.")

    lineas.extend(["", "## Historias de usuario"])
    if historias:
        for hu in historias:
            if isinstance(hu, dict):
                hu_id = hu.get("id", "HU")
                titulo = hu.get("titulo", "Sin título")
                desc = hu.get("descripcion", "")
                lineas.append(f"### {hu_id}: {titulo}")
                if desc:
                    lineas.append(f"{desc}")
                lineas.append("")
    else:
        lineas.append("- No se generaron historias de usuario.")

    ruta_md = carpeta_salidas / f"{nombre_salida}_resumen.md"
    ruta_md.write_text("\n".join(lineas).strip() + "\n", encoding="utf-8")
    return ruta_md


def imprimir_resumen_consola(datos_qa: dict) -> None:
    """Imprime un bloque ejecutivo breve con los totales clave en consola."""
    historias = datos_qa.get("historias_de_usuario", []) if isinstance(datos_qa, dict) else []
    casos = datos_qa.get("casos_de_prueba", {}) if isinstance(datos_qa, dict) else {}
    humo = casos.get("humo", []) if isinstance(casos, dict) else []
    funcionales = casos.get("funcionales", []) if isinstance(casos, dict) else []
    regresion = casos.get("regresion", []) if isinstance(casos, dict) else []
    automatizacion = casos.get("automatizacion", []) if isinstance(casos, dict) else []

    print(
        f"[Resumen QA] HUs: {len(historias)} | Humo: {len(humo)} | "
        f"Funcionales: {len(funcionales)} | Regresión: {len(regresion)} | "
        f"Automatización: {len(automatizacion)}"
    )