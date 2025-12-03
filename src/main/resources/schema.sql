CREATE TABLE IF NOT EXISTS group_message (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  group_id INTEGER NOT NULL,
  sender_qq INTEGER NOT NULL,
  sender_nickname TEXT,
  content TEXT,
  send_time TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_group_message_group_id ON group_message(group_id);
CREATE INDEX IF NOT EXISTS idx_group_message_send_time ON group_message(send_time);
