"""Le worker doit pouvoir configurer tous les mappers ORM sans l'API.

Le 21/09/2026, le rapport offert d'un nouvel inscrit a échoué dans le worker :
`Report.project_id` référence `projects`, dont le modèle n'était importé que
par les routeurs de l'API. Ce test rejoue l'import du worker seul, dans un
sous-processus vierge, puis force la configuration des mappers.
"""
import subprocess
import sys


def test_worker_configure_tous_les_mappers():
    code = (
        "import worker.main\n"
        "from app.modules.reports.models import Report\n"
        # `.column` résout la table cible : NoReferencedTableError si `projects`
        # n'est pas dans les métadonnées, exactement ce qui a cassé en prod.
        "fk = next(iter(Report.__table__.c.project_id.foreign_keys))\n"
        "assert fk.column.table.name == 'projects'\n"
        "print('ok')\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       env={"QDRANT_URL": ":memory:", "PATH": "/usr/bin:/bin", "AUTH_MODE": "local",
                            "DATABASE_URL": "sqlite://", "PYTHONPATH": "."}, timeout=120)
    assert r.returncode == 0, r.stderr[-2000:]
    assert "ok" in r.stdout
