#!/usr/bin/env python3 
# -*- coding: utf-8 -*-

from cresta_msgs.msg import ObjectStatus


def msgObjectStatus():
    """
    Header header
    string object_class
    int8 object_ID
    float64 confidence 
    float64[] bounding_box_vertices  
    float64[] bounding_box_center 
    float64[] bounding_box_vertices_meter
    float64[] bounding_box_center_meter
    float64[] bounding_box_wh
    std_msgs/Float64MultiArray segmentation_mask
    """
    msg = ObjectStatus() 
    msg.object_class = ""
    msg.object_ID = ""
    msg.confidence = -1  
    msg.bounding_box_vertices = [] 
    msg.bounding_box_center = [] 
    msg.bounding_box_vertices_meter = [] 
    msg.bounding_box_center_meter = [] 
    msg.bounding_box_wh = [] 
    msg.segmentation_mask = [] 
    return msg
