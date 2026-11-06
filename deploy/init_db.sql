-- 迭代一：创建 mall_db 与同名账号（在 MariaDB 11.8 上实测通过）
-- 用法：mysql -u root -p < init_db.sql
-- 注意：脚本里的 'change-me' 与 backend/.env.example 中的占位密码一致，
--       仅用于本地开发；生产环境必须改成独立强密码，并同步 backend/.env。
CREATE DATABASE IF NOT EXISTS mall_db
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'mall'@'127.0.0.1' IDENTIFIED BY 'change-me';
CREATE USER IF NOT EXISTS 'mall'@'localhost' IDENTIFIED BY 'change-me';

GRANT ALL PRIVILEGES ON mall_db.* TO 'mall'@'127.0.0.1';
GRANT ALL PRIVILEGES ON mall_db.* TO 'mall'@'localhost';
FLUSH PRIVILEGES;

SELECT SCHEMA_NAME, DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME
FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = 'mall_db';
