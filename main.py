import json
import re
from pathlib import Path

from azure_devops_cliente import AzureDevOpsCliente, formatear_work_item
from cache_qa import calcular_clave_cache, guardar_cache_qa, leer_cache_qa
from calidad_qa import evaluar_calidad_artefactos
from exportador_word import exportar_qa_a_word
from guardrails_qa import guardar_docx_seguro, normalizar_y_validar_qa
from lector_archivos import leer_archivo_requerimiento
from llm_cliente import extraer_json, preguntar_llm
from llm_resilience import ejecutar_llm_con_resiliencia
from model_router import seleccionar_modelo_qa
from motor_rag import recuperar_contexto_rag
from observabilidad_evals import (
    TimerEjecucion,
    evaluar_cobertura_criterios,
    registrar_metricas_ejecucion,
)
from reporte_ejecutivo_qa import generar_resumen_ejecutivo_md, imprimir_resumen_consola
from reranker_rag import preparar_texto_por_secciones, rerank_fragmentos_rag
from subagentes_qa import ejecutar_orquestacion_subagentes_qa
from trazabilidad_qa import construir_matriz_trazabilidad

MODELO_OLLAMA = "llama3"
MODELO_RAPIDO = "llama3.2:3b"

SYSTEM_PROMPT_QA = """
Eres un Arquitecto y Analista Senior de QA especializado en ingeniería de software y arquitectura agéntica.
Tu trabajo es analizar requerimientos de negocio y generar artefactos de calidad completos, exhaustivos y accionables, siguiendo estrictamente las políticas internas de QA proporcionadas en el contexto RAG y los criterios de aceptación del requerimiento.

Debes responder ÚNICAMENTE con un objeto JSON válido (sin markdown extra ni texto fuera del JSON) con esta estructura exacta:
{
  "refinamiento": {
    "observaciones_criticas": ["..."],
    "preguntas_escalamiento": ["..."]
  },
  "historias_de_usuario": [
    {
      "id": "HU-01",
      "titulo": "...",
      "descripcion": "Como [rol], quiero [acción], para [beneficio]",
      "criterios_aceptacion": ["..."]
    }
  ],
  "casos_de_prueba": {
    "humo": [
      {"id": "SMK-01", "escenario": "...", "resultado_esperado": "..."}
    ],
    "funcionales": [
      {"id": "FNC-01", "escenario": "...", "resultado_esperado": "..."}
    ],
    "regresion": [
      {"id": "REG-01", "escenario": "...", "resultado_esperado": "..."}
    ],
    "automatizacion": [
      {"id": "AUT-01", "escenario": "...", "candidato_porque": "...", "resultado_esperado": "..."}
    ]
  }
}

Reglas obligatorias de desglose y cobertura:
1. Analiza SIEMPRE tanto la "Descripción" como los "Criterios de aceptación". Si los "Criterios de aceptación" incluyen categorías/módulos y subopciones con guiones ("- ..."), NO las resumas ni las omitas: genera un caso funcional por CADA subopción.
2. Redacta cada caso funcional de forma clara y explícita siguiendo este estilo:
   "Se debe validar que la subopción [nombre de la subopción] esté funcional en el sistema (dentro de [categoría/módulo si aplica])."
   Si una subopción tiene una condición especial (como "(aplica unicamente PSE)"), inclúyela en el escenario y en el resultado esperado.
3. En "casos_de_prueba.humo": genera entre 2 y 3 casos verificando disponibilidad del módulo, acceso y carga inicial sin errores.
4. En "casos_de_prueba.regresion": genera entre 2 y 3 casos verificando que no haya afectación en otros módulos, proyectos/OT de referencia ni pérdida de consistencia de datos.
5. En "casos_de_prueba.automatizacion": genera entre 2 y 3 casos priorizando pruebas repetitivas, de regresión o validación de reportes/reglas críticas, explicando en "candidato_porque" el motivo técnico concreto.
"""


def _extraer_subopciones_criterios(contenido_req: str) -> list[tuple[str, str]]:
    """Extrae pares (categoria, subopcion) soportando viñetas, numeración y Excel sin guiones."""
    if not contenido_req or not contenido_req.strip():
        return []

    # 1. Intentar aislar un bloque explícito de criterios/reglas si existe
    match_bloque = re.search(
        r"(?:criterios(?:\s+de\s+aceptaci[oó]n)?|subopciones|reglas\s+de\s+negocio|alcance)\s*:\s*(.*)",
        contenido_req,
        flags=re.DOTALL | re.IGNORECASE,
    )
    texto_objetivo = match_bloque.group(1) if match_bloque else contenido_req

    categoria_actual = ""
    subopciones: list[tuple[str, str]] = []
    vistos: set[str] = set()

    patrones_item = re.compile(
        r"^(?:[-*•–—]+|\d+[.)\-]|(?i:[a-z])[.)])\s*(.+)$"
    )
    patrones_etiqueta = re.compile(
        r"^(?:criterio|subopci[oó]n|requisito|regla|validaci[oó]n|escenario)\s*[:\-]\s*(.+)$",
        flags=re.IGNORECASE,
    )
    prefijos_metadata = (
        "id:",
        "tipo:",
        "estado:",
        "título:",
        "titulo:",
        "descripción:",
        "descripcion:",
        "hoja:",
        "sheet:",
    )

    for linea_raw in texto_objetivo.splitlines():
        texto = re.sub(r"\s+", " ", linea_raw).strip()
        if not texto or re.fullmatch(r"[-_=*]{3,}", texto):
            continue

        lower = texto.lower()
        if not match_bloque and lower.startswith(prefijos_metadata):
            continue

        # Si viene en formato tabla tipo "Col1 | Col2 | Col3" desde Excel
        if "|" in texto:
            celdas = [c.strip() for c in texto.split("|") if c.strip()]
            if len(celdas) >= 2:
                candidato = " - ".join(celdas)
                clave = candidato.lower()
                if len(candidato) >= 4 and clave not in vistos:
                    vistos.add(clave)
                    subopciones.append((categoria_actual, candidato))
                continue

        # Detectar viñetas (-, *, •, –) o listas numeradas (1., 1), a))
        m_item = patrones_item.match(texto)
        if m_item:
            subopcion = m_item.group(1).strip()
            clave = subopcion.lower()
            if len(subopcion) >= 3 and clave not in vistos:
                vistos.add(clave)
                subopciones.append((categoria_actual, subopcion))
            continue

        # Detectar líneas con etiqueta tipo "Criterio: ..." o "Subopción: ..."
        m_etiq = patrones_etiqueta.match(texto)
        if m_etiq:
            subopcion = m_etiq.group(1).strip()
            clave = subopcion.lower()
            if len(subopcion) >= 3 and clave not in vistos:
                vistos.add(clave)
                subopciones.append((categoria_actual, subopcion))
            continue

        # Detectar categoría que termina en ":"
        if texto.endswith(":") and len(texto) <= 90:
            categoria_actual = texto[:-1].strip()
            continue

        # Si no hay encabezado explícito de criterios, aprovechar líneas descriptivas sustanciales
        if not match_bloque and len(texto) >= 25 and not texto.endswith("."):
            clave = lower
            if clave not in vistos:
                vistos.add(clave)
                subopciones.append((categoria_actual, texto))

    return subopciones


def _completar_casos_funcionales_desde_criterios(
    datos: dict, contenido_req: str
) -> dict:
    """Garantiza que cada subopción de los criterios de aceptación tenga su caso funcional."""
    subopciones = _extraer_subopciones_criterios(contenido_req)
    if not subopciones:
        return datos

    casos_qa = datos.setdefault("casos_de_prueba", {})
    funcionales = casos_qa.setdefault("funcionales", [])
    texto_existente = " ".join(
        c.get("escenario", "").lower() for c in funcionales
    )

    siguiente_num = len(funcionales) + 1
    for categoria, subopcion in subopciones:
        nombre_limpio = subopcion.lower()
        if nombre_limpio in texto_existente:
            continue

        contexto_cat = f" en la categoría {categoria}" if categoria else ""
        escenario = (
            f"Se debe validar que la subopción {subopcion} esté funcional "
            f"en el sistema{contexto_cat}."
        )
        resultado = (
            f"La subopción {subopcion} se visualiza y ejecuta correctamente "
            f"mostrando la información esperada sin errores."
        )

        funcionales.append(
            {
                "id": f"FNC-{siguiente_num:02d}",
                "escenario": escenario,
                "resultado_esperado": resultado,
            }
        )
        texto_existente += f" {nombre_limpio}"
        siguiente_num += 1

    return datos


def _completar_minimos_regresion_y_automatizacion(
    datos: dict, minimo_por_tipo: int = 2
) -> dict:
    """Garantiza un mínimo de casos de regresión y automatización si el LLM los omite."""
    casos_qa = datos.setdefault("casos_de_prueba", {})

    regresion = casos_qa.setdefault("regresion", [])
    plantillas_regresion = [
        (
            "Validar que la implementación del requerimiento no genere errores ni "
            "afectaciones colaterales en módulos o flujos relacionados existentes.",
            "Los módulos relacionados continúan operando con normalidad y sin "
            "regresiones funcionales.",
        ),
        (
            "Validar que los registros y estados previos en el sistema mantengan "
            "su integridad y consistencia tras ejecutar los nuevos flujos.",
            "La información existente permanece íntegra, sin datos corruptos ni "
            "pérdidas de consistencia.",
        ),
    ]
    idx_reg = len(regresion) + 1
    for escenario, resultado in plantillas_regresion:
        if len(regresion) >= minimo_por_tipo:
            break
        regresion.append(
            {
                "id": f"REG-{idx_reg:02d}",
                "escenario": escenario,
                "resultado_esperado": resultado,
            }
        )
        idx_reg += 1

    automatizacion = casos_qa.setdefault("automatizacion", [])
    plantillas_auto = [
        (
            "Ejecutar de forma automatizada las validaciones principales y reglas "
            "de negocio críticas definidas en el requerimiento.",
            "Alta repetitividad en cada ciclo de release y validación rápida de "
            "reglas críticas de negocio.",
            "El flujo automatizado valida las condiciones clave y reporta "
            "resultados consistentes sin intervención manual.",
        ),
        (
            "Ejecutar de forma automatizada la prueba de no regresión sobre el "
            "flujo principal y sus validaciones de entrada/salida.",
            "Permite detectar regresiones tempranas en integración continua con "
            "bajo costo de mantenimiento.",
            "La suite automatizada aprueba el flujo principal y alerta "
            "inmediatamente ante cualquier desviación.",
        ),
    ]
    idx_auto = len(automatizacion) + 1
    for escenario, motivo, resultado in plantillas_auto:
        if len(automatizacion) >= minimo_por_tipo:
            break
        automatizacion.append(
            {
                "id": f"AUT-{idx_auto:02d}",
                "escenario": escenario,
                "candidato_porque": motivo,
                "resultado_esperado": resultado,
            }
        )
        idx_auto += 1

    return datos


def _parsear_ids_desde_texto(texto: str) -> list[int]:
    ids: list[int] = []
    for parte in texto.split(","):
        limpio = parte.strip()
        if limpio.isdigit():
            valor = int(limpio)
            if valor not in ids:
                ids.append(valor)
    return ids


def _procesar_y_guardar_qa(
    contenido_req: str,
    tipo_fuente: str,
    nombre_base_salida: str,
    carpeta_docs: Path,
    carpeta_salidas: Path,
    modo_orquestacion: str = "directo",
) -> None:
    timer = TimerEjecucion()
    desde_cache = False

    print("[2/4] Consultando estándares QA en el motor RAG...")
    contexto_rag = recuperar_contexto_rag(
        consulta="refinamiento historias de usuario pruebas humo funcionales regresion automatizacion escalamiento",
        carpeta_docs=str(carpeta_docs),
        top_k=3,
    )
    contexto_rag = rerank_fragmentos_rag(
        consulta="refinamiento historias de usuario pruebas humo funcionales regresion automatizacion escalamiento criterios de aceptacion",
        fragmentos=contexto_rag,
        top_k=3,
    )

    subopciones_ca = _extraer_subopciones_criterios(contenido_req)
    modelo_activo, motivo_ruta = seleccionar_modelo_qa(
        contenido_req=contenido_req,
        cantidad_subopciones=len(subopciones_ca),
        modelo_base=MODELO_OLLAMA,
        modelo_rapido=MODELO_RAPIDO,
        modelo_complejo=MODELO_OLLAMA,
    )
    print(f"[Router] Modelo seleccionado: {modelo_activo} ({motivo_ruta})")

    carpeta_cache = Path(__file__).parent / ".cache_qa"
    extraido: dict | None = None

    if modo_orquestacion == "subagentes":
        print("[3/4] Orquestando subagentes especializados por etapa...")
        extraido, modelo_efectivo = ejecutar_orquestacion_subagentes_qa(
            contenido_req=contenido_req,
            contexto_rag=contexto_rag,
            tipo_fuente=tipo_fuente,
            modelo_principal=modelo_activo,
            modelo_rapido=MODELO_RAPIDO,
            carpeta_cache=carpeta_cache,
            preguntar_fn=preguntar_llm,
            extraer_json_fn=extraer_json,
            timeout=900,
        )
        modelo_activo = modelo_efectivo
        if not extraido:
            print("Los subagentes no devolvieron una estructura válida.")
            return
        datos_estructurados = normalizar_y_validar_qa(extraido)
        datos_estructurados = _completar_casos_funcionales_desde_criterios(
            datos_estructurados, contenido_req
        )
        datos_estructurados = _completar_minimos_regresion_y_automatizacion(
            datos_estructurados, minimo_por_tipo=2
        )
    else:
        prompt_usuario = f"""
POLÍTICAS INTERNAS DE QA (RAG):
{contexto_rag}

REQUERIMIENTO DEL CLIENTE ({tipo_fuente.upper()}):
{contenido_req}

Analiza el requerimiento y genera el JSON solicitado aplicando las políticas de QA.
"""
        clave_cache = calcular_clave_cache(
            contenido_req=contenido_req,
            contexto_rag=contexto_rag,
            modelo=modelo_activo,
        )
        datos_estructurados = leer_cache_qa(carpeta_cache, clave_cache)

        if datos_estructurados is not None:
            desde_cache = True
            print(f"[3/4] Resultado recuperado desde caché local ({clave_cache[:10]}...).")
        else:
            print(f"[3/4] Procesando con {modelo_activo} en Ollama...")
            extraido, modelo_efectivo, info_res = ejecutar_llm_con_resiliencia(
                prompt=prompt_usuario,
                system_prompt=SYSTEM_PROMPT_QA,
                modelo_principal=modelo_activo,
                preguntar_fn=preguntar_llm,
                extraer_json_fn=extraer_json,
                modelo_fallback=MODELO_RAPIDO,
                timeout=900,
                max_reintentos_por_modelo=1,
            )
            modelo_activo = modelo_efectivo

            if extraido:
                datos_estructurados = normalizar_y_validar_qa(extraido)
                datos_estructurados = _completar_casos_funcionales_desde_criterios(
                    datos_estructurados, contenido_req
                )
                datos_estructurados = _completar_minimos_regresion_y_automatizacion(
                    datos_estructurados, minimo_por_tipo=2
                )
                guardar_cache_qa(carpeta_cache, clave_cache, datos_estructurados)
            else:
                print(
                    f"Fallo tras reintentos/fallback ({info_res['ultimo_error']})."
                )
                return

    print("[4/4] Guardando resultados en carpeta salidas/...")
    if datos_estructurados:
        ruta_json = carpeta_salidas / f"{nombre_base_salida}_qa.json"
        ruta_json.write_text(
            json.dumps(datos_estructurados, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"JSON estructurado guardado en: {ruta_json}")

        ruta_docx = carpeta_salidas / f"{nombre_base_salida}_qa.docx"
        ruta_guardada = guardar_docx_seguro(
            datos_estructurados, ruta_docx, exportar_qa_a_word
        )
        if ruta_guardada:
            print(f"Documento Word guardado en: {ruta_guardada}")

        eval_cov = evaluar_cobertura_criterios(datos_estructurados, subopciones_ca)
        registrar_metricas_ejecucion(
            carpeta_salidas=carpeta_salidas,
            nombre_salida=nombre_base_salida,
            tipo_fuente=tipo_fuente,
            modelo=modelo_activo,
            desde_cache=desde_cache,
            duracion_seg=timer.elapsed_seg(),
            datos_qa=datos_estructurados,
            eval_cobertura=eval_cov,
        )

        eval_calidad = evaluar_calidad_artefactos(datos_estructurados)
        print(
            f"[Calidad QA] Puntaje: {eval_calidad['puntaje']}/100 | "
            f"Aprobado: {eval_calidad['aprobado']}"
        )
        for adv in eval_calidad["advertencias"]:
            print(f"  - Advertencia: {adv}")

        trazabilidad = construir_matriz_trazabilidad(
            datos_estructurados, subopciones_ca
        )
        ruta_traza = carpeta_salidas / f"{nombre_base_salida}_trazabilidad.json"
        ruta_traza.write_text(
            json.dumps(trazabilidad, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(
            f"[Trazabilidad QA] {trazabilidad['criterios_cubiertos']}/"
            f"{trazabilidad['total_criterios_detectados']} "
            f"({trazabilidad['porcentaje_trazabilidad']}%) -> {ruta_traza.name}"
        )

        imprimir_resumen_consola(datos_estructurados)
        ruta_resumen = generar_resumen_ejecutivo_md(
            datos_qa=datos_estructurados,
            nombre_salida=nombre_base_salida,
            carpeta_salidas=carpeta_salidas,
            modelo_usado=modelo_activo,
            eval_calidad=eval_calidad,
            trazabilidad=trazabilidad,
        )
        print(f"[Resumen MD] Guardado en: {ruta_resumen.name}")
    else:
        print("No se pudo extraer un JSON válido de la respuesta del modelo.")


def ejecutar_pipeline_qa(
    nombre_archivo: str, modo_orquestacion: str = "directo"
) -> None:
    base_dir = Path(__file__).parent
    ruta_entrada = base_dir / "entradas" / nombre_archivo
    carpeta_docs = base_dir / "documentos"
    carpeta_salidas = base_dir / "salidas"
    carpeta_salidas.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] Leyendo archivo de requerimiento: {ruta_entrada}")
    lectura = leer_archivo_requerimiento(str(ruta_entrada))
    if not lectura["ok"]:
        print(f"Error al leer archivo: {lectura['error']}")
        return

    contenido_req = preparar_texto_por_secciones(lectura["contenido"], max_chars=8000)
    base_nombre = Path(nombre_archivo).stem

    _procesar_y_guardar_qa(
        contenido_req=contenido_req,
        tipo_fuente=lectura["tipo"],
        nombre_base_salida=base_nombre,
        carpeta_docs=carpeta_docs,
        carpeta_salidas=carpeta_salidas,
        modo_orquestacion=modo_orquestacion,
    )


def ejecutar_pipeline_qa_devops(
    work_item_id: int | None = None,
    ids_manuales: list[int] | None = None,
    nombre_salida_custom: str | None = None,
    top: int = 5,
    modo_orquestacion: str = "directo",
) -> None:
    base_dir = Path(__file__).parent
    carpeta_docs = base_dir / "documentos"
    carpeta_salidas = base_dir / "salidas"
    carpeta_salidas.mkdir(parents=True, exist_ok=True)

    print("[1/4] Consultando Work Items desde Azure DevOps...")
    cliente = AzureDevOpsCliente()

    if ids_manuales:
        ids = ids_manuales
        nombre_salida = nombre_salida_custom or f"wi_{'_'.join(str(i) for i in ids[:3])}"
    elif work_item_id is not None:
        ids = [work_item_id]
        nombre_salida = nombre_salida_custom or f"wi_{work_item_id}"
    else:
        ids = cliente.listar_ids_work_items(top=top)
        nombre_salida = nombre_salida_custom or f"devops_top_{top}"

    items = cliente.obtener_work_items(ids)
    if not items:
        print("No se encontraron Work Items para procesar.")
        return

    textos_formateados = [formatear_work_item(item) for item in items]
    contenido_req = preparar_texto_por_secciones(
        "\n\n---\n\n".join(textos_formateados), max_chars=12000
    )

    _procesar_y_guardar_qa(
        contenido_req=contenido_req,
        tipo_fuente="AZURE DEVOPS WORK ITEM",
        nombre_base_salida=nombre_salida,
        carpeta_docs=carpeta_docs,
        carpeta_salidas=carpeta_salidas,
        modo_orquestacion=modo_orquestacion,
    )


def ejecutar_pipeline_qa_interactivo(
    top: int = 10, modo_orquestacion: str = "directo"
) -> None:
    cliente = AzureDevOpsCliente()

    print("\n¿Cómo quieres seleccionar los Work Items de Azure DevOps?")
    print("1. Ingresar uno o varios IDs manualmente (ej. 57265 o 57265,63693)")
    print("2. Listar los últimos Work Items, filtrar por tipo y elegir cuáles procesar")
    opcion = input("Selecciona una opción (1 o 2, Enter para 1): ").strip()

    if opcion == "2":
        filtro_tipo = (
            input(
                "Filtrar por tipo (ej. User Story, Bug, Task) o Enter para todos: "
            )
            .strip()
            .lower()
        )
        ids_recientes = cliente.listar_ids_work_items(top=top)
        items = cliente.obtener_work_items(ids_recientes)

        if filtro_tipo:
            items = [
                item
                for item in items
                if item.get("tipo", "").strip().lower() == filtro_tipo
            ]

        if not items:
            print("No hay Work Items que coincidan con el criterio.")
            return

        print("\nWork Items disponibles:")
        for item in items:
            print(
                f"  - ID: {item['id']} | Tipo: {item['tipo']} | "
                f"Estado: {item['estado']} | Título: {item['titulo']}"
            )

        seleccion = input(
            "\nEscribe los IDs a procesar separados por coma (o Enter para todos los listados): "
        ).strip()

        if not seleccion:
            ids_elegidos = [item["id"] for item in items]
        else:
            ids_elegidos = _parsear_ids_desde_texto(seleccion)

        if not ids_elegidos:
            print("No se seleccionaron IDs válidos.")
            return

        nombre_salida = f"wi_{'_'.join(str(i) for i in ids_elegidos[:3])}"
        ejecutar_pipeline_qa_devops(
            ids_manuales=ids_elegidos,
            nombre_salida_custom=nombre_salida,
            top=top,
            modo_orquestacion=modo_orquestacion,
        )
    else:
        entrada_ids = input("Escribe el ID o IDs separados por coma (ej. 57265): ").strip()
        ids_elegidos = _parsear_ids_desde_texto(entrada_ids)
        if not ids_elegidos:
            print("No se ingresaron IDs numéricos válidos.")
            return

        nombre_salida = f"wi_{'_'.join(str(i) for i in ids_elegidos[:3])}"
        ejecutar_pipeline_qa_devops(
            ids_manuales=ids_elegidos,
            nombre_salida_custom=nombre_salida,
            top=top,
            modo_orquestacion=modo_orquestacion,
        )


if __name__ == "__main__":
    print("Estrategia de generación LLM:")
    print("1. Directa (1 llamada con resiliencia/fallback)")
    print("2. Subagentes por etapa (refinamiento, historias, casos)")
    estrategia = input("Elige 1 o 2 (Enter para 1): ").strip()
    modo_llm = "subagentes" if estrategia == "2" else "directo"

    print("\nOrigen del requerimiento:")
    print("1. Azure DevOps (seleccionar ID o listar recientes)")
    print("2. Archivo local en carpeta entradas/")
    modo = input("Elige 1 o 2 (Enter para Azure DevOps): ").strip()

    if modo == "2":
        archivo_prueba = "GP-FM-01 Requerimiento - Convenio de infracciones creadas.xlsx"
        ejecutar_pipeline_qa(archivo_prueba, modo_orquestacion=modo_llm)
    else:
        ejecutar_pipeline_qa_interactivo(top=10, modo_orquestacion=modo_llm)