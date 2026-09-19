#!/bin/sh
# Testlauf im Container gegen die Testdatenbank (siehe AGENTS.md, Abschnitt Testing)
pip install -q -r requirements-dev.txt 2>&1 | grep -v -i "notice\|warning"
python -m pyflakes main.py common.py core.py product_service.py models.py calc.py units.py seed.py database.py routers tests && echo "pyflakes: sauber"
pytest -q "$@" 2>&1 | grep -v -i "warn\|deprecat\|^  \|^$"