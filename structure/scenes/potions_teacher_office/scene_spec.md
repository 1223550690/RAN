# 魔药课教师办公室 2D 场景设定文档

## 1. 场景概述

**场景名称：** 魔药课教师办公室  
**场景类型：** 单人叙事型室内场景  
**使用目标：** 人类行为模拟、单人日常行为链、轻剧情触发、物品交互测试  
**视觉方向：** 英伦魔法学院风格、古堡石室、温暖烛光、深色木质家具、黄铜器具、蓝绿色魔药微光  
**主要角色：** 魔药课教师  
**辅助角色：** 偶尔来访的学生、猫头鹰信使、学院管理员

这个房间属于一位魔法学院的魔药课教师。房间不是大型教室。它更像一个私人办公室和小型研究室的结合体。教师平时在这里备课、批改作业、调制药剂、整理材料、接待学生、记录实验。大部分时间只有教师一人活动，所以这个场景适合单人行为模拟。

空间需要保留清晰的行为路径。入口、办公桌、魔药台、材料柜、会客桌、清洗区都要可以被 agent 识别和访问。场景要有故事感，也要有功能性。每个区域都要支持明确的行为。

---

## 2. 房间背景设定

这间办公室位于魔法学院地下层和主塔之间的一条旧石廊旁。墙体由深灰色石砖砌成。房间常年带着草药、蜡烛、墨水和药剂蒸汽的味道。厚重木门外有一块小铜牌，上面写着魔药课教师的名字和办公时间。

教师性格冷静、严谨、喜欢独处。他习惯把所有材料分类编号。他会把危险材料锁在柜子里。他也会在深夜继续研究一些尚未公开的配方。办公室里有很多学生作业、课堂示范药剂、旧书、卷轴、材料瓶和实验器具。

这个场景的核心叙事是：

> 一位魔药课教师在安静的办公室中完成日常教学和私人研究。他在规则、秘密和责任之间维持自己的秩序。

场景可以支持平静日常，也可以支持轻微悬疑。比如某个药剂突然变色、某个材料瓶标签脱落、某封匿名信出现在门口、某份学生作业里出现奇怪符号。

---

## 3. 整体空间说明

房间为一个紧凑的单间。建议使用 2D 等距或俯视切面视角。左侧展示完整房间。右侧展示 asset sheet。

房间整体分为 8 个主要 area：

1. `entrance_area`：入口区
2. `teacher_work_area`：教师办公区
3. `potion_brewing_area`：魔药调制区
4. `ingredient_storage_area`：材料储藏区
5. `student_consult_area`：学生答疑区
6. `cleanup_area`：清洗收尾区
7. `fireplace_area`：壁炉与温控区
8. `decor_and_lore_area`：装饰与叙事信息区

每个 area 都有明确的交互目标。教师可以在不同区域之间形成稳定的日常行为链。

---

## 4. Area 与 Element 设计

### 4.1 entrance_area

**功能说明：**  
入口区负责进出、身份切换和来访触发。它是房间的边界区域。教师从这里进入工作状态。学生也会在这里敲门、等待或留下纸条。

**主要元素：**

| Element ID | 中文名称 | 类型 | 可交互 | 说明 |
|---|---|---|---|---|
| `heavy_wooden_door` | 厚重木门 | structure | yes | 连接走廊和办公室 |
| `brass_nameplate` | 黄铜门牌 | decor | yes | 显示教师姓名和办公时间 |
| `door_knocker` | 敲门环 | tool | yes | 触发来访事件 |
| `entrance_rug` | 入口地毯 | furniture | no | 标记入口区域 |
| `robe_rack` | 长袍架 | furniture | yes | 挂放教师长袍 |
| `dark_teacher_robe` | 深色教师长袍 | clothing | yes | 可穿上或挂起 |
| `boots_pair` | 皮靴 | clothing | yes | 可穿脱或整理 |
| `umbrella_stand` | 伞桶 | furniture | yes | 放伞、手杖或长柄工具 |
| `walking_stick` | 手杖 | tool | yes | 可拿起或放回 |
| `small_notice_board` | 小留言板 | information | yes | 存放来访留言 |
| `visitor_note` | 来访纸条 | document | yes | 可阅读或收起 |
| `wall_lantern` | 墙灯 | light | yes | 可点亮或熄灭 |

**可能的交互模式：**

- `open_door`：打开门
- `close_door`：关闭门
- `knock_door`：敲门
- `read_nameplate`：查看门牌
- `hang_robe`：挂起长袍
- `wear_robe`：穿上长袍
- `take_walking_stick`：拿起手杖
- `place_walking_stick`：放回手杖
- `read_visitor_note`：阅读留言
- `add_visitor_note`：留下纸条
- `turn_on_lantern`：点亮墙灯
- `turn_off_lantern`：熄灭墙灯

**状态变量建议：**

```json
{
  "door_state": "open | closed | locked",
  "robe_state": "on_rack | worn | missing",
  "lantern_state": "on | off",
  "visitor_note_state": "none | unread | read"
}
```

---

### 4.2 teacher_work_area

**功能说明：**  
教师办公区是房间的核心。它支持备课、批改作业、写信、记录实验和查看课程安排。这个区域体现教师身份。

**主要元素：**

| Element ID | 中文名称 | 类型 | 可交互 | 说明 |
|---|---|---|---|---|
| `large_wooden_desk` | 大木书桌 | furniture | yes | 主要工作台 |
| `high_back_chair` | 高背椅 | furniture | yes | 教师座椅 |
| `desk_lamp` | 桌灯 | light | yes | 提供局部照明 |
| `candle_stand` | 烛台 | light | yes | 魔法氛围照明 |
| `quill_pen` | 羽毛笔 | tool | yes | 写字工具 |
| `ink_bottle` | 墨水瓶 | container | yes | 羽毛笔配套物 |
| `parchment_stack` | 羊皮纸堆 | document | yes | 记录和作业材料 |
| `open_lesson_plan` | 打开的课程计划 | document | yes | 教师备课材料 |
| `student_homework_stack` | 学生作业堆 | document | yes | 待批改作业 |
| `wax_seal` | 火漆印章 | tool | yes | 封信或标记文件 |
| `sealed_letter` | 密封信件 | document | yes | 可阅读或投递 |
| `magic_books_stack` | 魔法书堆 | book | yes | 查阅资料 |
| `small_hourglass` | 小沙漏 | tool | yes | 计时工具 |
| `task_note` | 任务便签 | information | yes | 显示当日任务 |
| `desk_drawer` | 书桌抽屉 | storage | yes | 存放私人文件 |

**可能的交互模式：**

- `sit_down`：坐下
- `stand_up`：起身
- `read_lesson_plan`：阅读课程计划
- `write_lesson_plan`：编写课程计划
- `grade_homework`：批改学生作业
- `write_experiment_note`：记录实验笔记
- `open_book`：打开书
- `read_book`：阅读书籍
- `write_letter`：写信
- `seal_letter`：封信
- `open_drawer`：打开抽屉
- `close_drawer`：关闭抽屉
- `search_drawer`：搜索抽屉
- `flip_hourglass`：翻转沙漏
- `turn_on_desk_lamp`：打开桌灯
- `turn_off_desk_lamp`：关闭桌灯

**状态变量建议：**

```json
{
  "chair_state": "empty | occupied",
  "desk_lamp_state": "on | off",
  "homework_state": "ungraded | partly_graded | graded",
  "lesson_plan_state": "draft | complete",
  "drawer_state": "closed | open | locked",
  "letter_state": "unwritten | written | sealed"
}
```

---

### 4.3 potion_brewing_area

**功能说明：**  
魔药调制区是最重要的魔法行为区域。教师在这里处理材料、熬制药剂、观察反应、制作课堂示范样品。这个区域适合产生视觉反馈和剧情事件。

**主要元素：**

| Element ID | 中文名称 | 类型 | 可交互 | 说明 |
|---|---|---|---|---|
| `iron_cauldron` | 铁坩埚 | equipment | yes | 主要熬制容器 |
| `cauldron_stand` | 坩埚支架 | equipment | yes | 支撑坩埚 |
| `heating_flame` | 加热火焰 | fire | yes | 控制火候 |
| `stirring_rod` | 搅拌棒 | tool | yes | 搅拌药液 |
| `glass_flask` | 玻璃烧瓶 | container | yes | 临时存放药液 |
| `potion_vial_green` | 绿色药剂瓶 | potion | yes | 成品或样本 |
| `potion_vial_blue` | 蓝色药剂瓶 | potion | yes | 成品或样本 |
| `potion_vial_purple` | 紫色药剂瓶 | potion | yes | 成品或样本 |
| `test_tube_rack` | 试管架 | equipment | yes | 放置试管 |
| `brass_scale` | 黄铜天平 | tool | yes | 称量材料 |
| `mortar_and_pestle` | 研钵和研杵 | tool | yes | 研磨材料 |
| `herb_cutting_board` | 草药切板 | tool | yes | 切割草药 |
| `small_knife` | 小刀 | tool | yes | 切割材料 |
| `measuring_spoon` | 量勺 | tool | yes | 控制剂量 |
| `steam_effect` | 蒸汽效果 | effect | no | 显示加热状态 |
| `bubble_effect` | 气泡效果 | effect | no | 显示反应状态 |

**可能的交互模式：**

- `start_brewing`：开始熬制
- `stop_brewing`：停止熬制
- `ignite_flame`：点燃火焰
- `extinguish_flame`：熄灭火焰
- `adjust_flame_low`：调小火候
- `adjust_flame_medium`：调中火候
- `adjust_flame_high`：调高火候
- `add_ingredient`：加入材料
- `stir_clockwise`：顺时针搅拌
- `stir_counterclockwise`：逆时针搅拌
- `observe_color`：观察颜色
- `observe_smell`：观察气味
- `measure_temperature`：测量温度
- `pour_potion`：倒出药液
- `bottle_potion`：装瓶
- `label_potion`：贴标签
- `discard_failed_potion`：丢弃失败药剂
- `clean_cauldron`：清洗坩埚

**状态变量建议：**

```json
{
  "cauldron_state": "empty | filled | brewing | finished | failed",
  "flame_state": "off | low | medium | high",
  "potion_color": "clear | green | blue | purple | black | unknown",
  "potion_stability": "stable | unstable | dangerous",
  "brewing_progress": 0,
  "steam_state": "none | light | heavy"
}
```

---

### 4.4 ingredient_storage_area

**功能说明：**  
材料储藏区支持长期模拟。它让魔药行为有资源来源。教师需要查找材料、补充库存、整理柜子、锁定危险材料。

**主要元素：**

| Element ID | 中文名称 | 类型 | 可交互 | 说明 |
|---|---|---|---|---|
| `apothecary_drawer_cabinet` | 药材抽屉柜 | storage | yes | 分类存放干材料 |
| `glass_jar_shelf` | 玻璃罐架 | storage | yes | 存放瓶装材料 |
| `rare_ingredient_cabinet` | 稀有材料柜 | storage | yes | 带锁柜子 |
| `herb_bundle_dried` | 干燥草药束 | ingredient | yes | 可取用 |
| `root_sample_jar` | 根茎标本罐 | ingredient | yes | 可取用 |
| `powder_bone_jar` | 骨粉罐 | ingredient | yes | 可取用 |
| `crystal_shard_bottle` | 水晶碎片瓶 | ingredient | yes | 可取用 |
| `insect_specimen_bottle` | 昆虫标本瓶 | ingredient | yes | 可取用 |
| `mushroom_box` | 蘑菇盒 | ingredient | yes | 可取用 |
| `label_tag` | 材料标签 | information | yes | 标识材料 |
| `cabinet_key` | 柜子钥匙 | tool | yes | 打开锁柜 |
| `inventory_scroll` | 库存卷轴 | document | yes | 记录库存 |

**可能的交互模式：**

- `open_cabinet`：打开柜子
- `close_cabinet`：关闭柜子
- `unlock_cabinet`：解锁柜子
- `lock_cabinet`：锁上柜子
- `search_ingredient`：查找材料
- `take_ingredient`：取出材料
- `return_ingredient`：放回材料
- `check_label`：查看标签
- `replace_label`：更换标签
- `update_inventory`：更新库存
- `sort_ingredients`：整理材料
- `detect_missing_ingredient`：发现材料缺失

**状态变量建议：**

```json
{
  "rare_cabinet_state": "locked | unlocked | open",
  "inventory_state": "normal | low_stock | missing_item",
  "label_state": "clear | damaged | missing",
  "dangerous_item_access": "allowed | denied"
}
```

---

### 4.5 student_consult_area

**功能说明：**  
学生答疑区支持少量社交和剧情。它不是主功能区，但它能让单人场景出现短时间对话事件。教师可以在这里接待学生、讲解问题、布置额外任务。

**主要元素：**

| Element ID | 中文名称 | 类型 | 可交互 | 说明 |
|---|---|---|---|---|
| `round_consult_table` | 小圆桌 | furniture | yes | 会谈桌 |
| `guest_chair_a` | 访客椅 A | furniture | yes | 学生座椅 |
| `guest_chair_b` | 访客椅 B | furniture | yes | 教师或学生座椅 |
| `consultation_candle` | 会客蜡烛 | light | yes | 桌面照明 |
| `student_question_note` | 学生问题纸条 | document | yes | 会谈内容 |
| `reference_book` | 参考书 | book | yes | 讲解材料 |
| `tea_cup` | 茶杯 | container | yes | 生活化物件 |
| `small_teapot` | 小茶壶 | container | yes | 可倒茶 |

**可能的交互模式：**

- `sit_for_consultation`：坐下答疑
- `invite_student_in`：邀请学生进入
- `ask_question`：学生提问
- `answer_question`：教师回答
- `show_reference_book`：展示参考书
- `assign_extra_task`：布置额外任务
- `receive_homework`：收取作业
- `return_homework`：归还作业
- `pour_tea`：倒茶
- `end_consultation`：结束会谈

**状态变量建议：**

```json
{
  "visitor_state": "none | waiting | seated | left",
  "consultation_state": "not_started | active | finished",
  "tea_state": "empty | poured | cold",
  "question_note_state": "unread | discussed | archived"
}
```

---

### 4.6 cleanup_area

**功能说明：**  
清洗收尾区让行为链完整。教师在调制魔药后要清洗器具、处理废液、晾干玻璃器皿、回收空瓶。这个区域适合表达工作结束状态。

**主要元素：**

| Element ID | 中文名称 | 类型 | 可交互 | 说明 |
|---|---|---|---|---|
| `stone_sink` | 石质水槽 | furniture | yes | 清洗器具 |
| `copper_tap` | 铜水龙头 | tool | yes | 出水控制 |
| `drying_rack` | 晾干架 | furniture | yes | 放置清洗后的玻璃器具 |
| `cleaning_cloth` | 清洁布 | tool | yes | 擦拭桌面 |
| `glassware_set_dirty` | 脏玻璃器具 | equipment | yes | 待清洗物品 |
| `glassware_set_clean` | 干净玻璃器具 | equipment | yes | 已清洗物品 |
| `waste_liquid_bucket` | 废液桶 | container | yes | 收集失败药剂或废液 |
| `bottle_recycling_box` | 空瓶回收箱 | container | yes | 回收空瓶 |
| `cleaning_brush` | 清洗刷 | tool | yes | 清洗坩埚和瓶子 |
| `soap_bottle` | 清洁液瓶 | container | yes | 清洗用品 |

**可能的交互模式：**

- `turn_on_tap`：打开水龙头
- `turn_off_tap`：关闭水龙头
- `wash_glassware`：清洗玻璃器具
- `dry_glassware`：晾干玻璃器具
- `wipe_table`：擦拭桌面
- `empty_waste_bucket`：清空废液桶
- `recycle_empty_bottle`：回收空瓶
- `clean_tool`：清洗工具
- `inspect_cleanliness`：检查清洁程度

**状态变量建议：**

```json
{
  "tap_state": "on | off",
  "sink_state": "clean | dirty | blocked",
  "glassware_state": "dirty | washing | clean | dry",
  "waste_bucket_state": "empty | half_full | full",
  "cleanup_progress": 0
}
```

---

### 4.7 fireplace_area

**功能说明：**  
壁炉与温控区提供热源、氛围和剧情触发。它可以用于保持房间温暖，也可以作为烧毁草稿、读取炉边信件或深夜独处的叙事点。

**主要元素：**

| Element ID | 中文名称 | 类型 | 可交互 | 说明 |
|---|---|---|---|---|
| `stone_fireplace` | 石质壁炉 | structure | yes | 房间热源 |
| `firewood_stack` | 木柴堆 | resource | yes | 添加燃料 |
| `fireplace_poker` | 拨火棍 | tool | yes | 调整火焰 |
| `ash_bucket` | 灰桶 | container | yes | 清理灰烬 |
| `mantel_shelf` | 壁炉台 | furniture | yes | 放置照片或小物 |
| `mantel_photo` | 壁炉照片 | decor | yes | 叙事物品 |
| `drying_herb_hook` | 草药挂钩 | furniture | yes | 挂草药 |

**可能的交互模式：**

- `light_fireplace`：点燃壁炉
- `extinguish_fireplace`：熄灭壁炉
- `add_firewood`：添加木柴
- `poke_fire`：拨火
- `clean_ash`：清理灰烬
- `warm_hands`：靠近取暖
- `burn_note`：烧毁纸条
- `inspect_mantel_photo`：查看照片
- `hang_drying_herbs`：挂起草药

**状态变量建议：**

```json
{
  "fireplace_state": "off | low | bright | ash_only",
  "firewood_amount": "none | low | enough",
  "ash_state": "clean | some_ash | full",
  "room_warmth": "cold | comfortable | warm"
}
```

---

### 4.8 decor_and_lore_area

**功能说明：**  
装饰与叙事信息区负责世界观表达。它包含墙面图谱、窗户、植物、奖状、仪器和旧书。大部分元素不是高频交互物，但可以触发观察、回忆、线索发现和氛围变化。

**主要元素：**

| Element ID | 中文名称 | 类型 | 可交互 | 说明 |
|---|---|---|---|---|
| `gothic_window` | 哥特式拱窗 | structure | yes | 提供外部光源 |
| `window_sill_plants` | 窗台植物 | plant | yes | 可浇水 |
| `potion_diagram_frame` | 魔药图谱 | information | yes | 可查看 |
| `alchemy_symbol_chart` | 炼金符号图 | information | yes | 可查看 |
| `brass_astrolabe` | 黄铜星盘 | tool | yes | 装饰和研究工具 |
| `wall_clock_magic` | 魔法墙钟 | tool | yes | 显示时间或课程提醒 |
| `certificate_frame` | 教师证书 | decor | yes | 叙事信息 |
| `old_portrait_frame` | 旧肖像画 | decor | yes | 可触发回忆 |
| `magical_potted_plant` | 魔法盆栽 | plant | yes | 可浇水或观察 |
| `glowing_crystal` | 发光水晶 | magic_object | yes | 氛围光源 |
| `red_runner_rug` | 红色长地毯 | decor | no | 引导动线 |

**可能的交互模式：**

- `look_out_window`：看向窗外
- `open_window`：打开窗户
- `close_window`：关闭窗户
- `water_plant`：浇植物
- `inspect_diagram`：查看图谱
- `inspect_symbol_chart`：查看符号图
- `adjust_astrolabe`：调整星盘
- `check_magic_clock`：查看魔法钟
- `inspect_certificate`：查看证书
- `inspect_portrait`：查看肖像画
- `observe_crystal_glow`：观察水晶光芒

**状态变量建议：**

```json
{
  "window_state": "closed | open",
  "plant_state": "healthy | thirsty | withered | glowing",
  "clock_state": "normal | class_reminder | midnight_alert",
  "crystal_state": "dim | glowing | flickering"
}
```

---

## 5. 全局交互模式

下面是整个房间可以支持的高层行为。它们可以由多个 area 和 element 组合完成。

### 5.1 日常办公行为

| 行为 ID | 行为名称 | 涉及 Area | 说明 |
|---|---|---|---|
| `prepare_lesson` | 备课 | teacher_work_area | 查看课程计划并写教学笔记 |
| `grade_student_homework` | 批改作业 | teacher_work_area | 批改学生提交的羊皮纸作业 |
| `write_private_note` | 写私人笔记 | teacher_work_area | 记录想法或秘密研究 |
| `read_reference_book` | 查阅书籍 | teacher_work_area, ingredient_storage_area | 查找配方或历史资料 |
| `send_sealed_letter` | 准备寄信 | teacher_work_area, entrance_area | 写信、封蜡、放到门边 |

### 5.2 魔药研究行为

| 行为 ID | 行为名称 | 涉及 Area | 说明 |
|---|---|---|---|
| `collect_ingredients` | 收集材料 | ingredient_storage_area | 找到并取出指定材料 |
| `weigh_ingredient` | 称量材料 | potion_brewing_area | 使用天平控制剂量 |
| `prepare_ingredient` | 处理材料 | potion_brewing_area | 切割、研磨或混合材料 |
| `brew_potion` | 熬制魔药 | potion_brewing_area | 控制火候、加入材料、搅拌 |
| `observe_potion_reaction` | 观察反应 | potion_brewing_area | 检查颜色、气泡和稳定性 |
| `bottle_and_label_potion` | 装瓶贴标 | potion_brewing_area, ingredient_storage_area | 保存成品 |

### 5.3 清洁收尾行为

| 行为 ID | 行为名称 | 涉及 Area | 说明 |
|---|---|---|---|
| `clean_brewing_tools` | 清洗器具 | cleanup_area | 清洗坩埚、烧瓶、试管 |
| `dispose_waste_liquid` | 处理废液 | cleanup_area | 倒入废液桶或特殊容器 |
| `recycle_empty_bottles` | 回收空瓶 | cleanup_area | 放入回收箱 |
| `restore_workbench` | 恢复实验台 | potion_brewing_area | 把工具和材料归位 |
| `final_room_check` | 离开前检查 | all | 检查火焰、门锁、材料柜和灯光 |

### 5.4 社交与叙事行为

| 行为 ID | 行为名称 | 涉及 Area | 说明 |
|---|---|---|---|
| `receive_student_visit` | 接待学生 | entrance_area, student_consult_area | 学生来访，教师邀请进入 |
| `answer_student_question` | 回答学生问题 | student_consult_area | 简短问答或辅导 |
| `assign_extra_reading` | 布置额外阅读 | student_consult_area, teacher_work_area | 给学生一本书或纸条 |
| `discover_anonymous_note` | 发现匿名纸条 | entrance_area | 触发轻悬疑事件 |
| `investigate_missing_ingredient` | 调查材料缺失 | ingredient_storage_area | 查找缺失材料原因 |
| `react_to_potion_failure` | 处理药剂失败 | potion_brewing_area, cleanup_area | 药剂冒烟或变色后处理 |

---

## 6. 推荐单人行为链

### 6.1 普通工作日循环

1. 教师从 `entrance_area` 进入房间。
2. 教师关闭木门。
3. 教师挂起长袍。
4. 教师点亮墙灯和桌灯。
5. 教师走到 `teacher_work_area`。
6. 教师坐下并查看课程计划。
7. 教师批改一部分学生作业。
8. 教师走到 `ingredient_storage_area`。
9. 教师查找并取出课堂示范材料。
10. 教师走到 `potion_brewing_area`。
11. 教师点燃火焰并开始熬制魔药。
12. 教师观察药剂颜色。
13. 教师回到书桌记录实验结果。
14. 教师接待一位来访学生。
15. 教师在会客桌回答问题。
16. 学生离开。
17. 教师清洗器具。
18. 教师整理材料柜。
19. 教师熄灭火焰和灯光。
20. 教师锁门离开。

### 6.2 深夜研究循环

1. 教师进入办公室。
2. 教师只点亮桌灯和几根蜡烛。
3. 教师打开锁住的稀有材料柜。
4. 教师取出特殊材料。
5. 教师翻开旧配方书。
6. 教师在坩埚中加入材料。
7. 药剂出现异常蓝绿色微光。
8. 教师记录反应。
9. 教师发现材料标签和记录不一致。
10. 教师检查库存卷轴。
11. 教师写下一封密封信。
12. 教师把信放在门边。
13. 教师清理实验台。
14. 教师锁上材料柜。
15. 教师离开。

---

## 7. 轻剧情事件设计

| 事件 ID | 事件名称 | 触发条件 | 影响 |
|---|---|---|---|
| `event_potion_color_shift` | 药剂突然变色 | brewing_progress > 60 且火候过高 | potion_stability 变为 unstable |
| `event_missing_ingredient` | 材料缺失 | 搜索指定材料失败 | inventory_state 变为 missing_item |
| `event_label_falls_off` | 标签脱落 | 打开某个材料罐时触发 | label_state 变为 damaged |
| `event_student_knock` | 学生敲门 | consultation 时间段 | visitor_state 变为 waiting |
| `event_anonymous_note` | 匿名纸条出现 | 教师离开后或清晨进入时 | visitor_note_state 变为 unread |
| `event_clock_class_reminder` | 课程提醒 | 到达上课时间 | clock_state 变为 class_reminder |
| `event_fireplace_low` | 壁炉火变弱 | firewood_amount 为 low | room_warmth 变为 cold |
| `event_crystal_flicker` | 水晶闪烁 | 魔药失败或深夜研究 | crystal_state 变为 flickering |
| `event_plant_glow` | 魔法植物发光 | 药剂蒸汽接触植物 | plant_state 变为 glowing |

---

## 8. 初始状态建议

```json
{
  "room_id": "potions_teacher_office",
  "time_of_day": "late_afternoon",
  "lighting": "warm_candlelight",
  "door_state": "closed",
  "teacher_location": "entrance_area",
  "active_area": "none",
  "visitor_state": "none",
  "cauldron_state": "empty",
  "flame_state": "off",
  "homework_state": "ungraded",
  "lesson_plan_state": "draft",
  "rare_cabinet_state": "locked",
  "inventory_state": "normal",
  "sink_state": "clean",
  "fireplace_state": "low",
  "room_warmth": "comfortable"
}
```

---

## 9. Agent 可用的目标示例

### 目标 1：完成课前准备

```json
{
  "goal_id": "prepare_for_potions_class",
  "goal_description": "教师需要准备下一节魔药课的示范材料和课程笔记。",
  "required_actions": [
    "read_lesson_plan",
    "collect_ingredients",
    "weigh_ingredient",
    "brew_potion",
    "bottle_and_label_potion",
    "write_lesson_plan"
  ],
  "success_condition": "lesson_plan_state == complete && cauldron_state == finished"
}
```

### 目标 2：处理失败的魔药实验

```json
{
  "goal_id": "handle_failed_potion",
  "goal_description": "坩埚中的药剂变得不稳定，教师需要安全处理。",
  "required_actions": [
    "observe_potion_reaction",
    "extinguish_flame",
    "discard_failed_potion",
    "clean_cauldron",
    "write_experiment_note"
  ],
  "success_condition": "potion_stability == stable || cauldron_state == empty"
}
```

### 目标 3：接待来访学生

```json
{
  "goal_id": "student_consultation",
  "goal_description": "一名学生来询问魔药作业问题。教师需要完成一次简短答疑。",
  "required_actions": [
    "knock_door",
    "open_door",
    "invite_student_in",
    "sit_for_consultation",
    "answer_student_question",
    "assign_extra_task",
    "end_consultation"
  ],
  "success_condition": "consultation_state == finished && visitor_state == left"
}
```

---

## 10. 设计落地建议

这个场景的第一版应该控制复杂度。建议保留 8 个 area，但每个 area 只启用一部分核心交互。这样可以先完成可运行的单人叙事循环。

第一版最重要的元素是：

- 厚重木门
- 长袍架
- 教师书桌
- 高背椅
- 羽毛笔和羊皮纸
- 学生作业
- 坩埚
- 火焰
- 药剂瓶
- 天平
- 研钵
- 材料柜
- 稀有材料锁柜
- 小圆桌
- 石质水槽
- 壁炉
- 魔法墙钟

第一版最重要的交互是：

- 进入房间
- 点灯
- 坐下
- 阅读
- 写字
- 批改作业
- 取材料
- 熬制魔药
- 观察药剂
- 装瓶贴标
- 清洗器具
- 接待学生
- 锁门离开

---

## 11. 简化版 JSON 结构

下面是可以作为环境配置入口的简化结构。

```json
{
  "scene_id": "potions_teacher_office",
  "scene_name": "魔药课教师办公室",
  "scene_type": "single_agent_narrative_room",
  "areas": [
    "entrance_area",
    "teacher_work_area",
    "potion_brewing_area",
    "ingredient_storage_area",
    "student_consult_area",
    "cleanup_area",
    "fireplace_area",
    "decor_and_lore_area"
  ],
  "primary_agent": "potions_teacher",
  "secondary_agents": [
    "student_visitor",
    "owl_messenger"
  ],
  "core_loop": [
    "enter_room",
    "prepare_lesson",
    "collect_ingredients",
    "brew_potion",
    "record_result",
    "grade_homework",
    "clean_tools",
    "lock_room"
  ]
}
```

---

## 12. 总结

魔药课教师办公室是一个适合单人叙事模拟的魔法室内场景。它的核心优势是功能清晰、氛围强、交互密度高。教师可以在办公、研究、整理、接待和收尾之间形成自然循环。场景也能轻松加入小型剧情事件，比如药剂异常、材料缺失、学生来访和匿名信件。

这个场景可以作为从现实办公室过渡到魔法世界场景的第一版模板。它保留了办公室的结构，又加入了魔药研究的独特行为。
