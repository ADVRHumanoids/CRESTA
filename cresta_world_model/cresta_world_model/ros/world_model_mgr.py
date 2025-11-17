#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import rospy  
import json

from cresta_world_model.core.knowledge_base_mgr import *
 
from cresta_msgs.srv import ClientToServerString, ClientToServerStringResponse


# This module implements CRESTA World Model (wm) component  
 

class WorldModelManager():
    def __init__(self): 

        # Initialize ROS node
        rospy.init_node('world_model_manager', anonymous=False)

        self.rate = rospy.Rate(60) 

        # initialize variables for wm
        self.knowledge_base_mgr = None 
        self.task_data = None
        self.actions_data = None 
       
        # task data service: starts/update World Model 
        task_data_service = rospy.Service('/wm_manager/tttask/task_data_service', ClientToServerString, self.handle_task_data_service)

        
    
      
    def handle_task_data_service(self, msg):
        if self.actions_data is None:

            try: 
                self.actions_data = json.loads(msg.data)
                self.actions_data = self.actions_data["action_data"]
                print("(WM Manager) Received action data", flush=True)
            except Exception as e: 
                print("(WM Manager) ERROR while loading JSON action data: %s"%e, flsuh=True) 
                return ClientToServerStringResponse(success=False)
            
        
        if self.task_data is None:
            try: 
                self.task_data = json.loads(msg.data)
                self.task_data = self.task_data["task_data"]
                print("(WM Manager) Received task data", flush=True)
            except Exception as e: 
                print("(WM Manager) ERROR while loading JSON task data: %s"%e, flsuh=True) 
                return ClientToServerStringResponse(success=False)
            
        if self.knowledge_base_mgr is None and self.task_data is not None and self.actions_data is not None: 
            print("(WM Manager) Calling Knowledge Base Manager...", flush=True)
            self.knowledge_base_mgr = KnowledgeBaseManager(self.task_data, self.actions_data)
             
              
            
        return ClientToServerStringResponse(success=True)
                   


    def run(self): 
        while not rospy.is_shutdown():              
            # rospy.loginfo("Running World Model Manager") 

            if self.knowledge_base_mgr is not None:
                self.knowledge_base_mgr.run()

            self.rate.sleep()
 
         
def main():
    try:
        node = WorldModelManager()
        node.run()
    except rospy.ROSInterruptException:
        pass
     

if __name__ == '__main__':
    main()


