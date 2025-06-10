import numpy as np

"""
This file contains utils for CRESTA Perception
"""

class CounterInference():
     
    def __init__(self, window=3):
        self.cnt = [] 
        self.fluent_was_true = False
        self.window = window
    
    def check_consecutives(self):
        if len(self.cnt) == self.window:
            if all(i == 0 for i in self.cnt):
                self.fluent_was_true = False

            elif all(i == 1 for i in self.cnt) or self.fluent_was_true:
                self.fluent_was_true = True
                return 1
        return 0
    
    def up(self):
        if len(self.cnt) < self.window:
            self.cnt.append(1)
        else:
            self.cnt = self.cnt[1:]
            self.cnt.append(1)
        return self.check_consecutives()
    
    def down(self):
        if len(self.cnt) < self.window:
            self.cnt.append(0)
        else:
            self.cnt = self.cnt[1:]
            self.cnt.append(0)
        return self.check_consecutives()

    def get_counter(self):
        print("Counter: ", self.cnt)
        return self.cnt       


 