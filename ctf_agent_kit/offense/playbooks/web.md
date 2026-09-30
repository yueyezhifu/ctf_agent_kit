# Web 攻击 Playbook

## 题型特征识别

- 给出 URL/源码包/docker 部署文件
- PHP/Java/Python 源码审计题：直接给源码找漏洞点
- 关键词：`admin`, `upload`, `login`, `api`, `debug`, 框架指纹

## 常用工具

- 侦察：curl、Burp Suite、dirsearch/feroxbuster、wappalyzer
- 注入：sqlmap（确认注入点后再用，手工优先）
- 反序列化：ysoserial（Java）、phpggc（PHP）
- 辅助：CyberChef（编码/JWT）、jwt_tool

## 标准攻击链

1. **攻击面测绘**：robots.txt、目录扫描、参数枚举、框架/组件指纹
2. **漏洞识别**（按收益排序尝试）：
   - 注入类：SQLi（报错/联合/盲注）、命令注入、SSTI（{{7*7}} 探测）
   - 文件类：LFI/RFI（伪协议 php://filter 读源码）、任意上传（MIME/扩展名绕过）
   - 逻辑类：越权（改 id）、条件竞争、JWT 弱密钥/alg=none
   - 反序列化：特征串（rO0AB / O: 开头 / pickle）
   - SSRF：内网探测、gopher 打 redis/mysql
3. **扩大战果**：读源码 → 找硬编码凭据 → 进后台 → 找 flag 文件/环境变量
4. **flag 定位**：常见位置 /flag、数据库、环境变量、备份文件（.git/.bak/.swp）

## 常见变体

- 过滤绕过：大小写、双写、编码、注释、等价函数
- 组合链：SSRF + 内网服务、文件上传 + 文件包含 = RCE
- 前端题：JS 审计找隐藏接口/key，wasm 逆向后端逻辑
- 条件竞争：Turbo Intruder 并发发包
