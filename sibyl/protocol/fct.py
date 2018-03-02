
import struct

print("ok")
def test():
	print ('abc')

def build(msg,time):

     buff=bytearray(len(msg)+6)   
     struct.pack_into('!LH'+str(len(msg))+'s', buff, 0, time, 6+len(msg), msg.encode('utf-8'))
     return(buff)


def unpack(forme,line):
    l=struct.unpack_from(forme,line)
    return(l)
