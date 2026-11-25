from pathlib import Path
import sys

# Asegura que la carpeta raíz del agente (agente_qa/) esté en sys.path al correr pytest
RAIZ_AGENTE = Path(__file__).resolve().parent.parent
if str(RAIZ_AGENTE) not in sys.path:
    sys.path.insert(0, str(RAIZ_AGENTE))

from cache_qa import calcular_clave_cache, guardar_cache_qa, leer_cache_qa
from guardrails_qa import normalizar_y_validar_qa
from seguridad_qa import _sanitizar_texto_sensible, sanitizar_con_auditoria
from trazabilidad_qa import construir_matriz_trazabilidad


def test_sanitizacion_dlp_placas_y_siglas():
    texto = "Placa ABC123 y moto XYZ98D en SIMIT con ciudadano: Carlos Ruiz"
    limpio, conteo = sanitizar_con_auditoria(texto)

    assert "[PLACA_OCULTA]" in limpio
    assert "SIMIT" in limpio
    assert "ciudadano: [NOMBRE_OCULTO]" in limpio
    assert conteo["placas"] == 2
    assert conteo["nombres_etiquetados"] == 1
    assert _sanitizar_texto_sensible(texto) == limpio


def test_cache_versionada_y_persistencia(tmp_path: Path):
    clave_v1 = calcular_clave_cache("req", "rag", "llama3.2:3b", version_esquema="v1.0")
    clave_v2 = calcular_clave_cache("req", "rag", "llama3.2:3b", version_esquema="v2.1")

    assert clave_v1 != clave_v2

    carga = {"historias_de_usuario": [{"id": "HU-01", "titulo": "Prueba"}]}
    guardar_cache_qa(tmp_path, clave_v2, carga)
    recuperado = leer_cache_qa(tmp_path, clave_v2)

    assert recuperado == carga
    assert leer_cache_qa(tmp_path, clave_v1) is None


def test_guardrails_garantiza_casos_de_humo_y_estructura():
    datos_incompletos = {
        "refinamiento": {"observaciones_criticas": ["Validar vigencia de convenio"]},
        "historias_de_usuario": [],
        "casos_de_prueba": {
            "humo": [],
            "funcionales": [
                {
                    "id": "FNC-01",
                    "escenario": "Validar registro de convenio activo en SIMIT",
                    "resultado_esperado": "Convenio registrado sin errores",
                }
            ],
        },
    }

    normalizado = normalizar_y_validar_qa(datos_incompletos)

    assert len(normalizado["historias_de_usuario"]) >= 1
    assert len(normalizado["casos_de_prueba"]["humo"]) >= 2
    assert len(normalizado["casos_de_prueba"]["funcionales"]) == 1


def test_trazabilidad_por_tokens_y_coincidencia():
    datos_qa = {
        "casos_de_prueba": {
            "funcionales": [
                {
                    "id": "FNC-01",
                    "escenario": "Verificar bloqueo de convenio cuando el comparendo ya está pagado",
                    "resultado_esperado": "Se rechaza la creación del convenio",
                }
            ]
        }
    }
    subopciones = [
        ("Regla", "Bloquear convenio si el comparendo está pagado"),
        ("Excepción", "Rechazar solicitud con placa inexistente en el sistema"),
    ]

    matriz = construir_matriz_trazabilidad(datos_qa, subopciones)

    assert matriz["total_criterios_detectados"] == 2
    assert matriz["criterios_cubiertos"] == 1
    assert matriz["porcentaje_trazabilidad"] == 50.0