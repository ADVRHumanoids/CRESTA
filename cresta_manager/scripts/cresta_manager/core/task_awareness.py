#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Import all the shortcuts, an handy way of using the unified_planning framework
from unified_planning.shortcuts import *
 

# This module instantiates the reasoning problem and handles the planner for solving it. 
# It works using the AIPlan4EU Unified Planning Library, handling the PDDL logic.

class  TaskAwareness():
    def __init__(self, task_data, actions_data):
        if task_data == None:
            print("(Task Awareness) ERROR: task data no available.", flush=True)
            return

        if actions_data == None:
            print("(Task Awareness) ERROR: actions data no available.", flush=True)
            return

        self.KEY_LIST = ['Exists', 'Forall', 'Or', 'And', 'Not']
        self.KEY_LOGIC = ['Or']
        self.KEY_PARAMETERS = ['Exists', 'Forall']
        self.KEY_ONE_FLUENT = ['Exists', 'Forall']

        # Initialize task problem 
        self.task_data = task_data
        self.actions_data = actions_data
        self.init_problem()
        

    def init_problem(self):

        self.problem = Problem(self.task_data["task_name"])

        self.task_objects = None

        if "objects" in self.task_data:
            self.task_objects = self.task_data["objects"]

        if self.task_objects is not None and "types" in self.task_objects:
            self.objects_types = self.task_objects["types"]
            for type in self.objects_types: 
                cmd = "self."+type+"= UserType('"+type+"'"  
                if "father" in self.objects_types[type]:
                    cmd = cmd + ", father=self." + self.objects_types[type]["father"] + ")"  
                else: 
                    cmd = cmd + ")"
                try: 
                    exec(cmd) 
                except:
                    print("(Task Awareness) ERROR while setting object type={}: exec taking bad command: \n".format(type), cmd)
                  

        if self.task_objects is not None and "instances" in self.task_objects:
            self.objects_instances = self.task_objects["instances"]
            for instance in self.objects_instances: 
                if "type" in self.objects_instances[instance] and self.objects_instances[instance]["type"] in self.objects_types:
                    
                    cmd = "locals()["+"'"+instance+"'"+"] = Object("+ "'"+ instance + "'"+ ", self."+self.objects_instances[instance]["type"] +")"  
                    
                    try: 
                        exec(cmd) 
                        self.problem.add_objects([locals()[instance]])
                    except:
                        print("(Task Awareness) ERROR while setting object instance={} of type={}: exec taking bad command: \n".format(instance, self.objects_instances[instance]["type"]), cmd)
                   
                else: 
                    print("(Task Awareness) ERROR while setting object instance={}: type not available".format(instance))
      
        # Initialize fluents 
        if "fluents" in self.task_data:
            fluents_dict = self.task_data["fluents"]
            for fluent in fluents_dict:
                
                cmd = "locals()["+"'"+fluent+"'"+"] = Fluent('"+fluent+"'"
                fluent_type = "BoolType()"   
                if "type" in fluents_dict[fluent] and fluents_dict[fluent]["type"] == "bool" : 
                    fluent_type = "BoolType()"
                
                else:  # TODO: expand fluent types
                    print("(Task Awareness) ERROR: type of fluent not supported.", flush=True)
                     

                cmd = cmd + ", "+fluent_type

                 
                
                if "parameters" in fluents_dict[fluent]: 
                    fluent_params = fluents_dict[fluent]["parameters"]
                    for param in fluent_params:
                        if "type" in fluent_params[param] and fluent_params[param]["type"] in self.objects_types:
                            cmd = cmd + ", "+ param + "=self."+ fluent_params[param]["type"]  
                        else:
                            print("(Task Awareness) ERROR while setting parameter={} of fluent={}: exec taking bad command: \n".format(param, fluent), cmd)
 
                cmd = cmd + ")"  

                try: 
                    exec(cmd) 
                except:
                    print("(Task Awareness) ERROR while initializing fluent={}: exec taking bad command: \n".format(fluent), cmd)
            
                   

                if "default_initialization" in fluents_dict[fluent] and fluents_dict[fluent]["default_initialization"] != None: 
                    self.problem.add_fluent(locals()[fluent], default_initial_value=fluents_dict[fluent]["default_initialization"])
                else: 
                    self.problem.add_fluent(locals()[fluent])
                    print("(Task Awareness) WARNING while adding fluent={} in the task problem: NO default initialization value available".format(fluent))
                
                if "initialization" in fluents_dict[fluent] and fluents_dict[fluent]["initialization"] != None: 
                    init_list = fluents_dict[fluent]["initialization"]
                    
                    if init_list.__class__ == [].__class__:
                        for init in init_list:
                            if "parameters" in init:
                                cmd = "self.problem.set_initial_value(locals()["+"'"+fluent+"'"+"](" 
                            
                                param_list = init["parameters"]
                                isfirst = True 
                                for param in param_list:
                                    if param in self.objects_instances:  # TODO: add check if fluent's expected param type is equal to object type 
                                        if isfirst:
                                            isfirst = False
                                            cmd = cmd + "locals()["+"'"+param+"'"+"]"
                                        else: 
                                            cmd = cmd + ", " + "locals()["+"'"+param+"'"+"]"

                                    else:
                                        print("(Task Awareness) ERROR while initializing fluent={}: object not in instances".format(fluent))
                                        break
                                cmd = cmd + "), " + str(init["value"]) + ")" 

                                try: 
                                    exec(cmd) 
                                except:
                                    print("(Task Awareness) ERROR while initializing fluent={}: exec taking bad command: \n".format(fluent), cmd)
                
                                    
                            else:
                                self.problem.set_initial_value(locals()[fluent], init["value"])      
                    else:
                        self.problem.set_initial_value(locals()[fluent], init_list)      
    
                else:
                    print("(Task Awareness) WARNING while initializing fluent={} in the task problem: NO initialization values available".format(fluent))                
        else: 
            print("(Task Awareness) ERROR: in task data there are NOT fluents.")

        # Initialize actions 
        actions_list = list(self.actions_data.keys())
        for action in actions_list:
            if action not in self.task_data["actions"]:
                print("(Task Awareness) WARNING: initialization of action={} skipped because NOT in task actions.".format(action))
                continue
            
  
           

            action_info = self.actions_data[action]
            if "parameters" in action_info:
                cmd = "self."+action+ "= InstantaneousAction("+"'"+action+"'"  
                
                for param in action_info["parameters"]: 
                    param_info = action_info["parameters"][param]
                    if "type" in param_info and param_info["type"] in self.objects_types:
                        cmd = cmd + ", " + param + "=self."+param_info["type"]  
                    else:
                        cmd = "locals()["+"'"+action+"'"+"]= InstantaneousAction"  
                        print("(Task Awareness) ERROR while initializing action={}: action parameter's type not available".format(action))
                        break
                cmd = cmd + " )"
                try: 
                    exec(cmd) 
                except:
                    print("(Task Awareness) ERROR while initializing action={}: exec taking bad command: \n".format(action), cmd)
 
                for param in action_info["parameters"]:   
                    cmd = "locals()["+"'"+param+"'"+"]= self." + action + ".parameter(" +"'"+param+"'"+ ")"  

                    try: 
                        exec(cmd) 
                    except:
                        print("(Task Awareness) ERROR while initializing param={} of action={}: exec taking bad command: \n".format(param, action), cmd )
     
            else:
                 
                cmd = "self."+action+ "= InstantaneousAction("+"'"+action+"'" +")"
                try: 
                    exec(cmd) 
                except:
                    print("(Task Awareness) ERROR while initializing action={} (w/o param): exec taking bad command: \n".format( action), cmd )
     
            
            # Adding preconditions to action
            preconditions_dict = self.actions_data[action]["preconditions"]
            for fluent in preconditions_dict: 
                fluent_info = preconditions_dict[fluent]
                if "parameters" in fluent_info:
                    act_param_info = fluent_info["parameters"]

                    if preconditions_dict[fluent]["value"]:
                        cmd = "self."+action+".add_precondition(locals()["+"'"+fluent+"'"+"]("  
                    else:
                        cmd = "self."+action+".add_precondition(Not(locals()["+"'"+fluent+"'"+"]("  

                    isfirst = True 
                    for param in act_param_info:
                        if "type" in act_param_info[param] and act_param_info[param]["type"] in self.objects_types: # TODO: check that param type is consistent with the fluent 
                            if isfirst:
                                isfirst = False
                                cmd = cmd + "locals()["+"'"+param+"'"+"]"
                            else: 
                                cmd = cmd + ", " + "locals()["+"'"+param+"'"+"]"

                        else:
                            print("(Task Awareness) ERROR while initializing precondition fluent={} of action={}: type not available".format(fluent, action))
                            break
                    if preconditions_dict[fluent]["value"]:
                        cmd = cmd + "))" 
                    else:
                        cmd = cmd + ")))" 

                    try: 
                        exec(cmd) 
                    except:
                        print("(Task Awareness) ERROR while initializing precondition fluent={} of action={}: exec taking bad command: \n".format(fluent, action), cmd)
    
                        
                else:                    
                    if preconditions_dict[fluent]["value"]:
                        cmd = "self."+action+ ".add_precondition(locals()["+"'"+fluent+"'"+"])"  
                        try: 
                            exec(cmd) 
                        except:
                            print("(Task Awareness) ERROR while initializing positive precondition fluent={} of action={} (w/o param): exec taking bad command: \n".format(fluent, action), cmd )
     
                    else:
                        cmd = "self."+action+ ".add_precondition(Not(locals()["+"'"+fluent+"'"+"]))"  
                        try: 
                            exec(cmd) 
                        except:
                            print("(Task Awareness) ERROR while initializing negative precondition fluent={} of action={} (w/o param): exec taking bad command: \n".format(fluent, action), cmd )
     
            # Adding effects to action
            effects_dict = self.actions_data[action]["effects"]
            for fluent in effects_dict:  
                fluent_info = effects_dict[fluent]
                if "parameters" in fluent_info:
                    act_param_info = fluent_info["parameters"]

                    cmd = "self."+action+".add_effect(locals()["+"'"+fluent+"'"+"]("  

                    isfirst = True 
                    for param in act_param_info:
                        if "type" in act_param_info[param] and act_param_info[param]["type"] in self.objects_types:  # TODO: check that param type is consistent with the fluent
                            if isfirst:
                                isfirst = False
                                cmd = cmd + "locals()["+"'"+param+"'"+"]"
                            else: 
                                cmd = cmd + ", " + "locals()["+"'"+param+"'"+"]"

                        else:
                            print("(Task Awareness) ERROR while initializing effect fluent={} of action={}: type not available".format(fluent, action))
                            break 
                    
                    cmd = cmd + "), "+str(effects_dict[fluent]["value"])+")"  

                    try: 
                        exec(cmd) 
                    except:
                        print("(Task Awareness) ERROR while initializing effect fluent={} of action={}: exec taking bad command: \n".format(fluent, action), cmd)
    
                        
                else:  
                    if effects_dict[fluent]["value"]:
                        cmd = "self."+action+ ".add_effect(locals()["+"'"+fluent+"'"+"], True)"  
                        try: 
                            exec(cmd) 
                        except:
                            print("(Task Awareness) ERROR while initializing positive effect fluent={} of action={} (w/o param): exec taking bad command: \n".format(fluent, action), cmd )
     
                    else:
                        cmd = "self."+action+ ".add_effect(locals()["+"'"+fluent+"'"+"], False)"   
                        try: 
                            exec(cmd) 
                        except:
                            print("(Task Awareness) ERROR while initializing negative effect fluent={} of action={} (w/o param): exec taking bad command: \n".format(fluent, action), cmd )
     

            # Adding action to problem 
            cmd = "self.problem.add_action(self."+action+")" 
            try: 
                exec(cmd) 
            except:
                print("(Task Awareness) ERROR while adding action={} to problem: exec taking bad command: \n".format( action), cmd )
    

        goals_dict = self.task_data["goals"]
        for fluent in goals_dict:
            if "operator" in fluent: 
                if "parameters" in goals_dict[fluent]:
                    for param in goals_dict[fluent]["parameters"]:
                        param_info = goals_dict[fluent]["parameters"][param]
                        if "type" in param_info and param_info["type"] in self.objects_types:
                            cmd = "locals()[" + "'" + param + "'" +" ] = Variable("+ "'" + param + "'" +", self." + param_info["type"] + " ) "  

                            try: 
                                exec(cmd) 
                            except:
                                print("(Task Awareness) ERROR while initializing Variable={} for operator={}: exec taking bad command: \n".format(param, fluent), cmd)

                goal_formula = self.parse_operator_json2formula({"operator":goals_dict[fluent]})
                cmd = "self.problem.add_goal(" + goal_formula + ")"
                try: 
                    exec(cmd) 
                except:
                    print("(Task Awareness) ERROR while initializing operator={}: exec taking bad command: \n".format(fluent), cmd)

            else:
             
                fluent_info = goals_dict[fluent]
                if "parameters" in fluent_info:
                    goal_param_list = fluent_info["parameters"]

                    if goals_dict[fluent]["value"]:
                        cmd = "self.problem.add_goal(locals()["+"'"+fluent+"'"+"](" 
                    else:
                        cmd = "self.problem.add_goal(Not(locals()["+"'"+fluent+"'"+"](" 
                    
                    isfirst = True
                    for param in goal_param_list:
                        if isfirst:
                            isfirst = False
                            cmd = cmd + "locals()["+"'"+param+"'"+"]"
                        else: 
                            cmd = cmd + ", " + "locals()["+"'"+param+"'"+"]"

                        
                    if goals_dict[fluent]["value"]:
                        cmd = cmd + "))" 
                    else:
                        cmd = cmd + ")))" 

                    try: 
                        exec(cmd) 
                    except:
                        print("(Task Awareness) ERROR while initializing goal fluent={}: exec taking bad command: \n".format(fluent), cmd)

                        
                else:                   
                    
                    if goals_dict[fluent]["value"]:
                        self.problem.add_goal(locals()[fluent])
                    else:
                        self.problem.add_goal(Not(locals()[fluent]))
    
    def update_problem(self):
        flag_initialization_complete = True

        self.problem = Problem(self.task_data["task_name"])
 
        self.task_objects = None

        if "objects" in self.task_data:
            self.task_objects = self.task_data["objects"]


        if self.task_objects is not None and "types" in self.task_objects:
            self.objects_types = self.task_objects["types"]
            for type in self.objects_types: 
                cmd = "self."+type+"= UserType('"+type+"'"  
                if "father" in self.objects_types[type]:
                    cmd = cmd + ", father=self." + self.objects_types[type]["father"] + ")"  
                else: 
                    cmd = cmd + ")"
                try: 
                    exec(cmd) 
                except:
                    print("(Task Awareness) ERROR while setting object type={}: exec taking bad command: \n".format(type), cmd)
    

        if self.task_objects is not None and "instances" in self.task_objects:
            self.objects_instances = self.task_objects["instances"]
            for instance in self.objects_instances: 
                if "type" in self.objects_instances[instance] and self.objects_instances[instance]["type"] in self.objects_types:
                    
                    cmd = "locals()["+"'"+instance+"'"+"] = Object("+ "'"+ instance + "'"+ ", self."+self.objects_instances[instance]["type"] +")"  
                    
                    try: 
                        exec(cmd) 
                        self.problem.add_objects([locals()[instance]])
                    except:
                        print("(Task Awareness) ERROR while setting object instance={} of type={}: exec taking bad command: \n".format(instance, self.objects_instances[instance]["type"]), cmd)
                   
                else: 
                    print("(Task Awareness) ERROR while setting object instance={}: type not available".format(instance))
      
        if "fluents" in self.task_data:
            fluents_dict = self.task_data["fluents"]
            for fluent in fluents_dict:
                cmd = "locals()["+"'"+fluent+"'"+"] = Fluent('"+fluent+"'"
                fluent_type = "BoolType()"  
                if "type" in fluents_dict[fluent] and fluents_dict[fluent]["type"] == "bool" : 
                    fluent_type = "BoolType()"
                
                else:  # TODO: expand fluent types
                    print("(Task Awareness) ERROR: type of fluent not supported.", flush=True)
                     

                cmd = cmd + ", "+fluent_type
 
                
                if "parameters" in fluents_dict[fluent]: 
                    fluent_params = fluents_dict[fluent]["parameters"]
                    for param in fluent_params:
                        if "type" in fluent_params[param] and fluent_params[param]["type"] in self.objects_types:
                            cmd = cmd + ", "+ param + "=self."+ fluent_params[param]["type"]  
                        else:
                            print("(Task Awareness) ERROR while setting parameter={} of fluent={}: exec taking bad command: \n".format(param, fluent), cmd)
 
                cmd = cmd + ")"  

                try: 
                    exec(cmd) 
                except:
                    print("(Task Awareness) ERROR while initializing fluent={}: exec taking bad command: \n".format(fluent), cmd)
             
 
                flag_default_init_available = True

                if "default_initialization" in fluents_dict[fluent] and fluents_dict[fluent]["default_initialization"] != None: 
                    self.problem.add_fluent(locals()[fluent], default_initial_value=fluents_dict[fluent]["default_initialization"])
                else: 
                    flag_default_init_available = False
                    self.problem.add_fluent(locals()[fluent])
                    print("(Task Awareness) WARNING while adding fluent={} in the task problem: NO default initialization value available".format(fluent))
                
                if "initialization" in fluents_dict[fluent] and fluents_dict[fluent]["initialization"] != None: 
                    init_list = fluents_dict[fluent]["initialization"]
                     
                    if init_list.__class__ == [].__class__:
                        for init in init_list:
                            if "parameters" in init:
                                cmd = "self.problem.set_initial_value(locals()["+"'"+fluent+"'"+"](" 
                            
                                param_list = init["parameters"]
                                isfirst = True 
                                for param in param_list:
                                    if param in self.objects_instances:  # TODO: add check if fluent's expected param type is equal to object type
                                        if isfirst:
                                            isfirst = False
                                            cmd = cmd + "locals()["+"'"+param+"'"+"]"
                                        else: 
                                            cmd = cmd + ", " + "locals()["+"'"+param+"'"+"]"

                                    else:
                                        print("(Task Awareness) ERROR while initializing fluent={}: object not in instances".format(fluent))
                                        break
                                cmd = cmd + "), " + str(init["value"]) + ")" 

                                try: 
                                    exec(cmd) 
                                except:
                                    print("(Task Awareness) ERROR while initializing fluent={}: exec taking bad command: \n".format(fluent), cmd)
                
                                    
                            else:
                                self.problem.set_initial_value(locals()[fluent], init["value"])  
                    else:
                        self.problem.set_initial_value(locals()[fluent], init_list)      
    
                else:
                    flag_initialization_complete = flag_default_init_available or False
                    print("(Task Awareness) WARNING while initializing fluent={} in the task problem: NO initialization values available".format(fluent))                
        else: 
            print("(Task Awareness) ERROR: in task data there are NOT fluents.")

        actions_list = list(self.actions_data.keys())
        for action in actions_list:
            
            cmd = "self.problem.add_action(self."+action+")"
            try: 
                exec(cmd) 
            except:
                print("(Task Awareness) ERROR in update problem while adding action={}: exec taking bad command: \n".format(action), cmd)


        goals_dict = self.task_data["goals"]
        for fluent in goals_dict:
            if "operator" in fluent: 
                if "parameters" in goals_dict[fluent]:
                    for param in goals_dict[fluent]["parameters"]:
                        param_info = goals_dict[fluent]["parameters"][param]
                        if "type" in param_info and param_info["type"] in self.objects_types:
                            cmd = "locals()[" + "'" + param + "'" +" ] = Variable("+ "'" + param + "'" +", self." + param_info["type"] + " ) "  

                            try: 
                                exec(cmd) 
                            except:
                                print("(Task Awareness) ERROR while initializing Variable={} for operator={}: exec taking bad command: \n".format(param, fluent), cmd)

                goal_formula = self.parse_operator_json2formula({"operator":goals_dict[fluent]})
                cmd = "self.problem.add_goal(" + goal_formula + ")"
                try: 
                    exec(cmd) 
                except:
                    print("(Task Awareness) ERROR while initializing operator={}: exec taking bad command: \n".format(fluent), cmd)

            else:
             
                fluent_info = goals_dict[fluent]
                if "parameters" in fluent_info:
                    goal_param_list = fluent_info["parameters"]

                    if goals_dict[fluent]["value"]:
                        cmd = "self.problem.add_goal(locals()["+"'"+fluent+"'"+"](" 
                    else:
                        cmd = "self.problem.add_goal(Not(locals()["+"'"+fluent+"'"+"](" 
                    
                    isfirst = True
                    for param in goal_param_list:
                        if isfirst:
                            isfirst = False
                            cmd = cmd + "locals()["+"'"+param+"'"+"]"
                        else: 
                            cmd = cmd + ", " + "locals()["+"'"+param+"'"+"]"

                        
                    if goals_dict[fluent]["value"]:
                        cmd = cmd + "))" 
                    else:
                        cmd = cmd + ")))" 

                    try: 
                        exec(cmd) 
                    except:
                        print("(Task Awareness) ERROR while initializing goal fluent={}: exec taking bad command: \n".format(fluent), cmd)

                        
                else:                   
                    
                    if goals_dict[fluent]["value"]:
                        self.problem.add_goal(locals()[fluent])
                    else:
                        self.problem.add_goal(Not(locals()[fluent]))
        return flag_initialization_complete
        
    def parse_operator_json2formula(self, json_data): 
        operator = json_data.get('operator', {})

        key = operator.get('key', '')
        if key == '' or key not in self.KEY_LIST:
            print("ERROR")
            return

        if key in self.KEY_PARAMETERS:
            parameters = operator.get('parameters', {})
            parameter_list = [param_name for param_name in parameters.keys()]
            if parameter_list is None or parameter_list == []:
                print("ERROR Parameters")
                return

        fluents = operator.get('fluents', {})
        if len(list(fluents.keys())) == 0:
            print("ERROR Fluents")
            return
        if key not in self.KEY_ONE_FLUENT and len(list(fluents.keys())) == 1:
            print("ERROR Fluents 1 ")
            return


        conditions = []

        for fluent_name, fluent_info in fluents.items():
            fluent_value = fluent_info.get('value', 'true')   
            fluent_params = fluent_info.get('parameters', [])  


            if fluent_params:
                fluent_args = [param_name for param_name in fluent_params]
                fluent_condition = f"{fluent_name}({', '.join(fluent_args)})"
            else:
                fluent_condition = fluent_name

            if fluent_value == 'false':
                fluent_condition = f"Not({fluent_condition})"

            conditions.append(fluent_condition)

        if key in self.KEY_LOGIC:
            combined_conditions = f"{', '.join(conditions)}"
        else:
            if len(conditions) > 1:
                combined_conditions = f"And({', '.join(conditions)})"
            else:
                combined_conditions = conditions[0]

        operator_value = operator.get('value', 'true')
         

        exists_condition = f"{key}("

        if key in self.KEY_PARAMETERS:
            exists_condition += f"{combined_conditions}, {', '.join(parameter_list)})"
        else:
            exists_condition += f"{combined_conditions})"

        if operator_value == 'false':
            exists_condition = f"Not({exists_condition})"


        return exists_condition


    def plan(self):
         
        if self.task_data == None:
            return 0 

        with OneshotPlanner(problem_kind=self.problem.kind) as planner:
            result = planner.solve(self.problem)
            if result.status == up.engines.PlanGenerationResultStatus.SOLVED_SATISFICING:
                print("%s returned: %s" % (planner.name, result.plan))
                plan = result.plan
                with PlanValidator(problem_kind=self.problem.kind, plan_kind=plan.kind) as validator:
                    if validator.validate(self.problem, plan):
                        print('(Task Awareness) The plan is valid', flush=True)
                        return result
                    else:
                        print('(Task Awareness) ERROR: The plan is invalid', flush=True)
                        return 0                
            else:
                print("(Task Awareness) WARNING: No plan found.", flush=True)
                return 0

    def update_task_data(self, new_task_data):

        self.task_data = new_task_data

        flag_initialization_complete = self.update_problem()
        
         
        
        return flag_initialization_complete

        
        
