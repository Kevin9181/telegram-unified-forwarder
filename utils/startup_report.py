"""启动自检报告：采集主机/数据库概况并渲染成 Telegram HTML 消息。"""
import os
import shutil
import sqlite3


def _bar(pct, width=10):
    """百分比 → 字符条。"""
    try:
        pct = max(0.0, min(100.0, float(pct)))
    except (TypeError, ValueError):
        return '░' * width
    filled = int(round(pct * width / 100.0))
    return '█' * filled + '░' * (width - filled)


def _load_glyph(load1, cores):
    """负载 → 档位字符，0~2 倍核数映射到 8 档。"""
    try:
        ratio = float(load1) / max(1, int(cores))
    except (TypeError, ValueError):
        return '▁'
    idx = min(7, max(0, int(ratio * 4)))
    return '▁▂▃▄▅▆▇█'[idx]


def collect_stats(db_path):
    """采集启动时的基本信息，任何一项失败都只跳过该字段。"""
    stats = {}

    try:
        stats['cores'] = os.cpu_count() or 1
    except Exception:
        pass

    try:
        memory = {}
        with open('/proc/meminfo', encoding='utf-8') as handle:
            for line in handle:
                key, _, value = line.partition(':')
                memory[key.strip()] = int(value.split()[0])
        total = memory.get('MemTotal', 0) // 1024
        available = memory.get('MemAvailable', memory.get('MemFree', 0)) // 1024
        if total:
            stats['mem_total'] = total
            stats['mem_used'] = total - available
            stats['mem_available'] = available
    except Exception:
        pass

    try:
        usage = shutil.disk_usage('/')
        stats['disk_used_pct'] = usage.used / usage.total * 100
        stats['disk_free_gb'] = usage.free / 1024 ** 3
    except Exception:
        pass

    try:
        stats['load'] = os.getloadavg()
    except Exception:
        pass

    try:
        with sqlite3.connect(db_path, timeout=3) as conn:
            cursor = conn.cursor()
            stats['rules_total'] = cursor.execute('select count(*) from forward_rules').fetchone()[0]
            stats['rules_keyword'] = cursor.execute(
                'select count(*) from forward_rules where is_monitor_compat=1'
            ).fetchone()[0]
            # 唯一关键词数。keywords 表按规则各存一份，直接 count(*) 会把 8 个词算成 168
            stats['keywords'] = cursor.execute(
                'select count(distinct keyword) from keywords'
            ).fetchone()[0]
            stats['chats'] = cursor.execute('select count(*) from chats').fetchone()[0]
    except Exception:
        pass

    return stats


def render_report(now, version, bot_label, user_label, stats):
    """渲染启动通知。只保留核心：时间、资源水位、配置规模。"""
    lines = ['<b>✅ 服务正常</b> · %s' % now.strftime('%H:%M'), '']

    rows = []
    if 'mem_total' in stats:
        pct = stats['mem_used'] / stats['mem_total'] * 100
        rows.append('内存  %s  %d%%   %dMB 可用'
                    % (_bar(pct), pct, stats.get('mem_available', 0)))
    if 'disk_used_pct' in stats:
        rows.append('磁盘  %s  %d%%   %.0fG 可用'
                    % (_bar(stats['disk_used_pct']), stats['disk_used_pct'],
                       stats.get('disk_free_gb', 0)))
    if 'load' in stats:
        rows.append('负载  %s  %.2f'
                    % (_load_glyph(stats['load'][0], stats.get('cores', 1)), stats['load'][0]))
    if rows:
        lines.extend(rows)
        lines.append('')

    if 'rules_total' in stats:
        lines.append('%d 条规则 · %d 个监听源 · %d 个关键词'
                     % (stats['rules_total'], stats.get('rules_keyword', 0),
                        stats.get('keywords', 0)))

    tips = []
    if stats.get('disk_used_pct', 0) >= 85:
        tips.append('⚠️ 磁盘快满了，建议清理')
    if stats.get('mem_total') and stats['mem_used'] / stats['mem_total'] >= 0.9:
        tips.append('⚠️ 内存吃紧，留意换页')
    if stats.get('rules_total') == 0:
        tips.append('💡 还没有规则，用 /bind <来源> [目标] 建第一条')
    if tips:
        lines.append('')
        lines.extend(tips)

    return '\n'.join(lines)
