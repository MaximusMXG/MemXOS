#!/usr/bin/env bash
# Autostart hook notes for the live ISO kiosk session.
exec env PYTHONPATH=/opt/memex-linux-installer /usr/bin/python3 -m memex_wizard.app
