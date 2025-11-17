#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import rospy 
import rospkg 
import json 

from std_msgs.msg import String
from cresta_manager.core.task_awareness import *

from cresta_msgs.srv import (ClientToServerString, ClientToServerStringResponse, 
                                ServerToClientString, ServerToClientStringResponse, 
                                TaskActionPlan, TaskActionPlanResponse, 
                                ClientToServerInt, ClientToServerIntResponse, 
                                ClientToServerTTTask, ClientToServerTTTaskResponse, ClientToServerTTTaskRequest)
 

class TTTaskManager():
    def __init__(self):

        # initialize ROS node 
        rospy.init_node('tttask_manager', anonymous=False)  

        self.rate = rospy.Rate(60) 

        # get an instance of RosPack with the default search paths
        self.rospack = rospkg.RosPack() 

        # Get the parameters
        try: 
            self.tasks_path = rospy.get_param('~tasks_path') 
        except: 
            # get the default file path for cresta_manager task configs 
            self.cresta_manager_path = self.rospack.get_path('cresta_manager')
            self.tasks_path = os.path.join(self.cresta_manager_path, "configs", "task_configs")           
        
        try: 
            self.actions_path = rospy.get_param('~actions_path') 
        except: 
            # get the default file path for cresta_manager actions configs 
            self.cresta_manager_path = self.rospack.get_path('cresta_manager')
            self.actions_path = os.path.join(self.cresta_manager_path, "configs", "action_configs")           
         


        # initialization 
        self.tttask = None
        self.task = None     
        self.flag_tttask_initialized = False
        self.flag_initialization_complete = False
        self.task_config = None 
        self.actions_config = None 
        self.task_awareness = None
        self.task_data = None
        self.actions_data = None
        self.task_awareness_planning_trials = 20
        self.actions_list = []
        self.plan = []
        


        # init set TTTask service - set_tttask_service
        set_tttask_service = rospy.Service('/tttask_manager/tttask/set_tttask', ClientToServerTTTask, self.handle_set_tttask_service)

         
        # init task data service: starts/update World Model 
        rospy.wait_for_service('/wm_manager/tttask/task_data_service')
        try:
            self.task_data_service = rospy.ServiceProxy('/wm_manager/tttask/task_data_service', ClientToServerString) 
        except rospy.ServiceException as e:
            print("(TTTask Manager) Init task service from TTTask to WM Manager failed: %s"%e)


        # init update data service: starts World Model, Perception and updates Action Awareness  
        update_data_service = rospy.Service('/tttask_manager/tttask/update_data_service', ServerToClientString, self.handle_update_data_service)

         
        # Task Action Plan (TAP) service gives the task data, actions data and plan 
        tap_service = rospy.Service('/tttask_manager/tttask/tap_service', TaskActionPlan, self.handle_tap_service)

        # Action Awareness service to monitor feedbacks from the Action Awareness node.
        action_awareness_service = rospy.Service('/tttask_manager/tttask/action_awareness_service', ClientToServerInt, self.handle_aw_service)

        # init Subscriber on WM about task data 
        self.task_data_sub = rospy.Subscriber('/wm_manager/kb/kb_data', String, self.receive_task_data)


        # init Publisher for the computed plan 
        self.plan_pub = rospy.Publisher('/tttask_manager/tttask/plan', String, queue_size=10)
    
    def handle_set_tttask_service(self, msg):
        print("(TTTask Manager) Received TTTask", flush=True)

        # Extract TTTask
        if not self.flag_tttask_initialized:
            self.tttask = msg.tt_task
            self.task = self.tttask.task_id  
            return ClientToServerTTTaskResponse(success=True)
        else: 
            return ClientToServerTTTaskResponse(success=False)
 
    
    def handle_update_data_service(self, msg):         
        msg = ServerToClientStringResponse()
        if self.flag_tttask_initialized and self.task_data is not None: 
            msg.data = json.dumps(self.task_data)
            msg.success = True 
        else:
            msg.data = ""
            msg.success = False 
        return msg 
    
  
        
    def receive_task_data(self, msg): 
        recv_task_data = json.loads(msg.data)
        
        if self.flag_tttask_initialized and recv_task_data != self.task_data:
            print("(TTTask Manager) Update TTTask data received from World Model.", flush = True)

            self.task_data = recv_task_data
            self.flag_initialization_complete = False
            try: 
                self.flag_initialization_complete = self.task_awareness.update_task_data(self.task_data)  
                if self.flag_initialization_complete: 
                    print("(TTTask Manager) Task Awareness: PDDL problem updated successfully.", flush=True)
                else: 
                    print("(TTTask Manager) ERROR: (Task Awareness) PDDL problem updated NOT successfully, probably due to fluent not initialized.", flush=True)
            except Exception as e:
                print("(TTTask Manager) ERROR: updating Task Awareness failed. %s"%e, flush=True)
            
             
      
    
    def handle_tap_service(self, msg):
        msg = TaskActionPlanResponse()
        if self.flag_tttask_initialized: 
            self.tttask_plan()            
            msg.task_data = json.dumps(self.task_data)
            msg.actions_data = json.dumps(self.actions_data)
            msg.plan = self.actions_list
            msg.success = True

            self.plan = self.actions_list
            self.actions_list = []
        else:
            msg.task_data = ""
            msg.actions_data = ""
            msg.plan = []
            msg.success = False            
        return msg

    def tttask_plan(self):    
 
        if self.flag_initialization_complete: 
            self.result = 0
            trials = 0

            while not self.result and trials <= self.task_awareness_planning_trials:
                print("(TTTask Manager) Loop for Task Awareness Plan - trial n.{}".format(trials), flush=True)             
                trials += 1
                self.result = self.task_awareness.plan()
            
            if trials > self.task_awareness_planning_trials and not self.result: 
                print("(TTTask Manager) Max trials for planning reached: Impossible to find a plan.", flush=True)
                return 

            self.actions_list = []
            for action in self.result.plan.actions:

                action_name = str(action.action.name)
                item = action_name 
                params_tuple = action.actual_parameters
                if len(params_tuple) > 0:
                    for e in params_tuple:
                        item += '/'+str(e)

                 
                self.actions_list.append(item) 

            self.plan = self.actions_list
            print("(TTTask Manager) Plan found and available.", flush=True)
        else:
            print("(TTTask Manager) Attempt to call Task Awareness Plan, but PDDL problem not initialized.", flush=True)
 
     

    def handle_aw_service(self, msg):
        if self.flag_tttask_initialized:
            self.actions_list = []
            self.plan = []
            aw_feedback = msg.data
            
            if not aw_feedback and self.flag_initialization_complete: 
                print("(TTTask Manager) Received feedback from Action Awareness: current task <{}> execution failed.".format(self.task), flush=True)
                
                
                if self.flag_initialization_complete: 
                    self.result = 0
                    trials = 0

                    while not self.result and trials <= self.task_awareness_planning_trials:
                        print("(TTTask Manager) Loop for Task Awareness Plan - trial n.{}".format(trials), flush=True)             
                        trials += 1
                        self.result = self.task_awareness.plan()
                    
                    if trials > self.task_awareness_planning_trials and not self.result: 
                        print("(TTTask Manager) Max trials for planning reached: Impossible to find a plan.", flush=True)
                        msg = ClientToServerTTTaskRequest()
                        msg.tt_task = self.tttask
                        msg.success = False  

                        self.tttask = None
                        self.task = None 
                        self.flag_tttask_initialized = False
                        self.flag_initialization_complete = False
                        self.task_awareness = None    
                        self.task_data = None
                        self.actions_data = None 
                        self.actions_list = []
                        self.plan = []

                        return 

                    self.actions_list = []
                    for action in self.result.plan.actions:

                        action_name = str(action.action.name)
                        item = action_name 
                        params_tuple = action.actual_parameters
                        if len(params_tuple) > 0:
                            for e in params_tuple:
                                item += '/'+str(e)

                        self.actions_list.append(item)
                    self.plan = self.actions_list 
                    print("(TTTask Manager) Plan found and available.", flush=True)
                else:
                    print("(TTTask Manager) Attempt to call Task Awareness Plan, but PDDL problem not initialized.", flush=True)
        

            else:
                print("(TTTask Manager) Received feedback from Action Awareness: current task <{}> executed successfully.".format(self.task), flush=True) 
                msg = ClientToServerTTTaskRequest()
                msg.tt_task = self.tttask
                msg.success = True
                 
                self.actions_list = []
                self.plan = []
            
            return ClientToServerIntResponse(success=True)
    
        else:

            return ClientToServerIntResponse(success=False)

    def run(self): 
        while not rospy.is_shutdown():              

            if self.task is not None and not self.flag_tttask_initialized: 
                 

                self.task_config = os.path.join(self.tasks_path, self.task + ".json")
                self.actions_config = os.path.join(self.actions_path, "actions.json")

                try:
                    with open(self.task_config, "r") as task_file:
                        self.task_data = json.load(task_file)
                except FileNotFoundError:
                    print("(TTTask Manager) ERROR: Unable to find the task config file.")


                try:
                    with open(self.actions_config, "r") as actions_file:
                        self.actions_data = json.load(actions_file)
                except FileNotFoundError:
                    print("(TTTask Manager) ERROR: Unable to find the actions config file.")

                self.task_awareness = TaskAwareness(self.task_data, self.actions_data)
                self.flag_initialization_complete = False
                try: 
                    self.flag_initialization_complete = self.task_awareness.update_task_data(self.task_data)   
                    if self.flag_initialization_complete: 
                        print("(TTTask Manager) Task Awareness: PDDL problem updated successfully.", flush=True)
                    else: 
                        print("(TTTask Manager) ERROR: (Task Awareness) PDDL problem updated NOT successfully, probably due to fluent not initialized.", flush=True)
                except: 
                    print("(TTTask Manager) ERROR: updating Task Awareness failed.", flush=True)

                try: 
                    all_data = {"task_data": self.task_data, "action_data": self.actions_data}
                    self.task_data_service(json.dumps(all_data))
                except Exception as e:
                    print("(TTTask Manager) ERROR: starting WM Manager failed. Message: %s"%e, flush=True)
 
                self.flag_tttask_initialized = True



            msg = String()
            msg.data = json.dumps(self.plan)
            self.plan_pub.publish(msg)


            self.rate.sleep()

        
def main():
    try:
        node = TTTaskManager()
        node.run()
    except rospy.ROSInterruptException:
        pass
     

if __name__ == '__main__':
    main()
   