"""
总后台语音素材：TTS 生成 / 上传录音，按「事件 × 语气」分配给区域
center/voice.py

· gentle 温和提醒：低 / 中危时播放，语气像老师在旁边提醒；
· stern  严厉干预：紧急事件或交叉验证为高危时播放，短、硬、明确下一步动作。
· 上传老师本人录音时必须勾选"已获本人同意"，素材只在本系统内使用。
TTS 用 edge-tts（可选依赖，需联网）；没装就只能上传音频。
"""
import asyncio
import os
import re
from typing import Dict, Optional, Tuple

MAX_UPLOAD = 5 * 1024 * 1024
AUDIO_TYPES = {  # 文件头 → 扩展名
    b"ID3": ".mp3", b"\xff\xfb": ".mp3", b"\xff\xf3": ".mp3", b"\xff\xf2": ".mp3",
    b"RIFF": ".wav", b"OggS": ".ogg", b"fLaC": ".flac",
}
TONES = {"gentle": "温和提醒", "stern": "严厉干预"}

# 可选音色（edge-tts 中文）
TTS_VOICES = {
    "zh-CN-XiaoxiaoNeural": "晓晓 · 温柔女声",
    "zh-CN-XiaoyiNeural": "晓伊 · 活泼女声",
    "zh-CN-YunxiNeural": "云希 · 青年男声",
    "zh-CN-YunjianNeural": "云健 · 沉稳男声",
    "zh-CN-YunyangNeural": "云扬 · 播音男声",
    "zh-CN-liaoning-XiaobeiNeural": "晓北 · 东北话女声",
    "zh-CN-shaanxi-XiaoniNeural": "晓妮 · 陕西话女声",
}

# 事件类型 → (名称, 温和提醒, 严厉干预)
KINDS: Dict[str, Tuple[str, str, str]] = {
    "ppe_goggles": ("未戴护目镜", "同学，记得戴好护目镜哦，眼睛只有一双。", "立即佩戴护目镜，否则停止操作！"),
    "ppe_coat": ("未穿实验服", "同学，请先把实验服穿好再继续。", "未穿实验服，立即停止操作！"),
    "ppe_gloves": ("未戴手套", "接触试剂前，记得戴上防护手套。", "立即戴上手套，停止接触试剂！"),
    "ppe_mask": ("未戴口罩", "请戴好口罩，避免吸入挥发气体。", "立即佩戴口罩！"),
    "ppe_headmask": ("未戴头罩", "请戴好头罩，把头发收进去。", "立即佩戴头罩！"),
    "eating": ("实验区饮食", "实验区不能吃东西喝水哦，请到室外再吃。", "立即停止饮食，离开实验区洗手！"),
    "sleeping": ("伏案", "同学，累了就先停下来休息，别趴在实验台上。", "请立即抬头，确认实验台状态！"),
    "edge_risk": ("器皿靠近桌边", "有器皿离桌边太近了，往里放一放。", "器皿即将掉落，立即移到台面内侧！"),
    "unattended_heating": ("加热无人", "加热还没结束，请回到实验台旁。", "加热中无人看守，即将自动断电，立即返回！"),
    "dry_burn_predict": ("即将干烧", "液体快烧干了，请降低火力或补充液体。", "即将干烧！立即关闭热源！"),
    "temp_rate": ("升温过快", "升温有点快，请调小加热功率。", "升温异常，立即降低功率！"),
    "dry_burn": ("干烧", "检测到干烧，已切断电源，请等器皿冷却。", "干烧！已自动断电，不要触碰器皿！"),
    "smoke": ("烟雾", "检测到烟雾，已切断电源并开启排风。", "烟雾超标！已断电，立即停止操作并准备撤离！"),
    "humidity_high": ("湿度过高", "实验室有点潮，请开启除湿。", "湿度过高，立即开启除湿！"),
    "non_heatable_heating": ("量器被加热", "量筒、容量瓶不能直接加热，请换成烧杯。", "量器不可加热，立即停止！"),
}


def sniff_ext(data: bytes) -> Optional[str]:
    for head, ext in AUDIO_TYPES.items():
        if data.startswith(head):
            if ext == ".wav" and data[8:12] != b"WAVE":
                continue
            return ext
    return None


def safe_name(name: str) -> str:
    name = re.sub(r"[\\/:*?\"<>|\r\n]", "", (name or "").strip())
    return name[:40] or "未命名"


def tts_available() -> bool:
    try:
        import edge_tts  # noqa: F401
        return True
    except Exception:
        return False


def tts(text: str, voice: str, path: str, rate: str = "+0%"):
    """生成 mp3；失败抛异常（未安装 / 断网）"""
    import edge_tts
    if voice not in TTS_VOICES:
        raise ValueError("不支持的音色")
    text = (text or "").strip()
    if not (1 <= len(text) <= 120):
        raise ValueError("文字 1–120 字")

    async def run():
        await edge_tts.Communicate(text, voice, rate=rate).save(path)

    asyncio.run(run())
    if not os.path.isfile(path) or os.path.getsize(path) < 100:
        raise RuntimeError("TTS 未生成音频")
