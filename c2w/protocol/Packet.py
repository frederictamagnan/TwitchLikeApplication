import c2w.protocol.utils as utils
import struct

class Packet:


    def __init__(self,message_type,num_seq,packet_length,data=[],format=""):
        self.message_type=message_type
        self.num_seq=num_seq
        self.packet_length=packet_length
        self.data=data
        self.packet_format=format





    def pack(self):

        #First, we transform our attributes from int to bits
        num_seqB = utils.binRes(self.num_seq, 10)

        message_typeB = utils.binRes(self.message_type, 8)

        packet_lengthB = utils.binRes(self.packet_length, 14)

        entireStrB =  message_typeB +num_seqB + packet_lengthB



        #Then we transform our entire field of bits into a dec

        dec = int(entireStrB, 2)



        if self.message_type in [0,48]:
            pack=struct.pack("!LB" + str(self.data[0]) + "s", dec,self.data[0], self.data[1].encode("utf-8"))

        elif self.message_type in [2,1,80,49,3]:
            print(dec)
            pack=struct.pack("!L",dec)

        elif self.message_type == 128:
            print(dec)
            pack = struct.pack("!LB" + str(self.data[0]) + "s", dec, self.data[0], self.data[1].encode("utf-8"))

        elif self.message_type in [16,19,64,65,18]:


            pack=struct.pack(self.packet_format,dec,*self.data)




        else:
            pass

        # elif self.message_type in [64,65]:
        #     pack=struct.pack("iB"+str(self.data[0])+'s'+"B"+str(self.data[2])+'s',dec,self.data[0],self.data[1].encode('utf8'),self.data[2],self.data[3].encode('utf8'))
        #     print('chat pack success')








        # print("PACK : ",pack)
        return pack



    def unpackHeader(self,datagram):
        """
        this method unpack the header from a datagram and update the parameter of the new packet
        :param datagram:
        :return: none
        """

        # Message = bin(struct.unpack("L", datagram)[0])[2:]
        header= struct.unpack_from("!L", datagram)
        # print("header from datagram",header)
        header=utils.binRes(header[0],32)
        # print("header in binary",header,"len",len(header))
        
        self.message_type = int(header[:8],2)
        self.num_seq = int(header[8:18],2)
        self.packet_length = int(header[18:32],2)



    def isEqual(self,packet2):
        a= self.num_seq==packet2.num_seq
        b= self.message_type==packet2.message_type
        c=self.packet_length==packet2.packet_length
        d=self.packet_format==packet2.packet_format
        e=self.data==packet2.data

        if  a and b and c and d and e:
            return True
        else:
            return False





    def __repr__(self):

        return "num_seq : " + str(self.num_seq)+"\nmessage_type : "+str(self.message_type)+"\npacket_length :"+str(self.packet_length)+"\ndata : "+str(self.data)+"\nformat :"+self.packet_format
