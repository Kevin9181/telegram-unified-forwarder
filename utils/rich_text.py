"""发送辅助：把 HTML 文本转成实体，并把 tg://user 链接升级成原生提及。

Telethon 的 HTML 解析只会生成 ``MessageEntityTextUrl``，客户端能否把它渲染成
可点击链接取决于它能否解析该 ID，因此同一条消息里会出现"有的能点有的不能点"。
改成 ``MessageEntityMentionName`` 后就是标准的提及实体，各客户端表现一致。
"""
import re

from telethon.extensions import html as html_parser
from telethon.tl.types import MessageEntityMentionName, MessageEntityTextUrl

_USER_LINK = re.compile(r"^tg://user\?id=(\d+)$")


def is_html(parse_mode):
    return str(getattr(parse_mode, "value", parse_mode) or "").lower() == "html"


def to_entities(markup):
    """HTML -> (纯文本, 实体列表)。

    Telethon 的 HTML 解析器会把 <a href="tg://user?id=N"> 转成
    MessageEntityMentionName，而 iOS 第三方客户端（Nagram）只把 TextUrl 渲染成超链。
    这里把 MentionName 换回 TextUrl：显示文字不变，链接可点，也不依赖用户名。
    """
    text, entities = html_parser.parse(markup)

    converted = []
    for entity in entities:
        if isinstance(entity, MessageEntityMentionName):
            converted.append(
                MessageEntityTextUrl(
                    offset=entity.offset,
                    length=entity.length,
                    url=f"tg://user?id={entity.user_id}",
                )
            )
        else:
            converted.append(entity)

    return text, converted


async def send_message(client, target, content, parse_mode, **kwargs):
    """发送文本消息；HTML 模式走实体发送，其余模式保持原样。"""
    if is_html(parse_mode):
        text, entities = to_entities(str(content))
        return await client.send_message(target, text, formatting_entities=entities, **kwargs)
    return await client.send_message(target, str(content), parse_mode=parse_mode, **kwargs)


async def send_file(client, target, file, caption, parse_mode, **kwargs):
    """发送文件/媒体；caption 同样按 HTML 实体处理。"""
    if is_html(parse_mode) and caption:
        text, entities = to_entities(str(caption))
        return await client.send_file(
            target, file, caption=text, formatting_entities=entities, **kwargs
        )
    return await client.send_file(target, file, caption=caption, parse_mode=parse_mode, **kwargs)


async def edit_message(client, entity, message, content, parse_mode, **kwargs):
    """编辑已有消息；HTML 模式同样走实体，保证提及链接可点击。"""
    if is_html(parse_mode):
        text, entities = to_entities(str(content))
        return await client.edit_message(
            entity, message, text=text, formatting_entities=entities, **kwargs
        )
    return await client.edit_message(entity, message, text=content, parse_mode=parse_mode, **kwargs)
