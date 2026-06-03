-- ============================================================
-- init.sql – Initiale Datenbankstruktur
-- Wird beim ersten Start von PostgreSQL automatisch ausgeführt.
-- ============================================================

-- Tabelle für erfasste Störungen
CREATE TABLE IF NOT EXISTS incidents (
    id          SERIAL PRIMARY KEY,
    title       VARCHAR(255) NOT NULL,
    description TEXT,
    service     VARCHAR(100),
    status      VARCHAR(50)  NOT NULL DEFAULT 'open',  -- open | resolved
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

-- Beispieldaten zum Testen
INSERT INTO incidents (title, description, service, status)
VALUES
    ('Webserver nicht erreichbar', 'Der Nginx antwortet nicht mehr auf Port 80.', 'nginx', 'resolved'),
    ('Datenbankverbindung unterbrochen', 'PostgreSQL meldet zu viele Verbindungen.', 'postgres', 'open');
