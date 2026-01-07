import random
import time
from typing import List, Tuple, Type
from src.plugin_system import (
    BasePlugin,
    register_plugin,
    ComponentInfo,
    ConfigField,
    BaseEventHandler,
    EventType,
    MaiMessages,
    ReplyContentType,
    chat_api,
    message_api,
    llm_api
)
from src.config.config import global_config
from src.common.logger import get_logger

logger = get_logger("forward_plugin")

def is_forward_message(message):
    """检查消息是否为转发消息"""
    # logger.debug(f"segments: {message.message_segments}")
    if not hasattr(message, 'message_segments'):
        return False

    for segment in message.message_segments:
        if segment.type == "seglist":
            # 转发消息
            return True
    return False


class ForwardMessages(BaseEventHandler):
    """
    把接收到的转发消息转发到指定群聊
    """

    event_type = EventType.ON_MESSAGE
    handler_name = "forward_messages_handler"
    handler_description = "把接收到的转发消息转发到指定群聊"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_forward_time = time.time()  # 初始化上一次转发时间

    def _is_source_message(self, message: MaiMessages) -> bool:
        """检查消息是否来自可信源头"""
        sources = self.get_config("forward.sources", [])
        if not sources:  # 检查配置源头是否为空
            logger.warning("转发源头为空")
            return False
        
        if message.is_group_message:
            # 获取消息的群ID
            group_id = message.message_base_info.get("group_id", None)
            if not group_id:
                logger.debug("无法获取群ID")
                return False
                
            return str(group_id) in sources
        if message.is_private_message:
            # 获取消息的QQID
            user_id = message.message_base_info.get("user_id", None)
            if not user_id:
                logger.debug("无法获取QQID")
                return False
            return str(user_id) in sources
    
    async def _should_forward(self, message: MaiMessages | None) -> bool:
        """检查是否应该转发消息"""
        if not message:
            logger.debug("消息为None")
            return False
        # 检查是否为转发消息
        if not is_forward_message(message):
            logger.debug("非转发消息")
            return False
        # 检查是否为配置的源头群消息
        if not self._is_source_message(message):
            logger.debug(f"丢弃非配置的来源的聊天记录")
            return False
        # llm判断消息合法性
        if not self.get_config("forward.disable_judge", False):  # 若未取消llm判断
            logger.info("开始LLM判断")
            models = llm_api.get_available_models()
            judge_model = self.get_config("forward.judge_model", "utils")
            judge_rule = self.get_config("forward.judge_rule", "")
            model_config = models[judge_model]

            prompt = "请根据下述规则，判断该聊天记录是否适合分享到其它群聊，仅回复'是'或'否'，不要输出多余内容，如理由、括号、引号等\n"
            prompt += f"判断规则：\n{judge_rule}\n"
            prompt += f"聊天记录：\n{message.plain_text}\n"
            prompt += "是否适合转发：(是/否)"
            result = await llm_api.generate_with_model(
                prompt=prompt,
                model_config=model_config
            )
            success, judge, _, _ = result
            if not success:
                logger.error("LLM不可用")
                return False
            if judge.lower() == "是":
                logger.info("LLM判断通过")
            else:
                logger.info("LLM判断未通过")
                return False
        
        # 检查冷却时间
        current_time = time.time()
        # 确保 self.interval 是数值类型
        interval = self.get_config("forward.interval", 0.0)
        if current_time - self.last_forward_time < interval:
            logger.info(f"进入冷却")
            sleep_duration = interval - (current_time - self.last_forward_time)
            if sleep_duration > 0:
                time.sleep(sleep_duration)

        return True

    async def execute(self, message: MaiMessages | None) -> Tuple[bool, bool, None, None, None]:
        message_time = time.time()
        if message is None:
            logger.debug("消息为None")
            return True, True, None, None, None
        # 检查是否应该转发消息
        if not await self._should_forward(message):  
            logger.debug("不满足转发条件")
            return True, True, None, None, None
        # 获取待转发的消息id
        # MaiMessages 竟然没有 message_id -- v0.12.1
        forward_message = message_api.get_messages_before_time_in_chat(
            chat_id=message.stream_id,
            timestamp=message_time,
            limit=1,
            filter_mai=True,
        )[0]
        message_id = forward_message.message_id
        logger.debug(f"获取消息ID {message_id}")
        # 获取目标群stream_id
        target_stream_ids = []
        target_groups = self.get_config("forward.target_groups", [])
        for group_id in target_groups:
            target_stream_id = chat_api.get_stream_by_group_id(group_id).stream_id
            if target_stream_id is None:
                logger.error(f"未找到目标群 {group_id} 的聊天流")
                continue
            target_stream_ids.append(target_stream_id)
        target_users = self.get_config("forward.target_users", [])
        for user_id in target_users:
            target_stream_id = chat_api.get_stream_by_user_id(user_id).stream_id
            if target_stream_id is None:
                logger.error(f"未找到目标用户 {user_id} 的聊天流")
                continue
            target_stream_ids.append(target_stream_id)
        if not target_stream_ids:
            logger.warning("无目标，无法转发消息")
            return False, True, None, None, None

        # 转发
        for target_stream_id in target_stream_ids:
            # 使用消息ID进行转发
            success = await self.send_forward(
                target_stream_id,
                [str(message_id)]
            )

        if success:
            self.last_forward_time = time.time()
            logger.info(f"转发消息成功")
        else:
            logger.error(f"转发消息失败")

        return True, True, None, None, None


# ===== 插件注册 =====


@register_plugin
class ForwardPlugin(BasePlugin):
    """搬史插件"""

    # 插件基本信息
    plugin_name: str = "forward_plugin"  # 内部标识符
    enable_plugin: bool = True
    dependencies: List[str] = []  # 插件依赖列表
    python_dependencies: List[str] = []  # Python包依赖列表
    config_file_name: str = "config.toml"  # 配置文件名

    # 配置节描述
    config_section_descriptions = {
        "plugin": "插件基本信息", 
        "forward": "转发消息配置",
        "cooldown": "冷却时间配置"
    }

    # 配置Schema定义
    config_schema: dict = {
        "plugin": {
            "config_version": ConfigField(type=str, default="1.0.0", description="配置文件版本"),
            "enabled": ConfigField(type=bool, default=True, description="是否启用插件"),
        },
        "forward": {
            "judge_model": ConfigField(type=str, default="utils", description="判断是否能够转发的模型"),
            "judge_rule": ConfigField(type=str, default="1.来源可信：确保重大信息经可靠信源证实，非匿名或可疑来源。\n2.合法性评估：信息无淫秽、引战、辱骂信息。\n3.娱乐为先：对于奇怪但是有趣的消息适当放宽标准", description="判断是否转发的规则"),
            "disable_judge": ConfigField(type=bool, default=False, description="取消大模型判断，进行无条件转发（请谨慎使用）"),
            "sources": ConfigField(type=List, default=[], description="要转发的源头群聊或用户ID"),
            "target_groups": ConfigField(type=List, default=[], description="目标群ID"),
            "target_users": ConfigField(type=List, default=[], description="目标用户ID"),
            "interval": ConfigField(type=int, default=0, description="转发冷却（秒）"),
        }
    }

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        return [
            (ForwardMessages.get_handler_info(), ForwardMessages),
        ]