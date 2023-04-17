#! /usr/bin/python
import socket as sock
import time

from library import *
import fnmatch
import getopt
import threading
import os
import sys
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)


def help():
    print('What do you want from the server.\n 1.List Files.\n 2.Download a '
              'File.\n '
              '3.Upload a File.\n 4.Delete a File. \n 5.Create a chatroom.\n 6.Join a chatroom.\n Enter an '
              'option:')


class Client(object):
    """
  Class object that stores peer information
  """

    def __init__(self, start=50000, tries=10):
        """
    Connect to server: Server uses some port between 50000 and 50009
    """
        self.sock = sock.socket(sock.AF_INET, sock.SOCK_STREAM)
        self.suspended = False
        self.pport = bind_to_random(self.sock)
        self.ip = gethostbyname(gethostname())
        self.file_share = dict()
        self.global_share = True
        self.iplist = ['0.0.0.0', '127.0.0.2', '127.0.0.3']  # 2 server IP's to be added here
        self.portlist = [i for i in range(start, start + tries - 1)]
        self.BUFFER_SIZE = 4096
        self.action = ''

        #  Try connecting to server IPs in iplist at port numbers in portlist. Exit on failure.
        for ip in self.iplist:
            for port in self.portlist:
                try:
                    self.sock.connect((ip, port))
                    return
                except error:
                    self.sock.close()
                    self.sock = socket(AF_INET, SOCK_STREAM)
        sys.exit('Cannot connect to server')

    def handle_exit_commands(self, msg):
        """
    Handle exit/quit and kill commands received from server.
    """
        if msg[0].lower() in ['exit', 'quit']:
            print("Thank You for using our chatroom. Press enter to continue.")
            self.suspended = True
        elif msg[0].lower() in ['kill']:
            print("Server has suspended operation. Thank You for using our chatroom. Press enter to continue.")
            client_send(self.sock, '@server|exit')
            self.suspended = True

    def listen_to_server(self):
        """
    Until client is suspended, keep listening to messages from server and perform necessary actions.
    Server commands to handle include: ['kill', 'exit', 'quit', 'whohas', 'getfile',
    'setshare', 'clrshare', 'setglobalshare', 'clrglobalshare', 'getsharestatus']
    """
        while not self.suspended:
            msg = client_recv(self.sock)
            self.handle_exit_commands(msg)
            if not self.suspended and len(msg) > 1:
                if msg[0] in 'sending_file':
                    filename = msg[1]
                    filesize = int(client_recv(self.sock)[0])
                    if filesize == 0:
                        print("File not found.")
                        continue
                    with open('folder' + '/' + filename, 'wb') as f:
                        data = self.sock.recv(self.BUFFER_SIZE)
                        total_bytes = len(data)
                        f.write(data)
                        while total_bytes < filesize:
                            data = self.sock.recv(self.BUFFER_SIZE)
                            total_bytes += len(data)
                            f.write(data)
                    print("File downloaded successfully.")
                    continue
                if msg[1].lower() in ['whohas', 'getfile', 'setshare', 'clrshare'] and len(msg) < 3:
                    client_send(self.sock, '@' + msg[0][1:] + '|ERROR: Please specify filename')
                    continue

    def listen_to_user(self):
        """
    Until client is suspended, keep listening to inputs from user and forward the message to the server.
    Also, on sensing a 'getfile' input, send IP and port details to destination, and start a udpclient thread.
    """
        while not self.suspended:
            user_input = input()
            if user_input == "1":
                mssg = "@server|list"
                self.sock.send(mssg.encode())
            elif user_input == '2' or user_input == '@server|download':
                mssg = "@server|download"
                self.sock.send(mssg.encode())
                filename = input("Enter the filename: ")
                self.sock.sendall(str.encode(filename + '\n'))
            elif user_input == '3' or user_input == '@server|upload':
                mssg = "@server|upload"
                self.sock.send(mssg.encode())
                filepath = input("Enter the filepath: ")
                if not os.path.exists(filepath):
                    print("File not found.")
                    continue
                filename = os.path.basename(filepath)
                filesize = os.path.getsize(filepath)
                self.sock.sendall(str.encode(filename + '\n'))
                self.sock.sendall(str.encode(str(filesize) + '\n'))
                with open(filepath, 'rb') as f:
                    data = f.read(self.BUFFER_SIZE)
                    while data:
                        self.sock.sendall(data)
                        data = f.read(self.BUFFER_SIZE)
            elif user_input == '4' or user_input == '@server|delete':
                mssg = '@server|delete'
                self.sock.send(mssg.encode())
                filename = input("Enter the filename to delete: ")
                self.sock.sendall(str.encode(filename + '\n'))
            elif user_input == '5':
                mssg = "@server|create"
                # print('Create sent')
                client_send(self.sock, mssg)
            elif user_input == '6':
                mssg = "@server|join"
                client_send(self.sock, mssg)
            elif user_input not in ['1', '2', '3', '4', '5', '6', 'Yes', 'No', 'help']:
                client_send(self.sock, user_input)
                user_input = user_input.rstrip('\n')
                user_input = user_input.split("|")
            elif user_input == 'Yes':
                mssg = "@admin|yes"
                client_send(self.sock, mssg)
            elif user_input == 'No':
                mssg = "@admin|no"
                client_send(self.sock, mssg)
            elif user_input == 'help':
                help()

    def execute(self):
        """
    Keep listening to messages from server and inputs from user in parallel. Exit when suspended.
    """
        empty_tuple = ()
        threading.Thread(target=self.listen_to_server, args=empty_tuple).start()
        self.listen_to_user()
        self.sock.close()


c1 = Client()
c1.execute()
