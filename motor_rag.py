from pathlib import Path


def dividir_en_fragmentos(texto: str, tamano: int = 600, solapamiento: int = 100) -> list[str]:
    """Divide un texto largo en bloques con solapamiento para no perder contexto."""
    texto_limpio = " ".join(texto.split())
    if not texto_limpio:
        return []

    fragmentos = []
    inicio = 0
    paso = max(1, tamano - solapamiento)

    while inicio < len(texto_limpio):
        fin = inicio + tamano
        fragmentos.append(texto_limpio[inicio:fin])
        inicio += paso

    return fragmentos


def recuperar_contexto_rag(consulta: str, carpeta_docs: str = "documentos", top_k: int = 3) -> str:
    """Busca los fragmentos más relevantes en los archivos .txt y .docx de /documentos."""
    carpeta = Path(carpeta_docs)
    if not carpeta.exists():
        carpeta.mkdir(parents=True, exist_ok=True)
        return "Sin políticas cargadas aún en la carpeta documentos/."

    palabras_clave = {p.lower() for p in consulta.split() if len(p) > 3}
    puntuados = []

    for archivo in carpeta.glob("*.txt"):
        contenido = archivo.read_text(encoding="utf-8")
        for chunk in dividir_en_fragmentos(contenido):
            chunk_lower = chunk.lower()
            score = sum(1 for palabra in palabras_clave if palabra in chunk_lower)
            puntuados.append((score, archivo.name, chunk))

    if not puntuados:
        return "No se encontraron documentos de políticas QA."

    puntuados.sort(key=lambda item: item[0], reverse=True)
    mejores = puntuados[:top_k]

    salida = []
    for score, nombre, chunk in mejores:
        salida.append(f"[Fuente: {nombre} | Coincidencias: {score}]\n{chunk}")

    return "\n\n".join(salida)