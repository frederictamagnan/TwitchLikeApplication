# -*- coding: utf-8 -*-
from twisted.internet.protocol import Protocol
import logging

from c2w.main.constants import ROOM_IDS

from c2w.protocol.Packet import Packet
from twisted.internet import reactor
import struct
logging.basicConfig()
moduleLogger = logging.getLogger('c2w.protocol.tcp_chat_client_protocol')
import time
import string
printable = set(string.printable)


class c2wTcpChatClientProtocol(Protocol):

    def __init__(self, clientProxy, serverAddress, serverPort):
        """
        :param clientProxy: The clientProxy, which the protocol must use
            to interact with the Graphical User Interface.
        :param serverAddress: The IP address (or the name) of the c2w server,
            given by the user.
        :param serverPort: The port number used by the c2w server,
            given by the user.

        Class implementing the UDP version of the client protocol.

        .. note::
            You must write the implementation of this class.

        Each instance must have at least the following attribute:

        .. attribute:: clientProxy

            The clientProxy, which the protocol must use
            to interact with the Graphical User Interface.

        .. attribute:: serverAddress

            The IP address of the c2w server.

        .. attribute:: serverPort

            The port number used by the c2w server.

        .. note::
            You must add attributes and methods to this class in order
            to have a working and complete implementation of the c2w
            protocol.
        """

        #: The IP address of the c2w server.
        self.serverAddress = serverAddress
        #: The port number used by the c2w server.
        self.serverPort = serverPort
        #: The clientProxy, which the protocol must use
        #: to interact with the Graphical User Interface.
        self.clientProxy = clientProxy


        self.movie_list=[]
        self.user_list = []
        self.num_seq=0
        self.expected_num_seq=0
        self.user_name=""
        self.timer=None
        self.room=''
        self.booleanDict={} #dictionnaire de boolean

        self.received_packet_history={}
        self.sent_packet_history={}


        self.buf = b''
        self.packet = Packet(-1, 0, 0, [])
        self.datagram = b''
        self.buf_total=b''

        self.sendAndWait = True
        self.queuePacket=[]


    def sendLoginRequestOIE(self, userName):
        """
        :param string userName: The user name that the user has typed.

        The client proxy calls this function when the user clicks on
        the login button.
        """
        moduleLogger.debug('loginRequest called with username=%s', userName)

        packet = Packet(0, 0, len(userName) + 1, [len(userName), userName])

        self.sendPacket(packet)
        # dés que j'envoie un data j'incremente mon num seq

        self.user_name = userName

    def sendChatMessageOIE(self, message):
        """
        :param message: The text of the chat message.
        :type message: string

        Called by the client proxy  when the user has decided to send
        a chat message

        .. note::
           This is the only function handling chat messages, irrespective
           of the room where the user is.  Therefore it is up to the
           c2wChatClientProctocol or to the server to make sure that this
           message is handled properly, i.e., it is shown only by the
           client(s) who are in the same room.
        """

        message=''.join(filter(lambda x: x in printable, message))
        seqNumber = self.num_seq
        message_packet = Packet(64, seqNumber, len(self.user_name) + len(message) + 2,
                                [len(self.user_name), self.user_name.encode('utf-8'), len(message),
                                 message.encode('utf8')])
        message_packet.packet_format = '!LB' + str(message_packet.data[0]) + 's' + 'B' + str(
            message_packet.data[2]) + 's'

        self.sendPacket(message_packet)

    def ack(self, packet, host_port):

        ack = Packet(80, packet.numSeq, 0, None)
        self.transport.write(ack.pack(), host_port)

    def sendJoinRoomRequestOIE(self, roomName):
        """
        :param roomName: The room name (or movie title.)

        Called by the client proxy  when the user
        has clicked on the watch button or the leave button,
        indicating that she/he wants to change room.

        .. warning:
            The controller sets roomName to
            c2w.main.constants.ROOM_IDS.MAIN_ROOM when the user
            wants to go back to the main room.
        """

        self.asked_room = roomName
        # disconnection from a movie room to the main room
        if roomName == ROOM_IDS.MAIN_ROOM:
            main_packet = Packet(49, self.num_seq, 0, None)
            self.sendPacket(main_packet)


        # connection to a movie room:
        else:

            movie_packet = Packet(48, self.num_seq, len(roomName) + 1, [len(roomName), roomName])
            self.sendPacket(movie_packet)



    def sendLeaveSystemRequestOIE(self):
        """
        Called by the client proxy  when the user
        has clicked on the leave button in the main room.
        """
        leave_paquet = Packet(3, self.num_seq, 0, "")
        self.sendPacket(leave_paquet)

    def dataReceived(self, data):
        """
        :param string buf: the payload of the UDP packet.
        :param host_port: a touple containing the source IP address and port.

        Called **by Twisted** when the client has received a UDP
        packet.
        """

        time1=time.time()

        self.buf_total+=data
        self.buf += data
        # print("buf tota",self.buf_total)

        while (True):
            #print("packet length", self.packet.packet_length, "len buf", len(self.buf))

            if self.packet.message_type == -1 and len(self.buf) >= 4:

                self.packet.unpackHeader(self.buf[:4])
                print("while packet", self.packet.packet_length)
                print("while self buf", self.buf[:4])
                self.datagram = self.buf[:4]
                self.buf = self.buf[4:]



            elif self.packet.message_type != -1 and self.packet.packet_length <= len(self.buf):

                self.datagram += self.buf[:self.packet.packet_length]
                self.buf = self.buf[self.packet.packet_length:]
                self.datagram_treatment((self.packet, self.datagram))
                self.packet = Packet(-1, 0, 0, [])

            else:
                break
        print(time.time()-time1,"sec")

    def datagram_treatment(self,packbuf):

        print("CLIENT RECEIVED PACKET",packbuf[0])

        packet = packbuf[0]
        buf = packbuf[1]


        # if we receive a message we ack it
        if packet.message_type != 80:
            self.ack(packet)



        # here we have a verified num_seq and and ack message we should cancel our callater
        if (packet.message_type == 80):
            print('Ack received')
            if self.num_seq == packet.num_seq:

                self.num_seq = (self.num_seq + 1) % 2047
                if self.timer is not None:

                    self.timer.cancel()
                    self.timer = None
                self.sendAndWait = True
                self.sendQueue()

                if self.lastPacketSent().message_type in [48,49]:
                    # if we receive the ack of join room or leave room
                    self.room=self.asked_room
                    self.clientProxy.joinRoomOKONE()
                    pass
                elif self.lastPacketSent().message_type == 3:
                    # if we receive the ack of leave main room
                    self.clientProxy.leaveSystemOKONE()
                else:
                    print("acquittement non pris en comtpe",packet)



        elif packet.num_seq in self.received_packet_history.keys() and  self.received_packet_history[packet.num_seq].isEqual(packet):

            print("paquet ignoré",packet,self.received_packet_history[packet.num_seq])


        elif self.expected_num_seq != packet.num_seq and packet.num_seq in self.received_packet_history.keys() and not self.received_packet_history[packet.num_seq].isEqual(packet):
            # todo
            self.wrongExpectedNumSeq()

            error = "error " + str(self.expected_num_seq) + " ! = " + str(packet.num_seq)
            print(error)

            # dans ce stade on est sur que le num seq est verifié et quil sagit pas dun message d'ack
        elif self.sendAndWait:


            print('')
            self.received_packet_history[packet.num_seq] = packet
            self.expected_num_seq += 1

            if packet.message_type == 1:
                print('connexion etablie')
            elif packet.message_type == 2:
                print('connexion echouée')

            elif packet.message_type == 128:

                self.errorReceived(buf)


            elif packet.message_type == 16:
                self.movieListReceived(packet, buf)




            elif packet.message_type == 19:
                self.updateUserListMainRoom(packet, buf)


            elif packet.message_type == 65:
                self.chatReceived(packet, buf)

            elif packet.message_type == 18:
                self.updateUserListMovieRoom(packet, buf)
        else:
            pass

    def chatReceived(self, packet, buf):

        packet.data = [0, 0, 0, 0]
        # offset=4
        # lenSender=struct.unpack_from('!B',buf,offset)[0]
        # offset+=1
        # sender=struct.unpack_from('!'+str(lenSender)+'s',offset)[0]
        # offset+=lenSender
        # lenMessage=struct.unpack_from('!B',buf,offset)[0]
        # message=struct.unpack_from('!'+str(lenMessage)+'s')



        len_sender = struct.unpack_from('!B', buf, offset=4)[0]

        format = '!LB' + str(len_sender) + 'sB' + str(packet.packet_length - 2 - len_sender) + 's'

        headerDec, packet.data[0], packet.data[1], packet.data[2], packet.data[3] = struct.unpack(format, buf)

        if packet.data[1].decode('utf-8') != self.user_name:
            self.clientProxy.chatMessageReceivedONE(packet.data[1].decode('utf8'), packet.data[3].decode('utf8'))

    def wrongExpectedNumSeq(self):
        self.error('wrongNumSeq:' + str(self.expected_num_seq))

    def error(self, errorType):
        error = Packet(128, self.num_seq, len(errorType) + 1, [len(errorType), errorType])
        self.sendPacket(error)

    def errorReceived(self, buf):


        packet = Packet(0, 0, 0, 0)
        packet.unpackHeader(buf)

        format = '!LB' + str(packet.packet_length - 1) + 's'
        packet.data = [0, 0]
        headerDec, packet.data[0], packet.data[1] = struct.unpack(format, buf)
        print("ERREUR",packet.data[1].decode("utf8"))
        if packet.data[1].decode('utf8') in ["wrongUserName", "serverSaturated", "userExists"]:
            self.clientProxy.connectionRejectedONE(packet.data[1].decode("utf8"))
        elif 'wrongNumSeq:' in packet.data[1].decode("utf8"):
            self.num_seq = int(packet.data[1][12:].decode("utf8"))
            print("new num seq",self.num_seq)
            pass
        print("error :", packet.data[1].decode("utf8"))
        return 0

    def updateUserListMainRoom(self, packet, buf):
        # here we receive the new list of user in main room

        self.user_list = []

        packet.data = []

        offset = 4
        len_Rooms = struct.unpack_from("!H", buf, offset)[0]  # number of movie room
        i = 0

        offset += 2
        packet.data.append(len_Rooms)
        for i in range(len_Rooms):

            len_UserList = struct.unpack_from('!H', buf, offset=offset)[0]

            packet.data.append(len_UserList)

            offset += 2

            if len_UserList != 0:
                # if room is not empty
                for j in range(0, len_UserList):

                    len_UserName = struct.unpack_from('!B', buf, offset=offset)[0]

                    packet.data.append(len_UserName)

                    offset += 1

                    user = struct.unpack_from("!" + str(len_UserName) + "s", buf, offset=offset)[0]

                    packet.data.append(user.decode('utf8'))

                    offset += len_UserName

                    if i == 0:
                        movie_title = ROOM_IDS.MAIN_ROOM
                    elif self.movie_list == []:
                        movie_title = i
                    else:
                        movie_title = self.movie_list[i - 1]

                    user_tuple = (user.decode('utf8'), movie_title)  # ("alice","batman")

                    self.user_list.append(user_tuple)

        if "initok" in self.booleanDict and self.booleanDict["initok"] == True:
            print("set user ok")
            self.clientProxy.setUserListONE(self.user_list)
        else:
           pass

    def updateUserListMovieRoom(self, packet, buf):

        self.user_list = []
        packet.data = []

        offset = 4
        len_users = struct.unpack_from("!H", buf, offset)[0]  # nombre de users

        offset += 2
        packet.data.append(len_users)

        for j in range(0, len_users):
            len_UserName = struct.unpack_from('!B', buf, offset=offset)[0]

            packet.data.append(len_UserName)

            offset += 1

            user = struct.unpack_from("!" + str(len_UserName) + "s", buf, offset=offset)[0]

            packet.data.append(user.decode('utf8'))

            offset += len_UserName

            user_tuple = (user.decode('utf8'), self.room)

            self.user_list.append(user_tuple)

        self.clientProxy.setUserListONE(self.user_list)


    def movieListReceived(self, packet, buf):

        self.movie_list = []
        packet.data = []
        len_movie_list = struct.unpack_from("!H", buf, offset=4)[0]  # nombre de salon

        packet.data.append(len_movie_list)
        offset = 6
        i = 0
        while i < len_movie_list:

            format = "!B"
            len_movie_title = struct.unpack_from(format, buf, offset=offset)[0]
            packet.data.append(len_movie_title)

            format = "!" + str(len_movie_title) + "s"
            offset += 1
            movie_title = struct.unpack_from(format, buf, offset=offset)[0]
            packet.data.append(movie_title.decode("utf8"))

            ip_movie = []
            format = "!B"

            offset += len_movie_title
            # unpacker l'adresse ip
            for j in range(0, 4):
                ip_movie.append(struct.unpack_from(format, buf, offset=offset)[0])
                offset += 1

            ip_movie = list(map(str, ip_movie))  # ecrire dans une liste les 4 octet de l'adresse ip

            packet.data.append('.'.join(list(map(str, ip_movie))))

            format = '!H'

            port_movie = struct.unpack_from(format, buf, offset)[0]
            packet.data.append(port_movie)
            offset += 2
            i = i + 1

            movie_tuple = (movie_title.decode("utf8"), ip_movie, port_movie)
            self.movie_list.append(movie_tuple)

        user_list_update = []
        for user in self.user_list:

            if user[1] != ROOM_IDS.MAIN_ROOM:
                movie_title = self.movie_list[user[1] - 1]
            else:
                movie_title = ROOM_IDS.MAIN_ROOM
            user_list_update.append((user[0], movie_title))
        self.user_list = user_list_update

        self.clientProxy.initCompleteONE(self.user_list, self.movie_list)
        self.booleanDict['initok'] = True

    def sendPacket(self, packet, call_count=1):


        if self.sendAndWait and call_count==1:
            print('CLIENT '+self.user_name+' SEND PACKET', packet)
            self.transport.write(packet.pack())

            self.sendAndWait=False
            self.sent_packet_history[packet.num_seq] = packet

            call_count += 1

            if call_count <= 4:
                self.timer = reactor.callLater(5, self.sendPacket, packet, call_count)

        elif call_count>1:

            print('CLIENT ' + self.user_name + ' SEND PACKET', packet)
            self.transport.write(packet.pack())


            call_count += 1

            if call_count <= 4:
                self.timer = reactor.callLater(5, self.sendPacket, packet, call_count)

        else:

            self.queuePacket.append(packet)
            print("packet ajoute a la queupacket",packet)
    def sendQueue(self):

        for packet in self.queuePacket:
            self.sendPacket(packet)
        self.queuePacket = []

    def ack(self, packet):

        ack = Packet(80, packet.num_seq, 0, None)
        self.transport.write(ack.pack())
        print("ack de",packet)

    def lastPacketReceived(self):

        return self.received_packet_history[len(self.received_packet_history.keys()) - 1]

    def nlastPacketReceived(self, i):
        return self.received_packet_history[len(self.received_packet_history.keys()) - i]

    def lastPacketSent(self):
        return self.sent_packet_history[len(self.sent_packet_history.keys()) - 1]

    def nlastPacketSent(self, i):
        return self.sent_packet_history[len(self.sent_packet_history.keys()) - i]
