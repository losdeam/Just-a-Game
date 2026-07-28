"""跑团本（Campaign Book）模块：把世界观数据组织成一桌单人跑团的完整剧本。

参考 SillyTavern 的角色卡 / 知识书（World Info）与环世界的故事讲述者，
"创建世界观" 即 "创建跑团本"——由 AI 充当主持人（Game Master）驱动整场跑团。
"""

from jag.campaign.book import (
    CampaignBook,
    CharacterCard,
    LorebookEntry,
    PlotThread,
)

__all__ = [
    "CampaignBook",
    "CharacterCard",
    "LorebookEntry",
    "PlotThread",
]
