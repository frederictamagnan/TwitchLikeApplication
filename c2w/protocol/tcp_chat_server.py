# -*- coding: utf-8 -*-
from twisted.internet.protocol import Protocol
import logging

logging.basicConfig()
moduleLogger = logging.getLogger('c2w.protocol.tcp_chat_server_protocol')
from c2w.protocol.Packet import Packet
from twisted.internet import reactor
import struct
from c2w.main.constants import ROOM_IDS




class c2wTcpChatServerProtocol(Protocol):

    def __init__(self, serverProxy, clientAddress, clientPort):
        """
        :param serverProxy: The serverProxy, which the protocol must use
            to interact with the user and movie store (i.e., the list of users
            and movies) in the server.
        :param clientAddress: The IP address (or the name) of the c2w server,
            given by the user.
        :param clientPort: The port number used by the c2w server,
            given by the user.

        Class implementing the TCP version of the client protocol.

        .. note::
            You must write the implementation of this class.

        Each instance must have at least the following attribute:

        .. attribute:: serverProxy

            The serverProxy, which the protocol must use
            to interact with the user and movie store in the server.

        .. attribute:: clientAddress

            The IP address of the client corresponding to this
            protocol instance.

        .. attribute:: clientPort

            The port number used by the client corresponding to this
            protocol instance.

        .. note::
            You must add attributes and methods to this class in order
            to have a working and complete implementation of the c2w
            protocol.

        .. note::
            The IP address and port number of the client are provided
            only for the sake of completeness, you do not need to use
            them, as a TCP connection is already associated with only
            one client.
        """
        #: The IP address of the client corresponding to this
        #: protocol instance.
        self.clientAddress = clientAddress

        #: The port number used by the client corresponding to this
        #: protocol instance.
        self.clientPort = clientPort
        #: The serverProxy, which the protocol must use
        #: to interact with the user and movie store in the server.
        self.serverProxy = serverProxy
        self.client_host_port=(self.clientAddress, self.clientPort)
        self.sent_packet_history={}
        self.received_packet_history={}
        self.errorVar=""
        self.user_name=None

        for movie in self.serverProxy.getMovieList():
            self.serverProxy.startStreamingMovie(movie.movieTitle)

        self.buf = b''
        self.packet = Packet(-1, 0, 0, [])
        self.datagram = b''
        self.buf_total=b''
        self.sendAndWait=True
        self.queuePacket=[]
    def dataReceived(self, data):
        """
        :param data: The data received from the client (not necessarily
                     an entire message!)

        Twisted calls this method whenever new data is received on this
        connection.
        """
        # self.buf_total+=data
        self.buf += data
        # print("buf tota",self.buf_total)
        while (True):
            #print("packet length", self.packet.packet_length, "len buf", len(self.buf))

            if self.packet.message_type == -1 and len(self.buf) >= 4:

                self.packet.unpackHeader(self.buf[:4])
                #print("while packet", self.packet.packet_length)
                #print("while self buf", self.buf[:4])
                self.datagram = self.buf[:4]
                self.buf = self.buf[4:]



            elif self.packet.message_type != -1 and self.packet.packet_length <= len(self.buf):

                self.datagram += self.buf[:self.packet.packet_length]
                self.buf = self.buf[self.packet.packet_length:]
                self.datagram_treatment((self.packet, self.datagram))
                self.packet = Packet(-1, 0, 0, [])

            elif self.packet.packet_length >100:
                self.buf=b''
                self.packet = Packet(-1, 0, 0, [])
                self.datagram=b''

            else:
                break

    def datagram_treatment(self,packbuf):
        packet=packbuf[0]
        buf=packbuf[1]

        user_name_print="unknown"
        if self.user_name is not None:
            user_name_print=self.user_name
        print("SERVER RECEIVED PACKET"+user_name_print,packet)

        # if the buf received is not an ack then we send an ack
        if packet.message_type != 80 :
            self.ack(packet)
            print('Ack sent')

        if packet.message_type == 0:

            self.connectionResponse(buf)




        # if it's and ack of connecion done we send user list then movielist

        elif (packet.message_type == 80):
            if packet.num_seq == self.num_seq:

                if self.num_seq==packet.num_seq:
                    self.num_seq = (self.num_seq + 1) % 2047

                    if self.timer is not None:
                        print("TIMER CANCEL")
                        self.timer.cancel()
                        self.timer = None
                    self.sendAndWait = True
                    self.sendQueue()
                if self.lastPacketSent().message_type == 1:
                    self.updateUserList(ROOM_IDS.MAIN_ROOM)


                elif self.nlastPacketSent( 2).message_type == 1:
                    self.sendMovieList()

                elif self.lastPacketSent().message_type == 2:

                    self.error(self.errorVar)
            else:
                return 0  # old ack



        elif packet.num_seq in self.received_packet_history.keys() and  self.received_packet_history[packet.num_seq].isEqual(packet):
            print("paquet ignoré",packet,self.received_packet_history[packet.num_seq])


        elif self.expected_num_seq != packet.num_seq:

            self.wrongExpectedNumSeq()
            error = "error "+str(self.expected_num_seq)+" ! = "+str(packet.num_seq)
            print(error)

        # if it's and ack of connecion done we send movie list then userlist
        # here we are sure that the num sq is verified and that i's not an ack
        elif self.sendAndWait:
            self.received_packet_history[packet.num_seq] = packet
            self.expected_num_seq += 1
            if packet.message_type == 64:
                print("MESSAGE BIEN RECU")
                self.forward(packet, buf)
            elif packet.message_type == 48:

                self.connectionMovieRoom(buf)

            elif packet.message_type == 49:

                print("PAQUET DECONNEXION RECU")
                self.deconnectionMovieRoom()
            elif packet.message_type == 3:
                self.leaveSystem()
            elif packet.message_type == 128:

                self.errorReceived(buf)
        else:
            pass

    def forward(self, packet, buf):

        len_sender = struct.unpack_from('!B', buf, offset=4)[0]

        format = '!LB' + str(len_sender) + 'sB' + str(packet.packet_length - 2 - len_sender) + 's'

        packet.data = [0, 0, 0, 0]
        headerDec, packet.data[0], packet.data[1], packet.data[2], packet.data[3] = struct.unpack(format, buf)

        if self.malformed(packet.data[3].decode('utf8')):

            self.error("malformed message")
        else:
            user_chat_room_dict = self.getUserChatRoomDict()

            if self.movieRoom == ROOM_IDS.MAIN_ROOM:
                sender_chat_room = "main_room"
            else:
                sender_chat_room = self.movieRoom

            i = 0
            while i < len(user_chat_room_dict[sender_chat_room]):
                receiver = user_chat_room_dict[sender_chat_room][i]
                print("FORWARD5")
                messagePacket = Packet(65, -1, packet.packet_length, packet.data, format)
                self.serverProxy.getUserByName(receiver).userChatInstance.sendPacket(messagePacket)
                print("FORWARD6")
                i += 1

    def connectionMovieRoom(self, buf):

        packet = Packet(0, 0, 0, 0)
        packet.unpackHeader(buf)

        format = '!LB' + str(packet.packet_length - 1) + 's'
        packet.data = [0, 0]
        headerDec, packet.data[0], packet.data[1] = struct.unpack(format, buf)
        # the joined room
        if self.existMovie(packet.data[1].decode("utf-8")) == False:
            self.error('Movie Room Does Not Exist')
            print(packet.data[1].decode("utf-8"), 'Movie Room Does Not Exist', self.serverProxy.getMovieList())
        else:
            print('the room does exist ')
            self.movieRoom = (packet.data[1].decode("utf-8"))
            # mettre à jour la liste des utilisateur du movie room dans le serveur
            self.serverProxy.updateUserChatroom(self.user_name, self.movieRoom)
            # self.serverProxy.startStreamingMovie(self.movieRoom)
            self.updateUserList(movie_room=self.movieRoom)

    def existMovie(self, movieRoom):
        Exist = False
        for movie in self.serverProxy.getMovieList():
            if movieRoom == movie.movieTitle:
                Exist = True
        return (Exist)

    def leaveSystem(self):

        old_movie_room = self.movieRoom
        self.serverProxy.removeUser(self.user_name)
        self.updateUserList(movie_room=old_movie_room)

    def deconnectionMovieRoom(self):

        old_movie_room = self.movieRoom
        self.movieRoom = ROOM_IDS.MAIN_ROOM
        self.serverProxy.updateUserChatroom(self.user_name, self.movieRoom)

        self.updateUserList(movie_room=old_movie_room)
        print("DECONNECTION OK")

    def connectionResponse(self, buf):

        packet = Packet(0, 0, 0, 0)
        packet.unpackHeader(buf)

        format = '!LB' + str(packet.packet_length - 1) + 's'
        packet.data = [0, 0]
        headerDec, packet.data[0], packet.data[1] = struct.unpack(format, buf)

        userName = packet.data[1].decode("utf-8")
        self.user_name=userName
        if self.serverProxy.userExists(userName):

            # num seq a traiter #todo


            self.expected_num_seq = 1
            self.num_seq = 0
            self.sent_packet_history = {}
            self.received_packet_history = {}
            self.failed()

            self.errorVar = "userExists"
        elif self.malformed(userName, user_name=True) == True:
            self.expected_num_seq = 1
            self.num_seq = 0
            self.sent_packet_history = {}
            self.received_packet_history = {}
            self.failed()
            self.errorVar = "malformed User Name"




        elif len(self.serverProxy.getUserList()) >= 513:

            self.expected_num_seq = 1
            self.num_seq = 0
            self.sent_packet_history = {}
            self.received_packet_history = {}
            self.failed()
            self.errorVar = "serverSaturated"



        else:
            self.expected_num_seq = 1
            self.num_seq = 0
            self.sent_packet_history = {}
            self.received_packet_history = {}


            self.serverProxy.addUser(userName, ROOM_IDS.MAIN_ROOM, self, self.client_host_port)
            self.movieRoom = ROOM_IDS.MAIN_ROOM
            connectionDone = Packet(1, self.num_seq, 0, '')

            self.sendPacket(connectionDone)

            # ?????
            self.serverProxy.updateUserChatroom(userName, ROOM_IDS.MAIN_ROOM)

    def malformed(self, message, user_name=False):

        if not user_name:
            message=message[:-1]

            return False



        elif len(message)==0 or (len(message)<=255 and message[0].isalpha() and (len(message)==1 or message[1:].isalnum())):
            return False

        return True

    def ack(self, packet):

        ack = Packet(80, packet.num_seq, 0, None)
        self.transport.write(ack.pack())
        user_name='unknown'
        if self.user_name is not None:
            user_name=self.user_name
        print('ACK',packet.num_seq,user_name)

    def error(self, errorType):
        error = Packet(128, self.num_seq, len(errorType) + 1, [len(errorType), errorType])
        self.sendPacket(error)

    def errorReceived(self, buf):

        packet = Packet(0, 0, 0, 0)
        packet.unpackHeader(buf)

        format = '!LB' + str(packet.packet_length - 1) + 's'
        packet.data = [0, 0]
        headerDec, packet.data[0], packet.data[1] = struct.unpack(format, buf)
        print("ERREUR", packet.data[1].decode("utf8"))
        if 'wrongNumSeq:' in packet.data[1].decode('utf8'):
            self.num_seq = int(packet.data[1][12:].decode("utf8"))
            print("new num seq", self.num_seq)
        print("error :", packet.data[1].decode("utf8"))
        return 0

    def wrongExpectedNumSeq(self):
        self.error('wrongNumSeq:' + str(self.expected_num_seq))

    def failed(self):

        failed = Packet(2, self.num_seq, 0, '')
        self.sendPacket(failed)

    def sendMovieList(self):
        # we send list of movie sorted


        movie_list = self.serverProxy.getMovieList()
        movie_list = sorted(movie_list, key=lambda x: x.movieTitle)

        data = []
        length = 2
        format = "!LH"
        data.append(len(movie_list))

        for movie in movie_list:
            format += "B" + str(len(movie.movieTitle)) + "sBBBBH"
            data.append(len(movie.movieTitle))

            data.append(movie.movieTitle.encode("utf-8"))
            print('movie.movieIpAddress', movie.movieIpAddress)
            data = data + list(map(int, movie.movieIpAddress.split(".")))
            data.append(movie.moviePort)
            # 1 byte -> lenghtmovie title, 4 bytes -> length ipv4 , 2 bytes -> port
            length = length + 1 + len(movie.movieTitle) + 4 + 2

        movie_list_packet = Packet(16, self.num_seq, length, data, format)

        self.sendPacket(movie_list_packet)

    def updateUserList(self, movie_room):
        # if user joined a main room: WE SEND TO EACH USER IN MAIN ROOM (EVEN THE USER HIMSELF) "UserListMainRoom"
        # if user joined a movie room: WE SEND TO EACH USER IN THAT MOVIE ROOM "UserListMovieRoom":
        #
        #                               WE SEND TO EACH USER IN THE MAIN ROOM "UserListMainRoom"


        user_list = self.serverProxy.getUserList()  # list of all users connected to the server

        # update user list in the case of joining the system
        if movie_room == ROOM_IDS.MAIN_ROOM:
            # I look for users in that main room and I send them the appropriate list
            for user in user_list:

                if user.userChatRoom == ROOM_IDS.MAIN_ROOM:
                    user.userChatInstance.sendUserListMainRoom()
        # update user list
        else:

            for user in user_list:

                if user.userChatRoom == movie_room:
                    user.userChatInstance.sendUserListMovieRoom( user.userChatRoom)
                elif user.userChatRoom == ROOM_IDS.MAIN_ROOM:
                    user.userChatInstance.sendUserListMainRoom()

    def sendUserListMovieRoom(self, movie_room):
        # send the Packet of usersList in a movie room  to the user

        user_chat_room_dict = self.getUserChatRoomDict()
        update_user_list_packet = Packet(18, -1, 0, [])

        update_user_list_packet.data.append(len(user_chat_room_dict[movie_room]))

        update_user_list_packet.packet_format = "!LH"
        update_user_list_packet.packet_length = 2
        for user_chat_room in user_chat_room_dict[movie_room]:
            update_user_list_packet.packet_format += "B" + str(len(user_chat_room)) + "s"
            update_user_list_packet.packet_length += 1 + len(user_chat_room)
            update_user_list_packet.data.append(len(user_chat_room))
            update_user_list_packet.data.append(user_chat_room.encode("utf8"))

        print("user list movie",update_user_list_packet)
        self.sendPacket(update_user_list_packet)

    def sendUserListMainRoom(self):
        user_list_packet = Packet(19, -1, 2, [], "!LH")

        user_chat_room_dict = {}
        user_chat_room_dict["main_room"] = []
        for movie in self.serverProxy.getMovieList():
            user_chat_room_dict[movie.movieTitle] = []
        # user_chat_room_dict={"main_room":[5,alice,3,bob];"batmann":[5,mario]...

        user_list = self.serverProxy.getUserList()
        for user in user_list:
            if user.userChatRoom == ROOM_IDS.MAIN_ROOM:
                user_chat_room_dict["main_room"].append(len(user.userName))
                user_chat_room_dict["main_room"].append(user.userName.encode('utf8'))

            else:
                user_chat_room_dict[user.userChatRoom].append(len(user.userName))
                user_chat_room_dict[user.userChatRoom].append(user.userName.encode('utf8'))

            user_list_packet.packet_length += 1 + len(user.userName)

        data = []
        # data= [Nombre de room,NombreUtilisateurMainRoom,5,alice,3,bob]

        user_list_packet.packet_format += "H"
        data.append(len(user_chat_room_dict.keys()))
        data.append(int(len(user_chat_room_dict["main_room"]) / 2))
        data += user_chat_room_dict["main_room"]
        user_list_packet.packet_length += 2
        i = 0
        while i < len(user_chat_room_dict["main_room"]):
            user_list_packet.packet_format += "B" + str(user_chat_room_dict["main_room"][i]) + "s"

            i += 2
        del user_chat_room_dict["main_room"]

        for movie in sorted(user_chat_room_dict.keys()):

            user_list_packet.packet_length += 2
            user_list_packet.packet_format += "H"

            data.append(int(len(user_chat_room_dict[movie]) / 2))
            data += user_chat_room_dict[movie]
            i = 0

            while i < len(user_chat_room_dict[movie]):
                user_list_packet.packet_format += "B" + str(user_chat_room_dict[movie][i]) + "s"

                i += 2

        user_list_packet.data = data

        self.sendPacket(user_list_packet)

    def sendPacket(self, packet,  call_count=1):

        if self.sendAndWait and call_count==1:
            if (packet.message_type in [65,18,19]):
                packet.num_seq=self.num_seq

            self.sendAndWait=False
            print('SERVER SEND PACKET TO '+self.user_name, packet)
            self.transport.write(packet.pack())


            self.sent_packet_history[packet.num_seq] = packet
            print("callcount",call_count)
            call_count += 1

            if call_count <= 4:
                self.timer = reactor.callLater(5, self.sendPacket, packet,  call_count)

        elif call_count>1:
            print('SERVER SEND PACKET TO ' + self.user_name, packet)
            self.transport.write(packet.pack())
            call_count += 1

            if call_count <= 4:
                self.timer = reactor.callLater(5, self.sendPacket, packet, call_count)



        else:
            self.queuePacket.append(packet)
            print("packet stocke",packet)



    def sendQueue(self):

        for packet in self.queuePacket:
            self.sendPacket(packet)
        self.queuePacket=[]

            #                   UTILS

    def lastPacketReceived(self):

        return self.received_packet_history[len(self.received_packet_history.keys()) - 1]

    def nlastPacketReceived(self, i):
        return self.received_packet_history[len(self.received_packet_history.keys()) - i]

    def lastPacketSent(self):

        return self.sent_packet_history[len(self.sent_packet_history.keys()) - 1]

    def nlastPacketSent(self ,i):
        if len(self.sent_packet_history) > (len(self.sent_packet_history.keys()) - i) and (
            len(self.sent_packet_history.keys()) - i) >= 0:
            return self.sent_packet_history[len(self.sent_packet_history.keys()) - i]
        else:
            return Packet(None, None, None, None)

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
