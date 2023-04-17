#! /usr/bin/python
import os
import re
from library import *
import socket
from chatRoom import *
import sqlite3
import datetime
import shutil

def DBConnect():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    return conn, c

class ClientNode(object):
    """
  Class object for holding client related information
  """

    def __init__(self, server_reference, ip, socket):
        """
    :param ip: IP address of client.
    :param socket: Socket at server used to communicate with client.
    """
        self.server = server_reference
        self.ip = ip
        self.socket = socket
        self.username = None
        self.suspended = False
        self.BUFFER_SIZE = 4096
        self.owner = ''
        self.chatroom_name = ''
        self.signed = False

    def execute(self):
        """
    This is the main per-client execution thread for the server.
    Enable a client to login and proceed to listen to, and forward, its messages.
    """
        msg = 'Connected to ' + self.server.ip + ' at port ' + str(self.server.port)
        msg += '\nSignup or Login:\n'
        send_data(self.socket, msg)
        rec_msg = decode_data(recv_data(self.socket))
        if rec_msg[0] == 'Signup':
            tries = 5
            while tries > 1:
                if self.Signup():
                    self.signed = True
                    break
                tries = tries - 1
            if self.signed:
                msg = '\nPlease Login.'
                send_data(self.socket, msg)
                self.Login()
            else:
                send_err(self.socket, 'Max tries reached, closing connection.\n')
                self.suspended = True
        elif rec_msg[0] == 'Login':
            self.Login()
        self.accept_login()
        while not self.suspended:
            self.create_or_join()
            continue

    def Signup(self, tries=5):
        conn, cursor = DBConnect()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users
                     (username text PRIMARY KEY, password text, admin_access text)''')
        conn.commit()
        msg = '\nPlease enter your username\n'
        send_data(self.socket, msg)
        rec_username = decode_data(recv_data(self.socket))[0]
        cursor.execute("SELECT * FROM users WHERE username = ?", (rec_username,))
        user = cursor.fetchone()
        if user:
            if tries > 0:
                send_err(self.socket, 'Username taken, kindly choose another.\n')
                return False
            else:
                send_err(self.socket, 'Max tries reached, closing connection.\n')
                self.suspended = True
        msg = '\nPlease enter the required password\n'
        send_data(self.socket, msg)
        rec_pwd = decode_data(recv_data(self.socket))[0]
        msg = '\nRequest for admin access. Yes/No'
        send_data(self.socket, msg)
        admin = decode_data(recv_data(self.socket))
        admin_access = 'No'
        if admin[1] == 'yes':
            print(f"\nNeed your approval. Please Send Active ACK\n")
            access = input(f"{rec_username} needs admin access. Please approve\n")
            if access == 'Yes':
                admin_access = 'Yes'
                msg = '\nAdmin access granted'
                send_data(self.socket, msg)
            else:
                admin_access = 'No'
                msg = '\nAdmin access Denied'
                send_data(self.socket, msg)
        cursor.execute("INSERT INTO users VALUES (?, ?, ?)", (rec_username, rec_pwd, admin_access))
        conn.commit()
        conn.close()
        msg = 'Signup successful'
        send_data(self.socket, msg)
        return True

    def Login(self, tries=5):
        conn, cursor = DBConnect()
        cursor.execute('''CREATE TABLE IF NOT EXISTS login_details
                             (username text, password text, ip text, login_time text)''')
        msg = '\nPlease enter your username\n'
        send_data(self.socket, msg)
        rec_username = decode_data(recv_data(self.socket))[0]
        msg = '\nPlease enter your password\n'
        send_data(self.socket, msg)
        rec_pwd = decode_data(recv_data(self.socket))[0]
        cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (rec_username, rec_pwd))
        user = cursor.fetchone()
        if user:
            msg = f'Welcome {rec_username}\n'
            send_data(self.socket, msg)
        else:
            if tries > 0:
                send_err(self.socket, 'Invalid username or password. Please try again.\n')
                self.Login(tries - 1)
            else:
                send_err(self.socket, 'Max tries reached, closing connection.\n')
                self.suspended = True
        login_time = datetime.datetime.now().isoformat()
        cursor.execute("INSERT INTO login_details VALUES (?, ?, ?, ?)", (rec_username, rec_pwd, str(self.ip), login_time))
        conn.commit()
        conn.close()
        self.username = rec_username
        self.server.clients[self.username] = self  # Add to dictionary in server.
        send_ok(self.socket,
                '\nWhat do you want from the server.\n 1.List Files.\n 2.Download a '
                                     'File.\n '
                                     '3.Upload a File.\n 4.Delete a File.\n 5.Create a chatroom.\n 6.Join a '
                                     'chatroom.\n Enter an '
                                     'option:')

    def list_files(self, folder):
        print(os.listdir(folder))  # Shows all the files at server side
        list1 = os.listdir(folder)
        if not list1:
            msg = 'Folder is empty'
            send_data(self.socket, msg)
        else:
            send_list(self.socket, list1)

    def download_files_test(self, folder):
        self.list_files(folder)
        FileName = self.socket.recv(1024).decode()
        FileName = FileName.rstrip()
        print("\nServer> Client wants to download :", FileName)
        print("Server> Checking the list of files ...")
        self.socket.send(f"sending_file|{FileName}".encode("ascii"))
        if not os.path.exists(folder + '/' + FileName):
            self.socket.sendall(str.encode("File not found.\n"))
            return
        filesize = os.path.getsize(folder + '/' + FileName)
        self.socket.sendall(str.encode(str(filesize) + '\n'))
        with open(folder + '/' + FileName, 'rb') as f:
            data = f.read(self.BUFFER_SIZE)
            while data:
                self.socket.sendall(data)
                data = f.read(self.BUFFER_SIZE)

    def upload_files_test(self, folder):
        filename = self.socket.recv(1024).decode()
        filename = filename.rstrip()
        filesize = self.socket.recv(1024).decode()
        filesize = int(filesize.rstrip())
        with open(folder + '/' + filename, 'wb') as f:
            data = self.socket.recv(self.BUFFER_SIZE)
            total_bytes = len(data)
            f.write(data)
            while total_bytes < filesize:
                data = self.socket.recv(self.BUFFER_SIZE)
                total_bytes += len(data)
                f.write(data)
        if os.path.exists(folder + '/' + filename):
            self.socket.sendall(str.encode("File uploaded successfully.\n"))
            print("File received to server")

    def delete_files_test(self, folder):
        self.list_files(folder)
        filename = self.socket.recv(1024).decode()
        filename = filename.rstrip()
        if not os.path.exists(folder + '/' + filename):
            self.socket.sendall(str.encode("File not found.\n"))
            return
        else:
            conn, cursor = DBConnect()
            cursor.execute("SELECT admin_access from users WHERE username = ?", (self.username,))
            data = cursor.fetchone()
            if data[0] == 'Yes':
                os.remove(folder + '/' + filename)
                if not os.path.exists('folder' + '/' + filename):
                    self.socket.sendall(str.encode("File deleted successfully.\n"))
                print("File Removed from server")
            else:
                msg = "You don't have admin access to delete the file"
                client_send(self.socket, msg)

    def chat_room(self):
        if not self.suspended:
            msg = 'Welcome to ' + self.chatroom.name + '. You are all set to pass messages\n'
            send_data(self.socket, msg)
        while not self.suspended:
            self.accept_message()
        if not self.server.suspended:
            print(self.chatroom, self.server.chatrooms)
            print(self.chatroom.get_usernames(), type(self.chatroom.get_usernames()))
            msg = 'exit'
            send_data(self.socket, msg)
            if self.chatroom is not None:
                self.chatroom.broadcast('INFO| User ' + self.username + ' has left\n', self.username)
                self.chatroom.remove_client(self.username)
                if not self.chatroom.get_usernames():
                    try:
                        print("Deleting chat room")
                        print(self.server.chatrooms)
                        del self.server.chatrooms[self.chatroom_name]
                    except KeyError:
                        pass
                    if os.path.exists(str(self.chatroom_name)):
                        shutil.rmtree(str(self.chatroom_name))
                        print("Temporary room deleted")
            self.server.remove_client(self.username)
        self.socket.close()

    def accept_login(self):
        """
    Establish the clients username and create a new chatroom, or add it to an existing one.
    """
        self.create_or_join()

    def create_or_join(self, tries=5):
        """
    Check if client wants to create a new chatroom or join an existing one.
    """
        if self.suspended:
            return
        msg = decode_data(recv_data(self.socket))
        if isinstance(msg, list) and len(msg) > 1:
            option = str(msg[1]).lower()
        else:
            option = msg
        if option == 'list':
            self.list_files('folder')
        elif option == 'download':
            self.download_files_test('folder')
        elif option == 'upload':
            self.upload_files_test('folder')
        elif option == 'delete':
            self.delete_files_test('folder')
        elif option == 'create':  # Create chatroom - check chatroom name
            send_ok(self.socket, 'Specify a chatroom name to create.\n')
            self.create_chatroom()
            self.chat_room()
        elif option == 'join':  # Join existing chatroom - Send list of available peers.
            if len(self.server.chatrooms):
                send_ok(self.socket, 'Here is a list of chatrooms you can join.\n')
                send_list(self.socket, self.server.get_chatrooms())
                self.join_chatroom()
                self.chat_room()
            else:  # There are no chatrooms to join
                if tries > 0:
                    send_err(self.socket, 'There are no chatrooms to join now\n')
                    self.create_or_join(tries - 1)
                else:
                    send_err(self.socket, 'Max tries reached, closing connection.\n')
                    self.suspended = True
        else:
            send_err(self.socket, 'Please enter a valid option\n')

    def create_chatroom(self, tries=5):
        """
    Create chatroom - Add client as first user of room when a unique name is received
    :param tries: Retry 'tries' number of times to get a unique chatroom name.
    """
        if self.suspended:
            return
        msg = decode_data(recv_data(self.socket))
        name, names = msg[0], list(self.server.chatrooms)
        if name in names:
            if tries > 0:
                send_err(self.socket, 'Sorry, chatroom already taken. Please try again.\n')
                self.create_chatroom(tries - 1)
            else:
                send_err(self.socket, 'Max tries reached, closing connection.\n')
                self.suspended = True
        else:
            send_ok(self.socket, 'Chatroom ' + name + ' created. Do you want to password protect the room? [yes/no]\n')
            self.passwd_protect_chatroom(name)

    def passwd_protect_chatroom(self, room_name, tries=5):
        """

    :param room_name: Name of chatroom being joined.
    :param tries:
    :return:
    """
        if self.suspended:
            return
        msg = decode_data(recv_data(self.socket))
        if msg[0][:3].lower() == 'yes':
            send_ok(self.socket, 'Please enter password.\n')
            msg = decode_data(recv_data(self.socket))
            send_ok(self.socket, 'Password ' + msg[0] + ' accepted.\n')
            new_room = ChatRoom(self.server, room_name, self.username, msg[0])
        else:
            send_ok(self.socket, 'Chatroom has been made public.\n')
            new_room = ChatRoom(self.server, room_name, self.username)
        if not os.path.exists(room_name):
            os.makedirs(room_name)
            self.owner = self.username
        self.server.chatrooms[room_name] = new_room
        self.chatroom = new_room
        self.chatroom_name = room_name

    def join_chatroom(self, tries=5):
        """
    Join chatroom - Add client to client list of room when request is received
    :param tries: Retry 'tries' number of times to get an existent chatroom name.
    """
        if self.suspended:
            return
        msg = decode_data(recv_data(self.socket))
        name = msg[0]
        for room_name in list(self.server.chatrooms):
            room = self.server.chatrooms[room_name]
            if name == room_name:
                self.check_password(room)
                if self.suspended:
                    return
                room.broadcast('INFO| New user ' + self.username + ' has joined\n', self.username)
                self.chatroom_name = name
                send_ok(self.socket, 'You have joined chatroom - ' + name + '\n')
                self.chatroom = room
                if len(room.clients):
                    send_data(self.socket, 'Here is a list of peers in the room:\n')
                    send_list(self.socket, self.chatroom.get_usernames())
                else:
                    send_data(self.socket, 'There are no peers in the room:\n')
                room.clients.append(self.username)
                return
        if tries > 0:
            send_err(self.socket, 'Sorry, chatroom name not found. Please try again.\n')
            self.join_chatroom(tries - 1)
        else:
            send_err(self.socket, 'Max tries reached, closing connection.\n')
            self.suspended = True

    def check_password(self, room, tries=5):
        if room.get_password() is None:
            return
        send_ok(self.socket, 'This chatroom is private. Please enter password.\n')
        msg = decode_data(recv_data(self.socket))
        if msg[0] != room.password:
            if tries > 1:
                send_err(self.socket, 'Sorry, incorrect password. You have ' + str(tries - 1) + ' tries left.\n')
                self.check_password(room, tries - 1)
            else:
                send_err(self.socket, 'Max tries reached, closing connection.\n')
                self.suspended = True
        else:
            send_ok(self.socket, 'Password accepted.\n')

    def accept_message(self):
        """
    Check the destination field in a message and unicast it to the destination or,
    broadcast if destination is 'all'. Edit message to include source instead of destination
    Messages with destination as 'server' may be an exit or quit message.
    """
        msg = decode_data(recv_data(self.socket))
        destination = msg[0]
        if destination[:1] != '@':
            send_err(self.socket, 'Sorry, first field in message should be @<destination>\n')
            return
        destination = destination[1:]
        msg[0] = '#me' if destination in [self.username, 'me'] else '#' + self.username
        if destination == 'all':
            self.chatroom.broadcast('|'.join(msg), self.username)
        elif destination == 'server':
            if len(msg) > 1:
                if msg[1].lower() in ['exit', 'quit']:
                    self.suspended = True
                elif msg[1].lower() == 'get_peers':
                    send_list(self.socket, self.chatroom.get_usernames())
                elif msg[1].lower() == 'get_rooms':
                    send_list(self.socket, self.server.get_chatrooms())
                elif msg[1].lower() == 'get_passwd':
                    message = self.chatroom.get_password()
                    if message is None:
                        message = 'This chatroom is public and has no password protection.'
                    send_data(self.socket, message)
                elif msg[1].lower() == 'download':
                    self.download_files_test(self.chatroom_name)
                elif msg[1].lower() == 'upload':
                    self.upload_files_test(self.chatroom_name)
                elif msg[1].lower() == 'delete':
                    self.delete_files_test(self.chatroom_name)
                elif msg[1].lower() == 'list':
                    self.list_files(self.chatroom_name)
                else:  # Just deliver the message to server console
                    print(('|'.join(msg)))
        else:
            dest_client = self.chatroom.get_client(destination) if destination != 'me' else self
            if dest_client is None:
                send_err(self.socket, 'Sorry, destination client not present in chatroom\n')
            else:
                send_list(dest_client.socket, msg)
