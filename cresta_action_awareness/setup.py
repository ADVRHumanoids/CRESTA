import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'cresta_action_awareness'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name, package_name + "/core", package_name + "/nodes", package_name + "/ros", package_name + "/utils"],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # Include all launch files.
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py', recursive=True)),
        (os.path.join('share', package_name, 'configs'), glob('configs/**/*', recursive=True)),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    #tests_require=['pytest'],
    maintainer="Damiano Gasperini",
    maintainer_email="damiano.gasperini@iit.it",
    description="TODO: Package description",
    license="PRIVATE",
    entry_points={
        'console_scripts': [
            f'cresta_action_awareness_node = {package_name}.nodes.cresta_action_awareness_node:main', 
        ],
    },
)

 
 
 
 
