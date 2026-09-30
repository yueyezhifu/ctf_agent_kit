# Forensics 攻击 Playbook

## 题型特征识别

- 附件：pcap/pcapng、内存镜像、磁盘镜像、日志、镜像文件（img/vmdk）
- 关键词：`capture`, `dump`, `incident`, `suspicious`, `exfiltration`

## 常用工具

- 流量：Wireshark/tshark、NetworkMiner
- 内存：volatility3（imageinfo/pslist/cmdline/dumpfiles）
- 磁盘：binwalk、foremost、fTK、7z（直接解镜像分区）
- 文件修复：010 Editor（改文件头/修复校验）、pngcheck

## 标准攻击链

1. **资产盘点**：`file` 确认类型；pcap 先看协议层级统计找异常占比
2. **按介质走标准流程**：
   - pcap：协议分级 → 导出 HTTP/SMB 对象 → 检查 DNS/ICMP 隧道 → 按流重组分片
   - 内存镜像：volatility 列进程 → 找可疑进程 → dump 内存段搜 flag 格式串
   - 磁盘镜像：挂载/导出文件 → 恢复已删文件（photorec）→ 查 bash 历史
   - 日志：时间线对齐、异常 IP/状态码/UA 聚类
3. **数据还原**：分片拼接（注意去重/排序）、编码层逐层解、损坏文件修头
4. **交叉验证**：还原出的 flag 与附件中其他证据互相印证后提交

## 常见变体

- 加密流量：找密钥交换/证书私钥/会话密钥日志（SSLKEYLOGFILE）
- USB 流量：键盘/鼠标 HID 报文还原击键
- 无线流量：aircrack 解 WPA 后解密 802.11
- 多层套娃：镜像套镜像、压缩包套压缩包（弱密码爆破：john/hashcat）
