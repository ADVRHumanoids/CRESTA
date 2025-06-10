#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import rospy  
import rospkg
import json
import threading 

import cv2
from cv_bridge import CvBridge



from std_msgs.msg import String 
from cresta_msgs.msg import ObjectStatusList 
from cresta_msgs.srv import (ClientToServerString, ClientToServerStringResponse, 
                             ClientToServerInt, ClientToServerIntResponse) 


# This module implements CRESTA World Model's Procedural Ontology (wm_proc_ont) component  


class ProceduralOntologyManager():
    def __init__(self): 

        # Initialize ROS node
        rospy.init_node('procedural_ontology_manager', anonymous=False)

        self.rate = rospy.Rate(60) 

        # initialize variables for procedural ontology 
        self.sem_objects_from_perception = threading.Semaphore(1)

        self.fluents_to_query = None 

        self.fluents_to_query_list = None 

        self.object_types = None  

        self.last_frame_ID = None

        self.last_frame = None  

        self.objects_from_perception = None

        self.bridge = CvBridge()

        # get an instance of RosPack with the default search paths
        self.rospack = rospkg.RosPack()
        self.cresta_wm_path = self.rospack.get_path('cresta_world_model')
         

       
        # data service: starts/update Ontology   
        fluents_to_query_service = rospy.Service('/procedural_ontology/set_what_to_query', ClientToServerString, self.handle_fluents_to_query_service)

        # shutdown service
        shutdown_service = rospy.Service('/wm_ontology_mgr/procedural_ont/shutdown_node_service', ClientToServerInt, self.handle_shutdown_service)


        # init Subscriber on Perception about object status
        # This Subscriber is initialized only in the case it is useful, 
        # i.e. if there are Objects in fluents to query  
        self.objects_status_sub = None


        self.fluents4wm_pub = rospy.Publisher('/wm_ontology_mgr/procedural_ont/fluents4wm', String, queue_size =10) 


        self.objs4wm_pub = rospy.Publisher('/wm_ontology_mgr/procedural_ont/objs4wm', String, queue_size =10)
       

      
    def handle_fluents_to_query_service(self, msg):

        print("(Procedural Ontology Manager) Received fluents to query.", flush=True)

        
        if self.fluents_to_query is None:

            try:                  
                self.fluents_to_query = json.loads(msg.data)

                self.fluents_to_query_list = list(self.fluents_to_query.keys())

                unique_element_types = set()
                
                value_list = list(self.fluents_to_query.values())

                # Iterate through the list and add elements to the set
                for item in value_list:
                    if "object_types" in item:
                        unique_element_types.update(item["object_types"])

                # Convert the set back to a list
                self.object_types = list(unique_element_types)

                if len(self.object_types) > 0 and self.objects_status_sub is None:

                    # init Subscriber on Perception about object status
                    # init this Subscriber only in the case it is useful, 
                    # i.e. if there are Objects in fluents to query   
                    self.objects_status_sub = rospy.Subscriber('/cresta_perception/yolo/object_status', ObjectStatusList, self.receive_objects_status_sub)

 
            except Exception as e: 
                print("(Procedural Ontology Manager) ERROR while loading JSON data: %s"%e) 
                return ClientToServerStringResponse(success=False) 
         
            
        return ClientToServerStringResponse(success=True)
                   
    
    def receive_objects_status_sub(self, msg):
        exeOnce = True
 
        local_objects_from_perception=[]

        objs4wm = {}

        for obj_status_msg in msg.objects_data: 
            
            if obj_status_msg.object_class in self.object_types: 
                
                if exeOnce: 
                    self.last_frame_ID = obj_status_msg.frame_ID

                    try:
                        self.last_frame = self.bridge.compressed_imgmsg_to_cv2(obj_status_msg.frame, "bgr8")
                         
                    except Exception as e:
                        print(e)
 

                    image_filename = os.path.join(self.save_dir, f'image_{obj_status_msg.frame_ID}.jpg')
                    cv2.imwrite(image_filename, self.last_frame)

                    exeOnce = False
                

                obj_status_msg.segmentation_mask = None 
                obj_status_msg.frame = None 


                local_objects_from_perception.append(obj_status_msg)

                obj_name_instance = obj_status_msg.object_class.lower()+str(obj_status_msg.object_ID)
                objs4wm[obj_name_instance] = {"type": None, "x": None, "y": None, "image": None}
                objs4wm[obj_name_instance]["type"] = obj_status_msg.object_class
                objs4wm[obj_name_instance]["x"] = obj_status_msg.bounding_box_center[0]
                objs4wm[obj_name_instance]["y"] = obj_status_msg.bounding_box_center[1]
                objs4wm[obj_name_instance]["image"] = image_filename
        
    

        self.sem_objects_from_perception.acquire()
        self.objects_from_perception = local_objects_from_perception
        self.sem_objects_from_perception.release()

        objs4wm_msg = String()
        objs4wm_msg.data = json.dumps(objs4wm)

        self.objs4wm_pub.publish(objs4wm_msg)

    def manage_fluents_to_query(self):
        if self.objects_from_perception is not None:
             
            output = {}
            for fluent in self.fluents_to_query_list:

                if fluent == "object_detected":
                    output[fluent] = self.object_detected_cb()
            
            return output
        
        return None
    
    def object_detected_cb(self):
        
        output = {"initialization" : []}
 
        self.sem_objects_from_perception.acquire()
        local_objects_from_perception = self.objects_from_perception
        self.sem_objects_from_perception.release()

        # Iterate through the list and add elements to the set
        for msg in local_objects_from_perception:
            obj_name_instance = msg.object_class.lower()+str(msg.object_ID)

            dict_value = {"parameters": [], "value": True }
            dict_value["parameters"].append(obj_name_instance)
            output["initialization"].append(dict_value)
        
        
        return output
    
    def handle_shutdown_service(self, msg): 
        if msg.data:
            # Shutting down the node
            print("(Procedural Ontology Manager) Shutting down the node.", flush=True)

            try:
                self.objects_status_sub.unregister()
            except:
                pass
          
            self.fluents4wm_pub.unregister() 
            self.objs4wm_pub.unregister() 

            rospy.signal_shutdown("(Procedural Ontology Manager) Shutting down the node.")

        return ClientToServerIntResponse(success=True)


    def run(self): 
        while not rospy.is_shutdown():              
            # rospy.loginfo("Running Procedural Ontology Manager")

            output = self.manage_fluents_to_query()

            if output is not None:

                msg = String()

                msg.data = json.dumps(output)

                self.fluents4wm_pub.publish(msg)

                self.rate.sleep()
 
         
def main():
    try:
        node = ProceduralOntologyManager()
        node.run()
    except rospy.ROSInterruptException:
        pass
     

if __name__ == '__main__':
    main()

 

