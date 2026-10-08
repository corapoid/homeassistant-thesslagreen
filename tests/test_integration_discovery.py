"""Discover a fresh HACS-style installation through the real HA loader."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def test_fresh_install_is_listed_and_starts_config_flow(tmp_path):
    source = Path(__file__).resolve().parents[1] / "custom_components" / "thessla_green"
    config = tmp_path / "ha_config"
    shutil.copytree(source, config / "custom_components" / "thessla_green",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    script = """
import asyncio
import json
import sys
from homeassistant import config_entries, loader
from homeassistant.core import HomeAssistant

async def check():
    hass = HomeAssistant(sys.argv[1])
    loader.async_setup(hass)
    hass.config_entries = config_entries.ConfigEntries(hass, {})
    try:
        custom = await loader.async_get_custom_components(hass)
        flows = await loader.async_get_config_flows(hass)
        metadata = await loader.async_get_integration_descriptions(hass)
        result = await hass.config_entries.flow.async_init('thessla_green', context={'source': 'user'})
        print(json.dumps({
            'detected': 'thessla_green' in custom,
            'listed': 'thessla_green' in flows,
            'name': metadata['custom']['integration']['thessla_green']['name'],
            'type': result['type'],
            'step_id': result['step_id'],
        }))
    finally:
        await hass.async_stop()

asyncio.run(check())
"""
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    result = subprocess.run([sys.executable, "-B", "-c", script, str(config)],
                            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report == {"detected": True, "listed": True, "name": "Thessla Green",
                      "type": "form", "step_id": "user"}
