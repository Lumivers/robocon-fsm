"""robot_serial 通用串口驱动 launch 文件."""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    config = os.path.join(
        get_package_share_directory('robot_serial'),
        'config',
        'serial_driver.yaml',
    )

    return LaunchDescription([
        Node(
            package='robot_serial',
            executable='serial_driver_node',
            name='serial_driver_node',
            parameters=[config],
            output='screen',
        ),
    ])
