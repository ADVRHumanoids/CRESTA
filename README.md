# CRESTA

### A Cognitivist Robot Execution framework for Semantic-driven Task Awareness

CRESTA is a modular ROS framework for building robots that do more than execute a fixed sequence: they maintain a semantic view of the world, reason and plan from the current state, monitor action execution and task state, and replan when reality changes.

Task knowledge is kept in readable JSON files. Perception, ontology, and reasoning capabilities are connected as plugins, so a robot can be adapted to new sensors, knowledge sources, and domains without rewriting the whole stack.

The CRESTA paper is available in [Robotics and Autonomous Systems](https://www.sciencedirect.com/science/article/pii/S0921889025004002).

## What is inside?

| Package | Responsibility |
| --- | --- |
| `cresta_manager` | Loads task and action configurations, creates a Unified Planning problem, computes a plan, and coordinates task execution. |
| `cresta_world_model` | Maintains the live knowledge base and routes work to ontology and reasoner plugins. Includes a procedural ontology and a rule-based default reasoner. |
| `cresta_perception` | Routes perception requests to perception plugins. Includes a YOLO segmentation plugin and a plugin template. |
| `cresta_action_awareness` | Executes the plan through the robot action interface, checks action conditions, reports success or failure, and triggers replanning when needed. |
| `cresta_msgs` | Shared ROS messages and services for tasks, plans, actions, and detected objects. |

The repository is organized as follows:

```text
CRESTA/
├── README.md
├── LICENSE
├── cresta_manager/                 # Task Manager
│   ├── configs/
│   │   ├── action_configs/         # Reusable action definitions
│   │   └── task_configs/           # Task-specific configurations
│   ├── launch/
│   ├── nodes/
│   └── scripts/cresta_manager/
│       ├── core/                   # Task Awareness (task planning) 
│       └── ros/                    # Task Manager 
│ 
├── cresta_world_model/             # World Model
│   ├── config/                     # Reasoning rules
│   ├── launch/
│   ├── nodes/
│   └── scripts/cresta_world_model/
│       ├── core/                   # Knowledge Base
│       └── ros/                    # Ontology and Reasoner managers with plugins
│            
├── cresta_perception/              # Perception 
│   ├── launch/
│   ├── nodes/
│   ├── weights/                    # Model weights (e.g. YOLO weights)
│   └── scripts/cresta_perception/
│       ├── core/ 
│       ├── utils/                   
│       └── ros/                    # Perception manager with plugins
│
├── cresta_action_awareness/        # Action Awareness
│   ├── launch/
│   ├── nodes/
│   └── scripts/cresta_action_awareness/
│       ├── core/ 
│       └── ros/                    # Action execution and monitoring 
│
└── cresta_msgs/                     
    ├── msg/                        # ROS messages 
    └── srv/                        # ROS services 
    └── scripts/cresta_msgs/ 
        └── utils/                  # Message constructors 
```

The repository also includes:

- an example door task in `cresta_manager/configs/task_configs/door_task_test_cresta.json`;
- the action model used by the planner in `cresta_manager/configs/action_configs/actions.json`;
- rules for the default reasoner in `cresta_world_model/config/reasoning_rules.json`;
- a YOLO 11 segmentation model and its configurable launch file.

## How CRESTA works

CRESTA starts from a task description containing the actions the robot can perform, the objects and facts that describe its world, and the goal it should achieve.

The World Model keeps this knowledge up to date using perception, ontology, and reasoner plugins. The Task Manager uses the current knowledge to create a planning problem and find a sequence of actions that reaches the goal.

During execution, Action Awareness monitors each action and its expected conditions. If an action fails or the world changes, CRESTA updates its knowledge and can compute a new plan.

## Requirements and build

CRESTA is a Python-based ROS catkin workspace. Before building it, make sure the following requirements are available:

- **ROS 1 and catkin.** Use the repository branch that matches your ROS distribution.
- **Python 3 and pip.**
- **JSON support.** CRESTA task, action, and reasoning-rule files use JSON. They are read with Python's built-in `json` module, so no separate JSON package is required.
- **Unified Planning.** Install [AIPlan4EU Unified Planning](https://github.com/aiplan4eu/unified-planning) together with a compatible planning engine.
- **ROS dependencies.** Install the dependencies declared in each package's `package.xml`, including `rospy`, `rospkg`, `cv_bridge`, `std_msgs`, and `sensor_msgs`.
- **Perception dependencies.** The included YOLO plugin additionally requires `ultralytics`, OpenCV, and NumPy.

For example, install the Python dependencies used by the planner and included perception plugin with:

```bash
python3 -m pip install unified-planning ultralytics opencv-python numpy
```

Unified Planning requires at least one planning engine. Choose and install the engine appropriate for your application by following the Unified Planning documentation.

From the root of your catkin workspace:

```bash
cd /path/to/catkin_ws
catkin_make
source devel/setup.bash
```

If Python dependencies live in a virtual environment, expose its site-packages before launching ROS:

```bash
export PYTHONPATH=/path/to/venv/lib/python3.x/site-packages:$PYTHONPATH
```

## Configure a task

CRESTA separates reusable action semantics from task-specific world knowledge.

### 1. Define actions

Edit `cresta_manager/configs/action_configs/actions.json`. Each top-level key is an action available to the planner:

```json
{
  "approach": {
    "parameters": {
      "o1": { "type": "Obj" }
    },
    "preconditions": {
      "object_detected": {
        "parameters": {
          "o1": { "type": "Obj" }
        },
        "value": true
      }
    },
    "effects": {
      "approached": {
        "parameters": {
          "o1": { "type": "Obj" }
        },
        "value": true
      }
    }
  }
}
```

- `parameters` declares typed action arguments.
- `preconditions` declares fluent values that must hold before execution.
- `effects` declares the expected fluent values after success.
- `value` may be `true` or `false`.
- A precondition can set `"check_exe": false` when it should be used for planning but not checked by Action Awareness during execution. If `"check_exe": true`, it is then considered as a `holding-condition`.

Parameter names and types must match the corresponding fluent declarations in the task file.

### 2. Define the task

Create `<task_id>.json` under `cresta_manager/configs/task_configs/`. The file is organized into:

| Key | Meaning |
| --- | --- |
| `task_name` | Human-readable/planning problem name. |
| `actions` | Actions enabled for this task; every name must exist in `actions.json`. |
| `objects.types` | Semantic type hierarchy. Use `father` for inheritance and `managed_by.perception` to assign object discovery. |
| `objects.instances` | Known object instances, written as `"instance_name": {"type": "TypeName"}`. Plugins may add live instances. |
| `fluents` | Boolean state variables, their typed parameters, defaults, initial values, sources, and plugin ownership. |
| `goals` | Desired final fluent values, including the logical/quantified form demonstrated by the example task. |
| `simulator` | Reserved space for simulator-specific configuration. |

A typical fluent looks like this:

```json
{
  "opened": {
    "parameters": {
      "o": { "type": "Obj" }
    },
    "type": "bool",
    "default_initialization": false,
    "initialization": null,
    "managed_by": {
      "reasoner": ["default_reasoner"]
    }
  }
}
```

`default_initialization` supplies the planner’s fallback value. `initialization` may be a direct Boolean or a list of assignments such as:

```json
[
  { "parameters": ["door0"], "value": false }
]
```

Use `managed_by` to route dynamic data:

```json
"managed_by": { "perception": ["my_detector"] }
"managed_by": { "ontology": ["my_ontology"] }
"managed_by": { "reasoner": ["my_reasoner"] }
```

The strings in these arrays are plugin identifiers. A manager turns an identifier such as `my_detector` into the exact service prefix `/my_detector`, so the plugin must expose the corresponding service shown below. A perception-managed fluent can also declare `"source": "/my_detector/fluents4wm"`; the World Model subscribes to that `std_msgs/String` topic and applies the JSON updates it receives.

By default the manager reads:

```text
cresta_manager/configs/task_configs/<task_id>.json
cresta_manager/configs/action_configs/actions.json
```

You can override those directories with the private ROS parameters `~tasks_path` and `~actions_path` on the `tttask_mgr` node.

## Implement a plugin

All three plugin families follow the same lifecycle:

1. Start the plugin node before selecting a task.
2. Expose the family-specific `cresta_msgs/ClientToServerString` service.
3. Decode `request.data` with `json.loads(...)`.
4. Process only the objects or fluents assigned by the manager.
5. Publish JSON with `std_msgs/String` for the World Model.
6. Add the plugin identifier to the task’s `managed_by` entry and include its node in a launch file.

Service and output conventions are:

| Plugin family | Required service | Input JSON | Output convention |
| --- | --- | --- | --- |
| Perception | `/<plugin>/set_what_to_perceive` | `{"object_types": [...], "fluents": [...]}` | Publish fluent updates on a topic referenced by the fluent’s `source`; object detectors can publish `cresta_msgs/ObjectStatusList`. |
| Reasoner | `/<plugin>/set_what_to_reason` | A list of fluent names (or action-mode data for a specialized reasoner). | Publish fluent-update JSON on a `fluents4wm` topic, conventionally `/wm_reasoner_mgr/<plugin>/fluents4wm`. |
| Ontology | `/<plugin>/set_what_to_query` | `{ "<fluent>": { "object_types": [...] } }` | Publish on `fluents4wm` and, when discovering objects, `objs4wm`; the procedural implementation shows the currently wired topic names. |

The existing implementations are the best starting points:

- perception skeleton: `cresta_perception/scripts/cresta_perception/ros/perception_plugin_template.py`;
- complete perception example: `cresta_perception/scripts/cresta_perception/ros/yolo_inference.py`;
- reasoner example: `cresta_world_model/scripts/cresta_world_model/ros/default_reasoner_mgr.py`;
- ontology example: `cresta_world_model/scripts/cresta_world_model/ros/procedural_ontology_mgr.py`.

### Perception plugin

For a plugin named `my_detector`, expose:

```python
self.set_service = rospy.Service(
    "/my_detector/set_what_to_perceive",
    ClientToServerString,
    self.set_what_to_perceive,
)
```

The callback receives only the task slice assigned to `my_detector`:

```json
{
  "object_types": ["Door", "Handle"],
  "fluents": ["open_logic_vision"]
}
```

For fluents, publish updates in the common format and set the same topic as `source` in the task configuration:

```json
{
  "open_logic_vision": {
    "initialization": [
      { "parameters": ["door0"], "value": true }
    ]
  }
}
```

For detected objects, follow the YOLO plugin and publish `cresta_msgs/ObjectStatusList`; ontology plugins can translate those observations into semantic instances and relations.

### Reasoner plugin

A reasoner named `my_reasoner` must expose `/my_reasoner/set_what_to_reason`. For ordinary fluent ownership, the request is a JSON list:

```json
["approached", "opened", "homing"]
```

Subscribe to the knowledge base at `/wm_manager/kb/kb_data` and to any action or sensor feedback needed by the rules. Publish inferred state as:

```json
{
  "opened": {
    "initialization": [
      { "parameters": ["door0"], "value": true }
    ]
  }
}
```

The included default reasoner publishes on `/wm_reasoner_mgr/default_reasoner/fluents4wm` and reads rules from `cresta_world_model/config/reasoning_rules.json`. A custom reasoner should use its own matching topic and connect that topic to the World Model in the same way as other fluent sources.

### Ontology plugin

An ontology plugin named `my_ontology` must expose `/my_ontology/set_what_to_query`. The callback receives the fluents assigned to it and the object types to which each property applies:

```json
{
  "isPartof": {
    "object_types": ["Door", "Handle"]
  }
}
```

Publish fluent values using the same `initialization` schema on `fluents4wm`. If the plugin discovers or enriches objects, publish `objs4wm` as a JSON object keyed by instance name:

```json
{
  "door0": {
    "type": "Door",
    "x": 640,
    "y": 360,
    "image": "/path/to/image.jpg"
  }
}
```

The procedural ontology demonstrates both publishers:

```text
/wm_ontology_mgr/procedural_ont/fluents4wm
/wm_ontology_mgr/procedural_ont/objs4wm
```

When adding a new output topic, also connect it to the Knowledge Base (or declare it as a fluent `source`, where applicable); publishing alone does not make the World Model consume it.

## Launch CRESTA

Launch the managers and all plugins required by the selected task. The current components can be started in separate terminals:

```bash
mon launch cresta_world_model cresta_world_model.launch
mon launch cresta_world_model cresta_reasoner.launch
mon launch cresta_world_model cresta_ontology.launch
mon launch cresta_perception cresta_perception.launch
mon launch cresta_manager cresta_manager.launch
mon launch cresta_action_awareness action_awareness.launch
```

Launch perception plugins separately when needed, for example:

```bash
mon launch cresta_perception yolo_inference.launch \
  image_topic:=/camera/color/image_raw \
  camera_info_topic:=/camera/color/camera_info \
  cuda_device:=cpu
```

The included Action Awareness node expects an application-specific action service at `/xbot_actions/call_action_service` and related feedback topics. Provide that robot action adapter before launching Action Awareness.

Finally, select a task. `task_id` must exactly match the task configuration filename without `.json`:

```bash
rosservice call /tttask_manager/tttask/set_tttask "tt_task:
	task_id: '<task_id>'
	task_name: '<task_name>'
	success: 0"
```

CRESTA will load the configuration, initialize its plugins and knowledge base, build the planning problem, and make the resulting plan available on `/tttask_manager/tttask/plan`.

## License

CRESTA is distributed under the GNU General Public License v3.0. See [LICENSE](LICENSE).

## Citation

If you use CRESTA in your research, please cite it 🚀:

```bibtex
@article{gasperini2026cresta,
  title = {CRESTA: A Cognitivist Robot Execution framework for Semantic-driven Task Awareness},
  journal = {Robotics and Autonomous Systems},
  volume = {197},
  pages = {105303},
  year = {2026},
  issn = {0921-8890},
  doi = {https://doi.org/10.1016/j.robot.2025.105303},
  url = {https://www.sciencedirect.com/science/article/pii/S0921889025004002},
  author = {Damiano Gasperini and Luca Muratore and Nikos Tsagarakis},
  keywords = {Autonomous robots, Planning and execution, Situation awareness, Task planning}
}
```
