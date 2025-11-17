import rospy
from cresta_world_model.ros.ontology_mgr import *

        
def main():
    try:
        node = OntologyManager()
        node.run()
    except rospy.ROSInterruptException:
        pass
     

if __name__ == '__main__':
    main()