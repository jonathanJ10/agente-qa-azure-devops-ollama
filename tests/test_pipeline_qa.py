import importlib
import json as _json
from pathlib import Path
import sys

# Asegura que la carpeta raíz del agente (agente_qa/) esté en sys.path al correr pytest
RAIZ_AGENTE = Path(__file__).resolve().parent.parent
if str(RAIZ_AGENTE) not in sys.path:
    sys.path.insert(0, str(RAIZ_AGENTE))

from azure_devops_cliente import _escapar_wiql, limpiar_html
from cache_qa import calcular_clave_cache, guardar_cache_qa, leer_cache_qa
from guardrails_qa import normalizar_y_validar_qa
from llm_resilience import ejecutar_llm_con_resiliencia
from model_router import seleccionar_modelo_qa
from reporte_ejecutivo_qa import construir_bloque_auditoria_dlp
from seguridad_qa import _sanitizar_texto_sensible, sanitizar_con_auditoria
from subagentes_qa import _es_salida_etapa_valida, ejecutar_orquestacion_subagentes_qa
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
        "historias_de_usuario": [
            {
                "id": "HU-01",
                "titulo": "Registro de convenio",
                "descripcion": "Como analista quiero registrar un convenio para habilitar el flujo.",
                "criterios_aceptacion": ["Validar vigencia activa del convenio"],
            }
        ],
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
    criterio_hu = normalizado["historias_de_usuario"][0]["criterios_aceptacion"][0].lower()
    assert "dado" in criterio_hu and "cuando" in criterio_hu and "entonces" in criterio_hu
    assert len(normalizado["casos_de_prueba"]["humo"]) >= 2
    assert len(normalizado["casos_de_prueba"]["funcionales"]) >= 3
    assert normalizado["casos_de_prueba"]["funcionales"][0]["id"] == "FNC-01"


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
    assert "FNC-01" in matriz["detalle"][0]["casos_asociados"]


def test_auditoria_dlp_reporte_ejecutivo():
    texto = "Placa ABC123, ciudadano: Ana Gomez y comparendo: CMP-998877"
    auditoria = construir_bloque_auditoria_dlp(texto)

    assert auditoria["total_elementos_enmascarados"] >= 2
    assert "ABC123" not in auditoria["resumen_linea"]
    assert "Ana Gomez" not in auditoria["resumen_linea"]


def test_extractor_subopciones_criterios_si_existe():
    extractor = None
    for modulo_nombre in ("trazabilidad_qa", "main"):
        try:
            mod = importlib.import_module(modulo_nombre)
        except Exception:
            continue
        candidato = getattr(mod, "_extraer_subopciones_criterios", None)
        if callable(candidato):
            extractor = candidato
            break

    if extractor is None:
        matriz = construir_matriz_trazabilidad({"casos_de_prueba": {"funcionales": []}}, [])
        assert matriz["porcentaje_trazabilidad"] == 100.0
        return

    texto_criterios = (
        "- Regla: Validar vigencia del convenio antes de crearlo\n"
        "- Excepción: Rechazar solicitud si el comparendo ya está pagado"
    )
    resultado = extractor(texto_criterios)
    assert isinstance(resultado, list)
    assert len(resultado) >= 1


def test_validacion_contrato_etapas_y_telemetria_cache(tmp_path: Path):
    assert _es_salida_etapa_valida("refinamiento", {}) is False
    assert _es_salida_etapa_valida("historias", {"historias_de_usuario": []}) is False
    assert (
        _es_salida_etapa_valida(
            "casos_prueba",
            {"casos_de_prueba": {"funcionales": [{"id": "FNC-01", "escenario": "Caso base"}]}},
        )
        is True
    )

    def fake_preguntar(*args, **kwargs):
        return "{}"

    def fake_extraer_json(raw: str):
        if '"observaciones_criticas"' in raw:
            return {"observaciones_criticas": ["Obs 1"], "preguntas_escalamiento": []}
        if '"historias_de_usuario"' in raw:
            return {
                "historias_de_usuario": [
                    {
                        "id": "HU-01",
                        "titulo": "Convenio",
                        "descripcion": "Como analista quiero validar convenio para cumplir regla",
                        "criterios_aceptacion": ["Dado convenio activo, cuando valida, entonces aprueba"],
                    }
                ]
            }
        return {
            "casos_de_prueba": {
                "humo": [{"id": "SMK-01", "escenario": "Smoke", "resultado_esperado": "OK"}],
                "funcionales": [{"id": "FNC-01", "escenario": "Func", "resultado_esperado": "OK"}],
                "regresion": [{"id": "REG-01", "escenario": "Reg", "resultado_esperado": "OK"}],
                "automatizacion": [
                    {
                        "id": "AUT-01",
                        "escenario": "Auto",
                        "candidato_porque": "Repetitivo",
                        "resultado_esperado": "OK",
                    }
                ],
            }
        }

    def preguntar_por_etapa(prompt: str, system_prompt: str = "", **kwargs):
        if "observaciones_criticas" in system_prompt:
            return '{"observaciones_criticas": ["Obs 1"], "preguntas_escalamiento": ["P1"]}'
        if "historias_de_usuario" in system_prompt:
            return (
                '{"historias_de_usuario": [{"id": "HU-01", "titulo": "Convenio", '
                '"descripcion": "Como analista quiero validar convenio para cumplir regla", '
                '"criterios_aceptacion": ["Dado convenio activo, cuando valida, entonces aprueba"]}]}'
            )
        return (
            '{"casos_de_prueba": {"humo": [{"id": "SMK-01", "escenario": "Smoke", "resultado_esperado": "OK"}], '
            '"funcionales": [{"id": "FNC-01", "escenario": "Func", "resultado_esperado": "OK"}], '
            '"regresion": [{"id": "REG-01", "escenario": "Reg", "resultado_esperado": "OK"}], '
            '"automatizacion": [{"id": "AUT-01", "escenario": "Auto", "candidato_porque": "Repetitivo", "resultado_esperado": "OK"}]}}'
        )

    consolidado_miss, _ = ejecutar_orquestacion_subagentes_qa(
        contenido_req="Requerimiento de convenio SIMIT",
        contexto_rag="Política QA",
        tipo_fuente="xlsx",
        modelo_principal="llama3",
        modelo_rapido="llama3.2:3b",
        carpeta_cache=tmp_path,
        preguntar_fn=preguntar_por_etapa,
        extraer_json_fn=lambda s: _json.loads(s),
    )
    assert consolidado_miss is not None
    assert consolidado_miss["_telemetria_subagentes"]["estado_cache"] == "miss"

    consolidado_hit, _ = ejecutar_orquestacion_subagentes_qa(
        contenido_req="Requerimiento de convenio SIMIT",
        contexto_rag="Política QA",
        tipo_fuente="xlsx",
        modelo_principal="llama3",
        modelo_rapido="llama3.2:3b",
        carpeta_cache=tmp_path,
        preguntar_fn=fake_preguntar,
        extraer_json_fn=fake_extraer_json,
    )
    assert consolidado_hit is not None
    assert consolidado_hit["_telemetria_subagentes"]["estado_cache"] == "full_hit"
    assert consolidado_hit["_telemetria_subagentes"]["cache_hits"] == 3


def test_router_resiliencia_y_azure_devops_helpers():
    modelo_rapido, _ = seleccionar_modelo_qa(
        "Validar estado del trámite",
        cantidad_subopciones=2,
        modelo_base="llama3",
        modelo_rapido="llama3.2:3b",
        modelo_complejo="llama3",
    )
    assert modelo_rapido == "llama3.2:3b"

    modelo_complejo, _ = seleccionar_modelo_qa(
        "Item 1\n\n---\n\nItem 2",
        cantidad_subopciones=2,
        modelo_base="llama3",
        modelo_rapido="llama3.2:3b",
        modelo_complejo="llama3",
    )
    assert modelo_complejo == "llama3"

    json_rescatado, modelo_usado, info = ejecutar_llm_con_resiliencia(
        prompt="Genera JSON",
        system_prompt="Responde JSON",
        modelo_principal="llama3",
        preguntar_fn=lambda **kwargs: 'Texto previo {"ok": true,} texto posterior',
        extraer_json_fn=lambda raw: None,
        modelo_fallback=None,
    )
    assert json_rescatado == {"ok": True}
    assert modelo_usado == "llama3"
    assert info["intentos_totales"] == 1

    limpio_html = limpiar_html("<p>A&B</p><ul><li>Opción 1</li></ul>")
    assert "A&B" in limpio_html and "- Opción 1" in limpio_html
    assert _escapar_wiql("Proyecto 'QA'") == "Proyecto ''QA''"