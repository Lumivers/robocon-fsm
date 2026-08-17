# 上位机向下位机下发的通用控制指令
float32 target_x       # 导航目标点 X (米)
float32 target_y       # 导航目标点 Y (米)
float32 target_yaw     # 导航目标朝向 Yaw (弧度)

uint8 action_code      # 机构功能码 (如 0x01:抓取, 0x02:释放, 0x03:发射, 0x00:无动作)
uint32 action_data     # 动作参数 (如电机转速、角度、目标槽位编号等)