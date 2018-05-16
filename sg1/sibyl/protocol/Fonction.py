
from twisted.internet.protocol import DatagramProtocol
import struct
import time

def coder_binaire(line):

	temps=int(time.time())

	time_binaire=struct_pack('I',temps)  

	message=line.encode('utf8')
	l=str(len(line))
	len_binaire=struct_pack('H',l+6)

	message_binaire=struct_pack(l+'s',message)

	return(time_binaire+len_binaire+message_binaire)


def decoder_binaire(msg):

	m=msg[6:]
	message=m.decode('utf8')
	return(message)


