import sqlite3
from contextlib import closing

import pytest

import src.database.connection as connection_module
from src.database.connection import Connection


def test_owner_token_controls_commit_and_close(tmp_path):
    dbfile = str(tmp_path / "owner.db")
    conn = Connection(dbfile)

    owner = conn.begin_transaction()
    con, cur = conn.connect()
    cur.execute("CREATE TABLE t(x INTEGER)")
    cur.execute("INSERT INTO t(x) VALUES (1)")

    other = conn.begin_transaction()
    # non-owner end should be ignored
    conn.end_transaction(other, commit=False)
    assert conn._active_con is not None

    # owner end should commit and close
    conn.end_transaction(owner, commit=True)
    assert conn._active_con is None

    # verify committed
    con2 = sqlite3.connect(dbfile)
    res = con2.execute("SELECT x FROM t").fetchone()[0]
    con2.close()
    assert res == 1


def test_maybe_close_ignores_active_connection(tmp_path):
    dbfile = str(tmp_path / "maybe.db")
    conn = Connection(dbfile)

    owner = conn.begin_transaction()
    con_active, cur = conn.connect()
    cur.execute("CREATE TABLE t2(y INTEGER)")

    # _maybe_close should not close the active connection
    conn._maybe_close(con_active)
    cur.execute("INSERT INTO t2(y) VALUES (2)")
    cur.execute("SELECT y FROM t2")
    assert cur.fetchone()[0] == 2

    conn.end_transaction(owner, commit=True)


def test_owner_rollback_undoes_drop_and_create_after_nested_commit(tmp_path):
    dbfile = tmp_path / "schema.db"
    with closing(sqlite3.connect(dbfile)) as con:
        con.execute("CREATE TABLE original(x INTEGER)")
        con.execute("INSERT INTO original VALUES (1)")
        con.commit()
    conn = Connection(dbfile)

    owner = conn.begin_transaction()
    _, cur = conn.connect()
    # No inserts or updates here: table changes alone must be transactional.
    cur.execute("DROP TABLE original")
    cur.execute("CREATE TABLE replacement(y INTEGER)")
    conn.end_transaction(conn.begin_transaction(), commit=True)
    conn.end_transaction(owner, commit=False)

    with closing(sqlite3.connect(dbfile)) as con:
        assert con.execute("SELECT x FROM original").fetchall() == [(1,)]
        assert con.execute("SELECT name FROM sqlite_master WHERE name='replacement'").fetchone() is None


def test_backup_copies_only_committed_state_during_active_transaction(tmp_path):
    dbfile = tmp_path / "backup.db"
    destination = tmp_path / "snapshot.db"
    with closing(sqlite3.connect(dbfile)) as con:
        con.execute("CREATE TABLE values_table(value INTEGER)")
        con.execute("INSERT INTO values_table VALUES (1)")
        con.commit()

    conn = Connection(str(dbfile))
    owner = conn.begin_transaction()
    _, cur = conn.connect()
    cur.execute("INSERT INTO values_table VALUES (2)")

    conn.backup_to(str(destination))
    conn.end_transaction(owner, commit=False)

    with closing(sqlite3.connect(destination)) as con:
        assert con.execute("SELECT value FROM values_table ORDER BY value").fetchall() == [(1,)]


def test_backup_does_not_leave_partial_output_on_publish_failure(tmp_path, monkeypatch):
    dbfile = tmp_path / "backup.db"
    destination = tmp_path / "snapshot.db"
    with closing(sqlite3.connect(dbfile)) as con:
        con.execute("CREATE TABLE values_table(value INTEGER)")
        con.commit()

    def fail_replace(_source, _destination):
        raise OSError("publish failed")

    monkeypatch.setattr(connection_module.os, "replace", fail_replace)

    with pytest.raises(OSError, match="publish failed"):
        Connection(str(dbfile)).backup_to(str(destination))

    assert not destination.exists()
    assert list(tmp_path.glob("snapshot.db.*.tmp")) == []


def test_backup_missing_source_fails_without_creating_files(tmp_path):
    dbfile = tmp_path / "missing.db"
    destination = tmp_path / "snapshot.db"

    with pytest.raises(sqlite3.OperationalError):
        Connection(dbfile).backup_to(str(destination))

    assert not dbfile.exists()
    assert not destination.exists()
    assert list(tmp_path.glob("snapshot.db.*.tmp")) == []


def test_backup_failure_cleans_up_and_preserves_previous_snapshot(tmp_path, monkeypatch):
    dbfile = tmp_path / "backup.db"
    destination = tmp_path / "snapshot.db"
    with closing(sqlite3.connect(dbfile)) as con:
        con.execute("CREATE TABLE values_table(value INTEGER)")
        con.commit()
    Connection(dbfile).backup_to(str(destination))
    previous_snapshot = destination.read_bytes()
    original_connect = sqlite3.connect

    class FailingBackupConnection(sqlite3.Connection):
        def backup(self, target, **kwargs):
            target.execute("CREATE TABLE partial_output(value INTEGER)")
            target.commit()
            raise sqlite3.OperationalError("backup failed")

    def connect(*args, **kwargs):
        if kwargs.get("uri"):
            kwargs["factory"] = FailingBackupConnection
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(connection_module.sqlite3, "connect", connect)

    with pytest.raises(sqlite3.OperationalError, match="backup failed"):
        Connection(dbfile).backup_to(str(destination))

    assert destination.read_bytes() == previous_snapshot
    assert list(tmp_path.glob("snapshot.db.*.tmp")) == []
