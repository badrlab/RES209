# -*- coding: utf-8 -*-
from twisted.internet.protocol import DatagramProtocol
from c2w.main.lossy_transport import LossyTransport
from c2w.main.constants import ROOM_IDS
import logging
import struct
from twisted.internet import reactor

logging.basicConfig()
moduleLogger = logging.getLogger('c2w.protocol.udp_chat_client_protocol')

class c2wUdpChatClientProtocol(DatagramProtocol):
    
    seq = 1
    lastMessage = ''
    attenteServer = 0 #Initié à 0 pour le premier envoie de login 
    ACKServer = 0
    waitForACK = ''
    
    def __init__(self, serverAddress, serverPort, clientProxy, lossPr):
        """
        :param serverAddress: The IP address (or the name) of the c2w server,
            given by the user.
        :param serverPort: The port number used by the c2w server,
            given by the user.
        :param clientProxy: The clientProxy, which the protocol must use
            to interact with the Graphical User Interface.

        Class implementing the UDP version of the client protocol.

        .. note::
            You must write the implementation of this class.

        Each instance must have at least the following attributes:

        .. attribute:: serverAddress

            The IP address of the c2w server.

        .. attribute:: serverPort

            The port number of the c2w server.

        .. attribute:: clientProxy

            The clientProxy, which the protocol must use
            to interact with the Graphical User Interface.

        .. attribute:: lossPr

            The packet loss probability for outgoing packets.  Do
            not modify this value!  (It is used by startProtocol.)

        .. note::
            You must add attributes and methods to this class in order
            to have a working and complete implementation of the c2w
            protocol.
        """

        #: The IP address of the c2w server.
        self.serverAddress = serverAddress
        #: The port number of the c2w server.
        self.serverPort = serverPort
        
        self.serverHost = serverAddress, serverPort
        #: The clientProxy, which the protocol must use
        #: to interact with the Graphical User Interface.
        self.clientProxy = clientProxy
        self.lossPr = lossPr
    
    
    def startProtocol(self):
        """
        DO NOT MODIFY THE FIRST TWO LINES OF THIS METHOD!!

        If in doubt, do not add anything to this method.  Just ignore it.
        It is used to randomly drop outgoing packets if the -l
        command line option is used.
        """
        self.transport = LossyTransport(self.transport, self.lossPr)
        DatagramProtocol.transport = self.transport


    def sendLoginRequestOIE(self, userName):
        """
        :param string userName: The user name that the user has typed.

        The client proxy calls this function when the user clicks on
        the login button.
        """
        
        moduleLogger.debug('loginRequest called with username=%s', userName)
        userName = userName.encode('utf8')
        self.attenteServer = 0
        self.ACKServer=0
        self.sendLogin(userName)
            
    def sendLogin(self, userName):
        if ((self.attenteServer < 10) and (self.ACKServer==0)):
            if self.attenteServer!=0: self.seq=1
            self.sender(len(userName), 1, userName, self.serverHost)
            self.waitForACK = reactor.callLater(1, self.sendLogin, userName)
            
            self.attenteServer+=1
        elif self.attenteServer == 10:
            print("The server do not answer")
            
            
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
        
        taille=len(message)
        if taille*2<65000:
            message=message.encode('utf-8')
            self.attenteServer = 0
            self.ACKServer=0
            self.sendChatMessage(message)
        
        
    def sendChatMessage(self, message):
        if ((self.attenteServer < 10) and (self.ACKServer==0)):
            self.sender(len(message), 5, message, self.serverHost)
            self.waitForACK = reactor.callLater(1, self.sendChatMessage, message)
            self.attenteServer+=1
            
        elif self.attenteServer == 10:
            print("The server do not answer")
            
            
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
        
        if not isinstance(roomName,str) : idm=0
        else: idm=movieIds[roomName]
        msg=bytearray(1)
        struct.pack_into('!b',msg,0,idm)
        self.attenteServer = 0
        self.ACKServer = 0
        self.sendJoinRoom(msg)     
        
    
    def sendJoinRoom(self, msg):
        if ((self.attenteServer < 10) and (self.ACKServer==0)):
            self.sender(1,6,msg,self.serverHost)
            self.waitForACK = reactor.callLater(1, self.sendJoinRoom, msg)
            self.attenteServer+=1
        elif self.attenteServer == 10:
            print("The server does not answer")
            
            
    def sendLeaveSystemRequestOIE(self):
        """
        Called by the client proxy  when the user
        has clicked on the leave button in the main room.
        """
        self.attenteServer = 0
        self.ACKServer = 0
        self.sendLeaveSystem()

    def sendLeaveSystem(self):
        if ((self.attenteServer < 10) and (self.ACKServer==0)):
            self.lastMessage = 'quit'
            self.sender(0,9,None,self.serverHost)
            self.waitForACK = reactor.callLater(1, self.sendLeaveSystem)
            self.attenteServer+=1
        elif self.attenteServer == 10:
            print("The server does not answer")
            
    def datagramReceived(self, datagram, host_port):
        """
        :param string datagram: the payload of the UDP packet.
        :param host_port: a touple containing the source IP address and port.

        Called **by Twisted** when the client has received a UDP
        packet.
        """
        global movieList
        global userList
        global movieIds
        
        msg = struct.unpack_from('!hh'+str(len(datagram)-4)+'s', datagram)
        taille = msg[0]
        st = msg[1] #Seq + Type
        if taille == len(datagram):
            seqType = self.getSeqType(st) #Tupple contenant la Sequence et le Type
            (nseq,tTrame)=seqType
            
            if seqType[1] != 63 : #Si le message reçu n'est pas un ACK, on envoie un ACK
                print('msg received -- ack sent response to ' + str(seqType[1]))                
                self.sendAck(seqType[0], host_port)
                
            if seqType[1]==8:#REFUSEE
                print('inscription refused')
                datagram=datagram[4:]
                check=struct.unpack_from('b',datagram)
                self.clientProxy.connectionRejectedONE(str(check[0]))
            
            if seqType[1]==11:self.clientProxy.joinRoomOKONE()
                            
            if seqType[1] == 2:#MOVIES
                print('movie list received')
                movieList=[]
                movieIds={}
                datagram=datagram[4:]
                while len(datagram)!=0:
                    tp=struct.unpack_from('b',datagram)#on recup la taille
                    form='bbbbb'
                    t=struct.unpack_from(form,datagram)
                    ipl=t[1:5]#recuperation de l ip 
                    ip=''
                    for i in range(4):#boucle de reconcatenation de l ip
                        ip+=str(ipl[i])+'.'
                    ip=ip[:-1]# enlever le dernier point
                    datagram=datagram[5:]
                    te=struct.unpack_from('!hb'+str(tp[0]-8)+'s',datagram)
                    movieList+=[(te[2].decode('utf-8'),ip,te[0])]
                    movieIds[te[2].decode('utf-8')]=te[1]
                    datagram=datagram[tp[0]-5:]
                    
            if seqType[1] == 3:#USERS
                print('user list received')
                userList=[]
                datagram=datagram[4:]
                while len(datagram)!=0:
                    tp=struct.unpack_from('b',datagram)#on recup la taille
                    form='bb'+str(tp[0]-2)+'s'
                    t=struct.unpack_from(form,datagram)
                    user=t[2].decode('utf-8')
                    #user=user[4:]
                    if t[1]==0:userList+=[(user,ROOM_IDS.MAIN_ROOM)]
                    else:userList+=[(user,t[1])]
                    datagram=datagram[tp[0]:]
                self.clientProxy.initCompleteONE(userList,movieList)
                
            if seqType[1]==10:#Message reçu
                print('message received')
                tailleUser=struct.unpack_from('!b',msg[2])
                form='!b'+str(tailleUser[0])+'s'+str(len(msg[2])-1-tailleUser[0])+'s'
                umsg=struct.unpack_from(form,msg[2])
                usr=umsg[1].decode('utf-8')
                msg=umsg[2].decode('utf-8')
                self.clientProxy.chatMessageReceivedONE(usr,msg)
                
            if seqType[1]==63:#ACK
                print('ack received')
                print(nseq,self.seq)
                if (nseq+1 == self.seq):
                    if (self.ACKServer==0):                                                                   #Si on attendait un ACK de l'utilisateur, on cancel le bouclage du racteur        
                        self.waitForACK.cancel()                                                             #On cancel le bouclage du Send&Wait
                        self.ACKServer=1
                    if self.lastMessage=='quit':
                        print('user left')
                        self.clientProxy.leaveSystemOKONE()
                #else:
                    
                
            if seqType[1]==8:#REFUS INSCRIPTION
                print('Inscription refused')
                print(datagram)
                    
            if seqType[1]==4:#MISE A JOUR UTILISATEUR
                datagram=datagram[4:]
                [idSalon,userName]=struct.unpack_from('b'+str(len(datagram)-1)+'s',datagram)
                userName=userName.decode('utf8')
                print('user updated')
                if idSalon==127:
                    self.clientProxy.userUpdateReceivedONE(userName,ROOM_IDS.OUT_OF_THE_SYSTEM_ROOM)
                elif idSalon==0:
                    self.clientProxy.userUpdateReceivedONE(userName,ROOM_IDS.MAIN_ROOM)
                else:
                    roomName=list(movieIds.keys())[list(movieIds.values()).index(idSalon)]
                    print(roomName)
                    self.clientProxy.userUpdateReceivedONE(userName,roomName)
            

    def sendAck(self, seq, host_port):
        typeM = self.dec2bin(63, 6)
        seqM= self.dec2bin(seq, 10)
        st=seqM+typeM
        msg=bytearray(4)
        struct.pack_into('!hh',msg,0, 4,int(st,2))
        self.transport.write(msg, host_port)
        
        
    def dec2bin(self, decimal, nbbits):
        if decimal == 0:
            return "0".zfill(nbbits)
        result=""
        while decimal != 0:
            decimal, rest = divmod(decimal, 2)
            result = "01"[rest] + result
        return result.zfill(nbbits)
        
        
    #RETOURNE lE NUM DE SEQ ET LE TYPE DE TRAME
    def getSeqType(self, st):
        st = self.dec2bin(st , 16)
        seq = st[:10]
        types = st[10:16]
        return int(seq,2), int(types,2) #tupple[0] = sequence, tupple[1] = type
      
      
    def sender(self, taille, typeM, data, host_port):
        
        typeM = self.dec2bin(typeM, 6) #conversion du type sur 6 bit
        seqM= self.dec2bin(self.seq, 10)#conversion seq sur 6 bit
        self.seq+=1
        
        st=seqM+typeM #on concatene sequence et type
        
        buf=bytearray(4)
        struct.pack_into('!hh',buf,0, taille+4, int(st,2))
        
        if data != None:
            buf=buf+data
            
        self.transport.write(buf, host_port)