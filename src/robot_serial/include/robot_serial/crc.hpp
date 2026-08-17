#ifndef ROBOT_SERIAL__CRC_HPP_
#define ROBOT_SERIAL__CRC_HPP_

#include <cstdint>
#include <cstddef>

namespace robot_serial
{

class CRC16
{
public:
  static uint16_t calcCRC16(const uint8_t * data, uint16_t length);
  static bool verifyCRC16(const uint8_t * data, uint16_t length);
  static void appendCRC16(uint8_t * data, uint16_t length);
};

}  // namespace robot_serial

#endif  // ROBOT_SERIAL__CRC_HPP_
