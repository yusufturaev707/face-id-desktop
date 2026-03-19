SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    zone_id INTEGER NOT NULL,
    zone_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS test_session (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hash_key TEXT NOT NULL UNIQUE,
    test TEXT NOT NULL,
    start_date TEXT NOT NULL,
    finish_date TEXT NOT NULL,
    zone_name TEXT NOT NULL,
    total_students INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    is_loaded INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS test_session_sm (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    test_day TEXT NOT NULL,
    sm INTEGER DEFAULT 0,
    count_st INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES test_session(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS student (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_sm_id INTEGER NOT NULL,
    zone_id INTEGER NOT NULL,
    last_name TEXT NOT NULL,
    first_name TEXT NOT NULL,
    middle_name TEXT,
    imei TEXT NOT NULL,
    gr_n INTEGER DEFAULT 0,
    sp_n INTEGER DEFAULT 0,
    gender INTEGER DEFAULT 0,
    subject_id INTEGER DEFAULT 0,
    subject_name TEXT NOT NULL,
    is_ready INTEGER DEFAULT 0,
    is_face INTEGER DEFAULT 0,
    is_image INTEGER DEFAULT 0,
    is_cheating INTEGER DEFAULT 0,
    is_blacklist INTEGER DEFAULT 0,
    is_entered INTEGER DEFAULT 0,
    ps_img TEXT,
    embedding TEXT,
    FOREIGN KEY (session_sm_id) REFERENCES test_session_sm(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS entry_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    first_captured TEXT,
    last_captured TEXT,
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
    FOREIGN KEY (student_id) REFERENCES student(id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(id) ON DELETE SET NULL
);
"""
