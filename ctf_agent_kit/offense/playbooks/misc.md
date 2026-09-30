# Misc 攻击 Playbook

## 题型特征识别

- 不好归入其他五类即 Misc：编码套娃、隐写、游戏、量子、AI、社会工程
- 附件：图片/音频/二维码/奇怪格式文件
- 关键词：`hidden`, `stego`, `encode`, `puzzle`, `osint`

## 常用工具

- 图片隐写：zsteg、steghide、stegsolve、exiftool、binwalk
- 音频：Audacity（频谱图）、Sonic Visualiser、morse 解码器
- 编码：CyberChef（Magic 模式自动识别）、basecrack
- 压缩：john/hashcat + rockyou、fcrackzip
- OSINT：Google 镜头、exif GPS、社交媒体检索

## 标准攻击链

1. **文件识别**：`file` + `exiftool` + `binwalk` + 十六进制看头尾
2. **分层剥离**：Misc 题几乎必套娃——每层的「答案」常是下层的钥匙
   - 编码链：Base64/32/85 → hex → rot13 → 摩斯 → 二维码
   - 隐写链：元数据 → LSB → 追加数据 → steghide（密码来自前层）
3. **针对性工具**：按介质选工具（见上表）
4. **拼接验证**：分段 flag 拼完整后整体提交，不分段提交

## 常见变体

- 像素级：改高度/宽度（PNG IHDR CRC 爆破）、RGB 通道分离
- 音频：频谱图藏字、SSTV 图像、DTMF 拨号音
- 游戏/脚本类：反作弊/内存修改/自动求解脚本
- 区块链/量子/AI 新题型：先搜同类 writeup（rag/writeup_store）再动手
