import rospy
from cresta_world_model.ros.procedural_ontology_mgr import *

        
def main():
    try:
        node = ProceduralOntologyManager()
        node.run()
    except rospy.ROSInterruptException:
        pass
     

if __name__ == '__main__':
    main()