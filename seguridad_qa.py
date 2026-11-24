import re


def _sanitizar_texto_sensible(texto: str) -> str:
    """Enmascara datos sensibles/PII comunes y reduce inyección de instrucciones."""
    if not texto:
        return ""

    limpio = str(texto)

    # 1. Credenciales / tokens / claves comunes
    limpio = re.sub(
        r"(?i)\b(?:bearer|token|api[_-]?key|secret|password|passwd|clave)\s*[:=]\s*[\w\-.~+/=]+",
        "[CREDENCIAL_OCULTA]",
        limpio,
    )

    # 2. Correos electrónicos
    limpio = re.sub(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "[CORREO_OCULTO]",
        limpio,
    )

    # 3. Documentos de identidad / NIT / cédulas con etiqueta o formato largo
    limpio = re.sub(
        r"(?i)\b(?:cc|c\.c\.|ced(?:ula)?|ti|ce|nit|pasaporte|doc(?:umento)?)\s*[:#-]?\s*\d{6,12}(?:-\d)?\b",
        "[DOC_OCULTO]",
        limpio,
    )

    # 4. Teléfonos móviles o fijos (Colombia / genéricos)
    limpio = re.sub(
        r"(?i)\b(?:tel(?:efono)?|cel(?:ular)?|wh?atsapp|movil|móvil)\s*[:#-]?\s*(?:\+?\d{1,3}[\s-]?)?\d{7,10}\b",
        "[TELEFONO_OCULTO]",
        limpio,
    )

    # 5. Placas vehiculares (ej. ABC123, ABC12D, AB123C) tras etiqueta o aisladas en mayúscula
    limpio = re.sub(
        r"(?i)\bplaca\s*[:#-]?\s*([A-Z]{2,3}\s*\d{2,3}[A-Z0-9]?)\b",
        "placa: [PLACA_OCULTA]",
        limpio,
    )

    # 6. Números de comparendo / infracción / convenio / radicado explícitos
    limpio = re.sub(
        r"(?i)\b(?:comparendo|infracci[oó]n|convenio|radicado|expediente)\s*(?:n[°o.]?|nro|num(?:ero)?|#|:)?\s*[:#-]?\s*[A-Z0-9-]{5,25}\b",
        r"\g<0>".split(":")[0] + ": [ID_TRAMITE_OCULTO]",
        limpio,
    )

    # 7. Mitigación básica de prompt injection dentro de requerimientos externos
    patrones_inyeccion = [
        r"(?i)ignora\s+(?:las\s+)?instrucciones\s+anteriores.*",
        r"(?i)ignore\s+(?:all\s+)?previous\s+instructions.*",
        r"(?i)act[uú]a\s+como\s+(?:administrador|root|sistema|system).*",
        r"(?i)muestra\s+(?:el\s+)?(?:system\s+prompt|prompt\s+del\s+sistema|token|clave).*",
    ]
    for patron in patrones_inyeccion:
        limpio = re.sub(patron, "[CONTENIDO_REQUERIMIENTO_SANITIZADO]", limpio)

    return limpio


def resumir_contexto_seguro(texto: str, max_chars: int = 2200) -> str:
    """Sanitiza y acota el contexto para proteger memoria y rendimiento local."""
    sanitizado = _sanitizar_texto_sensible(texto).strip()
    if len(sanitizado) <= max_chars:
        return sanitizado
    return sanitizado[:max_chars].rstrip() + "\n...[contexto acotado para eficiencia]..."