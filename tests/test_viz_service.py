import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.modules.viz import service

BON = ('```viz\n{"version":"1","intent":"domination","title":"Parts","unit":"%",'
       '"series":[{"label":"A","value":60},{"label":"B","value":40}]}\n```')


@pytest.fixture
def db():
    engine = create_engine("sqlite://", future=True)
    import app.modules.viz.models  # noqa: F401
    Base.metadata.create_all(engine, tables=[Base.metadata.tables["viz_rendus"]])
    with Session(engine) as s:
        yield s


def test_preparer_compile_et_enregistre_le_rendu(db):
    out = service.preparer(db, "intro\n" + BON)
    assert out[0]["statut"] == "ok" and out[0]["kind"] == "bar_h"
    assert service.rendu_par_empreinte(db, out[0]["empreinte"]) == out[0]["vl"]


def test_preparer_est_idempotent_sur_le_meme_spec(db):
    a = service.preparer(db, BON)
    b = service.preparer(db, BON)
    assert a[0]["empreinte"] == b[0]["empreinte"]
    from app.modules.viz.models import VizRendu

    assert db.query(VizRendu).count() == 1


def test_un_texte_sans_bloc_renvoie_une_liste_vide(db):
    assert service.preparer(db, "Rien à voir ici.") == []
    assert service.preparer_sans_faute(db, "Rien à voir ici.") is None


def test_un_bloc_invalide_est_conserve_avec_son_statut(db):
    out = service.preparer(db, "```viz\n{nope\n```")
    assert out[0]["statut"].startswith("repli_tableau") and out[0]["empreinte"] == ""
