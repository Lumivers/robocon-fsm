cmake_minimum_required(VERSION 3.10)
project(robot_serial)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_definitions(-Wall -Werror)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

#######################
## Find dependencies ##
#######################

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_auto REQUIRED)
find_package(ament_cmake_ros REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(serial_driver REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_components REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(rosidl_default_generators REQUIRED)

###########################
## Generate Custom Msgs  ##
###########################

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/Command.msg"
  "msg/Ack.msg"
)

###########
## Build ##
###########

set(LIB_NAME "${PROJECT_NAME}_lib")

ament_auto_add_library(${LIB_NAME} SHARED
  src/serial_driver_node.cpp
  src/crc.cpp
)

target_include_directories(${LIB_NAME} PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

rosidl_get_typesupport_target(cpp_typesupport_target ${PROJECT_NAME} "rosidl_typesupport_cpp")
target_link_libraries(${LIB_NAME} "${cpp_typesupport_target}")

ament_target_dependencies(${LIB_NAME}
  rclcpp
  rclcpp_components
  geometry_msgs
  nav_msgs
  std_msgs
  serial_driver
)

rclcpp_components_register_node(${LIB_NAME}
  PLUGIN robot_serial::SerialDriverNode
  EXECUTABLE serial_driver_node)

#############
## Testing ##
#############

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  list(APPEND AMENT_LINT_AUTO_EXCLUDE
    ament_cmake_copyright
    ament_cmake_uncrustify
  )
  ament_lint_auto_find_test_dependencies()
endif()

#############
## Install ##
#############
ament_auto_package(
  INSTALL_TO_SHARE
  config
  launch
)
