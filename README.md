# CRESTA: A Cognitivist Robot Execution framework for Semantic-driven Task Awareness
## Overview
CRESTA is a skill-based robot control framework addressing Task Awareness built on top of ROS. It brings together:
- Explicit knowledge representation: i) uses a custom world model so that all robot capabilities, object types,
and world relations are openly encoded; ii) skills are parameterized, with human-readable pre-, hold- and
post-conditions.
- Layered, hybrid deliberative–reactive control: i) at the top level it automatically generates a PDDL planning
domain and problem from the current world model, calls a planner, then manages the resulting plan for execution;
ii) at the lower level, reactive primitives (e.g. motor commands, sensor feedbacks) tick at high frequency,
checking pre-, hold-, post-conditions and allowing fast preemption or failure recovery.
- Modularity and flexibility: the architecture aims to be easily configurable, and its base modules aims to be
expandable with custom plugins for ontology, reasoning, perception, and low-level control.

The repository contains a package for each component of the system (plus some utilities):
``` 
  root/ 
  ├── README.md 
  ├── CRESTA Task Manager (cresta_manager)
  ├── CRESTA World Model (cresta_world_model)
  │ ├── Ontology
  │ │  └── Plugins 
  │ └── Reasoner 
  │ │  └── Plugins
  ├── CRESTA Perception (cresta_perception)
  │ └── Plugins
  ├── CRESTA Action Awareness (cresta_action_awareness)
  ├── CRESTA msgs (cresta_msgs)
  └── .gitignore 
```  
<!-- ├── CRESTA Actions Plugin
    ├── CRESTA GUI
-->


## Requirements 
To use CRESTA you must have **ROS** installed on your machine (choose the correct branch according to your ROS distribution). 
You also need pip to install python dependencies:
- Unified Planning ( [AIPlan4EU Unified Planning](https://github.com/aiplan4eu/unified-planning) )
- JSON 

## Task Configuration 
**TODO**


## How to launch CRESTA 
The user should launch his/her plugins developed, which are linked to the framework and configured in the task configuration files (see [Task Configuration](#task-configuration)).

Each component package has its own launch files to be executed (you can use ```roslaunch``` or ```mon launch```). 
If you installed the requirements in a python virtual environment, remember to insert it into the ```PYTHONPATH```: 
```
export PYTHONPATH=/home/<user>/<path_to_virtual_environment>/lib/python3.8/site-packages:$PYTHONPATH
```

The following is a list of the main ones: 
```
- mon launch cresta_world_model cresta_world_model.launch 
- mon launch cresta_world_model cresta_reasoner.launch  
- mon launch cresta_world_model cresta_ontology.launch  
- mon launch cresta_perception cresta_perception.launch  
- mon launch cresta_manager cresta_manager.launch   
- mon launch cresta_action_awareness action_awareness.launch
```

For communicating the task name to the Task Manager: 
```
rosservice call /tttask_manager/tttask/set_tttask "tt_task:
	task_id: '<task_id>'
	task_name: '<task_name>' 
	success: 0"
```

## Plugin Configuration 
TODO

