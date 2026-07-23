#!/usr/bin/env python3 
# -*- coding: utf-8 -*-

import os
import cv2
import json
import rospy  
import threading 
from ultralytics import YOLO   
from dataclasses import dataclass

from cv_bridge import CvBridge, CvBridgeError
from sensor_msgs.msg import Image, CompressedImage, CameraInfo
from std_msgs.msg import MultiArrayDimension 

from cresta_msgs.msg import ObjectStatus, ObjectStatusList
from cresta_msgs.srv import ClientToServerString, ClientToServerStringResponse


# This ROS node implements the YOLO plugin   

# Triples of 30 different colors
rgb_colors = [
    (255, 0, 0),     # Red
    (0, 255, 0),     # Green
    (0, 0, 255),     # Blue
    (255, 255, 0),   # Yellow
    (0, 255, 255),   # Cyan
    (255, 0, 255),   # Magenta
    (128, 0, 0),     # Maroon
    (0, 128, 0),     # Dark Green
    (0, 0, 128),     # Navy
    (128, 128, 0),   # Olive
    (128, 0, 128),   # Purple
    (0, 128, 128),   # Teal
    (192, 192, 192), # Silver
    (128, 128, 128), # Gray
    (255, 165, 0),   # Orange
    (255, 20, 147),  # Deep Pink
    (0, 100, 0),     # Dark Green
    (75, 0, 130),    # Indigo
    (238, 130, 238), # Violet
    (173, 216, 230), # Light Blue
    (255, 192, 203), # Pink
    (244, 164, 96),  # Sandy Brown
    (46, 139, 87),   # Sea Green
    (210, 105, 30),  # Chocolate
    (0, 191, 255),   # Deep Sky Blue
    (70, 130, 180),  # Steel Blue
    (123, 104, 238), # Medium Slate Blue
    (220, 20, 60),   # Crimson
    (250, 128, 114), # Salmon
    (154, 205, 50),  # Yellow Green
]
 
@dataclass
class CameraIntrinsics:
    width: int = 0
    height: int = 0
    cx: float = 0.0
    cy: float = 0.0
    fx: float = 0.0
    fy: float = 0.0
    model: str = ''
    coeffs: list = None

    def __post_init__(self):
        if self.coeffs is None:
            self.coeffs = []

class YOLOInference():
    def __init__(self):

        # Initialize ROS node 
        rospy.init_node('cresta_perception_yolo_inference', anonymous=False)

        self.rate = rospy.Rate(60)   
 
 
        # Get the parameters
        weights_path = rospy.get_param('~weights_path')
        weights_version = rospy.get_param('~weights_version')
        image_topic = rospy.get_param('~image_topic')
        camera_info_topic = rospy.get_param('~camera_info_topic')
        self.detection_confidence_threshold = rospy.get_param('~detection_confidence_threshold')
        self.cuda_device = rospy.get_param('~cuda_device')
        self.verbose = rospy.get_param('~verbose')
        self.visualize_boundbox = rospy.get_param('~visualize_boundbox')
 

        if weights_path == None: 
            print("(YOLO plugin) ERROR: weights_path missing.", flush=True)
            return None 

        if image_topic.endswith("compressed"):
            self.sub_compressed = True
            print("(YOLO plugin) Receiving compressed images", flush=True)
        else:
            self.sub_compressed = False
            print("(YOLO plugin) Receiving raw images", flush=True)


        # Initialize variables  
        self.sem_frame_data = threading.Semaphore(1) 
        self.what_to_perceive = {}                   # {"object_types":["Door", "Handle"], "fluents": ["fluent1", ...] }
        self.class_to_perceive = []
        self._color_frame = []                       # store the color frame 
        self._intrinsics= CameraIntrinsics()         # store the camera info
        self.detection_response = []      
        self.bridge = CvBridge() 
        self.image_received_header_seq = 0
        self.image_received_header_stamp = rospy.Time.now()
        self.image_received_header_frame_id = ""
        self.color_frame_id = 0


        # Initialize subscribers 
        if self.sub_compressed:
            self.img_sub = rospy.Subscriber(image_topic, CompressedImage, self.getColorFrame)
        else:
            self.img_sub = rospy.Subscriber(image_topic, Image, self.getColorFrame)       


        self.camera_info_sub = rospy.Subscriber(camera_info_topic, CameraInfo, self.getCameraInfo)
 

        # Initialize model & useful variables
         
        # Load weights (model for object instance segmentation)
        path_to_weights = os.path.join(weights_path, weights_version)
        self.model_detection = YOLO(path_to_weights)  

        # Model classes 
        self.model_detection_classes = self.model_detection.names # dictionary {id_number: "class_name"}
        
        try: 
            # Invert the dictionary
            self.model_detection_classes_inverted = {v: k for k, v in self.model_detection_classes.items()}  # dictionary {"class_name": id_number}
        except Exception as e:
            print("(YOLO plugin) ERROR: model detection classes dictionary is NOT invertible, %s"%e, flush=True)
            return 
    
        self.map_modelclasses_2_crestatypes = {"bottle": "Bottle", "door": "Door", "handle":"Handle"}
        self.map_crestatypes_2_modelclasses = {"Bottle": "bottle", "Door": "door", "Handle":"handle"}
        
        

        # Initialize publishers
        # 1. pub object_status
        self.object_status_pub = rospy.Publisher('/cresta_perception/yolo/object_status', ObjectStatusList, queue_size=10) 
        """while self.object_status_pub.get_num_connections() == 0:
            rospy.loginfo("Inference: waiting for subscriber to connect.")
            self.rate.sleep()"""
    
        # 2. pub visualize_boundbox
        if self.visualize_boundbox:
            self.visualize_boundbox_pub = rospy.Publisher(
                '/cresta_perception/yolo/visualize_boundbox/image_raw/compressed', CompressedImage, queue_size=1)
         
         
        # Initialize services 
        # 1. start what_to_perceive_service
        self.what_to_perceive_service = rospy.Service('/yolo/set_what_to_perceive', ClientToServerString, self.set_what_to_perceive_service) 
         

    # Service callback      
    def set_what_to_perceive_service(self, msg):
        self.what_to_perceive = json.loads(msg.data) 
        values_list = self.what_to_perceive["object_types"]
        values_list.extend(self.what_to_perceive["fluents"])
        self.class_to_perceive = []
        for item in values_list:
            try: 
                yolo_class_name = self.map_crestatypes_2_modelclasses[item]
                
                self.class_to_perceive.append(self.model_detection_classes_inverted[yolo_class_name])
            except Exception as e:
                print("(YOLO plugin) ERROR: item={} in what to perceive not found in map. {}".format(item, e), flush=True)
                if item in self.model_detection_classes_inverted:
                    self.class_to_perceive.append(self.model_detection_classes_inverted[item])

        return ClientToServerStringResponse(success=True)

    # Callback function to receive the color frame    
    def getColorFrame(self, msg):  
        self.sem_frame_data.acquire()
        try:
            if self.sub_compressed:
                self._color_frame = self.bridge.compressed_imgmsg_to_cv2(msg, "bgr8")
            else:
                self._color_frame = self.bridge.imgmsg_to_cv2(msg, "bgr8") 
            self.image_received_header_seq = msg.header.seq
            self.image_received_header_stamp = msg.header.stamp
            self.image_received_header_frame_id = msg.header.frame_id

            self.color_frame_id += 1
            if self.color_frame_id == 500:
                self.color_frame_id = 1

        except CvBridgeError as e:
            print(e, flush=True)
        self.sem_frame_data.release()

    
    # Callback function to receive the camera info
    def getCameraInfo(self, cameraInfo): 
        self._intrinsics.width = cameraInfo.width
        self._intrinsics.height = cameraInfo.height
        self._intrinsics.cx = cameraInfo.K[2]
        self._intrinsics.cy = cameraInfo.K[5]
        self._intrinsics.fx = cameraInfo.K[0]
        self._intrinsics.fy = cameraInfo.K[4]
        self._intrinsics.model  = cameraInfo.distortion_model
        self._intrinsics.coeffs = [i for i in cameraInfo.D]  
        self.camera_info_sub.unregister()
    
    # Inference functions 
    def detect(self, frame, frame_id, object_classes_list): 
        # This function calls the model_detection for instance segmentation
        # and publishes the detections on the corresponding ROS topics.
        # It returns a customized list of items/predictions (e.g [item1, item2, item3,...]).
        # Each item is an ObjectStatus msg. 
        # In the returned list there will be only predictions with a confidence above a threshold (self.detection_confidence_threshold).
        
        # YOLO function to predict on a frame using the loaded model
        # TODO: implement parameter to select if to do tracking or not 
        # results = self.model_detection(source=frame, show=False, save=False, verbose=False, device=self.cuda_device)[0] 
        results = self.model_detection.track(source=frame, persist=True, conf=self.detection_confidence_threshold, classes=object_classes_list, show=False, save=False, verbose=False, device=self.cuda_device)[0] 
         

        if len(results)!= 0 : # case of predictions 

            confidence_list = results.boxes.conf.cpu().numpy() 
            detected_classes_list = results.boxes.cls.cpu().numpy().astype(int)

            if self.verbose:  
                print("Detected classes ID: ", detected_classes_list)   
                detected_classes_name = [ self.model_detection_classes[i] for i in detected_classes_list ] 
                print("Detected classes name: ", detected_classes_name)
                print("Confidence list of detected classes: ", confidence_list)  
                
            try:    
                xyxy = results.boxes.xyxy # left top corner (x1,y1) and right bottom corner (x2,y2)
                xyxy = xyxy.cpu().numpy()  
                
                xywh = results.boxes.xywh  # center (x,y), width and height of the bounding boxes 
                xywh = xywh.cpu().numpy()   

                if results.masks:
                    masks = results.masks.xy 
                else:
                    if self.verbose:
                        print("(YOLO plugin) No masks results available. Are you sure you are running a Segmentation model?", flush=True)
                    masks = [] 


                if results.boxes.id is not None:
                    track_ids = results.boxes.id.int().cpu().tolist()

                    if self.verbose:
                        print("Objects track ID: ", track_ids)
                else:
                    if self.verbose:
                        print("(YOLO plugin) No track ID results available. Are you sure you are running a Tracking model?", flush=True)
                    track_ids = [] 

               
            except Exception as e: 
                print("Error while extracting bounding boxes and masks from inference results: %s"%e)
                return []
            
             
            custom_pred =[]
            object_status_list_msg = ObjectStatusList()
            found_classes = {}
            __once__ = True

            __track_id_available__ = len(confidence_list) == len(track_ids)

            for idx, conf in enumerate(confidence_list):
                id_class = detected_classes_list[idx]

                if __track_id_available__:
                    track_id = track_ids[idx]
   
                class_name = self.model_detection_classes[id_class]                    
    
                # Initialize message corresponding to objects instance segmentation & detection 
                msg_object_status = ObjectStatus()   

                if id_class in found_classes:  
                    available_obj_id = found_classes[id_class]
                    found_classes[id_class] += 1
                else: 
                    found_classes[id_class] = 1
                    available_obj_id = 0

                try: 
                    msg_object_status.object_class = self.map_modelclasses_2_crestatypes[class_name]  
                except Exception as e:
                    print("(YOLO plugin) ERROR: object detected class={} in what to perceive not found in map. {}".format(class_name, e), flush=True)
                    if class_name in self.model_detection_classes_inverted:
                        msg_object_status.object_class = class_name

                msg_object_status.object_class_id = id_class
                msg_object_status.object_ID =  available_obj_id # TODO: rely on track_id 
                msg_object_status.confidence = conf 
                msg_object_status.bounding_box_vertices = [xyxy[idx][0],xyxy[idx][1], xyxy[idx][2], xyxy[idx][3]] 
                msg_object_status.bounding_box_center = [xywh[idx][0], xywh[idx][1]] 
                msg_object_status.bounding_box_vertices_meter = [(xyxy[idx][0]-self._intrinsics.cx)/self._intrinsics.fx,(xyxy[idx][1]-self._intrinsics.cy)/self._intrinsics.fy, (xyxy[idx][2]-self._intrinsics.cx)/self._intrinsics.fx, (xyxy[idx][3]-self._intrinsics.cy)/self._intrinsics.fy] 
                msg_object_status.bounding_box_center_meter = [(xywh[idx][0]-self._intrinsics.cx)/self._intrinsics.fx, (xywh[idx][1]-self._intrinsics.cy)/self._intrinsics.fy] 
                msg_object_status.bounding_box_wh = [xywh[idx][2], xywh[idx][3]] 

                shape_maks = masks[idx].shape
                flattened_mask = masks[idx].flatten()
                msg_object_status.segmentation_mask.data = flattened_mask
                msg_object_status.segmentation_mask.layout.dim.append(MultiArrayDimension())
                msg_object_status.segmentation_mask.layout.dim[0].label = 'rows'
                msg_object_status.segmentation_mask.layout.dim[0].size = shape_maks[0]
                msg_object_status.segmentation_mask.layout.dim[0].stride = shape_maks[1]
                msg_object_status.segmentation_mask.layout.dim.append(MultiArrayDimension())
                msg_object_status.segmentation_mask.layout.dim[1].label = 'cols'
                msg_object_status.segmentation_mask.layout.dim[1].size = shape_maks[1]
                msg_object_status.segmentation_mask.layout.dim[1].stride = 1


                msg_object_status.frame_ID = frame_id

                if __once__:
                    msg_object_status.frame = self.bridge.cv2_to_compressed_imgmsg(frame)
                    __once__ = False

                custom_pred.append(msg_object_status)

                object_status_list_msg.objects_data.append(msg_object_status)  

            self.object_status_pub.publish(object_status_list_msg)  

            return custom_pred
        
        return []
    

    def object_detection(self, object_classes_list):
        # This function returns a list:
        # list[0]: boolean (True: some detections available, False: no detections)
        # list[1]: corresponding color frame of the prediction (necessary because in the meanwhile the frame may be updated)
        # list[2]: list of predictions (from <detect> function)
        # list[3]: header's seq of the received image  
        # list[4]: header's stamp of the received image  
        # list[5]: header's frame id of the received image  
         
        if (len(self._color_frame) > 0): 
            self.sem_frame_data.acquire()
            color_frame = self._color_frame
            image_received_header_seq = self.image_received_header_seq 
            image_received_header_stamp  = self.image_received_header_stamp 
            image_received_header_frame_id = self.image_received_header_frame_id 
            color_frame_id = self.color_frame_id 
            self.sem_frame_data.release()
            
            predictions = self.detect(frame=color_frame, frame_id=color_frame_id, object_classes_list=object_classes_list) 
            if len(predictions)!=0:
                results = [True, color_frame, predictions, image_received_header_seq, image_received_header_stamp, image_received_header_frame_id]  
                return results

        return [False, [], [], None, None, None]



    # Draw bounding box from YOLO output 
    def draw_boundbox_yolo(self):  
        response = self.detection_response   # NOTE: Not needed       

        if len(response) != 0:
 
            image = response[1]           
            if response[0]:         

                predictions = response[2]  # This is a list of msg_object_status
                
                for obj in predictions:   
                    center_x = obj.bounding_box_center[0]
                    center_y = obj.bounding_box_center[1]
                    width = obj.bounding_box_wh[0]
                    height = obj.bounding_box_wh[1]

                    # Calculate the coordinates of the top-left and bottom-right corners of the rectangle
                    x1 = int(center_x - width / 2)
                    y1 = int(center_y - height / 2)
                    x2 = int(center_x + width / 2)
                    y2 = int(center_y + height / 2)

                    # Draw the rectangle on the image
                    cv2.rectangle(image, (x1, y1), (x2, y2), rgb_colors[obj.object_class_id % len(rgb_colors)], 2)
                    cv2.putText(image, obj.object_class + str(obj.object_ID) + " {:.2f}".format(obj.confidence), (x1, y1), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

                    # cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    # cv2.putText(image, obj.object_class + str(obj.object_ID) + " {:.2f}".format(obj.confidence), (x1, y1), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

                image_msg = self.bridge.cv2_to_compressed_imgmsg(image)
                image_msg.header.seq = response[3]
                image_msg.header.stamp = response[4]
                image_msg.header.frame_id = response[5]   

                return image_msg
        
        image_msg = self.bridge.cv2_to_compressed_imgmsg(self._color_frame)  
        return image_msg


    def run_inference(self):

        # Loop function: at each cycle run the inference on the updated data

        # rospy.loginfo("(YOLO plugin) Running inference.")

        if len(self._color_frame) == 0:
            rospy.logwarn_throttle(2, "(YOLO plugin) Received image is empty or no received at all!")
            return 
        
        if len(self.class_to_perceive) != 0: 
            self.detection_response = self.object_detection(self.class_to_perceive)

        if self.visualize_boundbox: 
            image_msg = self.draw_boundbox_yolo()
            self.visualize_boundbox_pub.publish(image_msg)
              
      
    def module_shutdown(self):
        self.img_sub.unregister() 
        self.object_status_pub.unregister()
        self.what_to_perceive_service.shutdown()


        
    def run(self): 
        while not rospy.is_shutdown():  
            self.run_inference() 
            # rospy.loginfo("Running YOLO plugin")
            self.rate.sleep()

        
def main():
    try:
        node = YOLOInference()
        node.run()
    except rospy.ROSInterruptException:
        pass
     

if __name__ == '__main__':
    main()
   
 