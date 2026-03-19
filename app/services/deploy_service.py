"""Limb bundle (ZIP) generation service."""

import io
import logging
import os
import zipfile

logger = logging.getLogger("smartexec.deploy")


def generate_limb_bundle(tenant, pattern: str, menus: list[str]) -> str:
    """Generate a Limb deployment ZIP for the given tenant.

    The ZIP contains startup scripts and configuration for running
    on the customer's local PC environment.
    """
    bundle_dir = "limb_bundles"
    os.makedirs(bundle_dir, exist_ok=True)
    zip_path = os.path.join(bundle_dir, f"{tenant.id}.zip")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Startup script
        zf.writestr(
            "start_limb.py",
            _generate_startup_script(tenant, pattern, menus),
        )

        # Configuration
        zf.writestr(
            "config.json",
            _generate_config_json(tenant, pattern, menus),
        )

        # README
        zf.writestr(
            "README.md",
            _generate_readme(tenant, pattern),
        )

        # Requirements
        zf.writestr(
            "requirements.txt",
            "httpx>=0.27.0\npython-dotenv>=1.0.0\n",
        )

        # .env template
        zf.writestr(
            ".env.template",
            "# Limb Environment Configuration\n"
            f"TENANT_ID={tenant.id}\n"
            "BRAIN_URL=https://your-brain-server.example.com\n"
            "# Add API keys as needed\n",
        )

    logger.info("Generated Limb bundle: %s", zip_path)
    return zip_path


def _generate_startup_script(tenant, pattern: str, menus: list[str]) -> str:
    return f'''\
"""Limb startup script for tenant: {tenant.name}"""

import json
import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

TENANT_ID = os.getenv("TENANT_ID", "{tenant.id}")
BRAIN_URL = os.getenv("BRAIN_URL", "http://localhost:8000")
PATTERN = "{pattern}"
MENUS = {menus!r}


def main():
    print(f"Limb starting for tenant: {{TENANT_ID}}")
    print(f"Pattern: {{PATTERN}}")
    print(f"Connecting to Brain: {{BRAIN_URL}}")

    # TODO: Implement actual Limb functionality
    # Pattern A: Connect to external SaaS APIs (freee, Google Calendar)
    # Pattern B: Connect to Google Sheets / Excel
    # Pattern C: RPA for legacy systems
    # Pattern D: No external connection needed

    while True:
        try:
            # Poll Brain for tasks
            resp = httpx.get(f"{{BRAIN_URL}}/tenants/{{TENANT_ID}}/status")
            if resp.status_code == 200:
                print(f"Status: {{resp.json()}}")
            time.sleep(30)
        except Exception as e:
            print(f"Connection error: {{e}}")
            time.sleep(60)


if __name__ == "__main__":
    main()
'''


def _generate_config_json(tenant, pattern: str, menus: list[str]) -> str:
    import json

    config = {
        "tenant_id": tenant.id,
        "tenant_name": tenant.name,
        "pattern": pattern,
        "menus": menus,
        "brain_url": "https://your-brain-server.example.com",
        "version": "1.0",
    }
    return json.dumps(config, indent=2, ensure_ascii=False)


def _generate_readme(tenant, pattern: str) -> str:
    return f"""\
# AI Shaker Limb - {tenant.name}

## Setup

1. Install Python 3.10+
2. Run: `pip install -r requirements.txt`
3. Copy `.env.template` to `.env` and configure
4. Run: `python start_limb.py`

## Pattern: {pattern}

This Limb bundle is configured for Pattern {pattern}.
See the AI Shaker documentation for details.
"""
