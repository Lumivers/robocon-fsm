from setuptools import setup, find_packages

package_name = "robocon_fsm"

setup(
    name=package_name,
    version="1.0.0",
    description="Universal Python Async FSM decision framework for Robocon/RoboMaster competition robots.",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", ["package.xml"]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Robocon Developer",
    maintainer_email="robocon@developer.com",
    license="Apache-2.0",
    python_requires=">=3.8",
)
