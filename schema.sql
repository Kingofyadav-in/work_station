-- kingofyadav.in — Full PostgreSQL Schema
-- Run: psql $DATABASE_URL -f schema.sql

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─────────────────────────────────────────
-- IDENTITY
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS identity (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name        VARCHAR(100) NOT NULL,
  tagline     TEXT,
  roles       JSONB        DEFAULT '[]',
  mission     TEXT,
  location    VARCHAR(100),
  hdi_code    VARCHAR(50)  UNIQUE,
  created_at  TIMESTAMPTZ  DEFAULT NOW(),
  updated_at  TIMESTAMPTZ  DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- PERSONAL — Habits
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS habits (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  title       VARCHAR(200) NOT NULL,
  description TEXT,
  frequency   VARCHAR(20)  DEFAULT 'daily',
  active      BOOLEAN      DEFAULT TRUE,
  created_at  TIMESTAMPTZ  DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS habit_logs (
  id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  habit_id     UUID REFERENCES habits(id) ON DELETE CASCADE,
  completed_on DATE        NOT NULL DEFAULT CURRENT_DATE,
  note         TEXT,
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (habit_id, completed_on)
);

-- ─────────────────────────────────────────
-- PERSONAL — Goals
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS goals (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  title       VARCHAR(200) NOT NULL,
  body        TEXT,
  progress    INT          DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
  deadline    DATE,
  status      VARCHAR(20)  DEFAULT 'active',
  created_at  TIMESTAMPTZ  DEFAULT NOW(),
  updated_at  TIMESTAMPTZ  DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- PERSONAL — Notes
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notes (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  title       VARCHAR(200),
  body        TEXT         NOT NULL,
  tags        JSONB        DEFAULT '[]',
  created_at  TIMESTAMPTZ  DEFAULT NOW(),
  updated_at  TIMESTAMPTZ  DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- PERSONAL — Mood / Energy Logs
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS mood_logs (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  logged_on   DATE        NOT NULL DEFAULT CURRENT_DATE UNIQUE,
  mood        INT         CHECK (mood   >= 1 AND mood   <= 10),
  energy      INT         CHECK (energy >= 1 AND energy <= 10),
  note        TEXT,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- PROFESSIONAL — Projects
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS projects (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  title       VARCHAR(200) NOT NULL,
  description TEXT,
  priority    INT          DEFAULT 3 CHECK (priority >= 1 AND priority <= 5),
  status      VARCHAR(20)  DEFAULT 'active',
  deadline    DATE,
  created_at  TIMESTAMPTZ  DEFAULT NOW(),
  updated_at  TIMESTAMPTZ  DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS project_tasks (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  project_id  UUID REFERENCES projects(id) ON DELETE CASCADE,
  title       VARCHAR(200) NOT NULL,
  done        BOOLEAN      DEFAULT FALSE,
  due_date    DATE,
  created_at  TIMESTAMPTZ  DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- PROFESSIONAL — General Tasks
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tasks (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  title       VARCHAR(200) NOT NULL,
  category    VARCHAR(50),
  done        BOOLEAN      DEFAULT FALSE,
  due_date    DATE,
  created_at  TIMESTAMPTZ  DEFAULT NOW(),
  updated_at  TIMESTAMPTZ  DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- SOCIAL — Contacts
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS contacts (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name            VARCHAR(100) NOT NULL,
  email           VARCHAR(200),
  phone           VARCHAR(30),
  whatsapp        VARCHAR(30),
  company         VARCHAR(100),
  relationship    VARCHAR(50),
  birthday        DATE,
  note            TEXT,
  follow_up_date  DATE,
  created_at      TIMESTAMPTZ  DEFAULT NOW(),
  updated_at      TIMESTAMPTZ  DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- SOCIAL — Events / Calendar
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS events (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  title           VARCHAR(200) NOT NULL,
  description     TEXT,
  event_date      DATE         NOT NULL,
  event_time      TIME,
  event_type      VARCHAR(50)  DEFAULT 'Meeting',
  follow_up_date  DATE,
  contact_id      UUID REFERENCES contacts(id) ON DELETE SET NULL,
  created_at      TIMESTAMPTZ  DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- JARVIS — AI Chat History
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS chat_sessions (
  id          VARCHAR(20)  PRIMARY KEY,  -- "session-YYYY-MM-DD"
  messages    JSONB        NOT NULL DEFAULT '[]',
  created_at  TIMESTAMPTZ  DEFAULT NOW(),
  updated_at  TIMESTAMPTZ  DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- HDI — Licenses / Certificates
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS hdi_licenses (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  claim_id      VARCHAR(100) UNIQUE NOT NULL,
  content_hash  VARCHAR(200) NOT NULL,
  claim_date    TIMESTAMPTZ  DEFAULT NOW(),
  status        VARCHAR(20)  DEFAULT 'active',
  metadata      JSONB        DEFAULT '{}'
);

-- ─────────────────────────────────────────
-- LIVE CLASSROOM
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS live_class_sessions (
  id          VARCHAR(50)  PRIMARY KEY,
  title       VARCHAR(200),
  subtitle    TEXT,
  theme       VARCHAR(20)  DEFAULT 'blackboard',
  status      VARCHAR(20)  DEFAULT 'active',
  teacher     VARCHAR(100),
  focus_id    VARCHAR(50),
  revision    INT          DEFAULT 0,
  created_at  TIMESTAMPTZ  DEFAULT NOW(),
  updated_at  TIMESTAMPTZ  DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS live_class_blocks (
  id          VARCHAR(50)  PRIMARY KEY,
  session_id  VARCHAR(50)  REFERENCES live_class_sessions(id) ON DELETE CASCADE,
  type        VARCHAR(20)  NOT NULL,
  content     TEXT,
  language    VARCHAR(30),
  url         VARCHAR(500),
  caption     TEXT,
  position    INT,
  created_at  TIMESTAMPTZ  DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS live_class_viewers (
  id          VARCHAR(50)  NOT NULL,
  session_id  VARCHAR(50)  REFERENCES live_class_sessions(id) ON DELETE CASCADE,
  name        VARCHAR(100),
  device      VARCHAR(50),
  ip          VARCHAR(45),
  joined_at   TIMESTAMPTZ  DEFAULT NOW(),
  last_seen   TIMESTAMPTZ  DEFAULT NOW(),
  PRIMARY KEY (id, session_id)
);

-- ─────────────────────────────────────────
-- BLOG — Posts
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS blog_posts (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  title         VARCHAR(300) NOT NULL,
  slug          VARCHAR(200) UNIQUE NOT NULL,
  category      VARCHAR(50),
  excerpt       TEXT,
  content       TEXT,
  image_url     VARCHAR(500),
  published_at  DATE,
  status        VARCHAR(20)  DEFAULT 'published',
  created_at    TIMESTAMPTZ  DEFAULT NOW(),
  updated_at    TIMESTAMPTZ  DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- CONTACT FORM — Submissions
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS contact_submissions (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name          VARCHAR(100) NOT NULL,
  email         VARCHAR(200) NOT NULL,
  subject       VARCHAR(200),
  message       TEXT         NOT NULL,
  status        VARCHAR(20)  DEFAULT 'new',
  submitted_at  TIMESTAMPTZ  DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- INDEXES
-- ─────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_habit_logs_date       ON habit_logs(completed_on);
CREATE INDEX IF NOT EXISTS idx_habit_logs_habit      ON habit_logs(habit_id);
CREATE INDEX IF NOT EXISTS idx_goals_status          ON goals(status);
CREATE INDEX IF NOT EXISTS idx_goals_deadline        ON goals(deadline);
CREATE INDEX IF NOT EXISTS idx_tasks_done            ON tasks(done);
CREATE INDEX IF NOT EXISTS idx_tasks_due             ON tasks(due_date);
CREATE INDEX IF NOT EXISTS idx_project_tasks_project ON project_tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_events_date           ON events(event_date);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_id      ON chat_sessions(id);
CREATE INDEX IF NOT EXISTS idx_blog_posts_slug       ON blog_posts(slug);
CREATE INDEX IF NOT EXISTS idx_blog_posts_status     ON blog_posts(status, published_at);
CREATE INDEX IF NOT EXISTS idx_contact_sub_status    ON contact_submissions(status);

-- ─────────────────────────────────────────
-- AUTO updated_at TRIGGER
-- ─────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_identity_updated        BEFORE UPDATE ON identity             FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE OR REPLACE TRIGGER trg_goals_updated           BEFORE UPDATE ON goals                FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE OR REPLACE TRIGGER trg_notes_updated           BEFORE UPDATE ON notes                FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE OR REPLACE TRIGGER trg_projects_updated        BEFORE UPDATE ON projects             FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE OR REPLACE TRIGGER trg_tasks_updated           BEFORE UPDATE ON tasks                FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE OR REPLACE TRIGGER trg_contacts_updated        BEFORE UPDATE ON contacts             FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE OR REPLACE TRIGGER trg_chat_sessions_updated   BEFORE UPDATE ON chat_sessions        FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE OR REPLACE TRIGGER trg_live_class_updated      BEFORE UPDATE ON live_class_sessions  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE OR REPLACE TRIGGER trg_blog_posts_updated      BEFORE UPDATE ON blog_posts           FOR EACH ROW EXECUTE FUNCTION update_updated_at();
