from setuptools import setup
from glob import glob

package_name = "ee3033_project"
setup(
    name=package_name, version="0.3.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml", "README_中文.md", "LICENSE"]),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
        ("share/" + package_name + "/config", glob("config/*.yaml") + glob("config/*.xml")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="EE3033 project group", maintainer_email="student@example.com",
    description="Autonomous mapping, target search, location reporting and return.",
    license="MIT",
    entry_points={"console_scripts": [
        "auto_mapper = ee3033_project.auto_mapper:main",
        "obstacle_detector = ee3033_project.obstacle_detector:main",
        "mock_robot = ee3033_project.mock_robot:main",
        "mission_manager = ee3033_project.mission_manager:main",
        "mock_map = ee3033_project.mock_map:main",
        "test_target_publisher = ee3033_project.test_target_publisher:main",
        "target_localizer = ee3033_project.target_localizer:main",
        "preflight_check = ee3033_project.preflight_check:main",
    ]},
)
