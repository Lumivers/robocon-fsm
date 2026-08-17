#ifndef ROBOT_SERIAL__SERIAL_DRIVER_NODE_HPP_
#define ROBOT_SERIAL__SERIAL_DRIVER_NODE_HPP_

#include <rclcpp/rclcpp.hpp>
#include <rclcpp/publisher.hpp>
#include <rclcpp/subscription.hpp>
#include <nav_msgs/msg/odometry.hpp>
#include <serial_driver/serial_driver.hpp>

#include <memory>
#include <string>
#include <thread>
#include <vector>

#include "robot_serial/msg/command.hpp"
#include "robot_serial/msg/ack.hpp"
#include "robot_serial/packet.hpp"

namespace robot_serial
{

class SerialDriverNode : public rclcpp::Node
{
public:
  explicit SerialDriverNode(const rclcpp::NodeOptions & options = rclcpp::NodeOptions());
  ~SerialDriverNode() override;

private:
  // ── 初始化与参数加载 ──
  void loadParameters();
  void openSerialPort();

  // ── 串口接收线程与发送 ──
  void receiveLoop();
  void sendPacket();

  // ── ROS 订阅回调 ──
  void onCommandCallback(const robot_serial::msg::Command::SharedPtr msg);
  void onOdometryCallback(const nav_msgs::msg::Odometry::SharedPtr msg);

  // ── 串口异常恢复 ──
  void reopenPort();

  // ── 串口资源 ──
  std::unique_ptr<IoContext> io_ctx_;
  std::unique_ptr<drivers::serial_driver::SerialDriver> serial_driver_;
  std::string device_name_;

  // ── 坐标修正参数 (雷达到底盘几何中心偏移量) ──
  double odom_offset_x_ = 0.0;
  double odom_offset_y_ = 0.0;

  // ── 缓存状态 ──
  SendPacket current_send_packet_{};
  bool has_command_ = false;

  // ── ROS 订阅与发布 ──
  rclcpp::Subscription<robot_serial::msg::Command>::SharedPtr cmd_sub_;
  rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr odom_sub_;
  rclcpp::Publisher<robot_serial::msg::Ack>::SharedPtr ack_pub_;

  // ── 线程与定时器 ──
  std::thread receive_thread_;
  rclcpp::TimerBase::SharedPtr send_timer_;
};

}  // namespace robot_serial

#endif  // ROBOT_SERIAL__SERIAL_DRIVER_NODE_HPP_
