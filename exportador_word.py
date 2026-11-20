from pathlib import Path
from docx import Document


def exportar_qa_a_word(datos_qa: dict, ruta_salida_docx: str) -> Path:
    """Convierte el diccionario estructurado de QA en un documento .docx legible."""
    doc = Document()
    doc.add_heading("Reporte de Refinamiento y Estrategia de Pruebas QA", level=1)

    # 1. Refinamiento y Escalamientos
    refinamiento = datos_qa.get("refinamiento", {})
    doc.add_heading("1. Refinamiento y Escalamientos", level=2)

    doc.add_heading("Observaciones Críticas", level=3)
    obs = refinamiento.get("observaciones_criticas", [])
    if obs:
        for item in obs:
            doc.add_paragraph(str(item), style="List Bullet")
    else:
        doc.add_paragraph("Sin observaciones críticas reportadas.")

    doc.add_heading("Preguntas de Escalamiento", level=3)
    pregs = refinamiento.get("preguntas_escalamiento", [])
    if pregs:
        for item in pregs:
            doc.add_paragraph(str(item), style="List Bullet")
    else:
        doc.add_paragraph("Sin preguntas de escalamiento pendientes.")

    # 2. Historias de Usuario
    doc.add_heading("2. Historias de Usuario", level=2)
    hus = datos_qa.get("historias_de_usuario", [])
    if hus:
        for hu in hus:
            hu_id = hu.get("id", "HU")
            titulo = hu.get("titulo", "Sin título")
            doc.add_heading(f"{hu_id}: {titulo}", level=3)
            if hu.get("descripcion"):
                doc.add_paragraph(f"Descripción: {hu['descripcion']}")
            for ca in hu.get("criterios_aceptacion", []):
                doc.add_paragraph(f"CA: {ca}", style="List Bullet")
    else:
        doc.add_paragraph("No se generaron historias de usuario.")

    # 3. Casos de Prueba por Tipo
    doc.add_heading("3. Casos de Prueba", level=2)
    casos = datos_qa.get("casos_de_prueba", {})
    categorias = [
        ("humo", "Pruebas de Humo (Smoke)"),
        ("funcionales", "Pruebas Funcionales"),
        ("regresion", "Pruebas de Regresión"),
        ("automatizacion", "Pruebas Candidatas a Automatización"),
    ]

    for clave, etiqueta in categorias:
        doc.add_heading(etiqueta, level=3)
        lista_casos = casos.get(clave, [])
        if not lista_casos:
            doc.add_paragraph("Sin casos registrados en esta categoría.")
            continue

        tabla = doc.add_table(rows=1, cols=3)
        tabla.style = "Table Grid"
        encabezados = tabla.rows[0].cells
        encabezados[0].text = "ID"
        encabezados[1].text = "Escenario / Detalle"
        encabezados[2].text = "Resultado Esperado / Automatización"

        for caso in lista_casos:
            fila = tabla.add_row().cells
            fila[0].text = str(caso.get("id", ""))
            fila[1].text = str(caso.get("escenario", ""))

            extra = str(caso.get("resultado_esperado", ""))
            if caso.get("candidato_porque"):
                extra = f"{extra} | Motivo auto: {caso['candidato_porque']}".strip(" |")
            fila[2].text = extra

    ruta_final = Path(ruta_salida_docx)
    ruta_final.parent.mkdir(parents=True, exist_ok=True)
    doc.save(ruta_final)
    return ruta_final