"""Migration test — upgrade head + downgrade base chạy sạch trên DB rỗng (M1 §7.2)."""
from __future__ import annotations

import os

import sqlalchemy as sa

EXPECTED_TABLES = {
    "project",
    "page",
    "text_region",
    "ocr_result",
    "translation_result",
    "typeset_result",
    "job",
}


def _sync_engine():
    url = os.environ["TEST_DATABASE_URL"].replace("+asyncpg", "+psycopg")
    return sa.create_engine(url)


def test_migration_tao_du_7_bang():
    eng = _sync_engine()
    with eng.connect() as conn:
        names = set(sa.inspect(conn).get_table_names())
    eng.dispose()
    assert EXPECTED_TABLES <= names, EXPECTED_TABLES - names


def test_cot_ket_qua_chua_chay_deu_nullable():
    """Evidence-first: field của bước chưa chạy phải NULL-able, không default giả."""
    eng = _sync_engine()
    with eng.connect() as conn:
        insp = sa.inspect(conn)
        page_cols = {c["name"]: c for c in insp.get_columns("page")}
        region_cols = {c["name"]: c for c in insp.get_columns("text_region")}
        ocr_cols = {c["name"]: c for c in insp.get_columns("ocr_result")}
    eng.dispose()
    assert page_cols["clean_image_path"]["nullable"] is True
    assert region_cols["confidence"]["nullable"] is True
    assert region_cols["reading_order"]["nullable"] is True
    assert ocr_cols["raw_text"]["nullable"] is True
    assert ocr_cols["confidence"]["nullable"] is True


def test_region_result_la_quan_he_1_1():
    eng = _sync_engine()
    with eng.connect() as conn:
        insp = sa.inspect(conn)
        for table in ("ocr_result", "translation_result", "typeset_result"):
            uniques = {
                tuple(u["column_names"]) for u in insp.get_unique_constraints(table)
            }
            assert ("region_id",) in uniques, f"{table} thiếu unique(region_id)"
    eng.dispose()


def test_upgrade_downgrade_hai_chieu_khong_loi(tmp_path):
    """Chạy thật downgrade base rồi upgrade head lại trên chính DB test."""
    from alembic import command
    from alembic.config import Config

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = Config(os.path.join(root, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(root, "alembic"))

    command.downgrade(cfg, "base")
    eng = _sync_engine()
    with eng.connect() as conn:
        names = set(sa.inspect(conn).get_table_names())
        leftover_enums = {
            r[0] for r in conn.execute(sa.text("SELECT typname FROM pg_type WHERE typtype='e'"))
        }
    eng.dispose()
    assert not (EXPECTED_TABLES & names), f"downgrade còn sót bảng: {EXPECTED_TABLES & names}"
    assert leftover_enums == set(), f"downgrade còn sót enum type: {leftover_enums}"

    command.upgrade(cfg, "head")
    eng = _sync_engine()
    with eng.connect() as conn:
        names = set(sa.inspect(conn).get_table_names())
    eng.dispose()
    assert EXPECTED_TABLES <= names
