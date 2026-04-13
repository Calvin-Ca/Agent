-- Executed automatically by MySQL container on first start
-- Sets character encoding and creates application database

ALTER DATABASE caic
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

-- Grant full privileges to application user
GRANT ALL PRIVILEGES ON caic.* TO 'caic'@'%';
FLUSH PRIVILEGES;
