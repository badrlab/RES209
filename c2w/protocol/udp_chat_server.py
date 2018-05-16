# -*- coding: utf-8 -*-
from twisted.internet.protocol import DatagramProtocol
from c2w.main.lossy_transport import LossyTransport
from c2w.main.constants import ROOM_IDS
import logging
import struct
from twisted.internet import reactor

logging.basicConfig()
moduleLogger = logging.getLogger('c2w.protocol.udp_chat_server_protocol')


class c2wUdpChatServerProtocol(DatagramProtocol):
    lastMessage = {} #Id du dernier message envoyé à un Host Port
    tempUsernames = {}
    seqUsers = {} #list des seq de chaque utilsateur
    attenteUsers = {} #dico permettant de stocker une variable indiquant le nombre de fois que l'on a envoyé un message sans réponse
    ACKUsers = {} #Chaque valeur vaut 1 ou 0 pour un host_port donné. Si 1 : on vient de recevoir un ACK (on arrete le reacteur de l'utilisateur), tant valeur = 0 on continue le bouclage 
    waitForACK = {} #Dico stockant les reacteurs
    seq = 1 #Seq du serveur
    
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
        
        
        msg = struct.unpack_from('!hh'+str(len(datagram)-4)+'s', datagram)
        taille = msg[0]
        st = msg[1]                                                                                                         #Seq + Type
        data=datagram
        if taille == len(datagram):                                                                                         #vérification que la taille du message est conforme
            seqType = self.getSeqType(st)                                                                                   #Tupple contenant la Sequence et le Type
            (nseq,tTrame)=seqType
            if tTrame!=63:
                print('ack sent respons to ' + str(seqType[1]))
                self.sendAck(seqType[0], host_port)
            
            if tTrame==1:                                                                                                   #Le message reçu est une inscription
                user = (data.decode('utf-8'))[4:]
                print("inscription received from " + user)                
                check = self.checkInscription(user)
                if check != 0:
                    print("inscription refused for " + user)
                    msg=bytearray(1)
                    struct.pack_into('b',msg ,0 ,check)
                    self.lastMessage[host_port]=8
                    self.sender(1, 8, msg, host_port)                                                                       #Envoie de l'erreur d'inscription avec le code d'erreur associé (check = 1, 2 ou 3)
                else:
                    print("inscription accepted for " + user)
                    self.lastMessage[host_port]=7                                                                           #On initie le dernier message de l'utilisateur à 7 (Inscription OK)
                    self.tempUsernames[host_port]=user     
                    self.ACKUsers[host_port]=0                    
                    self.attenteUsers[host_port] = 0                     
                    self.inscriptionAccepted(host_port)                                                                     #Envoie du msg 7 : inscription acceptée. Doit se faire APRES l'ajout de l'user
                                        
                                   
            if tTrame==5:#MESSAGE RECU
                print('msg received from '+(self.serverProxy.getUserByAddress(host_port).userName)+' and relayed')
                self.lastMessage[host_port]=5                                                                               #Le dernier message reçu de l'utilisateur est "l'envoie d'un msg instantanné
                self.redirchat(msg[2],host_port)                                                                            #On redirige le message
                
            if tTrame==6:#JOINDRE UN SALON
                print('user ' + (self.serverProxy.getUserByAddress(host_port).userName) + ' trying to join room')
                self.lastMessage[host_port]=6
                self.join_room_response(datagram,host_port)
                
            if tTrame==9:#LEAVING
                print('user ' + (self.serverProxy.getUserByAddress(host_port).userName) + ' leaving')
                self.lastMessage[host_port]=5
                self.userUpdate(self.serverProxy.getUserByAddress(host_port).userName, 127, host_port)
                self.serverProxy.removeUser(self.serverProxy.getUserByAddress(host_port).userName)
                print(self.serverProxy.getUserList())
        
        
            if tTrame == 63 :#ACK RECU                    
                print('ack received')
                if self.lastMessage[host_port] == 7:
                    
                    if (nseq+1 == self.seq):
                        if (self.ACKUsers[host_port]==0):                                                                   #Si on attendait un ACK de l'utilisateur, on cancel le bouclage du racteur        
                            self.waitForACK[host_port].cancel()                                                             #On cancel le bouclage du Send&Wait
                            self.ACKUsers[host_port]=1
                            
                        self.seqUsers[host_port]=2                                                                          #On initie la sequence de l'utilisateur à 1
                        self.serverProxy.addUser(self.tempUsernames[host_port], 0, None, host_port)                         #Ajout de l'utilisateur dans la base de donnée
                        #self.userUpdate((self.serverProxy.getUserByAddress(host_port).userName), 0, host_port)              #Envoie la mise a jour aux autres utilisateurs
                        self.lastMessage[host_port]=2                                                                       #On indique que le dernier message envoyé est la liste des firlm
                        print('sending list of films to ' + (self.serverProxy.getUserByAddress(host_port).userName))
                        self.ACKUsers[host_port]=0                                                                          #Comme on envoie un message, on initie la valeur de l'ACK de l'utilisateur à 0 (on n'a pas reçu d'acquittements)                       
                        self.attenteUsers[host_port] = 0                                                                    #Pareil que l'ACK mais pour le nombre de tentative. 
                        self.sendListFilm(host_port)                                                                        #On envoie les films.
                    
                elif self.lastMessage[host_port] != 8:
                    if (nseq+1 == self.seqUsers[host_port]):
                        if (self.ACKUsers[host_port]==0):                                                                   #Si on attendait un ACK de l'utilisateur, on cancel le bouclage du racteur        
                            self.waitForACK[host_port].cancel()
                            self.ACKUsers[host_port]=1
                            
                        if self.lastMessage[host_port] == 2:                                                                #Si le dernier message est l'envoie de film
                            self.lastMessage[host_port]=3                                                                   #On envoie la liste des utilisateurs
                            print('sending list of users to ' + (self.serverProxy.getUserByAddress(host_port).userName))
                            self.ACKUsers[host_port]=0                        
                            self.attenteUsers[host_port] = 0 
                            self.sendListUsers(host_port)
                            self.userUpdate((self.serverProxy.getUserByAddress(host_port).userName), 0, host_port)
            print("uizef")

    #ENVOIE DE L'INSCRIPTION ACCEPTEE  
    def inscriptionAccepted(self, host_port):
        if ((self.attenteUsers[host_port] < 10) and (self.ACKUsers[host_port]==0)):
            if self.attenteUsers[host_port]!=0: self.seq+=-1
            self.sender(0, 7, None, host_port)                                                                              #Envoie du message Inscription OK
            self.waitForACK[host_port] = reactor.callLater(1, self.inscriptionAccepted, host_port)
            self.attenteUsers[host_port]+=1
            
        elif self.attenteUsers[host_port] == 10:
            print("The new user did not send any answer")
            
            
    
    #ENVOIE LA LISTE DE FILM
    def sendListFilm(self, host_port):
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
                struct.pack_into('!b',buffer,n,len(title)+8)                                                                #taille dans le buffer 8 = taille,ip ,port,id
                ipe=ip.split('.')
                for i in range(4):
                    struct.pack_into('b',buffer,n+1+i,int(ipe[i]))
                form='!hb'+str(len(title))+'s'
                struct.pack_into(form,buffer,n+5,port,ide,title)
                n+=8+len(title)
            self.sender(taille,2,buffer,host_port)
            self.waitForACK[host_port] = reactor.callLater(1, self.sendListFilm, host_port)
            self.attenteUsers[host_port]+=1 
            
        elif self.attenteUsers[host_port] == 10:
            print('user ' + (self.serverProxy.getUserByAddress(host_port).userName) + ' has been removed from database')
            self.serverProxy.removeUser(self.serverProxy.getUserByAddress(host_port).userName)
            
        
            
      
     
     #ENVOIE LA LISTE DES USERS
    def sendListUsers(self, host_port):
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
                    print(idroom)
                user=user.encode('utf8')
                form='!bb'+str(len(user))+'s'
                struct.pack_into(form,buffer,n,len(user)+1+1,idroom,user) #taille données=longueur titre + 1 octet de taille + 2 + 4 + 1) suivie par ip, port etc..
                n+=len(user)+2
            self.sender(taille,3,buffer, host_port)
            self.waitForACK[host_port] = reactor.callLater(1, self.sendListUsers, host_port)
            self.attenteUsers[host_port]+=1
            
        elif self.attenteUsers[host_port] == 10:
            print('user ' + (self.serverProxy.getUserByAddress(host_port).userName) + ' has been removed from database')
            self.serverProxy.removeUser(self.serverProxy.getUserByAddress(host_port).userName)
        
   
    #METTRE A JOUR UN USER
    def userUpdate(self, userName, idSalon, host_port):
        userName=userName.encode('utf-8')
        buffer=bytearray(len(userName)+1)
        struct.pack_into('b'+str(len(userName))+'s',buffer,0,idSalon,userName)
        for i in self.serverProxy.getUserList():
            hp=i.userAddress
            #if host_port!=hp:
            print('sending update')
            self.ACKUsers[hp]=0                        
            self.attenteUsers[hp] = 0 
            self.sendUserUpdate((len(userName)+1,buffer,hp))
                
                
                
           
    def sendUserUpdate(self, touple):
        taille = touple[0]
        buffer = touple[1]
        host_port = touple[2]
        if ((self.attenteUsers[host_port] < 10) and (self.ACKUsers[host_port]==0)):
            self.sender(taille,4,buffer,host_port)
            self.waitForACK[host_port] = reactor.callLater(1, self.sendUserUpdate,touple)
            self.attenteUsers[host_port]+=1
            
        elif self.attenteUsers[host_port] == 10:
            print('user ' + (self.serverProxy.getUserByAddress(host_port).userName) + ' has been removed from database')
            self.serverProxy.removeUser(self.serverProxy.getUserByAddress(host_port).userName)
    
    
    
    def sendRedirChat(self, taille, buffer, host_port) :
        if ((self.attenteUsers[host_port] < 10) and (self.ACKUsers[host_port]==0)):
            self.sender(taille,10,buffer,host_port)
            self.waitForACK[host_port] = reactor.callLater(1, self.sendRedirChat,(taille, buffer, host_port))
            self.attenteUsers[host_port]+=1
            
        elif self.attenteUsers[host_port] == 10:
            print('user ' + (self.serverProxy.getUserByAddress(host_port).userName) + ' has been removed from database')
            self.serverProxy.removeUser(self.serverProxy.getUserByAddress(host_port).userName)
            
            
            
    #REDIRIGE CHAT
    def redirchat(self,message,host_port):
        
        user = self.serverProxy.getUserByAddress(host_port).userName
        taille_user=len(user)
        user=user.encode('utf-8')
        taille_msg=len(message)
        taille_data = taille_user+taille_msg+1#+1 car taille de l'utilisateur est sur 1 octet
        msg=bytearray(taille_data)
        form='!b'+str(taille_user)+'s'+str(taille_msg)+'s'
        struct.pack_into(form,msg,0,taille_user,user,message)
        for i in self.serverProxy.getUserList():
            if i.userChatRoom==self.serverProxy.getUserByAddress(host_port).userChatRoom :
                hp=i.userAddress
                #if host_port!=hp:
                self.ACKUsers[hp]=0                        
                self.attenteUsers[hp] = 0 
                self.sendRedirChat(taille_data,msg,hp)
                         
                         
    #REPONSE A UNE DEMANDE D'ACCES A UNE ROOM                  
    def join_room_response(self,datagram,host_port):
        
        form='!hhb'
        data=struct.unpack_from(form,datagram)
        id_movie=data[2]
        user = self.serverProxy.getUserByAddress(host_port).userName
        if id_movie==0:
            self.sender(0,11,None,host_port)
            self.serverProxy.updateUserChatroom(user, ROOM_IDS.MAIN_ROOM)
            self.userUpdate(user,0, host_port)
        else:
            m=self.serverProxy.getMovieById(id_movie) 
            if m==None:
                self.sender(0,12,None,host_port)
            else:
                self.sender(0,11,None,host_port)
                self.serverProxy.updateUserChatroom(user, m.movieId)
                self.userUpdate(user, m.movieId, host_port)
                n=0
                for i in self.serverProxy.getUserList():
                    if i.userChatRoom!=ROOM_IDS.MAIN_ROOM and self.serverProxy.getMovieById(i.userChatRoom)!=None and self.serverProxy.getMovieById(i.userChatRoom).movieId==m.movieId:
                        n+=1
                if n==1:
                    self.serverProxy.startStreamingMovie(m.movieTitle)
                         

    #def leave_system_response(self,datagram,host_port):
        
                         
    #ENVOIE D'UN ACK
    def sendAck(self, seq, host_port):
        
        typeM = self.dec2bin(63, 6)
        seqM= self.dec2bin(seq, 10)
        st=seqM+typeM
        msg=bytearray(4)
        struct.pack_into('!hh',msg,0,4,int(st,2))
        self.transport.write(msg, host_port)
        
        
        
        
     #METHODE ASSEMBLANT LE MESSAGE ET L'ENTETE  
    def sender(self, taille, typeM, data, host_port):
        
        if ((typeM != 8) and (typeM != 7)): #7 ou 8 = Inscription acceptée/Refusée ===> User n'est pas encore dans la base de donnée du serveur
            user = self.serverProxy.getUserByAddress(host_port).userName #on trouve l'utilisateur à qui on envoie le message
            seqM = self.dec2bin(self.seqUsers[host_port],10)
            self.seqUsers[host_port]+=1
        else : 
            user = None 
            seqM= self.dec2bin(self.seq, 10) #Si l'utilisateur n'existe pas, on envoie avec la séquence du serveur
            self.seq+=1
        typeM = self.dec2bin(typeM, 6) #conversion du type sur 6 bit
            
        st=seqM+typeM #on concatene sequence et type
        buf=bytearray(4)
        struct.pack_into('!hh',buf,0, taille+4, int(st,2))
        
        if data != None:
            buf=buf+data
        self.transport.write(buf, host_port)  
        
     
     
     #VERIFICATION DE L'INSCRIPTION
    def checkInscription(self, data):
        
        check = 0
        if(data.find(" ")!=-1):
            check = 3 
        if len(data)>127: #Username > 254 caractere = 254 octets
            check = 2
        if self.serverProxy.userExists(data) : check = 1
        return check        
        
       
       
        #CONVERTISSEUR BINAIRE    
    def dec2bin(self, decimal, nbbits): #Le convertisseur fait une division euclidienne
        
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