import rospy
from cresta_world_model.ros.reasoner_mgr import *

        
def main():
    try:
        node = ReasonerManager()
        node.run()
    except rospy.ROSInterruptException:
        pass
     

if __name__ == '__main__':
    main()