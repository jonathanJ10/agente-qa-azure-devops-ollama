from pathlib import Path
import os

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

if load_dotenv is not None and ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH, override=True)


class AzureDevOpsSettings:
    def __init__(self) -> None:
        self.org: str = os.getenv("AZURE_DEVOPS_ORG", "DataToolsSA").strip()
        self.project: str = os.getenv("AZURE_DEVOPS_PROJECT", "Circulemos").strip()
        self.pat: str = os.getenv("AZURE_DEVOPS_PAT", "").strip()
        self.api_version: str = os.getenv("AZURE_DEVOPS_API_VERSION", "7.1").strip()

    @property
    def base_url(self) -> str:
        return f"https://dev.azure.com/{self.org}"

    def validar(self) -> None:
        if not self.org:
            raise ValueError("Falta configurar AZURE_DEVOPS_ORG en .env o en el entorno.")
        if not self.project:
            raise ValueError("Falta configurar AZURE_DEVOPS_PROJECT en .env o en el entorno.")
        if not self.pat:
            raise ValueError("Falta configurar AZURE_DEVOPS_PAT en .env o en el entorno.")


settings = AzureDevOpsSettings()