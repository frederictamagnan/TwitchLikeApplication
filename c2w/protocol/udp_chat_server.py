# -*- coding: utf-8 -*-
#derniermodifie
from twisted.internet.protocol import DatagramProtocol
from c2w.main.lossy_transport import LossyTransport
from c2w.main.constants import ROOM_IDS
import logging

from c2w.protocol.Packet import Packet
logging.basicConfig()
moduleLogger = logging.getLogger('c2w.protocol.udp_chat_server_protocol')
import struct
from twisted.internet import reactor


class c2wUdpChatServerProtocol(DatagramProtocol):

    def __init__(self, serverProxy, lossPr):
        """
        :param serverProxy: The serverProxy, which the protocol must use
            to interact with the user and movie store (i.e., the list of users
            and movies) in the server.
        :param lossPr: The packet loss probability for outgoing packets.  Do
            not modify this value!

        Class implementing the UDP version of the client protocol.

        .. note::
            You must write the implementation of this class.

        Each instance must have at least the following attribute:

        .. attribute:: serverProxy
            The serverProxy, which the protocol must use
            to interact with the user and movie store in the server.

        .. attribute:: lossPr

            The packet loss probability for outgoing packets.  Do
            not modify this value!  (It is used by startProtocol.)

        .. note::
            You must add attributes and methods to this class in order
            to have a working and complete implementation of the c2w
            protocol.
        """
        #: The serverProxy, which the protocol must use
        #: to interact with the server (to access the movie list and to
        #: access and modify the user list).
        self.serverProxy = serverProxy
        self.lossPr = lossPr
        self.num_seq={}
        self.user_adress={}
        self.received_packet_history={}
        self.sent_packet_history={}
        self.expected_num_seq={}
        self.errorList=["nonExpectedNumSeq","wrongUserName","serverSaturated","userExists"]
        self.timer={}
        self.movieRoom={}
        self.errorDict={}

        for movie in self.serverProxy.getMovieList():
            self.serverProxy.startStreamingMovie(movie.movieTitle)

        self.sendAndWait=True

        self.queuepacket=[]
    def startProtocol(self):
        """
        DO NOT MODIFY THE FIRST TWO LINES OF THIS METHOD!!

        If in doubt, do not add anything to this method.  Just ignore it.
        It is used to randomly drop outgoing packets if the -l
        command line option is used.
        """
        self.transport = LossyTransport(self.transport, self.lossPr)
        DatagramProtocol.transport = self.transport

    def datagramReceived(self, datagram, host_port):
        """
        :param string datagram: the payload of the UDP packet.
        :param host_port: a touple containing the source IP address and port.

        Twisted calls this method when the server has received a UDP
        packet.  You cannot change the signature of this method.
        """

        packet = Packet(0, 0,0, 0)
        packet.unpackHeader(datagram)
        print("SERVER RECEIVING PACKET",packet)


        if self.serverProxy.getUserByAddress(host_port) is not None:
            user_name = self.serverProxy.getUserByAddress(host_port).userName

        elif host_port in self.num_seq.keys():
            user_name=host_port

        else:
            user_name=None
        print('host_port',host_port)



        #if the datagram received is not an ack then we send an ack
        if packet.message_type != 80:
            self.ack(packet,host_port)

        if packet.message_type==0:

            self.connectionResponse(datagram, packet, host_port)




        #if it's and ack of connecion done we send user list then movielist

        elif (packet.message_type ==80):
            if packet.num_seq==self.num_seq[user_name]:

                self.num_seq[user_name] =(self.num_seq[user_name]+1)% 1023

                if self.timer[user_name] != None:
                    self.timer[user_name].cancel()
                    self.timer[user_name]=None
                self.sendAndWait=True
                self.sendqueuepacket()

                if self.lastPacketSent(user_name).message_type==1:
                    self.updateUserList(ROOM_IDS.MAIN_ROOM)


                elif self.nlastPacketSent(user_name,2).message_type==1:
                    self.sendMovieList(user_name, host_port)

                elif self.lastPacketSent(user_name).message_type==2:

                    self.error(self.errorDict[user_name],host_port,user_name)


            else:
                return 0 #old ack

        elif packet.num_seq in self.received_packet_history.keys() and  self.received_packet_history[packet.num_seq].isEqual(packet):
            print("paquet ignoré",packet,self.received_packet_history[packet.num_seq])


        elif self.expected_num_seq[user_name]!=packet.num_seq:

            self.wrongExpectedNumSeq(host_port,user_name)
            print("ERROR")

        #if it's and ack of connecion done we send movie list then userlist
        #here we are sure that the num sq is verified and that i's not an ack
        else:
                self.received_packet_history[user_name][packet.num_seq]=packet
                self.expected_num_seq[user_name]=(self.expected_num_seq[user_name]+1)%1023
                if packet.message_type==64:
                    print("MESSAGE BIEN RECU")
                    self.forward(packet,datagram,host_port,user_name)
                elif packet.message_type==48:

                    self.connectionMovieRoom(datagram,packet,host_port,user_name)

                elif packet.message_type==49:
                    self.deconnectionMovieRoom(datagram,packet,host_port,user_name)
                elif packet.message_type==3:
                    self.leaveSystem(user_name)
                elif packet.message==128:
                    self.errorReceived( datagram,user_name)

    def forward(self,packet,datagram,host_port,user_name):


        len_sender=struct.unpack_from('!B',datagram,offset=4)[0]

        format='!LB'+str(len_sender)+'sB'+str(packet.packet_length-2-len_sender)+'s'

        packet.data=[0,0,0,0]
        headerDec, packet.data[0],packet.data[1],packet.data[2],packet.data[3]=struct.unpack(format,datagram)


        if self.malformed(packet.data[3].decode('utf8')):

            self.error("malformed message",host_port,user_name=user_name)
        else:
            user_chat_room_dict=self.getUserChatRoomDict()

            if self.movieRoom[packet.data[1].decode('utf8')]==ROOM_IDS.MAIN_ROOM:
                sender_chat_room="main_room"
            else:
                sender_chat_room=self.movieRoom[packet.data[1].decode('utf8')]

            i=0
            while i <len(user_chat_room_dict[sender_chat_room]):
                receiver=user_chat_room_dict[sender_chat_room][i]
                print("FORWARD5")
                messagePacket=Packet(65,self.num_seq[receiver],packet.packet_length,packet.data,format)
                #messagePacket.packet_format="!LB" + str(self.data[0]) + 's' + "B" + str(self.data[2]) + 's'
                self.sendPacket(messagePacket,self.serverProxy.getUserByName(receiver).userAddress)
                print("FORWARD6")
                i+=1


    def connectionMovieRoom(self,datagram,packet,host_port,user_name):

        packet = Packet(0, 0, 0, 0)
        packet.unpackHeader(datagram)

        format = '!LB' + str(packet.packet_length - 1) + 's'
        packet.data = [0, 0]
        headerDec, packet.data[0], packet.data[1] = struct.unpack(format, datagram)
        # the joined room
        if self.existMovie(packet.data[1].decode("utf-8"))==False:
            self.error('Movie Room Does Not Exist', host_port,user_name)
            print(packet.data[1].decode("utf-8"),'Movie Room Does Not Exist',self.serverProxy.getMovieList())
        else:
            print('the room does exist ')
            self.movieRoom[user_name] = (packet.data[1].decode("utf-8"))
            # mettre à jour la liste des utilisateur du movie room dans le serveur
            self.serverProxy.updateUserChatroom(user_name, self.movieRoom[user_name])
            # self.serverProxy.startStreamingMovie(self.movieRoom[user_name])
            self.updateUserList(movie_room=self.movieRoom[user_name])


    def existMovie(self,movieRoom):
        Exist=False
        for movie in self.serverProxy.getMovieList():
                if movieRoom ==movie.movieTitle:
                    Exist= True
        return(Exist)

    def leaveSystem(self,user_name):

        old_movie_room = self.movieRoom[user_name]
        self.serverProxy.removeUser(user_name)
        self.updateUserList(movie_room=old_movie_room)


    def deconnectionMovieRoom(self,datagram,packet,host_port,user_name):

        old_movie_room=self.movieRoom[user_name]
        self.movieRoom[user_name] = ROOM_IDS.MAIN_ROOM
        self.serverProxy.updateUserChatroom(user_name, self.movieRoom[user_name])

        self.updateUserList(movie_room=old_movie_room)
        print('sent_packet_history', self.sent_packet_history)
        print('received_packet_history', self.received_packet_history)


    def connectionResponse(self,datagram,packet,host_port):

        packet = Packet(0, 0, 0, 0)
        packet.unpackHeader(datagram)

        format = '!LB' + str(packet.packet_length - 1) + 's'
        packet.data = [0, 0]
        headerDec, packet.data[0], packet.data[1] = struct.unpack(format, datagram)


        userName=packet.data[1].decode("utf-8")


        if self.serverProxy.userExists(userName):

            #num seq a traiter #todo


            self.expected_num_seq[host_port] = 1
            self.num_seq[host_port] = 0
            self.sent_packet_history[host_port] = {}
            self.received_packet_history[host_port] = {}
            self.failed(host_port)

            self.errorDict[host_port] = "userExists"
        elif self.malformed(userName,user_name=True)==True:
            self.expected_num_seq[host_port] = 1
            self.num_seq[host_port] = 0
            self.sent_packet_history[host_port] = {}
            self.received_packet_history[host_port] = {}
            self.failed(host_port)
            self.errorDict[host_port]="malformed User Name"




        elif len(self.serverProxy.getUserList())>=513:


            self.expected_num_seq[host_port] = 1
            self.num_seq[host_port] = 0
            self.sent_packet_history[host_port] = {}
            self.received_packet_history[host_port] = {}
            self.failed(host_port)
            self.errorDict[host_port] = "serverSaturated"



        else:
            self.expected_num_seq[userName]=1
            self.num_seq[userName]=0
            self.sent_packet_history[userName]={}
            self.received_packet_history[userName]={}


            self.serverProxy.addUser(userName, ROOM_IDS.MAIN_ROOM, None, host_port)
            self.movieRoom[userName]=ROOM_IDS.MAIN_ROOM
            connectionDone = Packet(1, self.num_seq[userName], 0, '')

            self.sendPacket(connectionDone, host_port)

            #?????
            self.serverProxy.updateUserChatroom(userName, ROOM_IDS.MAIN_ROOM)




    def malformed(self,message,user_name=False):

        if not user_name:
            message=message[:-1]
            return False

        elif len(message)==0 or (len(message)<=255 and message[0].isalpha() and (len(message)==1 or message[1:].isalnum())):
            return False

        return True

    def ack(self,packet,host_port):

        ack=Packet(80,packet.num_seq,0,None)
        self.transport.write(ack.pack(), host_port)
        print('ACKACKACK')

    def error(self,errorType,host_port,user_name):
            error=Packet(128,self.num_seq[user_name],len(errorType)+1,[len(errorType),errorType])
            self.sendPacket(error, host_port)

    def errorReceived(self, datagram,user_name):

        packet = Packet(0, 0, 0, 0)
        packet.unpackHeader(datagram)

        format = '!LB' + str(packet.packet_length - 1) + 's'
        packet.data = [0, 0]
        headerDec, packet.data[0], packet.data[1] = struct.unpack(format, datagram)

        if 'wrongNumSeq:' in packet.data[1].decode('utf8'):
            self.num_seq[user_name] = int(packet.data[1][12:].decode("utf8"))
        print("error :", packet.data[1].decode("utf8"))
        return 0


    def wrongExpectedNumSeq(self,host_port,user_name):
        self.error('wrongNumSeq:'+str(self.expected_num_seq[user_name]), host_port)


    def failed(self,host_port):

        failed=Packet(2,self.num_seq[host_port],0,'')
        self.sendPacket(failed, host_port)




    def sendMovieList(self,user_name,host_port):
        # we send list of movie sorted


        movie_list=self.serverProxy.getMovieList()
        movie_list = sorted(movie_list, key=lambda x: x.movieTitle)

        data=[]
        length=2
        format="!LH"
        data.append(len(movie_list))

        for movie in movie_list:
            format += "B"+str(len(movie.movieTitle))+"sBBBBH"
            data.append(len(movie.movieTitle))

            data.append(movie.movieTitle.encode("utf-8"))
            print('movie.movieIpAddress',movie.movieIpAddress)
            data = data + list(map(int, movie.movieIpAddress.split(".")))
            data.append(movie.moviePort)
            # 1 byte -> lenghtmovie title, 4 bytes -> length ipv4 , 2 bytes -> port
            length=length+1+len(movie.movieTitle)+4+2

        movie_list_packet=Packet(16,self.num_seq[user_name],length,data,format)


        self.sendPacket(movie_list_packet,host_port)


    def updateUserList(self, movie_room):
        # if user joined a main room: WE SEND TO EACH USER IN MAIN ROOM (EVEN THE USER HIMSELF) "UserListMainRoom"
        # if user joined a movie room: WE SEND TO EACH USER IN THAT MOVIE ROOM "UserListMovieRoom":
        #
        #                               WE SEND TO EACH USER IN THE MAIN ROOM "UserListMainRoom"


        user_list = self.serverProxy.getUserList() # list of all users connected to the server

        #update user list in the case of joining the system
        if movie_room == ROOM_IDS.MAIN_ROOM:
            #I look for users in that main room and I send them the appropriate list
            for user in user_list:

                if user.userChatRoom == ROOM_IDS.MAIN_ROOM:
                    self.sendUserListMainRoom(user.userName, user.userAddress)
        #update user list
        else:

            for user in user_list:

                if user.userChatRoom == movie_room:
                    self.sendUserListMovieRoom(user, user.userChatRoom)
                elif user.userChatRoom == ROOM_IDS.MAIN_ROOM:
                    self.sendUserListMainRoom(user.userName, user.userAddress)

    def sendUserListMovieRoom(self,user,movie_room):
        #send the Packet of usersList in a movie room  to the user

        user_chat_room_dict = self.getUserChatRoomDict()
        update_user_list_packet = Packet(18, self.num_seq[user.userName], 0, [])

        update_user_list_packet.data.append(len(user_chat_room_dict[movie_room]))

        update_user_list_packet.packet_format = "!LH"
        update_user_list_packet.packet_length = 2
        for user_chat_room in user_chat_room_dict[movie_room]:
            update_user_list_packet.packet_format += "B" + str(len(user_chat_room)) + "s"
            update_user_list_packet.packet_length += 1 + len(user_chat_room)
            update_user_list_packet.data.append(len(user_chat_room))
            update_user_list_packet.data.append(user_chat_room.encode("utf8"))

        self.sendPacket(update_user_list_packet, user.userAddress)


    def sendUserListMainRoom(self,user_name,host_port):
        user_list_packet = Packet(19, self.num_seq[user_name], 2, [], "!LH")

        user_chat_room_dict={}
        user_chat_room_dict["main_room"]=[]
        for movie in self.serverProxy.getMovieList():
            user_chat_room_dict[movie.movieTitle]=[]
        #user_chat_room_dict={"main_room":[5,alice,3,bob];"batmann":[5,mario]...

        user_list=self.serverProxy.getUserList()
        for user in user_list:
            if user.userChatRoom==ROOM_IDS.MAIN_ROOM:
                user_chat_room_dict["main_room"].append(len(user.userName))
                user_chat_room_dict["main_room"].append(user.userName.encode('utf8'))

            else:
                user_chat_room_dict[user.userChatRoom].append(len(user.userName))
                user_chat_room_dict[user.userChatRoom].append(user.userName.encode('utf8'))

            user_list_packet.packet_length+= 1 + len(user.userName)


        data=[]
        #data= [Nombre de room,NombreUtilisateurMainRoom,5,alice,3,bob]

        user_list_packet.packet_format+="H"
        data.append(len(user_chat_room_dict.keys()))
        data.append(int(len(user_chat_room_dict["main_room"])/2))
        data+=user_chat_room_dict["main_room"]
        user_list_packet.packet_length +=2
        i=0
        while i < len(user_chat_room_dict["main_room"]):

            user_list_packet.packet_format += "B" + str(user_chat_room_dict["main_room"][i]) + "s"

            i += 2
        del user_chat_room_dict["main_room"]



        for movie in sorted(user_chat_room_dict.keys()):

            user_list_packet.packet_length +=2
            user_list_packet.packet_format+="H"

            data.append(int(len(user_chat_room_dict[movie])/2))
            data+=user_chat_room_dict[movie]
            i=0

            while i <len(user_chat_room_dict[movie]):

                user_list_packet.packet_format+="B"+str(user_chat_room_dict[movie][i])+"s"

                i+=2


        user_list_packet.data=data


        self.sendPacket(user_list_packet,host_port)








    def sendPacket(self,packet,host_port,call_count=1):

        if self.serverProxy.getUserByAddress(host_port) is not None:
            user_name = self.serverProxy.getUserByAddress(host_port).userName

        elif host_port in self.num_seq.keys():
            user_name = host_port

        else:
            user_name = None

        if self.sendAndWait==True and call_count==1:


            print('SERVER SEND PACKET',packet)
            self.transport.write(packet.pack(), host_port)


            self.sent_packet_history[user_name][packet.num_seq]=packet



            self.sendAndWait=False

            call_count+=1

            if call_count <=4:
                self.timer[user_name]=reactor.callLater(5, self.sendPacket,packet, host_port, call_count)
        elif call_count>1:

            print('SERVER SEND PACKET', packet)
            self.transport.write(packet.pack(), host_port)

            call_count += 1

            if call_count <= 4:
                self.timer[user_name] = reactor.callLater(5, self.sendPacket, packet, host_port, call_count)



        else:

            self.queuepacket.append((packet,host_port))


    def sendqueuepacket(self):
        print("SEND AND WAIIIIIT")
        for packethost in self.queuepacket:
            self.sendPacket(*packethost)

        self.queuepacket=[]


#                   UTILS

    def lastPacketReceived(self,user_name):

        return self.received_packet_history[user_name][len(self.received_packet_history[user_name].keys())-1]
    def nlastPacketReceived(self,user_name,i):
        return self.received_packet_history[user_name][len(self.received_packet_history[user_name].keys())-i]

    def lastPacketSent(self,user_name):
        print(self.sent_packet_history[user_name].keys(),user_name)
        return self.sent_packet_history[user_name][len(self.sent_packet_history[user_name].keys())-1]

    def nlastPacketSent(self,user_name,i):
        if len(self.sent_packet_history[user_name])>(len(self.sent_packet_history[user_name].keys())-i) and (len(self.sent_packet_history[user_name].keys())-i) >=0:
            return self.sent_packet_history[user_name][len(self.sent_packet_history[user_name].keys())-i]
        else:
            return Packet(None,None,None,None)

    def getUserChatRoomDict(self):
        """
        this method return a dict with dict[movie_room]= [list of user of the movie room]
        :return:
        """

        user_chat_room_dict = {}
        user_chat_room_dict["main_room"] = []
        for movie in self.serverProxy.getMovieList():
            user_chat_room_dict[movie.movieTitle] = []
        user_list = self.serverProxy.getUserList()
        for user in user_list:
            if user.userChatRoom == ROOM_IDS.MAIN_ROOM:

                user_chat_room_dict["main_room"].append(user.userName)

            else:

                user_chat_room_dict[user.userChatRoom].append(user.userName)

        return user_chat_room_dict
