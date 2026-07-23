#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os 
import rospy  
import rospkg
import json
import itertools
import threading 

from std_msgs.msg import String, Int32
from cresta_msgs.msg import ActionStatus
from cresta_msgs.srv import ClientToServerString, ClientToServerStringResponse


# This module implements CRESTA World Model's Default Reasoner plugin.

# The DefaultReasonerManager takes: 
# - what to reason: ["fluent1", ...] 
# - a config file with reasoning rules 

"""
Rules example:
- if fluent1 and fluent2 => fluent3 
- if action1 is on, then action1 is off and action1 succeeded => fluent4
- if action1 is on and fluent3 => fluent5
"""


class DefaultReasonerManager():
    def __init__(self): 

        # Initialize ROS node
        rospy.init_node('default_reasoner_manager', anonymous=False)

        self.rate = rospy.Rate(60)         
        
        # Get an instance of RosPack with the default search paths
        self.rospack = rospkg.RosPack()     

        self.reasoning_rules = {}   

        # Get the parameters
        try: 
            reasoning_rules_path = rospy.get_param('~reasoning_rules_path')
        except: 
            # Get the default file path for cresta_world_model task configs 
            cresta_world_model_path = self.rospack.get_path('cresta_world_model')
            reasoning_rules_path = os.path.join(cresta_world_model_path, "config", "reasoning_rules.json")

        # Read reasoning rules file
        try:
            with open(reasoning_rules_path, "r") as rules_file:
                self.reasoning_rules = json.load(rules_file)
        except FileNotFoundError:
            print("(Default Reasoner Manager) ERROR: Unable to find the reasoning rules config file.")
            rospy.signal_shutdown("(Default Reasoner Manager) ERROR: Unable to find the reasoning rules")


        # Initialize variables for reasoner  
        self.kb_data = {}
        self.fluents_data = {}
        self.what_to_reason = []    
        self.objects_type_instances = {} 
        self.objects_instance_types = {} 
        self.objects_types_hierarchy = {}

        self.sem_kb_data = threading.Semaphore(1)

        self.cartesian_pose_reached = None  
        self.action = {"name": None, "execution":None, "params":[], "success": None} # TODO: add mode support 

        # Initialize Subscriber for Knowledge Base 
        self.kb_data_sub = rospy.Subscriber('/wm_manager/kb/kb_data', String, self.kb_data_callback)

        # Initialize Subscriber for Cartesian Pose reached  
        cartesian_pose_reached_sub = rospy.Subscriber('/xbot_actions/cartesio_task_state_completed', Int32, self.cartesian_pose_reached_callback)
        
        # Initialize Subscriber on action execution status 
        act_exe_sub = rospy.Subscriber('/action_awareness/action_exe', ActionStatus, self.getActionExe)

        # Initialize Publisher for Default Reasoner output   
        self.fluents4wm_pub = rospy.Publisher('/wm_reasoner_mgr/default_reasoner/fluents4wm', String, queue_size =10) 
        
        # Data service: starts/update Reasoner about what predicate to reason on
        what_to_reason_service = rospy.Service('/default_reasoner/set_what_to_reason', ClientToServerString, self.handle_what_to_reason_service)

    def getActionExe(self, msg):  
        
        self.action["name"] = msg.name 
        self.action["execution"] =  True if msg.execution else False 
        self.action["params"] = msg.params
        self.action["success"] = msg.success
    
        print(f"(Default Reasoner Manager) Received ActionStatus in getActionExe: action={msg.name}, params={msg.params}, execution={msg.execution} ", flush=True)
        

    def cartesian_pose_reached_callback(self, msg):
        self.cartesian_pose_reached = msg.data


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


    def kb_data_callback(self, msg): 
        tmp_kb_data = json.loads(msg.data)

        if self.kb_data != tmp_kb_data:
            self.sem_kb_data.acquire() 
            self.kb_data = tmp_kb_data
            self.fluents_data = self.kb_data["fluents"]

            self.objects_type_instances, self.objects_instance_types, self.objects_types_hierarchy = self.map_instances_to_types(self.kb_data["objects"])
            self.sem_kb_data.release()
      
    def handle_what_to_reason_service(self, msg):     
         
        # This service is for receiving a list of what to reason on
        tmp = msg.data

        tmp_what_to_reason= json.loads(tmp) 
         

        if self.what_to_reason != tmp_what_to_reason:
            
            self.what_to_reason = tmp_what_to_reason

            print(f"(Default Reasoner Manager) Received what to reason: {self.what_to_reason}")

        return ClientToServerStringResponse(success=True)

    def check_action_in_if_rule(self, if_params, action_name, action_data):
         
        if self.action["name"] == action_name:
            action_params = {}
            if "parameters" in action_data:
                action_params = action_data["parameters"]
             
            combine_checks = True
            if "value" in action_data: 
                combine_checks = combine_checks and action_data["value"] == self.action["execution"] 
                if not combine_checks:
                    return if_params, combine_checks 
            if "cartesian_pose_reached" in action_data:
                combine_checks = combine_checks and action_data["cartesian_pose_reached"] == self.cartesian_pose_reached
                 
                if not combine_checks:
                    return if_params, combine_checks 
            
            action_params_list = list(action_params.keys())

            if len(self.action["params"]) == 0 and len(action_params_list) == 0:
                return if_params, combine_checks
                
            combine_checks = combine_checks and (len(action_params_list) == len(self.action["params"]) or len(action_params_list)==0)
            if not combine_checks:
                return if_params, combine_checks 
            
            check_params = True
            for idx, param in enumerate(action_params):
                if param in if_params:
                    if "initialization" not in if_params[param]:
                        if_params[param]["initialization"] = [self.action["params"][idx]]
                    
                    elif "initialization" in if_params[param] and if_params[param]["initialization"] is None:
                        if_params[param]["initialization"] = [self.action["params"][idx]]
                    
                    elif "initialization" in if_params[param] and if_params[param]["initialization"] is not None \
                        and if_params[param]["initialization"].__class__ == [].__class__:

                         
                        ist_param_list = if_params[param]["initialization"]                       
                        length_ist_param_list = len(ist_param_list)

                        if length_ist_param_list > 0:
                            ist_found = False
                            for ist in ist_param_list:
                                if ist == self.action["params"][idx]:
                                    if_params[param]["initialization"] = [ist]
                                    ist_found = True
                                    break
                            if not ist_found:
                                check_params = False
                                break
                        else:
                            if_params[param]["initialization"] = [self.action["params"][idx]]

                    elif "initialization" in if_params[param] and if_params[param]["initialization"] != self.action["params"][idx]:
                        check_params = False
                        break
                    else:
                        check_params = False
                        break
                else:
                    check_params = check_params and param==self.action["param"][idx]
                    if not check_params: 
                        break

            combine_checks = combine_checks and check_params 

            return if_params, combine_checks
        
        elif self.action["name"] != action_name and not action_data["value"]:
            return if_params, True 
              
        else:
            return if_params, False
        
        
    def retrieve_fluent_value_kb_noparam(self, fluent, fluent_general_data):   
        fluent_default_initialization = None
        try: 
            fluent_default_initialization = fluent_general_data["default_initialization"] 
        except Exception as e:
            print("(Default Reasoner Manager) WARNING while retrieving fluent value with no param: Fluent {} does not have default initialization property.".format(fluent), flush=True)
        
        fluent_initialization = None
        try: 
            fluent_initialization = fluent_general_data["initialization"] 
        except Exception as e:
            print("(Default Reasoner Manager) WARNING while retrieving fluent value with no param: Fluent {} does not have initialization property.".format(fluent), flush=True)
        
        if fluent_initialization is None and fluent_default_initialization is None:
            print("(Default Reasoner Manager) ERROR while retrieving fluent {} value with no param: Both initialization and default initialization are NOT available.".format(fluent), flush=True)
            return 
        
        if "parameters" not in fluent_general_data:

            if fluent_initialization is not None: 
                if fluent_initialization.__class__ == True.__class__:
                    return fluent_initialization

                else:
                    print("(Default Reasoner Manager) ERROR while retrieving fluent {} value with no param: unexpected fluent initialization, type mismatch.".format(fluent), flush=True)
                    if fluent_default_initialization is None:
                        return '/CRESTAxAW/ERROR_SIGNAL'
                    else:
                        return fluent_default_initialization

            else:
                return fluent_default_initialization

    def retrieve_fluent_value_kb_withparam_instance(self, fluent, fluent_instance_parameters, fluent_general_data):   
        fluent_default_initialization = None
        try: 
            fluent_default_initialization = fluent_general_data["default_initialization"] 
        except Exception as e:
            print("(Default Reasoner Manager) WARNING while retrieving fluent value with params instance: Fluent {} does not have default initialization property.".format(fluent), flush=True)
        
        fluent_initialization = None
        try: 
            fluent_initialization = fluent_general_data["initialization"] 
        except Exception as e:
            print("(Default Reasoner Manager) WARNING while retrieving fluent value with params instance: Fluent {} does not have initialization property.".format(fluent), flush=True)
        
        if fluent_initialization is None and fluent_default_initialization is None:
            print("(Default Reasoner Manager) ERROR while retrieving fluent {} value with params instance: Both initialization and default initialization are NOT available.".format(fluent), flush=True)
            return 
        
         
        if len(fluent_instance_parameters)==0:
            fluent_instance_parameters = None
        
        if fluent_instance_parameters is not None:
                
            if fluent_initialization is not None: 
                if fluent_initialization.__class__ == [].__class__ and len(fluent_initialization) >0:
                     
                    for init in fluent_initialization:
                        if init["parameters"] == fluent_instance_parameters:
                            return init["value"]
                

                    print("(Default Reasoner Manager) WARNING while retrieving fluent {} value with params instance: no fluent initialization matching.".format(fluent), flush=True)
                    if fluent_default_initialization is None:
                        return '/CRESTAxAW/ERROR_SIGNAL'
                    else:
                        return fluent_default_initialization

                else:
                    print("(Default Reasoner Manager) ERROR while retrieving fluent {} value with params instance: unexpected fluent initialization.".format(fluent), flush=True)
                    if fluent_default_initialization is None:
                        return '/CRESTAxAW/ERROR_SIGNAL'
                    else:
                        return fluent_default_initialization

            else:
                return fluent_default_initialization
        else:
            print("(Default Reasoner Manager) ERROR while retrieving fluent {} value with params instance: unexpected fluent initialization, empty parameters list.".format(fluent), flush=True)
            if fluent_default_initialization is None:
                return '/CRESTAxAW/ERROR_SIGNAL'
            else:
                return fluent_default_initialization
         
    def generate_combinations(self, mask_list, allocation_list, possible_values_list):

        zero_indices = [i for i in range(len(mask_list)) if mask_list[i] == 0]
        if len(possible_values_list) != len(zero_indices):
            raise ValueError("(Default Reasoner Manager) Lists in possible values must match the number of zeros in mask_list")

        # Generate all combinations of possible_values_list 
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

    def checkExistsonFluent4If(self, fluent, exist_param, fluent_exist_data, fluent_general_data):
                    
        fluent_general_param = None
        if "parameters" in fluent_general_data:
            fluent_general_param = fluent_general_data["parameters"]

        fluent_exist_param_list = None 
        if "parameters" in fluent_exist_data:
            fluent_exist_param_list = list(fluent_exist_data["parameters"].keys())
        
        if (fluent_general_param is None or fluent_general_param == {}) and \
            not (fluent_exist_param_list is None or fluent_exist_param_list == []):

            return exist_param, "'/CRESTAxAW/ERROR_SIGNAL'"
        
        if not (fluent_general_param is None or fluent_general_param == {}) and \
            (fluent_exist_param_list is None or fluent_exist_param_list == []):

            return exist_param, "'/CRESTAxAW/ERROR_SIGNAL'"
        
        if (fluent_general_param is None or fluent_general_param == {}) and \
            (fluent_exist_param_list is None or fluent_exist_param_list == []):

            fluent_value = self.retrieve_fluent_value_kb_noparam(fluent, fluent_general_data)

            return exist_param, fluent_value == fluent_exist_data["value"]
        
        fluent_general_param_list = list(fluent_general_param.keys())
        num_fluent_general_param = len(fluent_general_param_list)
 
        num_fluent_exist_param = len(fluent_exist_param_list)

        if num_fluent_exist_param != num_fluent_general_param:
            return exist_param, "'/CRESTAxAW/ERROR_SIGNAL'"
        
        if exist_param is None or exist_param == {}:            
            fluent_exist_param_instance = []
            for k, gen_k in zip(fluent_exist_param_list, fluent_general_param):
                if k not in self.objects_instance_types or fluent_general_param[gen_k]["type"] not in self.objects_instance_types[k]:
                    return exist_param, "'/CRESTAxAW/ERROR_SIGNAL'"
                else:
                    fluent_exist_param_instance.append(k)
            
            fluent_value = self.retrieve_fluent_value_kb_withparam_instance(fluent, fluent_exist_param_instance, fluent_general_data)
            return exist_param, fluent_value == fluent_exist_data["value"]
        

        bit_mask = []
        allocation_instance_mask = []
        allocation_type_mask = []
        allocation_possible_values=[]
        allocation_possible_values_from_param=[]
 

        for kf, gen_k in zip(fluent_exist_param_list, fluent_general_param):
 
            
            if kf in exist_param and (fluent_general_param[gen_k]["type"] == exist_param[kf]["type"] or exist_param[kf]["type"] in self.objects_types_hierarchy[fluent_general_param[gen_k]["type"]]):
                                 
                if "initialization" in exist_param[kf] and exist_param[kf]["initialization"] is not None \
                    and exist_param[kf]["initialization"].__class__ == [].__class__:

                    ist_param_list = exist_param[kf]["initialization"] 
 
                    if len(ist_param_list) > 1:
                        ist_found = False
                        key_to_possible_ist = []
                        for ist in ist_param_list:
                            if ist in self.objects_instance_types and \
                                fluent_general_param[gen_k]["type"] in self.objects_instance_types[ist]:
                                ist_found = True
                                key_to_possible_ist.append(ist)
                        
                        if not ist_found:
                            return exist_param, "'/CRESTAxAW/ERROR_SIGNAL'"
                         
                        bit_mask.append(0)
                        allocation_type_mask.append('/CRESTAxDRM/POSSIBLE_VALUES_ALREADY_GENERATED')
                        allocation_possible_values_from_param.append(key_to_possible_ist)
                    elif len(ist_param_list) == 0:
                        bit_mask.append(0)
                        allocation_type_mask.append(fluent_general_param[gen_k]["type"])
                    else:
                        ist = exist_param[kf]["initialization"][0]
                        if ist in self.objects_instance_types and \
                            fluent_general_param[gen_k]["type"] in self.objects_instance_types[ist]:
                            bit_mask.append(1)
                            allocation_instance_mask.append(ist)
                        else:
                            return exist_param, "'/CRESTAxAW/ERROR_SIGNAL'"
                
                
                elif "initialization" in exist_param[kf] and exist_param[kf]["initialization"] is not None:
                    ist = exist_param[kf]["initialization"]
                    exist_param[kf]["initialization"] = [ist]
                    if ist in self.objects_instance_types and \
                        fluent_general_param[gen_k]["type"] in self.objects_instance_types[ist]:
                        bit_mask.append(1)
                        allocation_instance_mask.append(ist)
                    else:
                        return exist_param, "'/CRESTAxAW/ERROR_SIGNAL'"
                
                elif "initialization" in exist_param[kf] and exist_param[kf]["initialization"] is None:
                    exist_param[kf]["initialization"] = []
                    bit_mask.append(0)
                    allocation_type_mask.append(fluent_general_param[gen_k]["type"])
                
                
                elif "initialization" not in exist_param[kf]:
                    exist_param[kf]["initialization"] = [] 

                    bit_mask.append(0)
                    allocation_type_mask.append(fluent_general_param[gen_k]["type"])
                
                else:
                    print("(Default Reasoner Manager) ERROR while checking initialization for key={} in if param of fluent={}.".format(kf, fluent), flush=True)
                    return exist_param, "'/CRESTAxAW/ERROR_SIGNAL'"
                                   
            elif kf not in exist_param and kf in self.objects_instance_types and \
                fluent_general_param[gen_k]["type"] in self.objects_instance_types[kf]:
                bit_mask.append(1)
                allocation_instance_mask.append(kf)
            else:
                print("(Default Reasoner Manager) ERROR while checking fluent {} value for exist operator in if rule: params mismatch.".format(fluent), flush=True)
                return exist_param, "'/CRESTAxAW/ERROR_SIGNAL'"

 
        for type in allocation_type_mask:
            if type == '/CRESTAxDRM/POSSIBLE_VALUES_ALREADY_GENERATED':
                
                try:
                    allocation_possible_values.append(allocation_possible_values_from_param.pop(0) )
                except Exception as e:
                    print("(Default Reasoner Manager) ERROR while retrieving possible values already generated: %s"%e, flush=True)
                    return exist_param, "'/CRESTAxAW/ERROR_SIGNAL'"
            else:
                allocation_possible_values.append(self.objects_type_instances[type])
        
        fluent_param_instance_combinations = self.generate_combinations(bit_mask, allocation_instance_mask, allocation_possible_values)
        # TODO: maybe order fluent_param_instance_combinations with the combinations in the "initialization" of the fluent at the head positions of the list to be more efficient 
 
        for idx, not_to_initialize in enumerate(bit_mask):
            if not not_to_initialize:
                 
                exist_param[fluent_exist_param_list[idx]]["initialization"] = []
 
        is_combination_found = False
        for combination in fluent_param_instance_combinations:
            fluent_value = self.retrieve_fluent_value_kb_withparam_instance(fluent, combination, fluent_general_data)

            if fluent_value == fluent_exist_data["value"]:  

                is_combination_found = True

                for idx, not_to_initialize in enumerate(bit_mask):
                    if not not_to_initialize:
                        exist_param[fluent_exist_param_list[idx]]["initialization"].append(combination[idx])  
        return exist_param, is_combination_found 
    

    def check_fluent_in_if_rule(self, if_params, fluent_name, fluent_data):
        
        if fluent_name in self.fluents_data: 
            return self.checkExistsonFluent4If(fluent_name, if_params, fluent_data, self.fluents_data[fluent_name])
        else:
            return if_params, False

    def solve_then_in_if_rule(self, if_params, key, key_data, key_general_data):

        output = {}
        output[key] = {}
        output[key]["initialization"] = []

        fluent_value = None
        
        if "value" in key_data:
            fluent_value = key_data["value"]            
        else:
            print(f"(Default Reasoner Manager) ERROR in then part of if rule for fluent={key}: missing desired value.", flush=True )
            return {} 
        
        if fluent_value is None:                 
            output[key]["initialization"] = None 
            return output
        
        key_general_data_params = {}
        key_general_data_params_list = []
        if "parameters" in key_general_data:
            key_general_data_params = key_general_data["parameters"]
            key_general_data_params_list = list(key_general_data_params.keys())
        
        key_data_params_list = []
        if "parameters" in key_data:
            key_data_params_list = key_data["parameters"]


        if len(key_data_params_list) != len(key_general_data_params_list):
            print(f"(Default Reasoner Manager) ERROR in then part of if rule for fluent={key}: bad parameters.", flush=True )
            return {} 

        bit_mask = [] 
        allocation_instance_mask = [] 
        allocation_possible_values=[]
        
        for idx, param in enumerate(key_data_params_list):
            if param in if_params:
                if "initialization" in if_params[param] and (if_params[param]["initialization"] is not None and if_params[param]["initialization"]!=[]):
                    if if_params[param]["initialization"].__class__ == [].__class__:
                        if len(if_params[param]["initialization"]) == 1:
                            bit_mask.append(1)
                            allocation_instance_mask.append(if_params[param]["initialization"][0])
                        else:
                            bit_mask.append(0)
                            allocation_possible_values.append(if_params[param]["initialization"])
                    else:
                        bit_mask.append(1)
                        allocation_instance_mask.append(if_params[param]["initialization"])

                else:
                    print(f"(Default Reasoner Manager) ERROR in then part of if rule for fluent={key}: bad initialization in if rule for parameter={param}.", flush=True )
                    return {} 
            else:
                if param in self.objects_instance_types and \
                key_general_data_params[key_general_data_params_list[idx]]["type"] in self.objects_instance_types[param]:
                    bit_mask.append(1)
                    allocation_instance_mask.append(param)
                else:
                    print(f"(Default Reasoner Manager) ERROR in then part of if rule for fluent={key}: bad parameter={param}.", flush=True )
                    return {} 

        fluent_param_instance_combinations = self.generate_combinations(bit_mask, allocation_instance_mask, allocation_possible_values)
        
        if len(key_general_data_params_list) == 0:
            output[key]["initialization"] = fluent_value
        else:
            for key_params in fluent_param_instance_combinations:
                init_item = {"parameters":key_params, "value": fluent_value}
                output[key]["initialization"].append(init_item)
        
        return output 

    def solve_if_rule(self, if_rule):
        params = {}
        if "parameters" in if_rule:
            params = if_rule["parameters"]
         
        conditions = {}
        if "conditions" in if_rule:
            conditions = if_rule["conditions"]
        else:
            print(f"(Default Reaoner Manager) WARNING: no conditions statement in if rule={if_rule}.", flush=True)

        then = {}
        if "then" in if_rule:
            then = if_rule["then"]
        else:
            print(f"(Default Reaoner Manager) ERROR: no then statement in if rule={if_rule}.", flush=True)
            return False, {}  
        
        is_rule_to_solve = False
        for key in then:
            if key in self.what_to_reason:
                is_rule_to_solve = True
                break


        # Order keys in conditions such that all keys of fluent type are after the keys of action type
        action_keys = []
        fluent_keys = []
        try:
            action_keys = [key for key, value in conditions.items() if value["type"] == "action"]
            fluent_keys = [key for key, value in conditions.items() if value["type"] == "fluent"]
        except Exception as e:
            print(f"(Default Reaoner Manager) ERROR while sorting keys in conditions of if rule={if_rule}.", flush=True)
            return False, {} 

        sorted_conditions = action_keys + fluent_keys 
 

        tot_conditions = True
        for key in sorted_conditions:
            key_data = conditions[key] 

            if "type" in key_data and key_data["type"] == "action" and key in self.kb_data["actions"]:
         

                params, check_action = self.check_action_in_if_rule(params, key, key_data)
                tot_conditions = tot_conditions and check_action
 

            elif "type" in key_data and key_data["type"] == "fluent" and key in self.fluents_data:
                params, check_fluent = self.check_fluent_in_if_rule(params, key, key_data)
                tot_conditions = tot_conditions and check_fluent
 

            else:
                print(f"(Default Reasoner Manager) ERROR for if condition={key}: bad type.")
                tot_conditions = False 

            if not tot_conditions:
                break
  
        if tot_conditions:  

            output = {}
            for key in then:
                key_data = then[key]

                if "type" in key_data and key_data["type"] == "fluent" and key in self.fluents_data:
                    key_output = self.solve_then_in_if_rule(params, key, key_data, self.fluents_data[key])
                    output = {**output, **key_output}
                
                else:
                    print(f"(Default Reasoner Manager) ERROR for if then-condition={key}: bad type.")
                    return False, {}
            return True, output
        else:
            return False, {}  
    
    def solver(self):  

        if len(self.what_to_reason)==0:   
            return {}
        
        if self.reasoning_rules == {}:   
            return {}
        
        output = {}
        for json_rule in self.reasoning_rules["rules"]:
            dict_rule = json_rule["rule"]
            if_rule = dict_rule["if"]

            self.sem_kb_data.acquire()
            if self.kb_data == {}:
                self.sem_kb_data.release()
                break   
            solver_success, rule_output = self.solve_if_rule(if_rule)
            self.sem_kb_data.release()

            output = {**output, **rule_output}

        print("OUTPUT: ", output )

        return output


    def run(self): 
        while not rospy.is_shutdown():              

            # rospy.loginfo("Running Default Reasoner Manager")

            output = self.solver() 

            if output != {}:

                msg = String()
                msg.data = json.dumps(output)
                self.fluents4wm_pub.publish(msg)

 
            self.rate.sleep()
 
         
def main():
    try:
        node = DefaultReasonerManager()
        node.run()
    except rospy.ROSInterruptException:
        pass
     

if __name__ == '__main__':
    main()

 

