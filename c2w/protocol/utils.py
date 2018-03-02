import struct


def binRes(integer, nbBits):
#converts decimal to binary written in nbBits
    integerB = bin(integer)[2:]#We should delete the two first bits "0b"
    while len(integerB) < nbBits:
        integerB = '0' + integerB
    return integerB


def fieldToBinaryStr(numSeq, typeOfMessage, longueur):
#concatenate binary value of fields of header as an str  
    numSeqB = binRes(numSeq, 10)
    typeOfMessageB = binRes(typeOfMessage, 8)
    longueurB = binRes(longueur, 14)
    entireStrB = numSeqB + typeOfMessageB + longueurB
    return entireStrB

def BinaryStrToDec(entireStrB):
#converts bianry number to decimal
    return int(entireStrB, 2)


def packDec(dec,message):
#returns the whole message on hexa 
    return struct.pack("L"+str(len(message))+"s", dec, message)
#L refers to 4 bytes 


def unpackDec(datagram):#datagram=header(32)+message(32)
    #Message=struct.unpack("L3s",message)[0]
    #Message=bin(struct.unpack("L3s",message)[0])[2:]
    #numSeqB = Message[:8]
    #typeOfMessageB = Message[8:18]
    #longueurB = Message[18:32]

	Header =unpack_from('!L',datagram)#decimal value of header
	BinHeader=bin(Header)[2:]#binary value of header
	length_message=int(BinHeader[18:32],2)-1#decimal value of length message exclu header
	HeaderDec,LengthMessage,Message=struct.unpack('!LB'+str(length_message)+'s',datagram)#decode of whole message 
	print(data)
	Message=bin(data)
	typeOfMessageB= int(Message[:8],2)
	num_seq = int(Message[8:18],2)
	longueurB = int(Message[18:32],2)
	print(typeOfMessageB,num_seq,longueurB)

