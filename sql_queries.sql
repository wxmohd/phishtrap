-- PhishTrap Database Queries
-- Use with: sqlite3 database/phishtrap.db < sql_queries.sql

-- ============================================
-- SCHEMA INSPECTION
-- ============================================

.mode column
.headers on
.width 20 10 10 10

-- Show all tables
.print "\n=== TABLES ==="
.tables

-- Show emails table schema
.print "\n=== EMAILS SCHEMA ==="
PRAGMA table_info(emails);

-- Show links table schema
.print "\n=== LINKS SCHEMA ==="
PRAGMA table_info(links);

-- Show connected_users table schema
.print "\n=== CONNECTED_USERS SCHEMA ==="
PRAGMA table_info(connected_users);

-- ============================================
-- SUMMARY STATISTICS
-- ============================================

.print "\n=== SUMMARY STATISTICS ==="

SELECT 
    'Total Emails' as metric,
    COUNT(*) as count
FROM emails
UNION ALL
SELECT 
    'Total Links',
    COUNT(*)
FROM links
UNION ALL
SELECT 
    'Connected Users',
    COUNT(*)
FROM connected_users
UNION ALL
SELECT 
    'Active Users',
    COUNT(*)
FROM connected_users
WHERE revoked_at IS NULL;

-- ============================================
-- CLASSIFICATION BREAKDOWN
-- ============================================

.print "\n=== CLASSIFICATION BREAKDOWN ==="

SELECT 
    COALESCE(ai_label, 'unclassified') as label,
    COUNT(*) as count,
    ROUND(AVG(ai_score) / 100.0, 3) as avg_score,
    MIN(ai_score) / 100.0 as min_score,
    MAX(ai_score) / 100.0 as max_score
FROM emails
GROUP BY ai_label
ORDER BY count DESC;

-- ============================================
-- RECENT EMAILS
-- ============================================

.print "\n=== RECENT EMAILS (Last 10) ==="
.width 20 30 25 12 8 40

SELECT 
    datetime(received_at) as received,
    sender,
    SUBSTR(subject, 1, 25) as subject,
    ai_label,
    ROUND(ai_score / 100.0, 2) as score,
    SUBSTR(ai_explanation, 1, 40) as explanation
FROM emails
ORDER BY received_at DESC
LIMIT 10;

-- ============================================
-- PHISHING EMAILS
-- ============================================

.print "\n=== PHISHING EMAILS ==="
.width 20 30 30 8 50

SELECT 
    datetime(received_at) as received,
    sender,
    SUBSTR(subject, 1, 30) as subject,
    ROUND(ai_score / 100.0, 2) as score,
    SUBSTR(ai_explanation, 1, 50) as explanation
FROM emails
WHERE ai_label = 'phishing'
ORDER BY ai_score DESC, received_at DESC
LIMIT 10;

-- ============================================
-- SUSPICIOUS EMAILS
-- ============================================

.print "\n=== SUSPICIOUS EMAILS ==="

SELECT 
    datetime(received_at) as received,
    sender,
    SUBSTR(subject, 1, 30) as subject,
    ROUND(ai_score / 100.0, 2) as score,
    SUBSTR(ai_explanation, 1, 50) as explanation
FROM emails
WHERE ai_label = 'suspicious'
ORDER BY ai_score DESC, received_at DESC
LIMIT 10;

-- ============================================
-- LINKS ANALYSIS
-- ============================================

.print "\n=== LINKS BY STATUS ==="
.width 15 10

SELECT 
    COALESCE(status, 'unknown') as status,
    COUNT(*) as count
FROM links
GROUP BY status
ORDER BY count DESC;

.print "\n=== RECENT LINKS ==="
.width 20 50 12 10

SELECT 
    datetime(l.fetched_at) as fetched,
    SUBSTR(l.url, 1, 50) as url,
    l.status,
    e.ai_label
FROM links l
JOIN emails e ON l.email_id = e.id
ORDER BY l.fetched_at DESC
LIMIT 10;

-- ============================================
-- TOP SENDERS
-- ============================================

.print "\n=== TOP SENDERS ==="
.width 30 10 15

SELECT 
    sender,
    COUNT(*) as email_count,
    GROUP_CONCAT(DISTINCT ai_label) as labels
FROM emails
GROUP BY sender
ORDER BY email_count DESC
LIMIT 10;

-- ============================================
-- CONNECTED USERS
-- ============================================

.print "\n=== CONNECTED USERS ==="
.width 30 10 20 20 10

SELECT 
    email,
    provider,
    datetime(connected_at) as connected,
    datetime(revoked_at) as revoked,
    CASE WHEN revoked_at IS NULL THEN 'Active' ELSE 'Revoked' END as status
FROM connected_users
ORDER BY connected_at DESC;

-- ============================================
-- DAILY EMAIL COUNTS
-- ============================================

.print "\n=== DAILY EMAIL COUNTS ==="
.width 12 10 10 10 10

SELECT 
    DATE(received_at) as date,
    COUNT(*) as total,
    SUM(CASE WHEN ai_label = 'phishing' THEN 1 ELSE 0 END) as phishing,
    SUM(CASE WHEN ai_label = 'suspicious' THEN 1 ELSE 0 END) as suspicious,
    SUM(CASE WHEN ai_label = 'legit' THEN 1 ELSE 0 END) as legit
FROM emails
GROUP BY DATE(received_at)
ORDER BY date DESC
LIMIT 7;

-- ============================================
-- EMAILS WITH MOST LINKS
-- ============================================

.print "\n=== EMAILS WITH MOST LINKS ==="
.width 30 30 12 10

SELECT 
    e.sender,
    SUBSTR(e.subject, 1, 30) as subject,
    e.ai_label,
    COUNT(l.id) as link_count
FROM emails e
LEFT JOIN links l ON e.id = l.email_id
GROUP BY e.id
HAVING link_count > 0
ORDER BY link_count DESC
LIMIT 10;

-- ============================================
-- CLEANUP QUERIES (commented out for safety)
-- ============================================

-- To delete all emails:
-- DELETE FROM emails;

-- To delete all links:
-- DELETE FROM links;

-- To revoke all users:
-- UPDATE connected_users SET revoked_at = datetime('now') WHERE revoked_at IS NULL;

-- To delete all connected users:
-- DELETE FROM connected_users;

-- To reset database (delete all data):
-- DELETE FROM emails;
-- DELETE FROM links;
-- DELETE FROM connected_users;
-- VACUUM;

.print "\n=== END OF REPORT ===\n"
