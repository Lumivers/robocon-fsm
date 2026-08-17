#include "robot_serial/serial_driver_node.hpp"

#include <rclcpp/logging.hpp>
#include <rclcpp/qos.hpp>

#include <cmath>
#include <chrono>
#include <cstdint>
#include <functional>
#include <memory>
#include <thread>
#include <vector>

namespace robot_serial
{

SerialDriverNode::SerialDriverNode(const rclcpp::NodeOptions & options)
: Node("serial_driver_node", options)
{
  RCLCPP_INFO(get_logger(), "Initializing SerialDriverNode (Robocon Generic Serial Driver)");

  loadParameters();
  openSerialPort();

  // ── 注册 ROS 订阅与发布 ──
  cmd_sub_ = this->create_subscription<robot_serial::msg::Command>(
    "command", rclcpp::SensorDataQoS(),
    std::bind(&SerialDriverNode::onCommandCallback, this, std::placeholders::_1));

  odom_sub_ = this->create_subscription<nav_msgs::msg::Odometry>(
    "odometry", rclcpp::SensorDataQoS(),
    std::bind(&SerialDriverNode::onOdometryCallback, this, std::placeholders::_1));

  ack_pub_ = this->create_publisher<robot_serial::msg::Ack>(
    "robot_status", rclcpp::SensorDataQoS());

  // ── 启动后台接收线程 ──
  receive_thread_ = std::thread(&SerialDriverNode::receiveLoop, this);

  // ── 50Hz 定时发送 (20ms) ──
  send_timer_ = this->create_wall_timer(
    std::chrono::milliseconds(20),
    std::bind(&SerialDriverNode::sendPacket, this));
}

SerialDriverNode::~SerialDriverNode()
{
  if (receive_thread_.joinable()) {
    receive_thread_.join();
  }
  if (serial_driver_ && serial_driver_->port()->is_open()) {
    serial_driver_->port()->close();
  }
  if (io_ctx_) {
    io_ctx_->waitForExit();
  }
}

void SerialDriverNode::loadParameters()
{
  using FlowControl = drivers::serial_driver::FlowControl;
  using Parity = drivers::serial_driver::Parity;
  using StopBits = drivers::serial_driver::StopBits;

  device_name_ = declare_parameter<std::string>("device_name", "/dev/ttyUSB0");
  auto baud_rate = declare_parameter<int>("baud_rate", 115200);
  odom_offset_x_ = declare_parameter<double>("odom_offset_x", 0.0);
  odom_offset_y_ = declare_parameter<double>("odom_offset_y", 0.0);

  auto fc_str = declare_parameter<std::string>("flow_control", "none");
  auto pt_str = declare_parameter<std::string>("parity", "none");
  auto sb_str = declare_parameter<std::string>("stop_bits", "1");

  auto fc = FlowControl::NONE;
  if (fc_str == "hardware") fc = FlowControl::HARDWARE;
  else if (fc_str == "software") fc = FlowControl::SOFTWARE;

  auto pt = Parity::NONE;
  if (pt_str == "odd") pt = Parity::ODD;
  else if (pt_str == "even") pt = Parity::EVEN;

  auto sb = StopBits::ONE;
  if (sb_str == "1.5") sb = StopBits::ONE_POINT_FIVE;
  else if (sb_str == "2" || sb_str == "2.0") sb = StopBits::TWO;

  device_config_ = std::make_unique<drivers::serial_driver::SerialPortConfig>(
    baud_rate, fc, pt, sb);
}

void SerialDriverNode::openSerialPort()
{
  io_ctx_ = std::make_unique<IoContext>(2);
  serial_driver_ = std::make_unique<drivers::serial_driver::SerialDriver>(*io_ctx_);

  try {
    serial_driver_->init_port(device_name_, *device_config_);
    if (!serial_driver_->port()->is_open()) {
      serial_driver_->port()->open();
    }
    RCLCPP_INFO(get_logger(), "Serial port %s opened successfully", device_name_.c_str());
  } catch (const std::exception & ex) {
    RCLCPP_ERROR(get_logger(), "Failed to open serial port %s: %s",
      device_name_.c_str(), ex.what());
    throw;
  }
}

void SerialDriverNode::onCommandCallback(const robot_serial::msg::Command::SharedPtr msg)
{
  current_send_packet_.target_x = msg->target_x;
  current_send_packet_.target_y = msg->target_y;
  current_send_packet_.target_yaw = msg->target_yaw;
  current_send_packet_.action_code = msg->action_code;
  current_send_packet_.action_data = msg->action_data;
  has_command_ = true;
}

void SerialDriverNode::onOdometryCallback(const nav_msgs::msg::Odometry::SharedPtr msg)
{
  double qz = msg->pose.pose.orientation.z;
  double qw = msg->pose.pose.orientation.w;
  float yaw = static_cast<float>(std::atan2(2.0 * qw * qz, 1.0 - 2.0 * qz * qz));

  double rx = msg->pose.pose.position.x;
  double ry = msg->pose.pose.position.y;

  // 考虑传感器到几何中心的偏移变换
  current_send_packet_.current_x = static_cast<float>(
    rx - odom_offset_x_ * std::cos(yaw) + odom_offset_y_ * std::sin(yaw));
  current_send_packet_.current_y = static_cast<float>(
    ry - odom_offset_x_ * std::sin(yaw) - odom_offset_y_ * std::cos(yaw));
  current_send_packet_.current_yaw = yaw;
}

void SerialDriverNode::sendPacket()
{
  if (!has_command_ || !serial_driver_ || !serial_driver_->port()->is_open()) {
    return;
  }

  try {
    auto buffer = serializePacket(current_send_packet_);
    serial_driver_->port()->send(buffer);
  } catch (const std::exception & ex) {
    RCLCPP_ERROR(get_logger(), "Serial send error: %s", ex.what());
    reopenPort();
  }
}

void SerialDriverNode::receiveLoop()
{
  std::vector<uint8_t> single_byte(1);
  const size_t PACKET_SIZE = sizeof(ReceivePacket);
  std::vector<uint8_t> frame_buffer(PACKET_SIZE);

  while (rclcpp::ok()) {
    try {
      // 1. 寻找首字节 0xAA
      serial_driver_->port()->receive(single_byte);
      if (single_byte[0] != FRAME_HEADER_0) {
        continue;
      }
      frame_buffer[0] = FRAME_HEADER_0;

      // 2. 读第二字节 0x56
      serial_driver_->port()->receive(single_byte);
      if (single_byte[0] != FRAME_HEADER_ACK) {
        continue;
      }
      frame_buffer[1] = FRAME_HEADER_ACK;

      // 3. 读取剩余负载
      std::vector<uint8_t> rest(PACKET_SIZE - 2);
      serial_driver_->port()->receive(rest);
      std::memcpy(frame_buffer.data() + 2, rest.data(), rest.size());

      // 4. 解析与 CRC 校验
      ReceivePacket pkt{};
      if (parseReceivePacket(frame_buffer.data(), frame_buffer.size(), pkt)) {
        auto msg = std::make_shared<robot_serial::msg::Ack>();
        msg->last_cmd_code = pkt.last_cmd_code;
        msg->status = pkt.status;
        msg->status_flags = pkt.status_flags;
        msg->feedback_data = pkt.feedback_data;
        ack_pub_->publish(*msg);
      } else {
        RCLCPP_WARN_THROTTLE(
          get_logger(), *get_clock(), 5000,
          "CRC check failed on received packet, dropping frame.");
      }

    } catch (const std::exception & ex) {
      RCLCPP_ERROR_THROTTLE(
        get_logger(), *get_clock(), 5000, "Serial read error: %s", ex.what());
      reopenPort();
    }
  }
}

void SerialDriverNode::reopenPort()
{
  RCLCPP_WARN(get_logger(), "Attempting to reopen serial port...");
  try {
    if (serial_driver_ && serial_driver_->port()->is_open()) {
      serial_driver_->port()->close();
    }
    if (serial_driver_) {
      serial_driver_->port()->open();
    }
    RCLCPP_INFO(get_logger(), "Serial port reopened successfully");
  } catch (const std::exception & ex) {
    RCLCPP_ERROR(get_logger(), "Failed to reopen port: %s", ex.what());
    if (rclcpp::ok()) {
      rclcpp::sleep_for(std::chrono::seconds(1));
    }
  }
}

}  // namespace robot_serial

#include "rclcpp_components/register_node_macro.hpp"
RCLCPP_COMPONENTS_REGISTER_NODE(robot_serial::SerialDriverNode)
