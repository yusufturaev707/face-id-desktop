import json
import logging
import socket
import sqlite3
import uuid
from datetime import datetime
from typing import Optional

import numpy as np

from config import DB_PATH
from database.models import SCHEMA_SQL
from utils.singleton import SingletonMeta

log = logging.getLogger(__name__)

EMBEDDING_DIM = 512
EMBEDDING_BYTES = EMBEDDING_DIM * 4  # float32


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
    try:
        import subprocess
        out = subprocess.check_output("getmac /fo csv /nh", shell=True, text=True)
        first_line = out.strip().splitlines()[0]
        mac = first_line.split(",")[0].strip('"')
        if mac and mac != "N/A":
            return mac
    except Exception:
        pass
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
        self._migrate()
        self._conn.commit()

    def _migrate(self):
        """Mavjud jadvalga yangi ustunlar qo'shish / eski ustunlarni tozalash."""
        # embedding TEXT → BLOB migration
        cur = self._conn.execute("PRAGMA table_info(student)")
        cols = {row[1]: row[2] for row in cur.fetchall()}
        if cols.get("embedding", "").upper() == "TEXT":
            rows = self._conn.execute(
                "SELECT id, embedding FROM student WHERE embedding IS NOT NULL"
            ).fetchall()
            self._conn.execute("ALTER TABLE student RENAME COLUMN embedding TO embedding_old")
            self._conn.execute("ALTER TABLE student ADD COLUMN embedding BLOB")
            for r in rows:
                try:
                    arr = np.array(json.loads(r["embedding_old"]), dtype=np.float32)
                    self._conn.execute(
                        "UPDATE student SET embedding=? WHERE id=?",
                        (arr.tobytes(), r["id"]),
                    )
                except (json.JSONDecodeError, ValueError):
                    pass
            cols["embedding_old"] = "TEXT"

        # eski embedding_old ustunini tozalash
        if "embedding_old" in cols:
            try:
                self._conn.execute("ALTER TABLE student DROP COLUMN embedding_old")
            except sqlite3.OperationalError:
                pass
            self._conn.commit()

        # student.reject_reason_id / rejected_at ustunlari yo'q bo'lsa — qo'shish
        cur = self._conn.execute("PRAGMA table_info(student)")
        cols2 = {row[1] for row in cur.fetchall()}
        if "reject_reason_id" not in cols2:
            try:
                self._conn.execute("ALTER TABLE student ADD COLUMN reject_reason_id INTEGER")
                self._conn.commit()
            except sqlite3.OperationalError:
                pass
        if "rejected_at" not in cols2:
            try:
                self._conn.execute("ALTER TABLE student ADD COLUMN rejected_at TEXT")
                self._conn.commit()
            except sqlite3.OperationalError:
                pass

        # student_id ustunini API id bilan to'ldirish (eski yozuvlarda 0/NULL qolgan bo'lsa,
        # lekin id=API id bo'lgan legacy ma'lumotlar uchun — migration xavfsiz)
        try:
            self._conn.execute(
                "UPDATE student SET student_id = id "
                "WHERE student_id IS NULL OR student_id = 0"
            )
            self._conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_student_student_id_unique "
                "ON student(student_id)"
            )
            self._conn.commit()
        except sqlite3.OperationalError:
            pass

        # entry_log jadvalida student_id → student.id ga FK bor bo'lsa (eski DB), uni
        # olib tashlash uchun jadvalni FK'siz qayta yaratamiz. SQLite ALTER orqali
        # FK ni o'zgartirib bo'lmaydi — jadvalni recreate qilish kerak.
        try:
            fks = self._conn.execute("PRAGMA foreign_key_list(entry_log)").fetchall()
            has_student_fk = any(fk[2] == "student" for fk in fks)
            if has_student_fk:
                self._conn.execute("PRAGMA foreign_keys=OFF")
                self._conn.executescript("""
                    CREATE TABLE entry_log_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id BIGINT NOT NULL,
                        first_captured BLOB,
                        last_captured BLOB,
                        first_enter_time TEXT DEFAULT (datetime('now','localtime')),
                        last_enter_time TEXT,
                        staff_id INTEGER NOT NULL,
                        score INTEGER DEFAULT 0,
                        max_score INTEGER DEFAULT 0,
                        is_check_hand INTEGER DEFAULT 0,
                        is_sent INTEGER DEFAULT 0,
                        sent_at TEXT,
                        retry_count INTEGER DEFAULT 0,
                        ip_address TEXT,
                        mac_address TEXT,
                        FOREIGN KEY (staff_id) REFERENCES staff(id) ON DELETE SET NULL
                    );
                    INSERT INTO entry_log_new
                      SELECT id, student_id, first_captured, last_captured,
                             first_enter_time, last_enter_time, staff_id, score, max_score,
                             is_check_hand, is_sent, sent_at, retry_count, ip_address, mac_address
                      FROM entry_log;
                    DROP TABLE entry_log;
                    ALTER TABLE entry_log_new RENAME TO entry_log;
                    CREATE INDEX IF NOT EXISTS idx_entry_log_student_id ON entry_log(student_id);
                """)
                self._conn.execute("PRAGMA foreign_keys=ON")
                self._conn.commit()
        except sqlite3.OperationalError as e:
            log.warning("entry_log FK migration skipped: %s", e)

        # entry_log.is_rejected / reject_reason_id ustunlari yo'q bo'lsa — qo'shish
        try:
            cur = self._conn.execute("PRAGMA table_info(entry_log)")
            el_cols = {row[1] for row in cur.fetchall()}
            if "is_rejected" not in el_cols:
                self._conn.execute(
                    "ALTER TABLE entry_log ADD COLUMN is_rejected INTEGER DEFAULT 0"
                )
            if "reject_reason_id" not in el_cols:
                self._conn.execute(
                    "ALTER TABLE entry_log ADD COLUMN reject_reason_id INTEGER"
                )
            # Visit tracking ustunlari — first/last captured logikasi uchun
            if "first_visit_max" not in el_cols:
                self._conn.execute(
                    "ALTER TABLE entry_log ADD COLUMN first_visit_max INTEGER DEFAULT 0"
                )
            if "current_visit_max" not in el_cols:
                self._conn.execute(
                    "ALTER TABLE entry_log ADD COLUMN current_visit_max INTEGER DEFAULT 0"
                )
            if "first_visit_locked" not in el_cols:
                self._conn.execute(
                    "ALTER TABLE entry_log ADD COLUMN first_visit_locked INTEGER DEFAULT 0"
                )
            self._conn.commit()
        except sqlite3.OperationalError:
            pass

        # reason_type / reason jadvallarida eski TEXT key li seed ma'lumotlari bo'lsa —
        # backend bilan sinxronlashga tayyorlash uchun tozalash
        try:
            has_text = self._conn.execute(
                "SELECT 1 FROM reason_type WHERE typeof(key) = 'text' LIMIT 1"
            ).fetchone()
            if has_text:
                self._conn.execute("DELETE FROM reason")
                self._conn.execute("DELETE FROM reason_type")
                self._conn.commit()
        except sqlite3.OperationalError:
            pass

        # reason_type.is_active ustuni yo'q bo'lsa — qo'shish
        try:
            cur = self._conn.execute("PRAGMA table_info(reason_type)")
            rt_cols = {row[1] for row in cur.fetchall()}
            if "is_active" not in rt_cols:
                self._conn.execute("ALTER TABLE reason_type ADD COLUMN is_active INTEGER DEFAULT 1")
            cur = self._conn.execute("PRAGMA table_info(reason)")
            r_cols = {row[1] for row in cur.fetchall()}
            if "is_active" not in r_cols:
                self._conn.execute("ALTER TABLE reason ADD COLUMN is_active INTEGER DEFAULT 1")
            self._conn.commit()
        except sqlite3.OperationalError:
            pass

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
        """API'dan kelgan studentlarni saqlash.
        `student_id` = API id (UNIQUE). `id` = local autoincrement PK."""
        self._conn.executemany(
            """INSERT INTO student
               (student_id, session_sm_id, zone_id, last_name, first_name, middle_name,
                imei, gr_n, sp_n, gender, subject_id, subject_name,
                is_ready, is_face, is_image, is_cheating, is_blacklist,
                is_entered, ps_img, embedding)
               VALUES (:student_id, :session_sm_id, :zone_id, :last_name, :first_name, :middle_name,
                :imei, :gr_n, :sp_n, :gender, :subject_id, :subject_name,
                :is_ready, :is_face, :is_image, :is_cheating, :is_blacklist,
                :is_entered, :ps_img, :embedding)
               ON CONFLICT(student_id) DO UPDATE SET
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

    def get_smena_with_session(self, session_sm_id: int) -> Optional[sqlite3.Row]:
        return self._conn.execute(
            """SELECT sm.*, ts.test, ts.start_date, ts.zone_name, ts.total_students
               FROM test_session_sm sm
               JOIN test_session ts ON ts.id = sm.session_id
               WHERE sm.id=?""",
            (session_sm_id,),
        ).fetchone()

    def get_total_student_count(self, session_sm_id: int) -> dict:
        row = self._conn.execute(
            """SELECT
                 COUNT(*) as total,
                 SUM(CASE WHEN gender=1 THEN 1 ELSE 0 END) as male,
                 SUM(CASE WHEN gender=2 THEN 1 ELSE 0 END) as female
               FROM student WHERE session_sm_id=?""",
            (session_sm_id,),
        ).fetchone()
        return {"total": row["total"], "male": row["male"] or 0, "female": row["female"] or 0}

    def get_student(self, student_id: int) -> Optional[sqlite3.Row]:
        """student_id (API id) bo'yicha student topish."""
        return self._conn.execute(
            "SELECT * FROM student WHERE student_id=?", (student_id,)
        ).fetchone()

    def get_student_by_pinfl(self, pinfl: str, session_sm_id: int) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM student WHERE imei=? AND session_sm_id=?",
            (pinfl, session_sm_id),
        ).fetchall()

    def get_recently_entered(self, session_sm_id: int, limit: int = 10) -> list[sqlite3.Row]:
        return self._conn.execute(
            """SELECT s.*, e.last_captured AS face_img FROM student s
               JOIN entry_log e ON e.student_id = s.student_id
               WHERE s.session_sm_id=? AND s.is_entered=1
               ORDER BY e.first_enter_time DESC LIMIT ?""",
            (session_sm_id, limit),
        ).fetchall()

    def get_students_by_smena(self, session_sm_id: int) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM student WHERE session_sm_id=?", (session_sm_id,)
        ).fetchall()

    def load_embeddings_for_smena(self, session_sm_id: int) -> list[dict]:
        rows = self._conn.execute(
            "SELECT student_id, last_name, first_name, middle_name, gender, sp_n, embedding "
            "FROM student WHERE session_sm_id=? AND embedding IS NOT NULL",
            (session_sm_id,),
        ).fetchall()
        result = []
        skipped = 0
        for r in rows:
            emb_raw = r["embedding"]
            if not emb_raw:
                continue

            # BLOB emas — TEXT/JSON formatda qolgan eski ma'lumot bo'lishi mumkin
            if isinstance(emb_raw, str):
                try:
                    emb_raw = np.array(json.loads(emb_raw), dtype=np.float32).tobytes()
                except (json.JSONDecodeError, ValueError, TypeError):
                    log.warning("student id=%s: embedding TEXT format buzuq, skip", r["student_id"])
                    skipped += 1
                    continue

            if not isinstance(emb_raw, (bytes, bytearray, memoryview)):
                log.warning("student id=%s: embedding turi kutilmagan (%s), skip",
                            r["student_id"], type(emb_raw).__name__)
                skipped += 1
                continue

            if len(emb_raw) != EMBEDDING_BYTES:
                log.warning("student id=%s: embedding uzunligi %d (kutilgan %d), skip",
                            r["student_id"], len(emb_raw), EMBEDDING_BYTES)
                skipped += 1
                continue

            try:
                emb = np.frombuffer(emb_raw, dtype=np.float32).copy()
            except ValueError as e:
                log.warning("student id=%s: embedding decode xato (%s), skip", r["student_id"], e)
                skipped += 1
                continue

            full_name = f"{r['last_name']} {r['first_name']}"
            if r["middle_name"]:
                full_name += f" {r['middle_name']}"
            # "id" key API student_id'ni saqlaydi — downstream (camera_worker, entry_log, sync)
            # shu qiymatni student_id sifatida ishlatadi.
            result.append({
                "id": r["student_id"],
                "full_name": full_name,
                "gender": r["gender"],
                "seat_number": r["sp_n"],
                "embedding": emb,
            })

        log.info(
            "load_embeddings_for_smena(sm_id=%s): %d ta yuklandi, %d ta skip",
            session_sm_id, len(result), skipped,
        )
        return result

    def mark_student_entered(self, student_id: int):
        self._conn.execute(
            "UPDATE student SET is_entered=1 WHERE student_id=?",
            (student_id,),
        )
        self._conn.commit()

    def mark_student_cheating(self, student_id: int, reason_id: Optional[int] = None):
        now = datetime.now().isoformat()
        self._conn.execute(
            "UPDATE student SET is_cheating=1, reject_reason_id=?, rejected_at=? "
            "WHERE student_id=?",
            (reason_id, now, student_id),
        )
        self._conn.commit()

    # ── Reasons ──
    def get_reason_types(self) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT id, name, key, is_active FROM reason_type "
            "WHERE COALESCE(is_active, 1)=1 ORDER BY id"
        ).fetchall()

    def get_reasons_by_type(self, reason_type_id: int) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT id, reason_type_id, name, key, is_active FROM reason "
            "WHERE reason_type_id=? AND COALESCE(is_active, 1)=1 ORDER BY id",
            (reason_type_id,),
        ).fetchall()

    def upsert_reason_types(self, items: list[dict]) -> int:
        """Backend'dan kelgan reason_type'larni upsert qilish.
        Har bir item: {id, name, key, is_active}."""
        if not items:
            return 0
        self._conn.executemany(
            """INSERT INTO reason_type (id, name, key, is_active)
               VALUES (:id, :name, :key, :is_active)
               ON CONFLICT(id) DO UPDATE SET
                   name=excluded.name,
                   key=excluded.key,
                   is_active=excluded.is_active""",
            [
                {
                    "id": int(it["id"]),
                    "name": it.get("name") or "",
                    "key": int(it.get("key") or 0),
                    "is_active": 1 if it.get("is_active", True) else 0,
                }
                for it in items
            ],
        )
        self._conn.commit()
        return len(items)

    def upsert_reasons(self, items: list[dict]) -> int:
        """Backend'dan kelgan reason'larni upsert qilish.
        Har bir item: {id, reason_type_id, name, key, is_active}."""
        if not items:
            return 0
        self._conn.executemany(
            """INSERT INTO reason (id, reason_type_id, name, key, is_active)
               VALUES (:id, :reason_type_id, :name, :key, :is_active)
               ON CONFLICT(id) DO UPDATE SET
                   reason_type_id=excluded.reason_type_id,
                   name=excluded.name,
                   key=excluded.key,
                   is_active=excluded.is_active""",
            [
                {
                    "id": int(it["id"]),
                    "reason_type_id": int(it["reason_type_id"]) if it.get("reason_type_id") else None,
                    "name": it.get("name") or "",
                    "key": int(it.get("key") or 0),
                    "is_active": 1 if it.get("is_active", True) else 0,
                }
                for it in items
            ],
        )
        self._conn.commit()
        return len(items)

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
    @staticmethod
    def _normalize_face_img(val) -> Optional[bytes]:
        """Face crop rasm turini BLOB uchun normallashtirish.
        Qabul qiladi: bytes/memoryview (raw) yoki base64 str (legacy) yoki bo'sh qiymat."""
        if not val:
            return None
        if isinstance(val, (bytes, bytearray, memoryview)):
            return bytes(val)
        if isinstance(val, str):
            try:
                import base64
                if "," in val and val.index(",") < 80:
                    val = val.split(",", 1)[1]
                return base64.b64decode(val)
            except Exception:
                return None
        return None

    def get_entry_by_student(self, student_id: int) -> Optional[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM entry_log WHERE student_id=? ORDER BY id DESC LIMIT 1",
            (student_id,),
        ).fetchone()

    def get_entry_by_id(self, entry_id: int) -> Optional[sqlite3.Row]:
        return self._conn.execute(
            """SELECT e.*, s.imei AS imei
               FROM entry_log e
               LEFT JOIN student s ON s.student_id = e.student_id
               WHERE e.id=?""",
            (entry_id,),
        ).fetchone()

    def add_entry_log(self, student_id: int, staff_id: int,
                      score: int = 0, is_sent: bool = False,
                      face_img: Optional[bytes] = None,
                      is_rejected: bool = False,
                      reject_reason_id: Optional[int] = None) -> int:
        """Yangi entry_log yozuvi. face_img — crop qilingan yuz (raw JPEG bytes) yoki None.
        is_rejected=True bo'lsa, chetlatilgan student uchun yozuv.

        Boshlang'ich holatda first_visit va current_visit'ning max'i aynan shu
        birinchi frame bo'ladi. first_visit_locked=0 — student hali cameradan
        ketmagan, birinchi tashrif davom etmoqda."""
        now = datetime.now().isoformat()
        face_blob = self._normalize_face_img(face_img)
        cur = self._conn.execute(
            """INSERT INTO entry_log
               (student_id, first_captured, last_captured, first_enter_time, last_enter_time,
                staff_id, score, max_score, is_sent, ip_address, mac_address,
                is_rejected, reject_reason_id,
                first_visit_max, current_visit_max, first_visit_locked)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (student_id, face_blob, face_blob, now, now, staff_id, score, score,
             int(is_sent), self._ip_address, self._mac_address,
             int(is_rejected), reject_reason_id,
             score, score),
        )
        self._conn.commit()
        return cur.lastrowid

    def mark_entry_rejected(self, entry_id: int, reject_reason_id: int):
        """Mavjud entry_log yozuvini chetlatilgan deb belgilash va sync qayta tiklash."""
        self._conn.execute(
            """UPDATE entry_log SET
                   is_rejected=1, reject_reason_id=?,
                   is_sent=0, sent_at=NULL, retry_count=0
               WHERE id=?""",
            (reject_reason_id, entry_id),
        )
        self._conn.commit()

    def update_entry_log(self, entry_id: int, score: int = 0,
                         face_img: Optional[bytes] = None,
                         is_new_visit: bool = False):
        """Entry_log yozuvini yangilash.

        Semantika:
        - `first_captured` — student BIRINCHI tashrif davomida cameraga
          ko'ringan eng yaxshi (max_score) frame. Student cameradan chiqib
          ketgach (birinchi tashrif tugagach) LOCK bo'ladi — keyingi
          tashriflarda o'zgarmaydi.
        - `last_captured` — HAR safar joriy (eng so'nggi) tashrifdagi eng
          yaxshi (current_visit_max) frame. Yangi tashrif boshlanganda
          current_visit_max reset bo'ladi.

        `is_new_visit=True` — bu chaqiriq yangi tashrif boshlanishiga to'g'ri
        keldi (oldingi tashrifdan keyin vaqt oralig'i o'tgan). Bu holatda:
          * first_visit_locked=1 qilinadi (birinchi tashrif endi bloklanadi),
          * current_visit_max score'ga teng qilib reset qilinadi,
          * last_captured yangi frame bilan almashtiriladi.

        `is_new_visit=False` — joriy (davom etayotgan) tashrif ichida:
          * first_visit_locked=0 bo'lsa va score > first_visit_max:
            first_captured va first_visit_max yangilanadi.
          * score > current_visit_max: last_captured va current_visit_max
            yangilanadi.
        """
        now = datetime.now().isoformat()
        face_blob = self._normalize_face_img(face_img)

        if is_new_visit:
            if face_blob is not None:
                self._conn.execute(
                    """UPDATE entry_log SET
                           last_enter_time=?,
                           score=?,
                           max_score=MAX(max_score, ?),
                           first_visit_locked=1,
                           current_visit_max=?,
                           last_captured=?
                       WHERE id=?""",
                    (now, score, score, score, face_blob, entry_id),
                )
            else:
                self._conn.execute(
                    """UPDATE entry_log SET
                           last_enter_time=?,
                           score=?,
                           max_score=MAX(max_score, ?),
                           first_visit_locked=1,
                           current_visit_max=?
                       WHERE id=?""",
                    (now, score, score, score, entry_id),
                )
        else:
            if face_blob is not None:
                # Birinchi tashrif hali lock bo'lmagan va score yangi rekord
                # bo'lsa — first_captured'ni yangilaymiz. Har doim joriy tashrif
                # max'i bilan solishtirib last_captured'ni yangilaymiz.
                self._conn.execute(
                    """UPDATE entry_log SET
                           last_enter_time=?,
                           score=?,
                           max_score=MAX(max_score, ?),
                           first_captured = CASE
                               WHEN first_visit_locked=0 AND ? > first_visit_max
                               THEN ? ELSE first_captured END,
                           first_visit_max = CASE
                               WHEN first_visit_locked=0 AND ? > first_visit_max
                               THEN ? ELSE first_visit_max END,
                           last_captured = CASE
                               WHEN ? > current_visit_max
                               THEN ? ELSE last_captured END,
                           current_visit_max = CASE
                               WHEN ? > current_visit_max
                               THEN ? ELSE current_visit_max END
                       WHERE id=?""",
                    (now, score, score,
                     score, face_blob,
                     score, score,
                     score, face_blob,
                     score, score,
                     entry_id),
                )
            else:
                self._conn.execute(
                    """UPDATE entry_log SET
                           last_enter_time=?,
                           score=?,
                           max_score=MAX(max_score, ?),
                           first_visit_max = CASE
                               WHEN first_visit_locked=0 AND ? > first_visit_max
                               THEN ? ELSE first_visit_max END,
                           current_visit_max = CASE
                               WHEN ? > current_visit_max
                               THEN ? ELSE current_visit_max END
                       WHERE id=?""",
                    (now, score, score, score, score, score, score, entry_id),
                )
        self._conn.commit()

    def count_unsent_entries(self) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM entry_log WHERE is_sent=0"
        ).fetchone()
        return row[0] if row else 0

    def count_entries_stats(self) -> dict:
        """Shu kompyuterdagi entry_log statistikasi: total / verified / sent / unsent.

        `verified` — camera tomonidan yuz orqali muvaffaqiyatli tanildi
        (max_score > 0). JShShIR orqali qo'shilgan yoki chetlatilgan
        yozuvlarda max_score=0 bo'lishi mumkin."""
        row = self._conn.execute(
            """SELECT
                   COUNT(*) AS total,
                   SUM(CASE WHEN COALESCE(max_score,0) > 0 THEN 1 ELSE 0 END) AS verified,
                   SUM(CASE WHEN is_sent=1 THEN 1 ELSE 0 END) AS sent,
                   SUM(CASE WHEN is_sent=0 THEN 1 ELSE 0 END) AS unsent
               FROM entry_log"""
        ).fetchone()
        if not row:
            return {"total": 0, "verified": 0, "sent": 0, "unsent": 0}
        return {
            "total": row["total"] or 0,
            "verified": row["verified"] or 0,
            "sent": row["sent"] or 0,
            "unsent": row["unsent"] or 0,
        }

    def get_unsent_entries(self, limit: int = 50) -> list[sqlite3.Row]:
        """Yuborilmagan entry_log yozuvlari + student.imei (blacklist uchun).
        Retry limit yo'q — har qanday yozuv yuborilgunicha urinib ko'riladi.
        Kam retry'li (yangi) yozuvlar oldin yuboriladi."""
        return self._conn.execute(
            """SELECT e.*, s.imei AS imei
               FROM entry_log e
               LEFT JOIN student s ON s.student_id = e.student_id
               WHERE e.is_sent=0
               ORDER BY e.retry_count ASC, e.id ASC
               LIMIT ?""",
            (limit,),
        ).fetchall()

    def mark_entry_sent(self, entry_id: int):
        self._conn.execute(
            "UPDATE entry_log SET is_sent=1, sent_at=? WHERE id=?",
            (datetime.now().isoformat(), entry_id),
        )
        self._conn.commit()

    def mark_entry_unsent(self, entry_id: int):
        """Yozuvni qayta yuborish uchun sync bayroqlarini tiklash.
        Silent update'da last_captured yangilansa — backend'ga yangi rasm
        bilan qayta submit qilish kerak."""
        self._conn.execute(
            "UPDATE entry_log SET is_sent=0, sent_at=NULL WHERE id=?",
            (entry_id,),
        )
        self._conn.commit()

    def mark_entries_sent(self, entry_ids: list[int]):
        """Batch sync uchun — bir nechta yozuvni birdan sent deb belgilash."""
        if not entry_ids:
            return
        now = datetime.now().isoformat()
        self._conn.executemany(
            "UPDATE entry_log SET is_sent=1, sent_at=? WHERE id=?",
            [(now, eid) for eid in entry_ids],
        )
        self._conn.commit()

    def increment_retry(self, entry_id: int):
        self._conn.execute(
            "UPDATE entry_log SET retry_count=retry_count+1 WHERE id=?",
            (entry_id,),
        )
        self._conn.commit()

    def increment_retry_bulk(self, entry_ids: list[int]):
        if not entry_ids:
            return
        self._conn.executemany(
            "UPDATE entry_log SET retry_count=retry_count+1 WHERE id=?",
            [(eid,) for eid in entry_ids],
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
