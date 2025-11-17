import rospy
from cresta_perception.ros.perception_mgr import *

        
def main():
    try:
        node = PerceptionManager()
        node.run()
    except rospy.ROSInterruptException:
        pass
     

if __name__ == '__main__':
    main()