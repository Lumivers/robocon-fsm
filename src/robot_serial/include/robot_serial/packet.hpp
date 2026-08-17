#ifndef ROBOT_SERIAL__PACKET_HPP_
#define ROBOT_SERIAL__PACKET_HPP_

#include <cstdint>
#include <cstring>
#include <vector>

#include "robot_serial/crc.hpp"

namespace robot_serial
{

// ── 帧头定义 ──
constexpr uint8_t FRAME_HEADER_0 = 0xAA;
constexpr uint8_t FRAME_HEADER_CMD = 0x55;  // 指令帧
constexpr uint8_t FRAME_HEADER_ACK = 0x56;  // 状态确认帧

#pragma pack(push, 1)

/**
 * @brief 上位机 -> 下位机 发送数据包
 */
struct SendPacket
{
  uint8_t header[2] = {FRAME_HEADER_0, FRAME_HEADER_CMD};
  
  // 当前机器人在场地上的雷达/里程计位姿 (用于下位机闭环校准)
  float current_x = 0.0f;
  float current_y = 0.0f;
  float current_yaw = 0.0f;

  // 导航目标位姿
  float target_x = 0.0f;
  float target_y = 0.0f;
  float target_yaw = 0.0f;

  // 通用机构控制指令
  uint8_t action_code = 0;
  uint32_t action_data = 0;

  // 校验码 (CRC16)
  uint16_t checksum = 0;
};

/**
 * @brief 下位机 -> 上位机 回传数据包
 */
struct ReceivePacket
{
  uint8_t header[2];       // 应匹配 {FRAME_HEADER_0, FRAME_HEADER_ACK}
  uint8_t last_cmd_code;   // 响应的功能码
  uint8_t status;          // 0: IDLE, 1: RUNNING, 2: DONE, 3: ERROR
  uint16_t status_flags;   // 传感器状态与微动开关掩码
  float feedback_data;     // 传感器测距/速度/位置反馈
  uint16_t checksum;       // 校验码 (CRC16)
};

#pragma pack(pop)

// ── 序列化与反序列化工具函数 ──

inline std::vector<uint8_t> serializePacket(SendPacket & pkt)
{
  pkt.checksum = CRC16::calcCRC16(reinterpret_cast<const uint8_t *>(&pkt), sizeof(SendPacket) - sizeof(uint16_t));
  std::vector<uint8_t> buffer(sizeof(SendPacket));
  std::memcpy(buffer.data(), &pkt, sizeof(SendPacket));
  return buffer;
}

inline bool parseReceivePacket(const uint8_t * data, size_t length, ReceivePacket & out_pkt)
{
  if (length < sizeof(ReceivePacket)) {
    return false;
  }
  std::memcpy(&out_pkt, data, sizeof(ReceivePacket));
  
  // 校验 CRC
  uint16_t expected_crc = CRC16::calcCRC16(data, sizeof(ReceivePacket) - sizeof(uint16_t));
  return out_pkt.checksum == expected_crc;
}

}  // namespace robot_serial

#endif  // ROBOT_SERIAL__PACKET_HPP_
