from pathlib import Path
from docx import Document


def _agregar_tabla_casos(
    doc: Document, casos: list[dict], es_automatizacion: bool = False
) -> None:
    if not casos:
        doc.add_paragraph("No se registraron casos en esta categoría.")
        return

    encabezados = (
        ["ID", "Escenario", "Candidato porque", "Resultado esperado"]
        if es_automatizacion
        else ["ID", "Escenario", "Resultado esperado"]
    )

    tabla = doc.add_table(rows=1, cols=len(encabezados))
    tabla.style = "Table Grid"

    for i, titulo_col in enumerate(encabezados):
        tabla.rows[0].cells[i].text = titulo_col

    for caso in casos:
        fila = tabla.add_row().cells
        fila[0].text = str(caso.get("id", ""))
        fila[1].text = str(caso.get("escenario", ""))
        if es_automatizacion:
            fila[2].text = str(caso.get("candidato_porque", ""))
            fila[3].text = str(caso.get("resultado_esperado", ""))
        else:
            fila[2].text = str(caso.get("resultado_esperado", ""))


def exportar_qa_a_word(datos_qa: dict, ruta_salida: str) -> None:
    """Genera un documento .docx con refinamiento, seguridad, historias y casos QA."""
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

    # 2. Refinamiento QA
    ref = datos_qa.get("refinamiento", {}) if isinstance(datos_qa, dict) else {}
    doc.add_heading("2. Refinamiento QA y escalamiento", level=2)

    doc.add_heading("Observaciones críticas", level=3)
    obs = ref.get("observaciones_criticas", []) or []
    if obs:
        for item in obs:
            doc.add_paragraph(str(item), style="List Bullet")
    else:
        doc.add_paragraph("Sin observaciones críticas registradas.")

    doc.add_heading("Preguntas de escalamiento", level=3)
    pregs = ref.get("preguntas_escalamiento", []) or []
    if pregs:
        for item in pregs:
            doc.add_paragraph(str(item), style="List Bullet")
    else:
        doc.add_paragraph("Sin preguntas de escalamiento registradas.")

    # 3. Historias de usuario
    doc.add_heading("3. Historias de usuario", level=2)
    historias = datos_qa.get("historias_de_usuario", []) or []
    for hu in historias:
        hu_id = hu.get("id", "HU")
        titulo = hu.get("titulo", "")
        doc.add_heading(f"{hu_id} — {titulo}".strip(" —"), level=3)
        doc.add_paragraph(str(hu.get("descripcion", "")))
        criterios = hu.get("criterios_aceptacion", []) or []
        if criterios:
            doc.add_paragraph("Criterios de aceptación:")
            for crit in criterios:
                doc.add_paragraph(str(crit), style="List Bullet")

    # 4. Casos de prueba
    casos = datos_qa.get("casos_de_prueba", {}) or {}
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