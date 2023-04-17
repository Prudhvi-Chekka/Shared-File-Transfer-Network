#! /usr/bin/python
import threading

from library import *
import socket as sock
from chatRoom import *
from clientNode import *


class Server(object):
    """
    Class object that stores all server related info.
    """

    def __init__(self):
        """
        self.clients is a list of all client objects instantiated by the server.
        Objects are not deleted once they are disconnected, so that indexing is maintained.
        However, the client object has a self.suspended field to check if the client is active.
        """
        self.s = sock.socket(sock.AF_INET, sock.SOCK_STREAM)
        self.port = 50000
        self.ip = gethostbyname(gethostname())
        self.clients = {}
        self.chatrooms = {}
        self.suspended = False
        self.admin_access = 'No'

    def remove_client(self, username):
        """
        Remove username from dictionary of clients.
        """
        try:
            self.clients.pop(username)
        except KeyError:
            print('Client not in server.clients{}')

    def get_chatrooms(self):
        """
        Return a list of chatroom names.
        """
        return list(self.chatrooms)

    def go_online(self, start=50000, tries=10):
        """
        Bind to a connection port and start listening on it.
        :param start: Try binding to port numbers starting at this value
        :param tries: Try binding 'tries' number of times till port = start+tries-1
        """
        flag = False
        for listen_port in (start, start + tries - 1):
            if bind_to_port(self.s, listen_port):
                flag = True
                break

        if not flag:
            print("Couldn't bind to connection port. Aborting...")
            sys.exit()

        self.s.listen(25)
        print('Server is listening at', listen_port)
        self.port = listen_port

    def broadcast(self, msg):
        """
        Send a message to all clients connected to server
        """
        for client in list(self.clients.values()):
            send_data(client.socket, msg)

    def get_user_input(self):
        """
        TODO Parse user input on server and take action
        """
        # print(("User Input plz", self.suspended))
        while not self.suspended:
            inp = input()
            inp = inp.split('|')
            if inp[0] in ['exit', 'quit', 'kill']:
                self.broadcast('kill')
                conn, cursor = DBConnect()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                for table in tables:
                    print(f"{table[0]} table removed from DB")
                    cursor.execute(f"DROP TABLE {table[0]}")
                # Commit the changes and close the connection
                conn.commit()
                conn.close()
                self.suspended = True
                for client in list(self.clients.values()):
                    client.socket.close()
                self.s.close()  # Have to connect to socket to exit server.
                sock = socket(AF_INET, SOCK_STREAM)
                port = bind_to_random(sock)
                sock.connect((str(self.ip), self.port))
            if inp[0] in ['logs']:
                conn, cursor = DBConnect()
                try:
                    cursor.execute("SELECT username, ip, login_time FROM login_details;")
                    data1 = cursor.fetchall()
                    print("Login details of the users")
                    print('(username,', 'ip,', 'login_details)')
                    for d in data1:
                        print(d)
                except:
                    print("No entries in the table")
            if inp[0] in ['users_info']:
                conn, cursor = DBConnect()
                try:
                    cursor.execute("SELECT * FROM users;")
                    data = cursor.fetchall()
                    print("Users info:")
                    print('(username,', 'password,', 'admin_access)')
                    for d in data:
                        print(d)
                except:
                    print("No entries in the table")
            elif len(inp) > 1:
                msg = '|'.join(['#server'] + inp[1:])
                if inp[0][:1] == '@':
                    destination = inp[0][1:].lower()
                    if destination == 'server':
                        print(msg)
                    elif destination == 'all':
                        self.broadcast(msg)
                    elif destination == 'access':
                        if inp[1] == 'Yes':
                            self.admin_access = 'Yes'
                    else:
                        client = self.clients.get(destination, None)
                        if client:
                            client_send(client.socket, msg)
                        else:
                            print('Destination not active')
                else:
                    print(msg)

    def execute(self):
        """
        This is the main server thread. Go online and start listening for connections.
        Accept client connections and start a new client thread using its execute method.
        """
        self.go_online()
        empty_tuple = ()
        threading.Thread(target=self.get_user_input, args=empty_tuple).start()

        while not self.suspended:
            ds, addr = self.s.accept()
            client = ClientNode(self, addr, ds)
            print((self.ip, self.port))
            # self.clients.append(client)  # Now happens after username is verified in clientNode.py
            print(('Incoming connection from', addr))
            if not self.suspended:
                threading.Thread(target=client.execute, args=empty_tuple).start()
        print('Server is suspended. Thank you!')


s1 = Server()
s1.execute()
