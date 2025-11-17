#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import rospy
import itertools
from datetime import datetime

from std_msgs.msg import String
from cresta_msgs.msg import ActionStatus
from cresta_msgs.srv import (ServerToClientString, ServerToClientStringRequest, 
                                TaskActionPlan, TaskActionPlanRequest,
                                ClientToServerInt, ClientToServerIntRequest, 
                                ClientToServerString, ClientToServerStringRequest)


class ActionAwareness():
    def __init__(self):
        print("(Action Awareness) AW initializing ... ", flush=True)
        # Initialize ROS node 
        rospy.init_node('action_awareness', anonymous=False)

        self.rate = rospy.Rate(60)
 
        kb_sub = rospy.Subscriber('/wm_manager/kb/kb_data', String, self.kb_callback)
        self.task_data = None
        self.knowledge_base = None 
        self.goals_dict = None
        self.objects_type_instances = None
        self.objects_instance_types = None
        self.objects_types_hierarchy = None 
        self.action_modes = None 
        
        while self.task_data == None or self.knowledge_base == None or \
            self.goals_dict == None or self.objects_type_instances == None or \
            self.objects_instance_types == None:
            rospy.sleep(0.1)

        # initialize client handle for the Task Action Plan service 
        rospy.wait_for_service('/tttask_manager/tttask/tap_service')
        try:
            self.tap_service = rospy.ServiceProxy('/tttask_manager/tttask/tap_service', TaskActionPlan)   
        except rospy.ServiceException as e:
            print("(Action Awareness) TAP Service call failed: %s"%e, flush=True)
            return
        print("(Action Awareness) TAP Service initialized", flush=True)

        
        # initialize client handle for the aw service to TTTAsk manager 
        rospy.wait_for_service('/tttask_manager/tttask/action_awareness_service')
        try:
            self.action_awareness_service = rospy.ServiceProxy('/tttask_manager/tttask/action_awareness_service', ClientToServerInt) 
        except rospy.ServiceException as e:
            print("(Action Awarness) Action Awareness Service for feedback to TTTask call failed: %s"%e, flush=True)
            return
        print("(Action Awareness) Action Awareness Service for feedback to TTTask initialized", flush=True)
        
        # initialize client handle for the call_action_service
        rospy.wait_for_service('/xbot_actions/call_action_service')
        try:
            self.call_action_service = rospy.ServiceProxy('/xbot_actions/call_action_service', ClientToServerString) 
        except rospy.ServiceException as e:
            print("(Action Awareness) Action Service call failed: %s"%e, flush=True)
            return
        print("(Action Awareness) Action Service initialized", flush=True)


        # init Subscribers
        action_mode_sub = rospy.Subscriber('/wm_reasoner_mgr/actions_mode_reasoner/output', String, self.getActionMode )


        # initialize Action Status publisher
        self.act_pub = rospy.Publisher('/action_awareness/action_exe', ActionStatus, queue_size = 10)



    def getActionMode(self, msg):
        self.action_modes = json.loads(msg.data)

    def map_instances_to_types(self, data):
        types = None
        instances = None

        if "types" in data:
            types = data["types"]
        if "instances" in data:
            instances = data["instances"]
        
        # Recursive function to add a type to all ancestor types in the types_dict
        def add_type_to_ancestors(child_type, type_name):
            if child_type not in types_dict[type_name]:
                types_dict[type_name].append(child_type)
            if "father" in types[type_name]:
                add_type_to_ancestors(child_type, types[type_name]["father"])

        
        if types is not None:
            # Initialize a dictionary to store the mapping of types to instance names
            objects = {type_name: [] for type_name in types}
            types_dict = {type_name: [] for type_name in types}
            
            # Iterate to build the type hierarchy
            for type_name in types:
                if "father" in types[type_name]:
                    add_type_to_ancestors(type_name, types[type_name]["father"])

        else:
            return {}, {}, {}
 
        

        # Function to recursively add an instance to all ancestor types
        def add_to_ancestors(instance_name, type_name):
            if type_name not in objects:
                objects[type_name] = []
            objects[type_name].append(instance_name)

            instances_dict[instance_name].append(type_name)

            if "father" in types[type_name]:
                add_to_ancestors(instance_name, types[type_name]["father"])
        
        instances_dict = {}
        if instances is not None:             

            # Iterate over each instance to map it to its type and all its parent types
            for instance_name, instance_info in instances.items():

                instances_dict[instance_name] = []

                instance_type = instance_info["type"]
                add_to_ancestors(instance_name, instance_type)
        
        return objects, instances_dict, types_dict

    def process_plan(self):   
        print("(Action Awareness) Processing plan", flush=True)
        
        try:  
            # Call the tap service
            response = self.tap_service()
  
            self.actions_data = json.loads(response.actions_data)
            self.plan = response.plan

        except rospy.ServiceException as e:
            print("(Action Awareness) TAP Service call failed while processing plan: %s"%e, flush=True) 
           


    def kb_callback(self, msg):  
        
        try:
            new_task_data = json.loads(msg.data)
        except Exception as e:
            print("(Action Awareness) ERROR while loading task data: %s"%e, flush=True)

        if new_task_data != self.task_data:
           
            self.task_data = new_task_data 
            self.knowledge_base = self.task_data["fluents"]
            self.goals_dict = self.task_data["goals"]

            self.objects_type_instances = {}
            self.objects_instance_types = {}  
            self.objects_types_hierarchy = {} 

            if "objects" in self.task_data:
                                 
                self.objects_type_instances, self.objects_instance_types, self.objects_types_hierarchy = self.map_instances_to_types(self.task_data["objects"])


    def retrieve_fluent_value_kb(self, fluent, fluent_data):   
        fluent_default_initialization = None
        try: 
            fluent_default_initialization = self.knowledge_base[fluent]["default_initialization"] 
        except Exception as e:
            print("(Action Awareness) WARNING while retrieving fluent value: Fluent {} does not have default initialization property.".format(fluent), flush=True)
        
        fluent_initialization = None
        try: 
            fluent_initialization = self.knowledge_base[fluent]["initialization"] 
        except Exception as e:
            print("(Action Awareness) WARNING while retrieving fluent value: Fluent {} does not have initialization property.".format(fluent), flush=True)
        
        if fluent_initialization is None and fluent_default_initialization is None:
            print("(Action Awareness) ERROR while retrieving fluent {} value: Both initialization and default initialization are NOT available.".format(fluent), flush=True)
            return 
        
        if "parameters" in self.knowledge_base[fluent] and fluent_data is not None and \
            len(list(self.knowledge_base[fluent]["parameters"].keys())) == len(list(fluent_data.keys())):
    
            fluent_parameters_dict = fluent_data
             
            fluent_parameters_name_list = list(fluent_parameters_dict.keys())

            if fluent_parameters_dict == {} or len(fluent_parameters_name_list)==0:
                fluent_parameters_dict = None
                fluent_parameters_name_list = None
            
            if fluent_parameters_dict is not None and fluent_parameters_name_list is not None:
                idx_list_action_param = []
                fluent_instance_parameters = []
                for fluent_param in fluent_parameters_name_list:
                    if "instance" in fluent_parameters_dict[fluent_param]:
                        fluent_instance_parameters.append(fluent_parameters_dict[fluent_param]["instance"])
                    else:
                        try:
                            idx = self.action_parameters_name_list.index(fluent_param)
                            idx_list_action_param.append(idx)
                            fluent_instance_parameters.append(self.action_instance_parameters[idx])
                        except:
                            print("(Action Awareness) WARNING: Parameter {} of fluent {} not found while retrieving fluent value.".format(fluent_param, fluent), flush=True)
                        
                # check that fluent_instance_parameters is in initialization and return its value  
                if fluent_initialization is not None: 
                    if fluent_initialization.__class__ == [].__class__ and len(fluent_initialization) >0:
                         
                        for init in fluent_initialization:
                            if init["parameters"] == fluent_instance_parameters:
                                return init["value"]
                    

                        print("(Action Awareness) ERROR while retrieving fluent {} value: no fluent initialization matching.".format(fluent), flush=True)
                        if fluent_default_initialization is None:
                            return '/CRESTAxAW/ERROR_SIGNAL'
                        else:
                            return fluent_default_initialization

                    else:
                        print("(Action Awareness) ERROR while retrieving fluent {} value: unexpected fluent initialization.".format(fluent), flush=True)
                        if fluent_default_initialization is None:
                            return '/CRESTAxAW/ERROR_SIGNAL'
                        else:
                            return fluent_default_initialization

                else:
                    return fluent_default_initialization
            else:
                print("(Action Awareness) ERROR while retrieving fluent {} value: unexpected fluent initialization, it is empty.".format(fluent), flush=True)
                if fluent_default_initialization is None:
                    return '/CRESTAxAW/ERROR_SIGNAL'
                else:
                    return fluent_default_initialization
        else:
            if fluent_initialization is not None: 
                if fluent_initialization.__class__ == True.__class__:
                    return fluent_initialization

                else:
                    print("(Action Awareness) ERROR while retrieving fluent {} value: unexpected fluent initialization, type mismatch.".format(fluent), flush=True)
                    if fluent_default_initialization is None:
                        return '/CRESTAxAW/ERROR_SIGNAL'
                    else:
                        return fluent_default_initialization

            else:
                return fluent_default_initialization


    def retrieve_fluent_value_kb_4goals(self, fluent):   
        fluent_default_initialization = None
        try: 
            fluent_default_initialization = self.knowledge_base[fluent]["default_initialization"] 
        except Exception as e:
            print("(Action Awareness) WARNING while retrieving fluent value for goal check: Fluent {} does not have default initialization property.".format(fluent), flush=True)
        
        fluent_initialization = None
        try: 
            fluent_initialization = self.knowledge_base[fluent]["initialization"] 
        except Exception as e:
            print("(Action Awareness) WARNING while retrieving fluent value for goal check: Fluent {} does not have initialization property.".format(fluent), flush=True)
        
        if fluent_initialization is None and fluent_default_initialization is None:
            print("(Action Awareness) ERROR while retrieving fluent {} value for goal check: Both initialization and default initialization are NOT available.".format(fluent), flush=True)
            return 
        
        if "parameters" in self.goals_dict[fluent]:

            fluent_instance_parameters = self.goals_dict[fluent]["parameters"]

            if len(fluent_instance_parameters)==0:
                fluent_instance_parameters = None
            
            if fluent_instance_parameters is not None:
                 
                # check that fluent_instance_parameters is in initialization and return its value  
                if fluent_initialization is not None: 
                    if fluent_initialization.__class__ == [].__class__ and len(fluent_initialization) >0:
                         
                        for init in fluent_initialization:
                            if init["parameters"] == fluent_instance_parameters:
                                return init["value"]
                    

                        print("(Action Awareness) WARNING while retrieving fluent {} value for goal check: no fluent initialization matching.".format(fluent), flush=True)
                        if fluent_default_initialization is None:
                            return '/CRESTAxAW/ERROR_SIGNAL'
                        else:
                            return fluent_default_initialization

                    else:
                        print("(Action Awareness) ERROR while retrieving fluent {} value for goal check: unexpected fluent initialization.".format(fluent), flush=True)
                        if fluent_default_initialization is None:
                            return '/CRESTAxAW/ERROR_SIGNAL'
                        else:
                            return fluent_default_initialization

                else:
                    return fluent_default_initialization
            else:
                print("(Action Awareness) ERROR while retrieving fluent {} value for goal check: unexpected fluent initialization, empty parameters list.".format(fluent), flush=True)
                if fluent_default_initialization is None:
                    return '/CRESTAxAW/ERROR_SIGNAL'
                else:
                    return fluent_default_initialization
        else:
            if fluent_initialization is not None: 
                if fluent_initialization.__class__ == True.__class__:
                    return fluent_initialization

                else:
                    print("(Action Awareness) ERROR while retrieving fluent {} value for goal check: unexpected fluent initialization, type mismatch.".format(fluent), flush=True)
                    if fluent_default_initialization is None:
                        return '/CRESTAxAW/ERROR_SIGNAL'
                    else:
                        return fluent_default_initialization

            else:
                return fluent_default_initialization
            
    def retrieve_fluent_value_kb_noparam(self, fluent):   
        fluent_default_initialization = None
        try: 
            fluent_default_initialization = self.knowledge_base[fluent]["default_initialization"] 
        except Exception as e:
            print("(Action Awareness) WARNING while retrieving fluent value with no param: Fluent {} does not have default initialization property.".format(fluent), flush=True)
        
        fluent_initialization = None
        try: 
            fluent_initialization = self.knowledge_base[fluent]["initialization"] 
        except Exception as e:
            print("(Action Awareness) WARNING while retrieving fluent value with no param: Fluent {} does not have initialization property.".format(fluent), flush=True)
        
        if fluent_initialization is None and fluent_default_initialization is None:
            print("(Action Awareness) ERROR while retrieving fluent {} value with no param: Both initialization and default initialization are NOT available.".format(fluent), flush=True)
            return 
        
        if "parameters" not in self.knowledge_base[fluent]:

            if fluent_initialization is not None: 
                if fluent_initialization.__class__ == True.__class__:
                    return fluent_initialization

                else:
                    print("(Action Awareness) ERROR while retrieving fluent {} value with no param: unexpected fluent initialization, type mismatch.".format(fluent), flush=True)
                    if fluent_default_initialization is None:
                        return '/CRESTAxAW/ERROR_SIGNAL'
                    else:
                        return fluent_default_initialization

            else:
                return fluent_default_initialization

    def retrieve_fluent_value_kb_withparam_instance(self, fluent, fluent_instance_parameters):   
        fluent_default_initialization = None
        try: 
            fluent_default_initialization = self.knowledge_base[fluent]["default_initialization"] 
        except Exception as e:
            print("(Action Awareness) WARNING while retrieving fluent value with params instance: Fluent {} does not have default initialization property.".format(fluent), flush=True)
        
        fluent_initialization = None
        try: 
            fluent_initialization = self.knowledge_base[fluent]["initialization"] 
        except Exception as e:
            print("(Action Awareness) WARNING while retrieving fluent value with params instance: Fluent {} does not have initialization property.".format(fluent), flush=True)
        
        if fluent_initialization is None and fluent_default_initialization is None:
            print("(Action Awareness) ERROR while retrieving fluent {} value with params instance: Both initialization and default initialization are NOT available.".format(fluent), flush=True)
            return 
        
         
        if len(fluent_instance_parameters)==0:
            fluent_instance_parameters = None
        
        if fluent_instance_parameters is not None:
                
            # check that fluent_instance_parameters is in initialization and return its value  
            if fluent_initialization is not None: 
                if fluent_initialization.__class__ == [].__class__ and len(fluent_initialization) >0:
                     
                    for init in fluent_initialization:
                        if init["parameters"] == fluent_instance_parameters:
                            return init["value"]
                

                    print("(Action Awareness) WARNING while retrieving fluent {} value with params instance: no fluent initialization matching.".format(fluent), flush=True)
                    if fluent_default_initialization is None:
                        return '/CRESTAxAW/ERROR_SIGNAL'
                    else:
                        return fluent_default_initialization

                else:
                    print("(Action Awareness) ERROR while retrieving fluent {} value with params instance: unexpected fluent initialization.".format(fluent), flush=True)
                    if fluent_default_initialization is None:
                        return '/CRESTAxAW/ERROR_SIGNAL'
                    else:
                        return fluent_default_initialization

            else:
                return fluent_default_initialization
        else:
            print("(Action Awareness) ERROR while retrieving fluent {} value with params instance: unexpected fluent initialization, empty parameters list.".format(fluent), flush=True)
            if fluent_default_initialization is None:
                return '/CRESTAxAW/ERROR_SIGNAL'
            else:
                return fluent_default_initialization
         
    def generate_combinations(self, mask_list, allocation_list, possible_values_list):
        # Check that the length of possible_values_list matches the number of zeros in mask_list
        zero_indices = [i for i in range(len(mask_list)) if mask_list[i] == 0]
        if len(possible_values_list) != len(zero_indices):
            raise ValueError("(Action Awaremess) Lists in possible values must match the number of zeros in mask_list")

        # Generate all combinations of possible_values_list, each sublist for each zero position
        possible_combinations = list(itertools.product(*possible_values_list))

        # Initialize the output list to hold all possible combinations
        output = []

        # For each combination of possible values, build a result list
        for combination in possible_combinations:
            # Initialize a new combination with placeholder values
            new_combination = [None] * len(mask_list)
            
            # Iterator for allocation_list
            alloc_iter = iter(allocation_list)
            
            # Fill in the values from allocation_list at indices marked by 1 in mask_list
            for idx, value in enumerate(mask_list):
                if value == 1:
                    new_combination[idx] = next(alloc_iter)

            # Fill in the values from combination where mask_list has 0
            for zero_idx, value in zip(zero_indices, combination):
                new_combination[zero_idx] = value

            # Append the newly created combination to the output list
            output.append(new_combination)

        return output

    def checkExistsonFluent4Goal(self, fluent, exist_param, fluent_exist_data, fluent_general_data):
        
        fluent_general_param = None
        if "parameters" in fluent_general_data:
            fluent_general_param = fluent_general_data["parameters"]

        fluent_exist_param_list = None 
        if "parameters" in fluent_exist_data:
            fluent_exist_param_list = fluent_exist_data["parameters"]
        
        if (fluent_general_param is None or fluent_general_param == {}) and \
            not (fluent_exist_param_list is None or fluent_exist_param_list == []):

            return "'/CRESTAxAW/ERROR_SIGNAL'"
        
        if not (fluent_general_param is None or fluent_general_param == {}) and \
            (fluent_exist_param_list is None or fluent_exist_param_list == []):

            return "'/CRESTAxAW/ERROR_SIGNAL'"
        
        if (fluent_general_param is None or fluent_general_param == {}) and \
            (fluent_exist_param_list is None or fluent_exist_param_list == []):

            fluent_value = self.retrieve_fluent_value_kb_noparam(fluent)
 
            return fluent_value == fluent_exist_data["value"]
        
        fluent_general_param_list = list(fluent_general_param.keys())
        num_fluent_general_param = len(fluent_general_param_list)
 
        num_fluent_exist_param = len(fluent_exist_param_list)

        if num_fluent_exist_param != num_fluent_general_param:
            return "'/CRESTAxAW/ERROR_SIGNAL'"
        
        if exist_param is None or exist_param == {}:            
            fluent_exist_param_instance = []
            for k, gen_k in zip(fluent_exist_param_list, fluent_general_param):
                if k not in self.objects_instance_types or fluent_general_param[gen_k]["type"] not in self.objects_instance_types[k]:
                    return "'/CRESTAxAW/ERROR_SIGNAL'"
                else:
                    fluent_exist_param_instance.append(k)
            
            fluent_value = self.retrieve_fluent_value_kb_withparam_instance(fluent, fluent_exist_param_instance)
            return fluent_value == fluent_exist_data["value"]
        

        bit_mask = []
        allocation_instance_mask = []
        allocation_type_mask = []
        allocation_possible_values=[]
        
        for kf, gen_k in zip(fluent_exist_param_list, fluent_general_param):
            
            if kf in exist_param and (fluent_general_param[gen_k]["type"] == exist_param[kf]["type"] or exist_param[kf]["type"] in self.objects_types_hierarchy[fluent_general_param[gen_k]["type"]]):
                
                bit_mask.append(0)
                allocation_type_mask.append(fluent_general_param[gen_k]["type"])
            elif kf not in exist_param and kf in self.objects_instance_types and \
                fluent_general_param[gen_k]["type"] in self.objects_instance_types[kf]:
                bit_mask.append(1)
                allocation_instance_mask.append(kf)
                # allocation_type_mask.append(fluent_general_param[gen_k]["type"])
            else:
                print("(ACTION AWARENESS) ERROR while checking fluent {} value for exist operator in goal: params mismatch.".format(fluent), flush=True)
                return "'/CRESTAxAW/ERROR_SIGNAL'"

        for type in allocation_type_mask:
            allocation_possible_values.append(self.objects_type_instances[type])
        
        fluent_param_instance_combinations = self.generate_combinations(bit_mask, allocation_instance_mask, allocation_possible_values)
        
        for combination in fluent_param_instance_combinations:
            fluent_value = self.retrieve_fluent_value_kb_withparam_instance(fluent, combination)
            # if there exists a combination with desired fluent value
            if fluent_value == fluent_exist_data["value"]:  
                return True
        return False 
        

         

    def retrieve_Exists_value4Goal(self, operator_id):
        
        fluents = self.goals_dict[operator_id]["fluents"]
        
        exist_param = None
        if "parameters" in self.goals_dict[operator_id]:
            exist_param = self.goals_dict[operator_id]["parameters"]


        tot_check = True
        for fluent in fluents:
            tot_check = tot_check and self.checkExistsonFluent4Goal(fluent, exist_param, fluents[fluent], self.knowledge_base[fluent])

        return tot_check  
            
                         
    def checkGoals(self):

        for fluent in self.goals_dict:
            if "operator" in fluent: 
                key_operator = self.goals_dict[fluent]["key"]
                if key_operator == "Exists":
                    operator_value = self.retrieve_Exists_value4Goal(fluent)
                    if not self.goals_dict[fluent]["value"] == operator_value:
                        return 0

            else:
                fluent_value = self.retrieve_fluent_value_kb_4goals(fluent)

                if not self.goals_dict[fluent]["value"] == fluent_value:
                    return 0
            
        return 1
     
        

    def checkPreconditionsEffects(self, check_preconditions = True): 
        # This function check the semantics of the action in execution 

        # It returns:
        # - 0 if at least a precondition is not matching & at least an effect is not satisfied yet --> error 
        # - 1 if at least a precondition is not matching & all effects are satisfied --> success
        # - 2 if all preconditions are matching & at least an effect is not satisfied yet --> move on 
        # - 3 if all preconditions are matching & all effects are satisfied --> success
        # - 4 if the goal is achieved 
   
        """
        if all(internal_KB[cond_goal].value == cond_goal.value for cond_goal in goal.conditions):
            return TASK_COMPLETED
        if check_preconditions:
            for cond_prec in action.preconditions:
                if internal_KB[cond_prec].value ≠ cond_prec.value:
                    for cond_eff in action.effects:
                        if internal_KB[cond_eff].value ≠ cond_eff.value:
                            return ERROR(cond_prec, cond_eff)
                    return SUCCESS
        else:
            for cond_hold in action.holdingcondtions:
                if internal_KB[cond_hold].value ≠ cond_hold.value:
                    for cond_eff in action.effects:
                        if internal_KB[cond_eff].value ≠ cond_eff.value:
                            return ERROR(cond_hold, cond_eff)
                    return SUCCESS
        for cond_eff in action.effects:
            if internal_KB[cond_eff].value ≠ cond_eff.value:
                return MOVE_ON
        return SUCCESS
        """

        if self.checkGoals():
            return 4

        if check_preconditions:
            for fluent in self.preconditions_dict: 

                fluent_data = None
                if "parameters" in self.preconditions_dict[fluent]:
                    fluent_data = self.preconditions_dict[fluent]["parameters"]

                fluent_value = self.retrieve_fluent_value_kb(fluent, fluent_data)

                if not self.preconditions_dict[fluent]["value"]==fluent_value:
                    for fluent_effect in self.effects_dict:

                        fluent_data = None
                        if "parameters" in self.effects_dict[fluent_effect]:
                            fluent_data = self.effects_dict[fluent_effect]["parameters"]

                        fluent_eff_value = self.retrieve_fluent_value_kb(fluent_effect, fluent_data)

                        if not self.effects_dict[fluent_effect]["value"] == fluent_eff_value:
                            print("(Action Awareness) Detected failure while checking KB: NOT coherent pre-condition={} + effect={}".format(fluent, fluent_effect), flush=True)
                            return 0
                    return 1
        
        else: 
            self.holdconditions_dict_augmented = {**self.preconditions_dict, **self.holdconditions_dict}
            for fluent in self.holdconditions_dict_augmented:
                if "check_exe" in self.holdconditions_dict_augmented[fluent].keys() and not self.holdconditions_dict_augmented[fluent]["check_exe"]:
                    continue

                fluent_data = None
                if "parameters" in self.holdconditions_dict_augmented[fluent]:
                    fluent_data = self.holdconditions_dict_augmented[fluent]["parameters"]

                fluent_value = self.retrieve_fluent_value_kb(fluent, fluent_data)

                if not self.holdconditions_dict_augmented[fluent]["value"]==fluent_value:
                    for fluent_effect in self.effects_dict:

                        fluent_data = None
                        if "parameters" in self.effects_dict[fluent_effect]:
                            fluent_data = self.effects_dict[fluent_effect]["parameters"]

                        fluent_eff_value = self.retrieve_fluent_value_kb(fluent_effect, fluent_data)

                        if not self.effects_dict[fluent_effect]["value"] == fluent_eff_value:
                            print("(Action Awareness) Detected failure while checking KB: NOT coherent hold-condition={} + effect={}".format(fluent, fluent_effect), flush=True)
                            return 0
                    return 1

        for fluent in self.effects_dict:

            fluent_data = None
            if "parameters" in self.effects_dict[fluent]:
                fluent_data = self.effects_dict[fluent]["parameters"]


            fluent_eff_value = self.retrieve_fluent_value_kb(fluent, fluent_data)
            if not self.effects_dict[fluent]["value"] == fluent_eff_value:
                return 2
        
        return 3

    def retrieveActionMode(self, action):
        mode = None 
        if self.action_modes is not None: 
            mode = self.action_modes[action]
        return mode 

    def follow_action(self, action_with_params, time=100.0):

        action_params_list = action_with_params.split('/')

        action = action_params_list[0]

        self.action_instance_parameters = [] 
        
        if len(action_params_list) > 1: 
            self.action_instance_parameters = action_params_list[1:]

        # 1. Retrieve action modality (if any) by reasoning 

        if "modes" in self.actions_data[action]:
            mode = self.retrieveActionMode(action)
            if mode is None:
                print(f"(Action Awareness) Mode for action={action} is not available!", flush=True)
                return 0 
            
            list_modes = self.actions_data[action]["modes"]["available_modes"]
            for md in list_modes:
                if mode in md: 
                    if "time" in md[mode]:
                        time = md[mode]["time"]

            mode = "_" + mode

        else: 
            mode = ""
        
        # 2. Verify preconditions match & not effects verified
        self.preconditions_dict = self.actions_data[action]["preconditions"]

        if "holdingconditions" in self.actions_data[action]:
            self.holdconditions_dict = self.actions_data[action]["holdingconditions"]
        else: 
            self.holdconditions_dict = {}
        
        self.effects_dict = self.actions_data[action]["effects"]
        self.action_parameters_dict = None
        self.action_parameters_name_list = None

        if "parameters" in self.actions_data[action]:
            self.action_parameters_dict = self.actions_data[action]["parameters"]
            self.action_parameters_name_list = list(self.action_parameters_dict.keys())
            if self.action_parameters_dict == {} or len(self.action_parameters_name_list)==0:
                self.action_parameters_dict = None
                self.action_parameters_name_list = None
           
        check_flag = self.checkPreconditionsEffects(check_preconditions=True)

        print("(Action Awareness) Check semantics before action returned: ", check_flag, flush=True)


        # check_flag can be:
        # - 0 if at least a precondition is not matching & at least an effect is not satisfied yet --> error 
        # - 1 if at least a precondition is not matching & all effects are satisfied --> success
        # - 2 if all preconditions are matching & at least an effect is not satisfied yet --> move on 
        # - 3 if all preconditions are matching & all effects are satisfied --> success
        # - 4 if the goal is achieved --> success

        if check_flag != 2: 

            msg_action = ClientToServerStringRequest()
            msg_action.data = "stop"   
            act_exe_msg = ActionStatus()
            act_exe_msg.execution = 1
            act_exe_msg.name = "stop"
            act_exe_msg.params = []                
            try: 
                self.call_action_service(msg_action)  
                self.act_pub.publish(act_exe_msg)                        
            except:
                print("(Action Awareness) ERROR: Bad action service in Skill Library.", flush=True)
        
            return check_flag   

        # 2. Start action 

        msg_action = ClientToServerStringRequest()
        msg_action.data = action + mode 
        
        act_exe_msg = ActionStatus()
 
        try: 
            act_exe_msg.execution = 1
            act_exe_msg.name = action  
            act_exe_msg.mode = mode
            act_exe_msg.params = self.action_instance_parameters 
            self.call_action_service(msg_action)
            self.act_pub.publish(act_exe_msg)

        except:
            print("(Action Awareness) ERROR: Bad action service in Skill Library.", flush=True) 
            act_exe_msg.execution = 0
            act_exe_msg.name = action  
            act_exe_msg.mode = mode
            act_exe_msg.params = self.action_instance_parameters
            act_exe_msg.success = False
            self.act_pub.publish(act_exe_msg)

        # 3. Follow its execution  

        start_time = datetime.now()
        actual_time = datetime.now()   
        elapsed_time = actual_time - start_time

        while (elapsed_time.total_seconds() < time):   

            check_flag = 0
            
            check_flag = self.checkPreconditionsEffects(check_preconditions=False)
            
            print("(Action Awareness) Check semantics online returned: ", check_flag, flush=True)
             
            
            # check_flag can be:
            # - 0 if at least a precondition is not matching & at least an effect is not satisfied yet --> error 
            # - 1 if at least a precondition is not matching & all effects are satisfied --> success
            # - 2 if all holding conditions are matching & at least an effect is not satisfied yet --> move on 
            # - 3 if all preconditions are matching & all effects are satisfied --> success 
            # - 4 if the goal is achieved --> success

            if check_flag != 2: 
                act_exe_msg.execution = 0
                act_exe_msg.name = action  
                act_exe_msg.mode = mode
                act_exe_msg.params = self.action_instance_parameters
                if check_flag==0:
                    act_exe_msg.success = False
                else:
                    act_exe_msg.success = True
                self.act_pub.publish(act_exe_msg)


                msg_action = ClientToServerStringRequest()
                msg_action.data = "stop"      
                act_exe_msg = ActionStatus()
                act_exe_msg.execution = 1
                act_exe_msg.name = "stop"
                act_exe_msg.params = []              
                try: 
                    self.call_action_service(msg_action) 
                    self.act_pub.publish(act_exe_msg)                         
                except:
                    print("(Action Awareness) ERROR: Bad action service in Skill Library.", flush=True)
 
                 

                return check_flag 

            actual_time = datetime.now() 
            elapsed_time = actual_time - start_time 

            print("(Action Awareness) Elapsed seconds from the beginning of action: ", elapsed_time.total_seconds(), flush=True)
   

        act_exe_msg.execution = 0
        act_exe_msg.name = action  
        act_exe_msg.mode = mode
        act_exe_msg.params = self.action_instance_parameters 
        act_exe_msg.success = False 
        self.act_pub.publish(act_exe_msg) 

        msg_action = ClientToServerStringRequest()
        msg_action.data = "stop"      
        act_exe_msg = ActionStatus()
        act_exe_msg.execution = 1
        act_exe_msg.name = "stop"
        act_exe_msg.params = []              
        try: 
            self.call_action_service(msg_action) 
            self.act_pub.publish(act_exe_msg)                         
        except:
            print("(Action Awareness) ERROR: Bad action service in Skill Library.", flush=True)
 

        return 0     
 
    
    def monitor(self):
        print("(Action Awareness) Monitoring plan ... ", flush=True)
              
 
        for num_action, action in enumerate(self.plan):        
            print("(Action Awareness) Executing action: ", action, flush=True)

            action_response = self.follow_action(action)
            print("(Action Awareness) Action {} ended with response: ".format(action), action_response, flush = True)


            # action_response can be:
            # - 0 if at least a precondition is not matching & at least an effect is not satisfied yet --> error 
            # - 1 if at least a precondition is not matching & all effects are satisfied --> success 
            # - 3 if all preconditions are matching & all effects are satisfied --> success
            # - 4 if the goal is achieved --> success

            if action_response == 0: 
                
                #send trigger to the manager: bad execution of action
                msg = ClientToServerIntRequest()
                msg.data = action_response
                self.action_awareness_service(msg) 
                
                rospy.sleep(1)  
                return
            
            rospy.sleep(1)  
        
        print("(Action Awareness) Plan successfully executed.", flush=True) 
         
        #send trigger to the manager: successful execution of the plan 
        msg = ClientToServerIntRequest()
        msg.data = 1
        self.action_awareness_service(msg) 

        rospy.sleep(5) 

    def run(self):
        print("(Action Awarness) AW is running...", flush=True)
        while not rospy.is_shutdown():  
            self.process_plan()
            print("(Action Awarness) Available plan: ", self.plan, flush=True)
            if self.plan != []:
                self.monitor()
            self.rate.sleep()
        
def main():
    try:
        node = ActionAwareness()
        node.run()
    except rospy.ROSInterruptException:
        pass
     

if __name__ == '__main__':
    main()
   
 