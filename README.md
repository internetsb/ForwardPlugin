# 搬史插件 (ForwardPlugin)

任何漏洞、疑问或功能建议请提出issue或联系我，qq:1523640161

## 插件简介

该插件可以自动从指定来源转发聊天记录到目标群聊或私聊

## 功能特性

- 自动转发指定来源的转发消息
- 支持群聊和私聊消息转发
- 可使用大模型辅助判断消息是否适合转发
- 可自定义转发规则和判断标准
- 支持设置转发冷却时间

## 配置说明

### 配置文件结构

配置文件为 `config.toml`，主要包含以下部分：

```toml
# 插件基本信息
[plugin]
config_version = "1.0.0"  # 配置文件版本
enabled = true            # 是否启用插件

# 转发消息配置
[forward]
judge_model = "utils"     # 判断是否适合转发的模型，从Maibot的model_config自动获取，可为replyer、tool_use等
judge_rule = "1.来源可信：确保重大信息经可靠信源证实，非匿名或可疑来源。\n2.合法性评估：信息无淫秽、引战、辱骂信息。\n3.娱乐为先：对于奇怪有趣的消息适当放宽标准"  # 判断规则
disable_judge = false     # 是否取消大模型判断，进行无条件转发（谨慎使用）
sources = ["xxxxx","xxxxx"]   # 要转发的源头群聊或用户ID
target_groups = ["xxxxx","xxxxx"]  # 目标群ID
target_users = ["xxxxx","xxxxx"]  # 目标用户ID
interval = 0              # 转发冷却（秒）
```

## 使用方法

1. 配置需要转发消息的来源群号或用户QQ号到 `sources` 列表中
2. 配置需要转发消息的目标群号到 `target_groups` 列表中
3. 配置需要转发消息的目标用户QQ号到 `target_users` 列表中
4. 如需使用大模型判断消息是否适合转发，保持 `disable_judge` 为 `false`
5. 如需修改判断规则，编辑 `judge_rule` 配置项

## 工作原理

1. 插件监听所有消息事件
2. 当接收到消息时，首先判断是否为转发消息
3. 检查消息是否来自配置的来源群或用户
4. 如果启用了大模型判断，使用配置的规则判断消息是否适合转发
5. sleep至冷却时间结束，继续转发
6. 将符合条件的消息转发到所有配置的目标群和用户

## 鸣谢

[MaiBot](https://github.com/MaiM-with-u/MaiBot)

灵感来源[anka-afk/astrbot_sowing_discord](https://github.com/anka-afk/astrbot_sowing_discord)
