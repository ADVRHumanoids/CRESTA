#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import rospy  
import json

from cresta_msgs.srv import ClientToServerString, ClientToServerStringRequest, ClientToServerStringResponse


# This module implements CRESTA World Model's Ontology (wm_ont) component  

 
class OntologyManager():
    def __init__(self): 

        # Initialize ROS node
        rospy.init_node('ontology_manager', anonymous=False)

        self.rate = rospy.Rate(60) 

        # initialize variables for ontology  
        self.fluents_to_query = None 

        # initialize variables for ontology  
        self.what_to_query = {} 

        self.initialized_ontology_modules = {}

        
        # data service: starts/update Ontology 
        fluents_to_query_service = rospy.Service('/wm_ontology_mgr/fluents_to_query_service', ClientToServerString, self.handle_fluents_to_query_service)

        print("(Ontology Manager) Ontology initialized successfully! State: Running.", flush=True)
      
    def handle_fluents_to_query_service(self, msg):


        print("(Ontology Manager) Received fluents to query.", flush=True)

         
        tmp = msg.data

        tmp_what_to_query = json.loads(tmp) 
         

        if self.what_to_query != tmp_what_to_query:
            
            self.what_to_query = tmp_what_to_query

            # Init ontology modules 
            
            ontology_modules_list = list(self.what_to_query.keys()) 

            for module in ontology_modules_list:
 
                if module not in self.initialized_ontology_modules:
                    # Module's what to query service
                    rospy.wait_for_service('/'+ module + '/set_what_to_query', timeout=10)
                    cmd = "self."+ module + "_set_service = rospy.ServiceProxy('/" + module + "/set_what_to_query', ClientToServerString)"

                    try: 
                        exec(cmd) 
                    except:
                        print("(Ontology Manager) ERROR while initializing set what to query service for Ontology module={}: exec taking bad command: \n".format(module), cmd, flush=True)

                    print("(Ontology Manager) Initialized Ontology module={}".format(module), flush=True)
                    
                    self.initialized_ontology_modules[module] = self.what_to_query[module]
                    msg = ClientToServerStringRequest()
                    msg.data = json.dumps(self.what_to_query[module])
 
                    cmd = "self."+ module + "_set_service(msg)"
                    try: 
                        exec(cmd) 
                    except:
                        print("(Ontology Manager) ERROR while calling set what to query service for Ontology module={}: exec taking bad command: \n".format(module), cmd, flush=True)

                    
                elif module in self.initialized_ontology_modules:
                    if self.what_to_query[module] != self.initialized_ontology_modules[module]:
                        self.initialized_ontology_modules[module] = self.what_to_query[module]
                        msg = ClientToServerStringRequest()
                        msg.data = json.dumps(self.what_to_query[module])
                        cmd = "self."+ module + "_set_service(msg)"
                        try: 
                            exec(cmd) 
                        except:
                            print("(Ontology Manager) ERROR while calling set what to query service for Ontology module={}: exec taking bad command: \n".format(module), cmd, flush=True)
 
        return ClientToServerStringResponse(success=True)
                   

    def run(self): 
        while not rospy.is_shutdown():              
            # rospy.loginfo("Running Ontology Manager")
 
            self.rate.sleep()
 
         
def main():
    try:
        node = OntologyManager()
        node.run()
    except rospy.ROSInterruptException:
        pass
     

if __name__ == '__main__':
    main()

 

