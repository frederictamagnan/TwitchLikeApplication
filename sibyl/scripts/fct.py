# -*- coding: utf-8 -*-
"""
Created on Sat Sep 16 13:46:12 2017

@author: massal
"""
import struct

def build(msg,time):
     buff=bytearray(len(msg)+6)   
     struct.pack_into('!LH'+str(len(msg))+'s', buff, 0, time, 6+len(msg), msg.encode('utf-8'))
     return(buff)
def destroy(forme,line):
    
    return(struct.unpack_from(forme,line))

