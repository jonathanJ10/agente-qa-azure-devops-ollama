from pathlib import Path
import pandas as pd
from docx import Document


def leer_archivo_requerimiento(ruta_str: str) -> dict:
    """Lee un archivo .xlsx o .docx y devuelve una estructura uniforme."""
    ruta = Path(ruta_str)

    if not ruta.exists():
        return {"ok": False, "error": f"No existe el archivo: {ruta.resolve()}", "contenido": ""}

    extension = ruta.suffix.lower()

    try:
        if extension == ".xlsx":
            df = pd.read_excel(ruta).fillna("")
            texto = df.to_json(orient="records", force_ascii=False, indent=2)
            return {"ok": True, "tipo": "excel", "contenido": texto}

        elif extension == ".docx":
            doc = Document(ruta)
            partes = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

            for idx_tabla, tabla in enumerate(doc.tables, start=1):
                partes.append(f"\n--- Tabla {idx_tabla} ---")
                for fila in tabla.rows:
                    celdas = [c.text.strip().replace("\n", " ") for c in fila.cells]
                    partes.append(" | ".join(celdas))

            return {"ok": True, "tipo": "word", "contenido": "\n".join(partes)}

        else:
            return {
                "ok": False,
                "error": f"Formato '{extension}' no soportado. Usa .xlsx o .docx.",
                "contenido": "",
            }

    except Exception as e:
        return {"ok": False, "error": f"Error leyendo archivo: {str(e)}", "contenido": ""}