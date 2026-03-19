import json
import socket
import sqlite3
import uuid
from datetime import datetime
from typing import Optional

import numpy as np

from config import DB_PATH
from database.models import SCHEMA_SQL
from utils.singleton import SingletonMeta


def _get_ip_address() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "0.0.0.0"


def _get_mac_address() -> str:
    mac = uuid.getnode()
    return ":".join(f"{(mac >> i) & 0xFF:02x}" for i in range(40, -1, -8))


class DatabaseManager(metaclass=SingletonMeta):
    def __init__(self):
        self._conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()
        self._ip_address = _get_ip_address()
        self._mac_address = _get_mac_address()

    def _init_schema(self):
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    # ── Staff ──
    def upsert_staff(self, staff_id: int, username: str, full_name: str,
                     zone_id: int = 0, zone_name: str = ""):
        self._conn.execute(
            """INSERT INTO staff (id, username, full_name, zone_id, zone_name)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   username=excluded.username,
                   full_name=excluded.full_name,
                   zone_id=excluded.zone_id,
                   zone_name=excluded.zone_name""",
            (staff_id, username, full_name, zone_id, zone_name),
        )
        self._conn.commit()

    def get_staff(self, staff_id: int) -> Optional[sqlite3.Row]:
        return self._conn.execute("SELECT * FROM staff WHERE id=?", (staff_id,)).fetchone()

    # ── Test Session ──
    def upsert_test_session(self, data: dict):
        self._conn.execute(
            """INSERT INTO test_session
               (id, hash_key, test, start_date, finish_date, zone_name, total_students, is_active)
               VALUES (:id, :hash_key, :test, :start_date, :finish_date, :zone_name, :total_students, :is_active)
               ON CONFLICT(id) DO UPDATE SET
                   hash_key=excluded.hash_key,
                   test=excluded.test,
                   start_date=excluded.start_date,
                   finish_date=excluded.finish_date,
                   zone_name=excluded.zone_name,
                   total_students=excluded.total_students,
                   is_active=excluded.is_active""",
            data,
        )
        self._conn.commit()

    def mark_session_loaded(self, session_id: int):
        self._conn.execute(
            "UPDATE test_session SET is_loaded=1 WHERE id=?", (session_id,),
        )
        self._conn.commit()

    def get_active_sessions(self) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM test_session WHERE is_active=1 ORDER BY start_date DESC"
        ).fetchall()

    def get_session(self, session_id: int) -> Optional[sqlite3.Row]:
        return self._conn.execute("SELECT * FROM test_session WHERE id=?", (session_id,)).fetchone()

    # ── Test Session Smena ──
    def upsert_session_smena(self, data: dict):
        self._conn.execute(
            """INSERT INTO test_session_sm
               (id, session_id, test_day, sm, count_st, is_active)
               VALUES (:id, :session_id, :test_day, :sm, :count_st, :is_active)
               ON CONFLICT(id) DO UPDATE SET
                   session_id=excluded.session_id,
                   test_day=excluded.test_day,
                   sm=excluded.sm,
                   count_st=excluded.count_st,
                   is_active=excluded.is_active""",
            data,
        )
        self._conn.commit()

    def get_smenas_by_session(self, session_id: int) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM test_session_sm WHERE session_id=? AND is_active=1",
            (session_id,),
        ).fetchall()

    # ── Student ──
    def bulk_upsert_students(self, students: list[dict]):
        self._conn.executemany(
            """INSERT INTO student
               (id, session_sm_id, zone_id, last_name, first_name, middle_name,
                imei, gr_n, sp_n, gender, subject_id, subject_name,
                is_ready, is_face, is_image, is_cheating, is_blacklist,
                is_entered, ps_img, embedding)
               VALUES (:id, :session_sm_id, :zone_id, :last_name, :first_name, :middle_name,
                :imei, :gr_n, :sp_n, :gender, :subject_id, :subject_name,
                :is_ready, :is_face, :is_image, :is_cheating, :is_blacklist,
                :is_entered, :ps_img, :embedding)
               ON CONFLICT(id) DO UPDATE SET
                   session_sm_id=excluded.session_sm_id,
                   zone_id=excluded.zone_id,
                   last_name=excluded.last_name,
                   first_name=excluded.first_name,
                   middle_name=excluded.middle_name,
                   imei=excluded.imei,
                   gr_n=excluded.gr_n,
                   sp_n=excluded.sp_n,
                   gender=excluded.gender,
                   subject_id=excluded.subject_id,
                   subject_name=excluded.subject_name,
                   is_ready=excluded.is_ready,
                   is_face=excluded.is_face,
                   is_image=excluded.is_image,
                   is_cheating=excluded.is_cheating,
                   is_blacklist=excluded.is_blacklist,
                   is_entered=excluded.is_entered,
                   ps_img=excluded.ps_img,
                   embedding=excluded.embedding""",
            students,
        )
        self._conn.commit()

    def get_students_by_smena(self, session_sm_id: int) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM student WHERE session_sm_id=?", (session_sm_id,)
        ).fetchall()

    def load_embeddings_for_smena(self, session_sm_id: int) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, last_name, first_name, middle_name, gender, sp_n, embedding "
            "FROM student WHERE session_sm_id=? AND embedding IS NOT NULL",
            (session_sm_id,),
        ).fetchall()
        result = []
        for r in rows:
            emb_json = r["embedding"]
            if emb_json:
                emb = np.array(json.loads(emb_json), dtype=np.float32)
                full_name = f"{r['last_name']} {r['first_name']}"
                if r["middle_name"]:
                    full_name += f" {r['middle_name']}"
                result.append({
                    "id": r["id"],
                    "full_name": full_name,
                    "gender": r["gender"],
                    "seat_number": r["sp_n"],
                    "embedding": emb,
                })
        return result

    def mark_student_entered(self, student_id: int):
        self._conn.execute(
            "UPDATE student SET is_entered=1 WHERE id=?",
            (student_id,),
        )
        self._conn.commit()

    def get_entered_count(self, session_sm_id: int) -> dict:
        row = self._conn.execute(
            """SELECT
                 COUNT(*) as total,
                 SUM(CASE WHEN gender=1 THEN 1 ELSE 0 END) as male,
                 SUM(CASE WHEN gender=2 THEN 1 ELSE 0 END) as female
               FROM student WHERE session_sm_id=? AND is_entered=1""",
            (session_sm_id,),
        ).fetchone()
        return {"total": row["total"], "male": row["male"], "female": row["female"]}

    # ── Entry Log ──
    def add_entry_log(self, student_id: int, staff_id: int,
                      score: int = 0, is_sent: bool = False) -> int:
        now = datetime.now().isoformat()
        cur = self._conn.execute(
            """INSERT INTO entry_log
               (student_id, first_captured, last_captured, first_enter_time, last_enter_time,
                staff_id, score, max_score, is_sent, ip_address, mac_address)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (student_id, now, now, now, now, staff_id, score, score,
             int(is_sent), self._ip_address, self._mac_address),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_unsent_entries(self) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM entry_log WHERE is_sent=0"
        ).fetchall()

    def mark_entry_sent(self, entry_id: int):
        self._conn.execute(
            "UPDATE entry_log SET is_sent=1, sent_at=? WHERE id=?",
            (datetime.now().isoformat(), entry_id),
        )
        self._conn.commit()

    def increment_retry(self, entry_id: int):
        self._conn.execute(
            "UPDATE entry_log SET retry_count=retry_count+1 WHERE id=?",
            (entry_id,),
        )
        self._conn.commit()

    def clear_all_data(self):
        self._conn.execute("DELETE FROM entry_log")
        self._conn.execute("DELETE FROM student")
        self._conn.execute("DELETE FROM test_session_sm")
        self._conn.execute("DELETE FROM test_session")
        self._conn.commit()

    def close(self):
        self._conn.close()
