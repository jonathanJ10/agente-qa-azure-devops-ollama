import re

_PALABRAS_NO_PLACA = {
    "JSON",
    "HTTP",
    "HTTPS",
    "REST",
    "SQL",
    "API",
    "URL",
    "XML",
    "HTML",
    "CSV",
    "XLSX",
    "DOCX",
    "PDF",
    "RAM",
    "CPU",
    "SSO",
    "SAML",
    "RUNT",
    "SIMIT",
    "POLCA",
    "CONVENIO",
    "COMPARENDO",
    "RECAUDO",
    "COACTIVO",
    "CARTERA",
    "MOVILIDAD",
    "TRANSITO",
    "TRÁNSITO",
    "BOGOTA",
    "BOGOTÁ",
    "AZURE",
    "DEVOPS",
    "OLLAMA",
    "LLAMA3",
    "GITHUB",
    "VERCEL",
    "GHERKIN",
    "ISTQB",
    "SMOKE",
    "REGRESION",
    "REGRESIÓN",
    "FUNCIONAL",
    "FUNCIONALES",
    "AUTOMATIZACION",
    "AUTOMATIZACIÓN",
}


def sanitizar_con_auditoria(texto: str) -> tuple[str, dict[str, int]]:
    """Enmascara datos sensibles/PII, mitiga inyección y retorna conteo por categoría."""
    conteo: dict[str, int] = {
        "credenciales": 0,
        "cadenas_conexion": 0,
        "correos": 0,
        "documentos": 0,
        "telefonos": 0,
        "placas": 0,
        "tramites": 0,
        "nombres_etiquetados": 0,
        "inyeccion": 0,
    }

    if not texto:
        return "", conteo

    limpio = str(texto)

    def _reemplazar_y_contar(patron: str, reemplazo: str, categoria: str, flags: int = 0) -> None:
        nonlocal limpio
        limpio, n = re.subn(patron, reemplazo, limpio, flags=flags)
        if n > 0:
            conteo[categoria] += n

    # 1. Credenciales / tokens / claves comunes
    _reemplazar_y_contar(
        r"(?i)\b(?:bearer|token|api[_-]?key|secret|password|passwd|clave)\s*[:=]\s*[\w\-.~+/=]+",
        "[CREDENCIAL_OCULTA]",
        "credenciales",
    )

    # 2. Cadenas de conexión (URIs o pares clave=valor)
    _reemplazar_y_contar(
        r"(?i)\b(?:postgres(?:ql)?|mysql|sqlserver|mongodb|redis)://[^\s\"']+",
        "[CONNECTION_STRING_OCULTA]",
        "cadenas_conexion",
    )
    _reemplazar_y_contar(
        r"(?i)\b(?:server|data\s*source|initial\s*catalog|database|uid|pwd)\s*=\s*[^;\r\n]+",
        "[CONN_PARAM_OCULTO]",
        "cadenas_conexion",
    )

    # 3. Correos electrónicos
    _reemplazar_y_contar(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "[CORREO_OCULTO]",
        "correos",
    )

    # 4. Documentos de identidad / NIT / cédulas
    _reemplazar_y_contar(
        r"(?i)\b(?:cc|c\.c\.|ced(?:ula)?|ti|ce|nit|pasaporte|doc(?:umento)?)\s*[:#-]?\s*\d{6,12}(?:-\d)?\b",
        "[DOC_OCULTO]",
        "documentos",
    )

    # 5. Teléfonos móviles o fijos
    _reemplazar_y_contar(
        r"(?i)\b(?:tel(?:efono)?|cel(?:ular)?|wh?atsapp|movil|móvil)\s*[:#-]?\s*(?:\+?\d{1,3}[\s-]?)?\d{7,10}\b",
        "[TELEFONO_OCULTO]",
        "telefonos",
    )

    # 6. Placas vehiculares con etiqueta y placas aisladas en mayúscula
    _reemplazar_y_contar(
        r"(?i)\bplaca\s*[:#-]?\s*([A-Z]{2,3}\s*\d{2,3}[A-Z0-9]?)\b",
        "placa: [PLACA_OCULTA]",
        "placas",
    )

    def _reemplazar_placa_aislada(match: re.Match) -> str:
        candidato = match.group(0)
        if candidato.upper() in _PALABRAS_NO_PLACA:
            return candidato
        conteo["placas"] += 1
        return "[PLACA_OCULTA]"

    limpio = re.sub(
        r"\b(?:[A-Z]{3}\d{3}|[A-Z]{3}\d{2}[A-Z]|[A-Z]{2}\d{3}[A-Z])\b",
        _reemplazar_placa_aislada,
        limpio,
    )

    # 7. Números de comparendo / infracción / convenio / radicado explícitos
    _reemplazar_y_contar(
        r"(?i)\b(comparendo|infracci[oó]n|convenio|radicado|expediente)\s*(?:n[°o.]?|nro|num(?:ero)?|#|:)?\s*[:#-]?\s*[A-Z0-9-]{5,25}\b",
        r"\1: [ID_TRAMITE_OCULTO]",
        "tramites",
    )

    # 8. Nombres tras etiquetas sensibles de ciudadano / infractor / usuario
    _reemplazar_y_contar(
        r"(?i)\b(ciudadan[oa]|infractor(?:a)?|conductor(?:a)?|propietari[oa]|solicitante|usuario)\s*[:\-]\s*[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3}",
        r"\1: [NOMBRE_OCULTO]",
        "nombres_etiquetados",
    )

    # 9. Mitigación básica de prompt injection dentro de requerimientos externos
    patrones_inyeccion = [
        r"(?i)ignora\s+(?:las\s+)?instrucciones\s+anteriores.*",
        r"(?i)ignore\s+(?:all\s+)?previous\s+instructions.*",
        r"(?i)act[uú]a\s+como\s+(?:administrador|root|sistema|system).*",
        r"(?i)muestra\s+(?:el\s+)?(?:system\s+prompt|prompt\s+del\s+sistema|token|clave).*",
    ]
    for patron in patrones_inyeccion:
        _reemplazar_y_contar(patron, "[CONTENIDO_REQUERIMIENTO_SANITIZADO]", "inyeccion")

    return limpio, conteo


def _sanitizar_texto_sensible(texto: str) -> str:
    """Enmascara datos sensibles/PII comunes y reduce inyección de instrucciones."""
    limpio, _ = sanitizar_con_auditoria(texto)
    return limpio


def resumir_contexto_seguro(texto: str, max_chars: int = 2200) -> str:
    """Sanitiza y acota el contexto para proteger memoria y rendimiento local."""
    sanitizado = _sanitizar_texto_sensible(texto).strip()
    if len(sanitizado) <= max_chars:
        return sanitizado
    return sanitizado[:max_chars].rstrip() + "\n...[contexto acotado para eficiencia]..."