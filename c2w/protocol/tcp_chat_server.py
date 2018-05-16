# -*- coding: utf-8 -*-
from twisted.internet.protocol import Protocol
from c2w.main.constants import ROOM_IDS
import logging
import struct
from twisted.internet import reactor

logging.basicConfig()
moduleLogger = logging.getLogger('c2w.protocol.tcp_chat_server_protocol')


class c2wTcpChatServerProtocol(Protocol):
    lastMessage = {} #Id du dernier message envoyé à un Host Port
    tempUsernames = {}
    seqUsers = {} #list des seq de chaque utilsateur
    attenteUsers = {} #dico permettant de stocker une variable indiquant le nombre de fois que l'on a envoyé un message sans réponse
    ACKUsers = {} #Chaque valeur vaut 1 ou 0 pour un host_port donné. Si 1 : on vient de recevoir un ACK (on arrete le reacteur de l'utilisateur), tant valeur = 0 on continue le bouclage 
    waitForACK = {} #Dico stockant les reacteurs
    seq = 1 #Seq du serveur


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
 
        self.messagebuf = bytearray()
        
        self.messageLength = 0
        
        self.lengthRecieved = False
        
    
    
    def reinititiation(self):
        self.messagebuf = self.messagebuf[self.messageLength:]
        self.messageLength = 0
        self.lengthRecieved = False

    def dataReceived(self, data):
        """
        :param data: The data received from the client (not necessarily
                     an entire message!)

        Twisted calls this method whenever new data is received on this
        connection.
        """
        #IDGAF
        global user
        global host_port 
        self.messagebuf+=data
        if len(self.messagebuf)>=4: #entete complete
            msg = struct.unpack_from('!hh'+str(len(self.messagebuf)-4)+'s', self.messagebuf)
            self.messageLength = msg[0]
            st = msg[1] #Seq + Type
            seqType = self.getSeqType(st) #Tupple contenant la Sequence et le Type
            (nseq,tTrame)=seqType
            self.lengthRecieved = True
            
        if (self.messageLength<=len(self.messagebuf) and self.lengthRecieved): #verify if we recieved the whole message
            message=self.messagebuf[4:self.messageLength]
            #host_port=(self.clientAddress,self.clientPort)
                
            if tTrame!=63:
                print('ack sent in response to '+ str(tTrame))
                self.sendAck(seqType[0])
                
            if tTrame==1: #Le message reçu est une inscription
                user = message.decode('utf-8')
                host_port=user
                print("inscription received from " + user)                
                check = self.checkInscription(user)
                if check != 0:
                    print("inscription refused for " + user)
                    msg=bytearray(1)
                    struct.pack_into('b',msg ,0 ,check)
                    self.sender(1, 8, msg) #Envoie de l'erreur d'inscription avec le code d'erreur associé (check = 1, 2 ou 3)
                else:
                    print("inscription accepted for " + user)
                    self.lastMessage[host_port]=7 #On initie le dernier message de l'utilisateur à 7 (Inscription OK)
                    self.seqUsers[host_port]=1 #On initie la sequence de l'utilisateur à 1
                    self.serverProxy.addUser(user, 0, None)#Ajout de l'utilisateur
                    self.ACKUsers[host_port]=0                    
                    self.attenteUsers[host_port] = 0                     
                    self.inscriptionAccepted()#Envoie du msg 7 : inscription acceptée. Doit se faire APRES l'ajout de l'user
                    #self.userUpdate(user, 0)#envoie la mise a jour
                        
            if tTrame == 63 :#ACK RECU                    
                print('ack received')
                if self.lastMessage[host_port] == 7:
                    
                    if (nseq+1 == self.seq):
                        if (self.ACKUsers[host_port]==0):                                                                   #Si on attendait un ACK de l'utilisateur, on cancel le bouclage du racteur        
                            #self.waitForACK[host_port].cancel()                                                             #On cancel le bouclage du Send&Wait
                            self.ACKUsers[host_port]=1
                            
                        self.seqUsers[host_port]=2 #On initie la sequence de l'utilisateur à 1
                        #self.serverProxy.addUser(user, 0, None)                         #Ajout de l'utilisateur dans la base de donnée
                        #self.userUpdate(user, 0)              #Envoie la mise a jour aux autres utilisateurs
                        self.lastMessage[host_port]=2                                                                       #On indique que le dernier message envoyé est la liste des firlm
                        print('sending list of films to ' + user)
                        self.ACKUsers[host_port]=0                                                                          #Comme on envoie un message, on initie la valeur de l'ACK de l'utilisateur à 0 (on n'a pas reçu d'acquittements)                       
                        self.attenteUsers[host_port] = 0                                                                    #Pareil que l'ACK mais pour le nombre de tentative. 
                        self.sendListFilm()                                                                        #On envoie les films.
                    
                elif self.lastMessage[host_port] != 8:
                    if (nseq+1 == self.seqUsers[host_port]):
                        if (self.ACKUsers[host_port]==0):                                                                   #Si on attendait un ACK de l'utilisateur, on cancel le bouclage du racteur        
                            #self.waitForACK[host_port].cancel()
                            self.ACKUsers[host_port]=1
                            
                        if self.lastMessage[host_port] == 2:                                                                #Si le dernier message est l'envoie de film
                            self.lastMessage[host_port]=3                                                                   #On envoie la liste des utilisateurs
                            print('sending list of users to ' + user)
                            
                            self.ACKUsers[host_port]=0                        
                            self.attenteUsers[host_port] = 0
                            self.sendListUsers() 
                            
            if tTrame==5:#MESSAGE RECU
                print('msg received from '+user+' and relayed')
                self.lastMessage[host_port]=5
                self.redirchat(msg[2])
                
            if tTrame==6:#JOINDRE UN SALON
                print('user ' + user + ' trying to join room')
                self.lastMessage[host_port]=6
                self.join_room_response(message)
                
            if tTrame==9:#LEAVING
                print('user ' + user + ' leaving')
                self.lastMessage[host_port]=5
                #self.userUpdate(user, 127)
                self.serverProxy.removeUser(user)
                print(self.serverProxy.getUserList())
            
            self.reinititiation()
            


    #CONVERTISSEUR BINAIRE    
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
        
        st = str(self.dec2bin(st,16))
        seq = st[:-6]
        types = st[-6:]
        return int(seq, 2), int(types, 2) #tupple[0] = sequence, tupple[1] = type
        
        
        
        #METHODE ASSEMBLANT LE MESSAGE ET L'ENTETE  
    def sender(self, taille, typeM, data):
        
        if ((typeM != 8) and (typeM != 7)): #7 ou 8 = Inscription acceptée/Refusée ===> User n'est pas encore dans la base de donnée du serveur
            seqM = self.dec2bin(self.seqUsers[host_port],10)
            self.seqUsers[host_port]+=1
        else : 
            seqM= self.dec2bin(self.seq, 10) #Si l'utilisateur n'existe pas, on envoie avec la séquence du serveur
            self.seq+=1
        typeM = self.dec2bin(typeM, 6) #conversion du type sur 6 bit
            
        st=seqM+typeM #on concatene sequence et type
        buf=bytearray(4)
        struct.pack_into('!hh',buf,0, taille+4, int(st,2))
        
        if data != None:
            buf=buf+data
        self.transport.write(buf)



    def inscriptionAccepted(self):
        if ((self.attenteUsers[host_port] < 10) and (self.ACKUsers[host_port]==0)):
            self.sender(0, 7, None) #Envoie du message Inscription OK
            self.waitForACK = reactor.callLater(1, self.inscriptionAccepted)
            self.attenteUsers[host_port]+=1
        elif self.attenteUsers[host_port] == 10:
            print('user ' + user + ' has been removed from database')
            self.serverProxy.removeUser(user)



    #VERIFICATION DE L'INSCRIPTION
    def checkInscription(self, data):
        
        check = 0
        if(data.find(" ")!=-1):
            check = 3 
        if len(data)>127: #Username > 254 caractere = 254 octets
            check = 2
        if self.serverProxy.userExists(data) : check = 1
        return check        
        
        
        
    #ENVOIE LA LISTE DE FILM
    def sendListFilm(self):
        if ((self.attenteUsers[host_port] < 10) and (self.ACKUsers[host_port]==0)):
            taille = 0
            LF = self.serverProxy.getMovieList()
            for i in LF:
                taille+=len(i.movieTitle)+8
            buffer=bytearray(taille)
            n=0
            for i in LF:
                title, port, ip, ide = i.movieTitle, i.moviePort, i.movieIpAddress, i.movieId
                title=title.encode('utf-8')
                struct.pack_into('!b',buffer,n,len(title)+8)#taille dans le buffer 8 = taille,ip ,port,id
                ipe=ip.split('.')
                for i in range(4):
                    struct.pack_into('b',buffer,n+1+i,int(ipe[i]))
                form='!hb'+str(len(title))+'s'
                struct.pack_into(form,buffer,n+5,port,ide,title)
                n+=8+len(title)
            self.sender(taille,2,buffer)
            self.waitForACK = reactor.callLater(1, self.sendListFilm)
            self.attenteUsers[host_port]+=1   

        elif self.attenteUsers[host_port] == 10:
            print('user ' + user + ' has been removed from database')
            self.serverProxy.removeUser(user)            
            
     #ENVOIE LA LISTE DES USERS
    def sendListUsers(self):
        if ((self.attenteUsers[host_port] < 10) and (self.ACKUsers[host_port]==0)):
            taille = 0
            for i in self.serverProxy.getUserList():
                taille+=len(i.userName)+2
            buffer=bytearray(taille)
            n=0
            for i in self.serverProxy.getUserList():
                user, idroom = i.userName, i.userChatRoom
                if idroom!=0:
                    idroom=self.serverProxy.getMovieById(i.userChatRoom).movieId
                user=user.encode('utf-8')
                form='!bb'+str(len(user))+'s'
                struct.pack_into(form,buffer,n,len(user)+1+1,idroom,user) #taille données=longueur titre + 1 octet de taille + 2 + 4 + 1) suivie par ip, port etc..
                n+=len(user)+2
            print(buffer)
            self.sender(taille,3,buffer)
            self.waitForACK = reactor.callLater(1, self.sendListUsers)
            self.attenteUsers[host_port]+=1
        elif self.attenteUsers[host_port] == 10:
            print('user ' + user + ' has been removed from database')
            self.serverProxy.removeUser(user)            


    #METTRE A JOUR UN USER
    def userUpdate(self, userName, idSalon):
        userName=userName.encode('utf-8')
        buffer=bytearray(len(userName)+1)
        struct.pack_into('b'+str(len(userName))+'s',buffer,0,idSalon,userName)
        for i in self.serverProxy.getUserList():
            hp=i.userAddress
            if host_port!=hp:
                print('sending update')
                self.ACKUsers[hp]=0                        
                self.attenteUsers[hp] = 0 
                self.sendUserUpdate((len(userName)+1,buffer))


    #get seq of other users and send msg to them
    def sendUserUpdate(self, touple):
        taille = touple[0]
        buffer = touple[1]
        if ((self.attenteUsers[host_port] < 10) and (self.ACKUsers[host_port]==0)):
            typeM = self.dec2bin(4, 6) #conversion du type sur 6 bit
            print(self.serverProxy.getUserList())            
            for i in self.serverProxy.getUserList():
                other=i
                print(other)
                seqM= self.dec2bin(other.seq, 10)#conversion seq sur 6 bit
                other.seq+=1
                st=seqM+typeM #on concatene sequence et type
                buf=bytearray(4)
                struct.pack_into('!hh',buf,0, taille+4, int(st,2))
                buffer=buf+buffer
                other.transport.write(buffer)
            #self.waitForACK[host_port] = reactor.callLater(1, self.sendUserUpdate,touple)
            self.attenteUsers[host_port]+=1
            
        elif self.attenteUsers[host_port] == 10:
            print('user ' + user + ' has been removed from database')
            self.serverProxy.removeUser(user)
            
            
           
    #A REVOIR same problem as senduserupdate
    #REDIRIGE CHAT
    def redirchat(self,message):
        user = host_port
        user=user[4:]
        taille_user=len(user)
        user=user.encode('utf-8')
        taille_msg=len(message)
        taille_data = taille_user+taille_msg+1#+1 car taille de l'utilisateur est sur 1 octet
        msg=bytearray(taille_data)
        form='!b'+str(taille_user)+'s'+str(taille_msg)+'s'
        struct.pack_into(form,msg,0,taille_user,user,message)
        for i in self.serverProxy.getUserList():
            """if i.userChatRoom==self.serverProxy.getUserByAddress(host_port).userChatRoom :
                hp=i.userAddress
                if host_port!=hp:"""
            self.sender(taille_data,10,msg)
                         
                         
    def join_room_response(self,datagram):
        
        form='!b'
        data=struct.unpack_from(form,datagram)
        id_movie=data[0]
        #user = self.serverProxy.getUserByAddress(host_port).userName
        if id_movie==0:
            self.sender(0,11,None)
            self.serverProxy.updateUserChatroom(user, ROOM_IDS.MAIN_ROOM)
            #self.userUpdate(user,0)
        else:
            m=self.serverProxy.getMovieById(id_movie) 
            if m==None:
                self.sender(0,12,None)
            else:
                self.sender(0,8,None)
                typeM = self.dec2bin(11, 6)
                seqM= self.dec2bin(self.seq, 10)
                st=seqM+typeM
                msg=bytearray(4)
                struct.pack_into('!hh',msg,0, 4,int(st,2))
                self.transport.write(msg)
                self.serverProxy.updateUserChatroom(user, m.movieId)
                #self.userUpdate(user, m.movieId)
                """n=0
                for i in self.serverProxy.getUserList():
                    if i.userChatRoom!=ROOM_IDS.MAIN_ROOM and self.serverProxy.getMovieById(i.userChatRoom)!=None and self.serverProxy.getMovieById(i.userChatRoom).movieId==m.movieId:
                        n+=1
                print('n',n)
                if n==1:"""
                self.serverProxy.startStreamingMovie(m.movieTitle)

        
                         
    #ENVOIE D'UN ACK
    def sendAck(self, seq):
        
        typeM = self.dec2bin(63, 6)
        seqM= self.dec2bin(seq, 10)
        st=seqM+typeM
        msg=bytearray(4)
        struct.pack_into('!hh',msg,0,4,int(st,2))
        self.transport.write(msg)