import sqlite3

from sqlalchemy import func, select

from app.core.config import get_settings
from app.database import models as m
from app.database.migrations import MIGRATIONS, current_version


def test_uses_separate_test_database(tmp_path):
    path = str(get_settings().database_path)
    assert "promptcraft-tests-" in path and not path.endswith("data/promptcraft.db")


def test_schema_and_seed_counts(client, db):
    count = lambda model: db.scalar(select(func.count()).select_from(model))
    assert count(m.Prompt) >= 75 and count(m.Category) == 16 and count(m.BeforeAfterExample) >= 15
    assert count(m.LearningModule) >= 16 and count(m.GlossaryTerm) >= 20 and count(m.KnowledgeCheck) >= 32
    assert db.scalar(select(func.count()).select_from(m.Prompt).where(m.Prompt.featured.is_(True))) >= 8


def test_minimum_prompt_distribution(client, db):
    minimum = {"Business Analysis": 7, "Project Management": 7, "Scrum and Agile": 5, "Customer Service": 5, "SQL": 5, "Excel": 5, "PowerPoint": 5,
               "Meeting Notes": 5, "Email Writing": 5, "Data Analysis": 5, "Coding": 5, "Marketing": 4, "Human Resources": 4, "Finance": 4,
               "Research": 4, "General Productivity": 4}
    rows = dict(db.execute(select(m.Category.name, func.count(m.Prompt.id)).join(m.Prompt).group_by(m.Category.id)).all())
    for name, n in minimum.items():
        assert rows.get(name, 0) >= n, name


def test_every_seeded_prompt_is_complete(client, db):
    for p in db.scalars(select(m.Prompt)).unique():
        assert p.title and p.description and p.full_prompt and p.why_it_works and p.expected_output and p.example_output, p.title
        assert p.customization_tips and p.common_mistakes and p.constraints and p.tags and p.ai_tools and p.difficulty
        for key in ("role", "context", "task", "input", "output_format", "constraints", "quality_criteria"):
            assert p.components.get(key), (p.title, key)
        assert p.slug and p.version == 1 and p.published and not p.archived
    texts = [p.full_prompt for p in db.scalars(select(m.Prompt)).unique()]
    assert len(set(texts)) == len(texts)  # no duplicated prompts


def test_seed_is_idempotent(client, db):
    from app.seed.seed_database import seed_all
    before = db.scalar(select(func.count()).select_from(m.Prompt))
    assert seed_all(db) == {"prompts": 0, "learning_modules": 0, "examples": 0, "glossary_terms": 0}
    assert seed_all(db, ignore_flags=True) == {"prompts": 0, "learning_modules": 0, "examples": 0, "glossary_terms": 0}
    assert db.scalar(select(func.count()).select_from(m.Prompt)) == before


def test_restart_preserves_user_data(client):
    from app.database.initialization import initialize_database
    c = client.post("/api/custom-prompts", json={"title": "Survives restart", "content": "Some content that must survive."}).json()
    p = client.get("/api/prompts?page_size=1").json()["items"][0]
    client.post(f"/api/favorites/{p['id']}")
    initialize_database()  # what every start-up does
    initialize_database()
    assert client.get(f"/api/custom-prompts/{c['id']}").status_code == 200
    assert p["id"] in {x["id"] for x in client.get("/api/favorites").json()["items"]}
    client.delete(f"/api/custom-prompts/{c['id']}?permanent=true")
    client.delete(f"/api/favorites/{p['id']}")


def test_fresh_database_initialisation_and_seed_markers(tmp_path):
    """A brand-new database gets the schema, seed data once, and never re-seeds deleted content."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.database.migrations import run_migrations
    from app.seed.seed_database import seed_all

    engine = create_engine(f"sqlite:///{(tmp_path / 'fresh.db').as_posix()}")
    assert current_version(engine) == 0
    assert run_migrations(engine) == MIGRATIONS[-1][0] and run_migrations(engine) == MIGRATIONS[-1][0]
    with Session(engine) as s:
        first = seed_all(s)
        assert first["prompts"] >= 75
        s.query(m.PromptTag).delete()
        s.query(m.Prompt).delete()
        s.commit()
        assert seed_all(s)["prompts"] == 0  # deliberately emptied tables are not silently refilled
        assert seed_all(s, ignore_flags=True)["prompts"] >= 75  # explicit recovery option
    engine.dispose()


def test_schema_version_table_and_indexes(client):
    path = get_settings().database_path
    con = sqlite3.connect(path)
    versions = [r[0] for r in con.execute("SELECT version FROM schema_version ORDER BY version")]
    assert versions == [v for v, _, _ in MIGRATIONS]
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    expected = {"prompts", "categories", "subcategories", "tags", "prompt_tags", "favorites", "custom_prompts", "custom_prompt_versions", "learning_modules",
                "learning_progress", "knowledge_checks", "before_after_examples", "glossary_terms", "prompt_usage_events", "app_settings", "local_profile",
                "admin_credentials", "import_history", "recently_viewed_prompts", "schema_version"}
    assert expected <= tables
    idx = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    assert "ix_prompts_listing" in idx and "ix_usage_type_created" in idx
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    con.close()


def test_unique_constraints_and_foreign_keys(db):
    import pytest
    from sqlalchemy.exc import IntegrityError
    db.add(m.Category(name="SQL", slug="sql-dup"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(m.Prompt(title="x", slug="y", description="d", full_prompt="p", category_id=999999))
    with pytest.raises(IntegrityError):  # foreign keys are enforced
        db.commit()
    db.rollback()


def test_failed_update_rolls_back(client, admin):
    p = client.get("/api/prompts?page_size=1").json()["items"][0]
    full = admin.get(f"/api/prompts/{p['id']}").json()
    bad = {**full, "category": "Missing Category", "category_id": None, "title": "Changed title that must not persist"}
    assert admin.put(f"/api/prompts/{p['id']}", json=bad).status_code == 422
    assert client.get(f"/api/prompts/{p['id']}").json()["title"] == p["title"]
