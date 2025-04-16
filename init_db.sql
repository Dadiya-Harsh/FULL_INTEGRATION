-- Connect to PostgreSQL as postgres user
-- Run: psql -U postgres -h 192.168.10.74 -p 5433

-- Create database if not exists
CREATE DATABASE test2;

-- Connect to test2 database
\c test2

-- Ensure public schema exists
CREATE SCHEMA IF NOT EXISTS public;
GRANT ALL ON SCHEMA public TO public;

-- Create role-based users
DO $$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'employee_role') THEN
      CREATE ROLE employee_role WITH LOGIN PASSWORD 'pass';
   END IF;
   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'manager_role') THEN
      CREATE ROLE manager_role WITH LOGIN PASSWORD 'pass';
   END IF;
   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'hr_role') THEN
      CREATE ROLE hr_role WITH LOGIN PASSWORD 'pass';
   END IF;
   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'sudo_role') THEN
      CREATE ROLE sudo_role WITH LOGIN PASSWORD 'pass';
   END IF;
END $$;

-- Grant schema privileges
GRANT USAGE, CREATE ON SCHEMA public TO employee_role, manager_role, hr_role, sudo_role;

-- Create tables
CREATE TABLE IF NOT EXISTS employee (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL UNIQUE,
    email VARCHAR,
    phone VARCHAR,
    status VARCHAR,
    role VARCHAR
);

CREATE TABLE IF NOT EXISTS meeting (
    id VARCHAR PRIMARY KEY,
    title VARCHAR,
    created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS meeting_transcript (
    id SERIAL PRIMARY KEY,
    meeting_id VARCHAR NOT NULL REFERENCES meeting(id) ON DELETE CASCADE,
    name VARCHAR NOT NULL,
    text TEXT,
    processed BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS rolling_sentiment (
    id SERIAL PRIMARY KEY,
    meeting_id VARCHAR NOT NULL REFERENCES meeting(id) ON DELETE CASCADE,
    name VARCHAR NOT NULL,
    role VARCHAR,
    rolling_sentiment JSONB,
    CONSTRAINT _unique_meeting_person UNIQUE (meeting_id, name)
);

CREATE TABLE IF NOT EXISTS employee_skills (
    id SERIAL PRIMARY KEY,
    meeting_id VARCHAR NOT NULL REFERENCES meeting(id) ON DELETE CASCADE,
    overall_sentiment_score FLOAT,
    role VARCHAR,
    employee_name VARCHAR
);

CREATE TABLE IF NOT EXISTS skill_recommendation (
    id SERIAL PRIMARY KEY,
    meeting_id VARCHAR NOT NULL REFERENCES meeting(id) ON DELETE CASCADE,
    skill_recommendation VARCHAR,
    name VARCHAR
);

CREATE TABLE IF NOT EXISTS task_recommendation (
    id SERIAL PRIMARY KEY,
    meeting_id VARCHAR NOT NULL REFERENCES meeting(id) ON DELETE CASCADE,
    task VARCHAR,
    assigned_by VARCHAR,
    assigned_to VARCHAR,
    deadline VARCHAR,
    status VARCHAR
);

-- Grant table privileges
GRANT SELECT, INSERT ON employee, meeting, meeting_transcript, rolling_sentiment, employee_skills, skill_recommendation, task_recommendation TO employee;
GRANT SELECT, INSERT, UPDATE, DELETE ON meeting_transcript, employee_skills, task_recommendation TO manager;
GRANT SELECT ON employee, meeting, meeting_transcript, rolling_sentiment, employee_skills, skill_recommendation, task_recommendation TO hr;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO sudo_role;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO sudo_role;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO sudo_role;

-- Enable Row-Level Security
ALTER TABLE employee_skills ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_recommendation ENABLE ROW LEVEL SECURITY;
ALTER TABLE meeting_transcript ENABLE ROW LEVEL SECURITY;

ALTER TABLE employee_skills FORCE ROW LEVEL SECURITY;
ALTER TABLE task_recommendation FORCE ROW LEVEL SECURITY;
ALTER TABLE meeting_transcript FORCE ROW LEVEL SECURITY;

-- Drop existing policies
DROP POLICY IF EXISTS own_skills_policy ON employee_skills;
DROP POLICY IF EXISTS insert_skills_policy ON employee_skills;
DROP POLICY IF EXISTS all_skills_for_hr ON employee_skills;
DROP POLICY IF EXISTS all_skills_for_manager ON employee_skills;

DROP POLICY IF EXISTS own_tasks_policy ON task_recommendation;
DROP POLICY IF EXISTS insert_tasks_policy ON task_recommendation;
DROP POLICY IF EXISTS all_tasks_for_hr ON task_recommendation;
DROP POLICY IF EXISTS all_tasks_for_manager ON task_recommendation;

DROP POLICY IF EXISTS own_transcript_policy ON meeting_transcript;
DROP POLICY IF EXISTS insert_transcript_policy ON meeting_transcript;
DROP POLICY IF EXISTS all_transcript_for_hr ON meeting_transcript;
DROP POLICY IF EXISTS all_transcript_for_manager ON meeting_transcript;

-- Create RLS policies (EMPLOYEE - can only access own data)
CREATE POLICY own_skills_policy ON employee_skills
    FOR SELECT
    TO employee_role
    USING (employee_name = current_setting('app.current_name'));

CREATE POLICY insert_skills_policy ON employee_skills
    FOR INSERT
    TO employee_role
    WITH CHECK (employee_name = current_setting('app.current_name'));

CREATE POLICY own_tasks_policy ON task_recommendation
    FOR SELECT
    TO employee_role
    USING (assigned_to = current_setting('app.current_name'));

CREATE POLICY insert_tasks_policy ON task_recommendation
    FOR INSERT
    TO employee_role
    WITH CHECK (assigned_to = current_setting('app.current_name'));

CREATE POLICY own_transcript_policy ON meeting_transcript
    FOR SELECT
    TO employee_role
    USING (name = current_setting('app.current_name'));

CREATE POLICY insert_transcript_policy ON meeting_transcript
    FOR INSERT
    TO employee_role
    WITH CHECK (name = current_setting('app.current_name'));

-- Create RLS policies (HR & MANAGER - can see all rows)
CREATE POLICY all_skills_for_hr ON employee_skills
    FOR SELECT
    TO hr_role
    USING (true);

CREATE POLICY all_skills_for_manager ON employee_skills
    FOR SELECT
    TO manager_role
    USING (true);

CREATE POLICY all_tasks_for_hr ON task_recommendation
    FOR SELECT
    TO hr_role
    USING (true);

CREATE POLICY all_tasks_for_manager ON task_recommendation
    FOR SELECT
    TO manager_role
    USING (true);

CREATE POLICY all_transcript_for_hr ON meeting_transcript
    FOR SELECT
    TO hr_role
    USING (true);

CREATE POLICY all_transcript_for_manager ON meeting_transcript
    FOR SELECT
    TO manager_role
    USING (true);

-- Insert sample data
INSERT INTO employee (name, email, role, status, phone)
VALUES
    ('John Doe', 'john.doe@example.com', 'employee', 'active', '123-456-7890'),
    ('Jane Manager', 'jane.manager@example.com', 'manager', 'active', '123-456-7891'),
    ('HR User', 'hr.user@example.com', 'hr', 'active', '123-456-7892')
ON CONFLICT (name) DO NOTHING;

INSERT INTO meeting (id, title, created_at)
VALUES ('meeting1', 'Team Sync', CURRENT_TIMESTAMP)
ON CONFLICT (id) DO NOTHING;

INSERT INTO meeting_transcript (meeting_id, name, text, processed)
VALUES ('meeting1', 'John Doe', 'Discussed project updates.', TRUE)
ON CONFLICT DO NOTHING;

INSERT INTO rolling_sentiment (meeting_id, name, role, rolling_sentiment)
VALUES ('meeting1', 'John Doe', 'employee', '{"positive": 0.8, "negative": 0.1, "neutral": 0.1}'::jsonb)
ON CONFLICT ON CONSTRAINT _unique_meeting_person DO NOTHING;

INSERT INTO employee_skills (meeting_id, overall_sentiment_score, role, employee_name)
VALUES ('meeting1', 0.85, 'employee', 'John Doe')
ON CONFLICT DO NOTHING;

INSERT INTO skill_recommendation (meeting_id, skill_recommendation, name)
VALUES ('meeting1', 'Improve communication skills', 'John Doe')
ON CONFLICT DO NOTHING;

INSERT INTO task_recommendation (meeting_id, task, assigned_by, assigned_to, deadline, status)
VALUES ('meeting1', 'Prepare presentation', 'Jane Manager', 'John Doe', '2025-04-30', 'pending')
ON CONFLICT DO NOTHING;
