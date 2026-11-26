import base64
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from settings import settings


def limpiar_html(texto_html: str) -> str:
    if not texto_html:
        return ""
    # Convierte elementos de lista en guiones para conservar estructura de subopciones
    texto = re.sub(r"<li[^>]*>", "\n- ", texto_html, flags=re.IGNORECASE)
    # Reemplaza saltos de línea y cierres de bloque HTML por saltos de línea
    texto = re.sub(r"<br\s*/?>", "\n", texto, flags=re.IGNORECASE)
    texto = re.sub(r"</(p|div|li|tr|h[1-6])>", "\n", texto, flags=re.IGNORECASE)
    # Elimina el resto de etiquetas HTML
    texto = re.sub(r"<[^>]+>", "", texto)
    # Decodifica entidades HTML ( , &, <, etc.)
    texto = html.unescape(texto)
    # Evita dobles guiones accidentales en listas
    texto = re.sub(r"^\s*-\s*-\s*", "- ", texto, flags=re.MULTILINE)
    # Limpia espacios múltiples y líneas vacías excesivas
    lineas = [re.sub(r"[ \t]+", " ", linea).strip() for linea in texto.splitlines()]
    return "\n".join(linea for linea in lineas if linea)


def _escapar_wiql(valor: str) -> str:
    return (valor or "").replace("'", "''")


def _formatear_error_http(exc: urllib.error.HTTPError) -> str:
    detalle = ""
    try:
        cuerpo = exc.read().decode("utf-8", errors="ignore").strip()
        if cuerpo:
            detalle = f" - {cuerpo[:200]}"
    except Exception:
        detalle = ""
    return f"HTTP {exc.code} {exc.reason}{detalle}"


def formatear_work_item(item: dict) -> str:
    descripcion_limpia = limpiar_html(item.get("descripcion", ""))
    criterios_limpios = limpiar_html(item.get("criterios_aceptacion", ""))

    bloques = [
        f"ID: {item.get('id')}",
        f"Tipo: {item.get('tipo', '')}",
        f"Estado: {item.get('estado', '')}",
        f"Título: {item.get('titulo', '')}",
        f"Descripción:\n{descripcion_limpia if descripcion_limpia else '(Sin descripción registrada)'}",
        f"Criterios de aceptación:\n{criterios_limpios if criterios_limpios else '(Sin criterios de aceptación registrados)'}",
    ]

    return "\n\n".join(bloques)


class AzureDevOpsCliente:
    def __init__(self, timeout: int = 30) -> None:
        settings.validar()
        self.timeout = timeout
        credenciales = f":{settings.pat}".encode("utf-8")
        token_b64 = base64.b64encode(credenciales).decode("ascii")
        self.headers = {
            "Authorization": f"Basic {token_b64}",
            "Content-Type": "application/json",
        }

    def listar_ids_work_items(self, top: int = 10) -> list[int]:
        limite = max(1, int(top))
        proyecto_url = urllib.parse.quote(str(settings.project), safe="")
        proyecto_wiql = _escapar_wiql(str(settings.project))
        url = (
            f"{settings.base_url}/{proyecto_url}/_apis/wit/wiql"
            f"?$top={limite}&api-version={settings.api_version}"
        )
        consulta = {
            "query": (
                f"SELECT [System.Id] FROM WorkItems "
                f"WHERE [System.TeamProject] = '{proyecto_wiql}' "
                f"ORDER BY [System.ChangedDate] DESC"
            ),
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(consulta).encode("utf-8"),
            headers=self.headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                datos = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            print(f"[Azure DevOps] Error listando Work Items: {_formatear_error_http(exc)}")
            return []
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"[Azure DevOps] Error listando Work Items: {exc}")
            return []

        items = datos.get("workItems", [])[:limite]
        return [int(item["id"]) for item in items if "id" in item]

    def obtener_work_items(self, ids: list[int]) -> list[dict]:
        if not ids:
            return []

        ids_unicos = [int(i) for i in dict.fromkeys(ids)]
        campos = [
            "System.Id",
            "System.Title",
            "System.WorkItemType",
            "System.State",
            "System.Description",
            "Microsoft.VSTS.Common.AcceptanceCriteria",
        ]
        campos_str = urllib.parse.quote(",".join(campos))
        proyecto_url = urllib.parse.quote(str(settings.project), safe="")
        resultado: list[dict] = []
        tamano_lote = 100

        for inicio in range(0, len(ids_unicos), tamano_lote):
            lote = ids_unicos[inicio : inicio + tamano_lote]
            ids_str = ",".join(map(str, lote))
            url = (
                f"{settings.base_url}/{proyecto_url}/_apis/wit/workitems"
                f"?ids={ids_str}&fields={campos_str}&api-version={settings.api_version}"
            )
            req = urllib.request.Request(
                url,
                headers=self.headers,
                method="GET",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    datos = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                print(
                    f"[Azure DevOps] Error obteniendo Work Items {lote}: {_formatear_error_http(exc)}"
                )
                continue
            except (urllib.error.URLError, TimeoutError) as exc:
                print(f"[Azure DevOps] Error obteniendo Work Items {lote}: {exc}")
                continue

            for item in datos.get("value", []):
                campos_item = item.get("fields", {})
                resultado.append(
                    {
                        "id": item.get("id"),
                        "tipo": campos_item.get("System.WorkItemType", ""),
                        "titulo": campos_item.get("System.Title", ""),
                        "estado": campos_item.get("System.State", ""),
                        "descripcion": campos_item.get("System.Description", ""),
                        "criterios_aceptacion": campos_item.get(
                            "Microsoft.VSTS.Common.AcceptanceCriteria", ""
                        ),
                    }
                )

        return resultado