# -*- coding: utf-8 -*-
from twisted.internet.protocol import Protocol
import struct
import time


class SibylServerTcpBinProtocol(Protocol):
    """The class implementing the Sibyl TCP binary server protocol.

        .. note::
            You must not instantiate this class.  This is done by the code
            called by the main function.

        .. note::

            You have to implement this class.  You may add any attribute and
            method that you see fit to this class.  You must implement the
            following method (called by Twisted whenever it receives data):
            :py:meth:`~sibyl.main.protocol.sibyl_server_tcp_bin_protocol.dataReceived`
            See the corresponding documentation below.

    This class has the following attribute:

    .. attribute:: SibylServerProxy

        The reference to the SibylServerProxy (instance of the
        :py:class:`~sibyl.main.sibyl_server_proxy.SibylServerProxy` class).

            .. warning::

                All interactions between the client protocol and the server
                *must* go through the SibylServerProxy.

    """

    def __init__(self, sibylServerProxy):
        """The implementation of the UDP server text protocol.

        Args:
            sibylServerProxy: the instance of the server proxy.
        """
        self.sibylServerProxy = sibylServerProxy
        self.buffer=''.encode('utf-8')

    def dataReceived(self, line):
        """Called by Twisted whenever a data is received

        Twisted calls this method whenever it has received at least one byte
        from the corresponding TCP connection.

        Args:
            line (bytes): the data received (can be of any length greater than
            one);

        .. warning::
            You must implement this method.  You must not change the parameters,
            as Twisted calls it.

        """
        self.buffer+=line
        if len(self.buffer)>6:
            lenght=self.buffer[5]
            frm='ih'+str(lenght)+'s'
            resp=struct.unpack(frm,self.buffer)
            resp=resp[2].decode('utf-8')
            if len(resp)==lenght:
                print('OK')
                resp=struct.unpack(frm,self.buffer)
                resp=resp[2].decode('utf-8')
                resp = self.sibylServerProxy.generateResponse(resp)
                resp=resp.encode('utf-8')
                lenght=len(resp)
                form='ih'+str(lenght)+'s'
                resp=struct.pack(form,int(time.time()),lenght,resp)
                self.transport.write(resp)
                self.buffer=''.encode('utf-8')
        pass
    