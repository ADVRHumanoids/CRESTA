#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rospy
import json
import threading
from std_msgs.msg import String 
from cresta_msgs.msg import ActionStatus, ObjectStatusList, ObjectStatus
from cresta_msgs.srv import ClientToServerString, ClientToServerStringRequest 

 
# This module implements CRESTA Knowledge Base (kb)  
 

class KnowledgeBaseManager():
 

    def __init__(self, task_data = None, actions_data = None):  

        print("(KB Manager) Initializing Knowledge Base ...", flush=True)
        # initialize variables for kb
        self.sem_task_data = threading.Semaphore(1)
        
        self.wm_topic_prefix = '/wm_manager/kb'
        self.task_data = task_data
        self.actions_data = actions_data
        
        if self.task_data is not None: 
            self.fluents_dict = self.task_data["fluents"]
        else: 
            raise Exception("(KB Manager) Task data is None.")
        
        if self.actions_data is None: 
            raise Exception("(KB Manager) Actions data is None.")


         
        self.managed_by_perception = {}  
        self.managed_by_ontology = {}    
        self.managed_by_reasoner = {} 

        rospy.wait_for_service('/cresta_perception/perception_mgr/what_to_perceive', timeout=10)
        try:
            self.what_to_perceive_service = rospy.ServiceProxy('/cresta_perception/perception_mgr/what_to_perceive', ClientToServerString) 
        except rospy.ServiceException as e:
            print("(KB Manager) Init Perception Manager's what to perceive service failed: %s"%e)
    

        rospy.wait_for_service('/wm_ontology_mgr/fluents_to_query_service', timeout=10)
        try:
            self.fluents_to_query_service = rospy.ServiceProxy('/wm_ontology_mgr/fluents_to_query_service', ClientToServerString) 
        except rospy.ServiceException as e:
            print("(KB Manager) Init Ontology Manager's fluents to query service failed: %s"%e)
     
        rospy.wait_for_service('/wm_reasoner_mgr/what_to_reason', timeout=10)
        try:
            self.what_to_reason_service = rospy.ServiceProxy('/wm_reasoner_mgr/what_to_reason', ClientToServerString) 
        except rospy.ServiceException as e:
            print("(KB Manager) Init Reasoner Manager's what to reason service failed: %s"%e)
     
    
        self.init_kb()
 
         
        # init Subscriber on action execution status 
        act_exe_sub = rospy.Subscriber('/action_awareness/action_exe', ActionStatus, self.getActionExe)

        # init Subscriber to Procedural Ontology output  
        procedural_ont_sub = rospy.Subscriber('/wm_ontology_mgr/procedural_ont/fluents4wm', String, self.getProceduralOntology)
      
        # init Subscriber on Perception about object status 
        self.objects_status_sub = rospy.Subscriber('/cresta_perception/yolo/object_status', ObjectStatusList, self.receive_objects_status_sub)

        # init Publisher for KB  
        self.kb_data_pub = rospy.Publisher(self.wm_topic_prefix+'/kb_data', String, queue_size =10) 
    
        print("(KB Manager) Knowledge Base successfully initialized! State: Running.",  flush=True)

    
    def receive_objects_status_sub(self, msg):

        objs={}
        
        for obj_status_msg in msg.objects_data:     
 

            obj_name_instance = obj_status_msg.object_class.lower()+str(obj_status_msg.object_ID)
            objs[obj_name_instance] = {"type": obj_status_msg.object_class} 
        
        self.sem_task_data.acquire() 
        self.task_data["objects"]["instances"] = objs
        self.sem_task_data.release()

        
 

    def getProceduralOntology(self, msg): 
 
        try: 
            data = json.loads(msg.data)
        except Exception as e:
            print("(KB Manager) ERROR while loading json in procedural ontology callback: %s"%e, flush=True)
            return 
        
        for fluent in data:
            self.sem_task_data.acquire()

            if fluent in self.task_data["fluents"]:            
                self.task_data["fluents"][fluent]["initialization"] = data[fluent]["initialization"]

            self.sem_task_data.release()
        
    
            
       
    def getActionExe(self, msg):
        
        action_exe = msg.execution
        action = msg.name 
        action_params_list = msg.params
        action_success = msg.success
        
        self.sem_task_data.acquire()
        if action in self.task_data["actions"]:
            if action_exe == 1 or action_exe == True:
                self.task_data["actions"][action]["execution"] = 1
                self.task_data["actions"][action]["params"] = action_params_list
            else:
                self.task_data["actions"][action]["execution"] = 0
                self.task_data["actions"][action]["params"] = []
        self.sem_task_data.release()
        print(f"(KB Manager) Received ActionStatus in getActionExe: action={action}, params={action_params_list}, execution={action_exe} ", flush=True)
        

            
    def init_kb(self):
        if self.actions_data is not None:
            for act_sem in self.actions_data:
                if "mode" in self.actions_data[act_sem]:
                    if "managed_by" in self.actions_data[act_sem]["modes"]:
                        if "reasoner" in self.actions_data[act_sem]["modes"]["managed_by"]:
                            reasoner_methods = self.actions_data[act_sem]["modes"]["managed_by"]["reasoner"]
                            for method in reasoner_methods:
                                if method in self.managed_by_reasoner:
                                    self.managed_by_reasoner[method][act_sem] = self.actions_data[act_sem]["modes"]["available_modes"]
                                else:
                                    self.managed_by_reasoner[method] = {act_sem:{}}
                                    self.managed_by_reasoner[method][act_sem] = self.actions_data[act_sem]["modes"]["available_modes"]

        else:
            print("(KB Manager) ERROR while initializing KB: actions data is None")


        
        if self.task_data is not None:

            if "actions" not in self.task_data:
                print("(KB Manager) ERROR: no actions in task configuration file!", flush=True)
                return
        
            for act in self.task_data["actions"]:
                if "execution" not in self.task_data["actions"][act]:
                    self.task_data["actions"][act]["execution"] = 0
                if "params" not in self.task_data["actions"][act]:
                    self.task_data["actions"][act]["params"] = []
                if "success" not in self.task_data["actions"][act]:
                    self.task_data["actions"][act]["success"] = None

            if "objects" in self.task_data and "types" in self.task_data["objects"]:
                types = self.task_data["objects"]["types"]

                for tp in types:
                    if "managed_by" in types[tp]:
                        if "perception" in types[tp]["managed_by"]:
                            perception_methods = types[tp]["managed_by"]["perception"]

                            for method in perception_methods: 
                                if method in self.managed_by_perception:
                                    self.managed_by_perception[method]["object_types"].append(tp)
                                else:
                                    self.managed_by_perception[method] = {"object_types":[], "fluents":[]}
                                    self.managed_by_perception[method]["object_types"].append(tp)


                  
            self.fluents_dict = self.task_data["fluents"]

            sources = []
            for fluent in self.fluents_dict: 

                
                if "managed_by" in self.fluents_dict[fluent]:
                    
                    if "perception" in self.fluents_dict[fluent]["managed_by"]:
                        perception_methods = self.fluents_dict[fluent]["managed_by"]["perception"]
                        for method in perception_methods: 
                            if method in self.managed_by_perception: 
                                self.managed_by_perception[method]["fluents"].append(fluent)
                                
                            else:
                                self.managed_by_perception[method] = {"object_types":[], "fluents":[]}
                                self.managed_by_perception[method]["fluents"].append(fluent)
                         

                    if "reasoner" in self.fluents_dict[fluent]["managed_by"]:
                        reasoner_methods = self.fluents_dict[fluent]["managed_by"]["reasoner"]
                        for method in reasoner_methods:
                            if method in self.managed_by_reasoner:
                                self.managed_by_reasoner[method].append(fluent)
                            else:
                                self.managed_by_reasoner[method] = [fluent]


                    if "ontology" in self.fluents_dict[fluent]["managed_by"]:
                        ontology_methods = self.fluents_dict[fluent]["managed_by"]["ontology"]
                        for method in ontology_methods:
                            if method in self.managed_by_ontology:
                                self.managed_by_ontology[method][fluent] = self.fluents_dict[fluent]["property_for"]
                            else:
                                self.managed_by_ontology[method] = {}
                                self.managed_by_ontology[method][fluent] = self.fluents_dict[fluent]["property_for"]
             

                if "source" in self.fluents_dict[fluent]:
                    topic = self.fluents_dict[fluent]["source"]
                    
        
                    if topic not in sources:

                        sources.append(topic)

                         
                        callback_name = "getUpdateFluents"
                        rosmsg_name = "String"
                          
                        cmd = "locals()["+"'"+topic+"'"+"] = rospy.Subscriber("+"'"+topic+"'"+", "+rosmsg_name+", self."+callback_name+")" 
                        try: 
                            exec(cmd) 
                        except:
                            print("(KB Manager) ERROR while setting subscriber to topic={}: exec taking bad command: \n".format(topic), cmd)
            
            # - starts perception 
            msg = ClientToServerStringRequest()
            msg.data = json.dumps(self.managed_by_perception)
            self.what_to_perceive_service(msg)
            
            # - starts ontology  
            msg = ClientToServerStringRequest()
            msg.data = json.dumps(self.managed_by_ontology)
            self.fluents_to_query_service(msg)

            # - starts reasoner
            msg = ClientToServerStringRequest()
            msg.data = json.dumps(self.managed_by_reasoner)
            self.what_to_reason_service(msg)
        
        else:
            print("(KB Manager) ERROR while initializing KB: task data is None")

    def getUpdateFluents(self, msg): 
        try:
            data = json.loads(msg.data)
        except Exception as e:
            print("(KB Manager) ERROR while loading json in update fluents callback: %s"%e, flush=True)
            return 

        
        for fluent in data:
            self.sem_task_data.acquire()
            if fluent in self.task_data["fluents"]:
                self.task_data["fluents"][fluent]["initialization"] = data[fluent]["initialization"]
            self.sem_task_data.release()
            


    def run(self):
        
        msg = String()
        self.sem_task_data.acquire()
        msg.data = json.dumps(self.task_data) 
        self.sem_task_data.release()
        self.kb_data_pub.publish(msg)
             
