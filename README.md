# Telegram Unified Forwarder

把几十个 Telegram 群组/频道里的消息，按关键词筛出来，自动带上来源、发送者、时间和原帖链接，转发到你指定的会话。

一套进程、一个数据库、一条过滤流水线。

## 为什么只跑一套

常见的做法是拆成两个服务：一个盯群，一个转发。两套 Telethon 客户端、两份配置、两条过滤链——同一条消息常常被处理两遍，配置改了一边忘了另一边，行为就对不上。

这个项目把它们收进一个进程：

- 一个**用户客户端**负责收消息，覆盖全部来源群
- 一个 **Bot 客户端**负责命令交互，手机上就能改规则
- 消息进来后走同一条过滤链，规则、关键词、媒体限制、替换规则共用一套配置

结果是内存占用减半，也不会出现「两边不一致」的怪现象。实测在 2 核 1.8G 的机器上，19 个群、23 条规则、168 条关键词绑定，常驻 160MB 左右。

## 适合谁

- 盯几十个群/频道，只把命中关键词的消息转到自己的私聊或频道
- 希望转发出来的消息自带来源和原帖链接，方便溯源
- 需要对某些频道做**全量转发**（不做关键词过滤，原样搬）
- 想在手机上用 Bot 管规则，而不是登录服务器改配置

> 只监听你有权访问的聊天。本项目不提供任何绕过权限的能力。

## 功能一览

| 能力 | 说明 |
|---|---|
| 多来源 × 多目标 | 每个「来源 × 目标」是一条独立规则，可单独启停和调整 |
| 关键词过滤 | 普通关键词、正则关键词、黑名单/白名单、组合模式 |
| 来源摘要 | 转发时自动附加来源、发送者、时间、命中关键词和原帖链接 |
| 全量频道转发 | `channel_watch_ids × channel_target_ids` 走无关键词规则，原生转发 |
| Bot 管理 | `/bind`、`/settings`、`/add` 等命令，不用改文件 |
| 内容处理 | 替换规则、媒体类型/大小/扩展名过滤、编辑或转发模式、延迟、评论区按钮 |
| AI 处理 | 内置多家服务商配置，可对消息做改写或定时总结 |
| 推送与 RSS | Apprise 多平台推送、RSS 订阅与管理页面 |
| **启动自检** | 每次起来发一条资源与配置概况，人为重启会标注原因 |
| **健康告警** | 内存/磁盘/负载/进程异常时主动推 Telegram，恢复时补一条 |
| 其他 | 链接转发、规则复制/同步、导入导出、UFB 集成 |

## 本版改动

在既有代码基础上做的实际工作：

**发言人链接**

- 发送前把 `MessageEntityMentionName` 转成 `MessageEntityTextUrl(url="tg://user?id=…")`。原实现发出去的 mention 实体在部分第三方客户端（如 Nagram）里是死文字，点不动
- 发送者 ID 做了三级兜底（`id` / `user_id` / 调用方传入），兼容不同 Telethon 版本返回的字段差异
- 频道类来源（负数 ID）单独走 `t.me/<username>`，私有群退回 `t.me/c/<id>`

**启动自检**

- 重写为字符条呈现（`██████░░░░ 57%`），负载用 `▁▂▃▄▅▆▇█` 档位
- 去掉版本号、Bot 名、固定命令列表等每次相同的信息
- 关键词按唯一值统计，避免「8 个词 × 21 条规则 = 168」这种失真数字
- 人为重启时读标记文件，在通知里注明「由人工触发：<原因>」，与崩溃自动拉起区分

**部署形态**

- 支持不使用 Docker 的部署：venv + systemd user 服务，常驻内存比容器低一档，也不需要 sudo 装 Docker
- 备份、告警、清理三个脚本改为 systemd 版（查进程而非容器）

**其他修复**

- `send_rich_message` 改名后调用方未同步导致的 `NameError`
- 全站超链接失效：`to_entities()` 主动把 mention 实体换回 text url

## 快速开始

### 0. 准备三样东西

| 需要 | 从哪里获取 |
|---|---|
| `API_ID` / `API_HASH` | <https://my.telegram.org/apps> 创建应用 |
| `BOT_TOKEN` | 找 [@BotFather](https://t.me/BotFather) 创建机器人 |
| 用户账号 | **必须已加入**所有要监听的来源群组/频道，否则收不到消息 |

`USER_ID` 可以用 [@userinfobot](https://t.me/userinfobot) 查。

### 1. 部署（Docker）

```bash
git clone https://github.com/Kevin9181/telegram-unified-forwarder.git
cd telegram-unified-forwarder
sudo ./deploy.sh
```

脚本会依次完成：

1. 检查系统与 Docker（缺 Docker 时询问后安装）
2. 交互式收集凭据，以 `0600` 权限写入 `.env`（**不会打印、不会提交到 Git**）
3. 构建镜像
4. 启动首次登录向导

### 1'. 部署（不用 Docker，内存紧张时推荐）

```bash
git clone https://github.com/Kevin9181/telegram-unified-forwarder.git
cd telegram-unified-forwarder
python3 -m venv .venv
curl -sS https://bootstrap.pypa.io/get-pip.py | .venv/bin/python3
.venv/bin/python3 -m pip install -r requirements.txt
cp .env.example .env && chmod 600 .env    # 手工填 API_ID / API_HASH / BOT_TOKEN / USER_ID
```

先用前台跑一次完成登录，确认两个客户端都起来了：

```bash
.venv/bin/python3 main.py
```

Ctrl+C 退出后装成服务：

```bash
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/tgforward.service <<'EOF'
[Unit]
Description=Telegram forwarder
After=network-online.target

[Service]
WorkingDirectory=%h/telegram-unified-forwarder
ExecStart=%h/telegram-unified-forwarder/.venv/bin/python3 main.py
Restart=always
RestartSec=5
StandardOutput=append:%h/telegram-unified-forwarder/logs/stdout.log
StandardError=append:%h/telegram-unified-forwarder/logs/stderr.log

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now tgforward
```

想让服务在注销后继续跑、开机自启，需要 `loginctl enable-linger $USER`。

### 2. 首次登录

Docker 方式：

```bash
sudo docker compose run --rm -it telegram-forwarder
```

按提示输入**手机号收到的验证码**（开了两步验证的话再输入密码），看到类似下面的输出就是成功：

```
用户客户端已启动: ...
机器人客户端已启动: ...
```

然后按 `Ctrl+C` 返回，启动后台服务：

```bash
sudo docker compose up -d
```

会话会持久化到 `sessions/`，之后重启不用再登录。

### 3. 建第一条规则

在 Bot 聊天里发：

```
/bind <来源群链接或名称> [目标会话链接或名称]
/settings
```

`/settings` 里可以加关键词、开关过滤模式、调整媒体限制。完整命令手册见 [README-forwarder-reference.md](README-forwarder-reference.md)。

## 日常运维

**Docker**

| 需求 | 命令 |
|---|---|
| 看容器状态 | `docker compose ps` |
| 实时日志 | `docker compose logs -f telegram-forwarder` |
| 只看错误 | `docker compose logs telegram-forwarder \| grep -iE 'error\|traceback'` |
| 重启 | `docker compose restart` |
| 停止（保留数据） | `docker compose down` |
| 更新代码后重建 | `git pull && docker compose build && docker compose up -d` |

**systemd**

| 需求 | 命令 |
|---|---|
| 状态 | `systemctl --user status tgforward` |
| 实时日志 | `tail -f logs/stderr.log` |
| 重启 | `systemctl --user restart tgforward` |
| 开机自启 | `systemctl --user enable tgforward` |

> `docker compose down` **不会**删除 `db/`、`sessions/` 等主机目录，数据安全。真正危险的只有 `docker volume rm` 和手动 `rm -rf`。

## 备份与恢复

会话文件等同于账号凭据，数据库存着全部规则，两者都要备份。

```bash
# 每天 03:30 备份，保留最近 7 份
sudo cp scripts/backup.sh /root/tf-backup.sh
sudo chmod 700 /root/tf-backup.sh
(crontab -l 2>/dev/null; echo "30 3 * * * /root/tf-backup.sh >> /root/backups/cron.log 2>&1") | crontab -
```

脚本会做三件事：用 SQLite 在线备份 API 导出数据库（避免拷到写了一半的文件）、打包 `db/ sessions/ .env`、清理旧备份。产物落在 `/root/backups/`，权限 `600`。

**恢复**：

```bash
docker compose down
tar xzf /root/backups/tf-<时间戳>.tar.gz -C /opt/telegram-unified
docker compose up -d
```

## 健康告警（可选）

想让服务器出问题时主动找你，而不是等你想起来去看：

```bash
sudo cp scripts/alert.sh /root/tf-alert.sh
sudo chmod 700 /root/tf-alert.sh
sudo /root/tf-alert.sh --test          # 先验证 Telegram 能收到
(crontab -l 2>/dev/null; echo "*/5 * * * * /root/tf-alert.sh >> /root/backups/alert.log 2>&1") | crontab -
```

触发条件（可用环境变量覆盖）：

| 指标 | 默认阈值 | 变量 |
|---|---|---|
| 可用内存 | < 100 MB | `MIN_AVAIL_MB` |
| 根分区使用率 | > 85% | `MAX_DISK_PCT` |
| Swap 使用 | > 400 MB | `MAX_SWAP_MB` |
| 容器状态 | 非 `healthy` | `CONTAINER` |

同一条告警只推一次，恢复时补发一条 ✅，不会每 5 分钟刷屏。

## 安全基线

项目本身不监听任何公网端口（RSS 默认也不发布），但服务器层面建议至少做到：

```bash
# 1. 只允许密钥登录（先确认密钥能进，再关密码！）
sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#*KbdInteractiveAuthentication.*/KbdInteractiveAuthentication no/' /etc/ssh/sshd_config
sshd -t && systemctl reload ssh

# 2. 防火墙只放行 SSH
ufw allow 22/tcp && ufw --force enable

# 3. 挡住密码爆破
apt install -y fail2ban && systemctl enable --now fail2ban
```

⚠️ 关密码前务必先验证密钥登录可用，否则会把自己锁在门外。

## 排障速查

| 现象 | 先看什么 |
|---|---|
| 完全没消息进来 | 日志看两个客户端是否「已启动」；账号是否还在源群里 |
| 有消息但不转发 | 日志搜「未匹配」「关键字匹配成功」；确认规则是白名单还是黑名单模式 |
| 某个来源一直不生效 | 该来源 ID 是否能被当前账号解析（私群需账号在群内） |
| 媒体总是发不出去 | `.env` 的 `DEFAULT_MAX_MEDIA_SIZE`，以及规则里的媒体过滤 |
| 服务反复重启 | 日志搜 Traceback；`systemd` 看 `MemoryMax` 是否卡太紧 |
| 提示 session 失效 | 删掉 `sessions/*.session` 后重新执行首次登录 |
| 发言人链接点不动 | 确认 `utils/rich_text.py` 的 `to_entities()` 未被改回原生 mention 实体 |

## 导入历史配置

如果之前用过独立的监控工具，旧配置里的监听源、目标、关键词、白名单可以整体导入。

```bash
# 1. 把旧配置放进 config/（该目录已被 .gitignore 忽略）
mkdir -p config
install -m 600 /path/to/config/config.json config/monitor-config.json

# 2. 先预览，确认无误再执行
.venv/bin/python3 import_monitor_config.py config/monitor-config.json --dry-run --allow-unresolved-source-ids

# 3. 正式导入（可重复运行，已有规则不会被覆盖）
.venv/bin/python3 import_monitor_config.py config/monitor-config.json --allow-unresolved-source-ids
```

导入器会把 `watch_ids × target_ids` 转成关键词规则，把 `channel_*` 转成独立的**全量转发**规则。旧的白名单保存在 `migration/monitor_compat_admins.json`，可用 `/allow`、`/unallow` 维护。

`--allow-unresolved-source-ids` 只适用于确认无误的数字频道 ID：当账号还没能解析该实体时，按 marked channel ID 存占位来源。它不会授予任何权限，账号仍然必须能收到该频道的更新。

## 目录结构

```
.
├── main.py                  # 入口：启客户端、调度器、监听器
├── message_listener.py      # 消息分发到规则
├── filters/                 # 过滤/转发流水线
│   ├── info_filter.py       #   来源、发送者、时间、关键词、原帖链接
│   ├── sender_filter.py     #   组装并发送
│   └── ...
├── handlers/                # Bot 命令与按钮
├── models/                  # SQLAlchemy 模型与数据库操作
├── rss/                     # 可选 RSS 服务（FastAPI）
├── scripts/                 # 运维脚本（备份、告警）
├── utils/                   # 日志、富文本实体、启动自检
├── deploy.sh                # 一键部署（Docker）
├── docker-compose.yml
└── .env.example             # 配置模板
```

运行时目录（`db/` `sessions/` `logs/` `temp/` `config/`）不进版本库。

## 更多文档

- [README-forwarder-reference.md](README-forwarder-reference.md) — 完整的命令与过滤器手册
- [NOTICE.md](NOTICE.md) — 代码来源与归属
- [deploy.sh](deploy.sh) — Docker 部署脚本源码（含交互流程）

## 许可

以 **GPL-3.0** 发行，因为核心包含 GPL-3.0 代码。来源与归属详见 [NOTICE.md](NOTICE.md)。
