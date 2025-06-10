#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import rospy  
import json

from cresta_msgs.srv import ClientToServerString, ClientToServerStringRequest, ClientToServerStringResponse


# This module implements CRESTA World Model's Reasoner (wm_rs) component  
 
 
class ReasonerManager():
    def __init__(self): 

        # Initialize ROS node
        rospy.init_node('reasoner_manager', anonymous=False)

        self.rate = rospy.Rate(60) 

        # initialize variables for reasoner  
        self.what_to_reason = {} 

        self.initialized_reasoner_modules = {}
        
        # data service: starts/update Reasoner  
        what_to_reason_service = rospy.Service('/wm_reasoner_mgr/what_to_reason', ClientToServerString, self.handle_what_to_reason_service)

        print("(Reasoner Manager) Reasoner successfully initialized! State:Running.", flush=True)     


      
    def handle_what_to_reason_service(self, msg):

        print("(Reasoner Manager) Received what to reason.", flush=True)     
         
        tmp = msg.data

        tmp_what_to_reason= json.loads(tmp) 
         

        if self.what_to_reason != tmp_what_to_reason:
            
            self.what_to_reason = tmp_what_to_reason

            # Init reasoner modules 
            
            reasoner_modules_list = list(self.what_to_reason.keys()) 

            for module in reasoner_modules_list:
 
                if module not in self.initialized_reasoner_modules:
                    # Module's what to reason service
                    rospy.wait_for_service('/'+ module + '/set_what_to_reason', timeout=10)
                    cmd = "self."+ module + "_set_service = rospy.ServiceProxy('/" + module + "/set_what_to_reason', ClientToServerString)"

                    try: 
                        exec(cmd) 
                    except:
                        print("(Reasoner Manager) ERROR while initializing set what to reason service for reasoner module={}: exec taking bad command: \n".format(module), cmd, flush=True)

                    print("(Reasoner Manager) Initialized Reasoner module={}".format(module), flush=True)
                    
                    self.initialized_reasoner_modules[module] = self.what_to_reason[module]
                    msg = ClientToServerStringRequest()
                    msg.data = json.dumps(self.what_to_reason[module])
 
                    cmd = "self."+ module + "_set_service(msg)"
                    try: 
                        exec(cmd) 
                    except:
                        print("(Reasoner Manager) ERROR while calling set what to reason service for reasoner module={}: exec taking bad command: \n".format(module), cmd, flush=True)

                    
                elif module in self.initialized_reasoner_modules:
                    if self.what_to_reason[module] != self.initialized_reasoner_modules[module]:
                        self.initialized_reasoner_modules[module] = self.what_to_reason[module]
                        msg = ClientToServerStringRequest()
                        msg.data = json.dumps(self.what_to_reason[module])
                        cmd = "self."+ module + "_set_service(msg)"
                        try: 
                            exec(cmd) 
                        except:
                            print("(Reasoner Manager) ERROR while calling set what to reason service for reasoner module={}: exec taking bad command: \n".format(module), cmd, flush=True)
 
         


        return ClientToServerStringResponse(success=True)
    


    def run(self): 
        while not rospy.is_shutdown():              

            # rospy.loginfo("Running Reasoner Manager")
 
            self.rate.sleep()
 
         
def main():
    try:
        node = ReasonerManager()
        node.run()
    except rospy.ROSInterruptException:
        pass
     

if __name__ == '__main__':
    main()

 

