#!/usr/bin/env python3 
# -*- coding: utf-8 -*-
 
import rospy   
import json  
 
from cresta_perception.utils.perception_utils import *

from cresta_msgs.srv import ClientToServerString, ClientToServerStringResponse, ClientToServerStringRequest
from cresta_msgs.utils.msg_constructors import *
 

# This ROS node implements CRESTA Perception Manager  


class PerceptionManager():
    def __init__(self):
        # Initialize ROS node 
        rospy.init_node('perception_manager', anonymous=False)

        self.rate = rospy.Rate(60) 
 
            
        self.what_to_perceive = {}   
        self.initialized_perception_modules = {}
 
        # initialize services 
        # 1. start what_to_perceive_service
        self.what_to_perceive_service = rospy.Service('/cresta_perception/perception_mgr/what_to_perceive', ClientToServerString, self.what_to_perceive_service) 
         
    def what_to_perceive_service(self, msg):
        tmp = msg.data

        tmp_what_to_perceive = json.loads(tmp)  

        if self.what_to_perceive != tmp_what_to_perceive:
            
            self.what_to_perceive = tmp_what_to_perceive

            # Init perception modules 
            
            perception_modules_list = list(self.what_to_perceive.keys()) 

            for module in perception_modules_list:
 

                if module not in self.initialized_perception_modules:
                    # Module's what to perceive service
                    rospy.wait_for_service('/'+ module + '/set_what_to_perceive')
                    cmd = "self."+ module + "_set_service = rospy.ServiceProxy('/" + module + "/set_what_to_perceive', ClientToServerString)"

                    try: 
                        exec(cmd) 
                    except:
                        print("(Perception Manager) ERROR while initializing set what to perceive service for perception module={}: exec taking bad command: \n".format(module), cmd, flush=True)

                    print("(Perception Manager) Initialized Perception module={}".format(module), flush=True)
                    
                    self.initialized_perception_modules[module] = self.what_to_perceive[module]
                    msg = ClientToServerStringRequest()
                    msg.data = json.dumps(self.what_to_perceive[module])
 
                    cmd = "self."+ module + "_set_service(msg)"
                    try: 
                        exec(cmd) 
                    except:
                        print("(Perception Manager) ERROR while calling set what to perceive service for perception module={}: exec taking bad command: \n".format(module), cmd, flush=True)

                    

                elif module in self.initialized_perception_modules:
                    if self.what_to_perceive[module] != self.initialized_perception_modules[module]:
                        self.initialized_perception_modules[module] = self.what_to_perceive[module]
                        msg = ClientToServerStringRequest()
                        msg.data = json.dumps(self.what_to_perceive[module])
                        cmd = "self."+ module + "_set_service(msg)"
                        try: 
                            exec(cmd) 
                        except:
                            print("(Perception Manager) ERROR while calling set what to perceive service for perception module={}: exec taking bad command: \n".format(module), cmd, flush=True)


        return ClientToServerStringResponse(success=True)
     
    def run(self): 
        while not rospy.is_shutdown():              
            # rospy.loginfo("Running Perception Manager")

            self.rate.sleep()

        
def main():
    try:
        node = PerceptionManager()
        node.run()
    except rospy.ROSInterruptException:
        pass
     

if __name__ == '__main__':
    main()
   
 