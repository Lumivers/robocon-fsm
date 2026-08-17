# 下位机向上位机回传的通用状态与确认
uint8 last_cmd_code    # 响应的功能码
uint8 status           # 状态码 (0: IDLE, 1: RUNNING, 2: DONE, 3: ERROR)
uint16 status_flags    # 状态掩码 (各传感器/微动开关/状态位)
float32 feedback_data  # 传感器读数或位置反馈