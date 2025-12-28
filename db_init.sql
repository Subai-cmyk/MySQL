-- 1. 如果存在旧库，先删除
DROP DATABASE IF EXISTS smart_lib_db;

-- 2. 创建新库
CREATE DATABASE smart_lib_db DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE smart_lib_db;

-- 3. 创建用户表 (用于登录)
CREATE TABLE users (
                       id INT AUTO_INCREMENT PRIMARY KEY,
                       username VARCHAR(50) NOT NULL UNIQUE,
                       password VARCHAR(255) NOT NULL, -- 存储加密后的密码
                       role VARCHAR(20) DEFAULT 'student' -- 'admin' 或 'student'
);

-- 4. 创建图书表 (包含借阅信息)
CREATE TABLE books (
                       id INT AUTO_INCREMENT PRIMARY KEY,
                       title VARCHAR(255) NOT NULL,
                       author VARCHAR(100) NOT NULL,
                       genre VARCHAR(50),
                       price DECIMAL(10, 2),
                       rating FLOAT DEFAULT 0.0,
                       summary TEXT,

    -- 状态管理字段
                       status VARCHAR(20) DEFAULT '可借阅', -- '可借阅' 或 '已借出'

    -- 借阅人关联字段
                       borrower_id INT DEFAULT NULL,
                       borrow_date TIMESTAMP DEFAULT NULL,

    -- 外键约束 (可选，关联到用户表)
                       FOREIGN KEY (borrower_id) REFERENCES users(id)
);

-- 5. 插入测试书籍
INSERT INTO books (title, author, genre, price, rating, summary, status) VALUES
                                                                             ('三体', '刘慈欣', '科幻', 39.00, 9.5, '地球文明与三体文明的信息交流与生死搏杀。', '可借阅'),
                                                                             ('活着', '余华', '剧情', 25.00, 9.2, '讲述了在大时代背景下，徐福贵的人生和家庭不断经受着苦难。', '可借阅'),
                                                                             ('百年孤独', '马尔克斯', '魔幻现实', 45.00, 9.0, '布恩迪亚家族七代人的传奇故事。', '可借阅'),
                                                                             ('Python编程', 'Eric Matthes', '技术', 89.00, 8.8, 'Python入门经典教材。', '可借阅'),
                                                                             ('沙丘', '赫伯特', '科幻', 55.00, 8.5, '控制香料的人控制宇宙。', '可借阅');
