#!/usr/bin/env python3 
# -*- coding: utf-8 -*-
 
import json
import rospy    
from sensor_msgs.msg import SensorMsg
from std_msgs.msg import  String 
 
from cresta_msgs.srv import ClientToServerString, ClientToServerStringResponse


class PerceptionPluginTemplate():
    def __init__(self):
        # Initialize ROS node 
        rospy.init_node('cresta_perception_plugin', anonymous=False)

        self.rate = rospy.Rate(60)   
 
 
        # Get the parameters  
        sensor_topic = rospy.get_param('~sensor_topic') 

 
 
        if sensor_topic == None: 
            print("(Perception Plugin Template) ERROR: sensor topic missing.", flush=True)
            return None   
         
     


        # initialize variables   
        self.what_to_perceive = {}    # {"object_types":["Obj1", "Obj2"], "fluents": ["fluent1", ...] }
        self.class_to_perceive = []
        
        self._sensor_data = None
 


        # initialize subscribers 
        # 1. sub sensor 
        self.sensor_sub = rospy.Subscriber(sensor_topic, SensorMsg, self.getSensorData)  

        # initialize publishers
        # 1. pub output
        self.output_pub = rospy.Publisher("/perception_plugin_template/output", String, queue_size=10)
 
         
        # initialize services 
        # 1. start what_to_perceive_service
        self.what_to_perceive_service = rospy.Service('/perception_plugin_template/set_what_to_perceive', ClientToServerString, self.set_what_to_perceive_service) 
         

    # Service callback      
    def set_what_to_perceive_service(self, msg):
        self.what_to_perceive = json.loads(msg.data)  

        return ClientToServerStringResponse(success=True)

    # Callback function to receive the sensor data  
    def getSensorData(self, msg):   
        self._sensor_data = msg.data
          
         

    def compute_predicate_1(self):
        # Implement the perception inference 
         
        data = { 'predicate_1': {'initialization': None} }
        
        return data 



     

    def run_inference(self):
        # Loop function: at each cycle run the inference on the updated data

        # rospy.loginfo("(Perception Plugin Template) Running inference.")
 
         
        if len(self.class_to_perceive) != 0: 
            output = {} 
 
            if "predicate_1" in self.class_to_perceive:
                data = self.compute_predicate_1()       
                output = {**output, **data}

            
            msg = String()
            try: 
                msg.data = json.dumps(output)
                
                self.output_pub.publish(msg)
            except Exception as e:
                print("(Perception Plugin Template) ERROR while publishing output: output={}. {}".format(output, e), flush=True)
                    
  
              
      
    def module_shutdown(self):
        self.sensor_sub.unregister() 
        self.output_pub.unregister()
        self.what_to_perceive_service.shutdown()


        
    def run(self): 
        while not rospy.is_shutdown():  
            self.run_inference() 
            # rospy.loginfo("Running Perception Plugin Template")
            self.rate.sleep()

        
def main():
    try:
        node = PerceptionPluginTemplate()
        node.run()
    except rospy.ROSInterruptException:
        pass
     

if __name__ == '__main__':
    main()
   
 