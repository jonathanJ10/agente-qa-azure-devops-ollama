import re
from pathlib import Path
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

_CARACTERES_XML_INVALIDOS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _texto_seguro_docx(valor: object) -> str:
    """Elimina caracteres de control incompatibles con XML de Word."""
    texto = str(valor or "")
    return _CARACTERES_XML_INVALIDOS.sub("", texto)


def _repetir_fila_encabezado(fila) -> None:
    """Marca una fila de tabla para repetirse al inicio de página si la tabla se divide."""
    tr_pr = fila._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tr_pr.append(tbl_header)


def _agregar_tabla_casos(
    doc: Document, casos: list[dict], es_automatizacion: bool = False
) -> None:
    lista_casos = casos if isinstance(casos, list) else []
    if not lista_casos:
        doc.add_paragraph("No se registraron casos en esta categoría.")
        return

    encabezados = (
        ["ID", "Escenario", "Candidato porque", "Resultado esperado"]
        if es_automatizacion
        else ["ID", "Escenario", "Resultado esperado"]
    )

    tabla = doc.add_table(rows=1, cols=len(encabezados))
    tabla.style = "Table Grid"
    _repetir_fila_encabezado(tabla.rows[0])

    for i, titulo_col in enumerate(encabezados):
        tabla.rows[0].cells[i].text = _texto_seguro_docx(titulo_col)
        for run in tabla.rows[0].cells[i].paragraphs[0].runs:
            run.bold = True

    for caso in lista_casos:
        if not isinstance(caso, dict):
            continue
        fila = tabla.add_row().cells
        fila[0].text = _texto_seguro_docx(caso.get("id", ""))
        fila[1].text = _texto_seguro_docx(caso.get("escenario", ""))
        if es_automatizacion:
            fila[2].text = _texto_seguro_docx(caso.get("candidato_porque", ""))
            fila[3].text = _texto_seguro_docx(caso.get("resultado_esperado", ""))
        else:
            fila[2].text = _texto_seguro_docx(caso.get("resultado_esperado", ""))


def exportar_qa_a_word(datos_qa: dict, ruta_salida: str) -> None:
    """Genera un documento .docx con refinamiento, seguridad, historias y casos QA."""
    base = datos_qa if isinstance(datos_qa, dict) else {}
    doc = Document()
    doc.add_heading("Artefactos de Calidad QA — Movilidad y Tránsito", level=1)

    # 1. Seguridad y gobierno de la información
    doc.add_heading("1. Seguridad y gobierno de la información", level=2)
    doc.add_paragraph(
        "Las entradas de texto se sanitizan previamente en el pipeline para enmascarar "
        "datos sensibles o de identificación (documentos, correos, teléfonos, placas, "
        "números de trámite/comparendo y credenciales) y mitigar instrucciones no confiables "
        "antes de enviar contexto a modelos o caché."
    )

    telemetria = base.get("_telemetria_subagentes")
    if isinstance(telemetria, dict) and telemetria.get("estado_cache"):
        doc.add_paragraph(
            _texto_seguro_docx(
                f"Telemetría de orquestación: caché {telemetria.get('estado_cache')} "
                f"({telemetria.get('cache_hits', 0)}/{telemetria.get('total_etapas', 0)} etapas, "
                f"duración total: {telemetria.get('duracion_total_s', 'N/A')}s)."
            )
        )

    # 2. Refinamiento QA
    ref_raw = base.get("refinamiento", {})
    ref = ref_raw if isinstance(ref_raw, dict) else {}
    doc.add_heading("2. Refinamiento QA y escalamiento", level=2)

    doc.add_heading("Observaciones críticas", level=3)
    obs = ref.get("observaciones_criticas", []) or []
    if obs:
        for item in obs:
            if isinstance(item, dict):
                continue
            doc.add_paragraph(_texto_seguro_docx(item), style="List Bullet")
    else:
        doc.add_paragraph("Sin observaciones críticas registradas.")

    doc.add_heading("Preguntas de escalamiento", level=3)
    pregs = ref.get("preguntas_escalamiento", []) or []
    if pregs:
        for item in pregs:
            if isinstance(item, dict):
                continue
            doc.add_paragraph(_texto_seguro_docx(item), style="List Bullet")
    else:
        doc.add_paragraph("Sin preguntas de escalamiento registradas.")

    # 3. Historias de usuario
    doc.add_heading("3. Historias de usuario", level=2)
    historias_raw = base.get("historias_de_usuario", [])
    historias = historias_raw if isinstance(historias_raw, list) else []
    for hu in historias:
        if not isinstance(hu, dict):
            continue
        hu_id = _texto_seguro_docx(hu.get("id", "HU"))
        titulo = _texto_seguro_docx(hu.get("titulo", ""))
        doc.add_heading(f"{hu_id} — {titulo}".strip(" —"), level=3)
        doc.add_paragraph(_texto_seguro_docx(hu.get("descripcion", "")))
        criterios = hu.get("criterios_aceptacion", []) or []
        if criterios:
            doc.add_paragraph("Criterios de aceptación:")
            for crit in criterios:
                doc.add_paragraph(_texto_seguro_docx(crit), style="List Bullet")

    # 4. Casos de prueba
    casos_raw = base.get("casos_de_prueba", {})
    casos = casos_raw if isinstance(casos_raw, dict) else {}
    doc.add_heading("4. Casos de prueba", level=2)

    doc.add_heading("Pruebas de humo", level=3)
    _agregar_tabla_casos(doc, casos.get("humo", []), es_automatizacion=False)

    doc.add_heading("Pruebas funcionales", level=3)
    _agregar_tabla_casos(doc, casos.get("funcionales", []), es_automatizacion=False)

    doc.add_heading("Pruebas de regresión", level=3)
    _agregar_tabla_casos(doc, casos.get("regresion", []), es_automatizacion=False)

    doc.add_heading("Pruebas candidatas a automatización", level=3)
    _agregar_tabla_casos(
        doc, casos.get("automatizacion", []), es_automatizacion=True
    )

    ruta = Path(ruta_salida)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(ruta))