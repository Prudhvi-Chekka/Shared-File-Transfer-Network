from library import *
from udpclient import *
from udpserver import *
import fnmatch
import os
import getopt
import threading

class Client(object):
  """
  Class object that stores peer information
  """
  def __init__(self, start=50000, tries=10):
    """
    Connect to server: Server uses some port between 50000 and 50009
    """
    self.socket = socket(AF_INET, SOCK_STREAM)
    self.suspended = False
    self.pport = bind_to_random(self.socket)
    self.ip = gethostbyname(gethostname())
    self.N = 16
    self.Err = 100
    self.file_share = dict()
    for filename in os.listdir('folder'):
      self.file_share[filename] = True
    self.global_share = True
    self.max_share_count = 2
    self.iplist = ['0.0.0.0', '127.0.0.1']  # 2 server IP's to be added here
    self.portlist = [i for i in xrange(start, start+tries-1)]
    self.max_conn_lock = threading.Lock()
    self.get_args()
    self.conn_left = self.max_share_count  # Counter to increment decrement inside locked code.

    #  Try connecting to server IPs in iplist at port numbers in portlist. Exit on failure.
    for ip in self.iplist:
      for port in self.portlist:
        try:
          self.socket.connect((ip, port))
          return
        except error:
          self.socket.close()
          self.socket = socket(AF_INET, SOCK_STREAM)
    sys.exit('Cannot connect to server')
    def handle_user_commands(self, instr, arg=None):
    """
    Check instr for user commands and call the required functions
    """
    if instr == 'setshare':
      self.set_share(arg, True)
    elif instr == 'clrshare':
      self.set_share(arg, False)
    elif instr == 'setglobalshare':
      self.set_global_share(True)
    elif instr == 'clrglobalshare':
      self.set_global_share(False)
    elif instr == 'getsharestatus':
      self.get_share_status()
    elif instr == 'setwindowsize':
      self.set_window_size(int(arg))

  def handle_exit_commands(self, msg):
    """
    Handle exit/quit and kill commands received from server.
    """
    if msg[0].lower() in ['exit', 'quit']:
      print "Thank You for using our chatroom. Press enter to continue."
      self.suspended = True
    elif msg[0].lower() in ['kill']:
      print "Server has suspended operation. Thank You for using our chatroom. Press enter to continue."
      client_send(self.socket, '@server|exit')
      self.suspended = True

  def listen_to_server(self):
    """
    Until client is suspended, keep listening to messages from server and perform necessary actions.
    Server commands to handle include: ['kill', 'exit', 'quit', 'whohas', 'getfile',
    'setshare', 'clrshare', 'setglobalshare', 'clrglobalshare', 'getsharestatus']
    """
    while not self.suspended:
      msg = client_recv(self.socket)
      self.handle_exit_commands(msg)
      if not self.suspended and len(msg) > 1:
        if msg[1].lower() in ['whohas', 'getfile', 'setshare', 'clrshare'] and len(msg) < 3:
          client_send(self.socket, '@' + msg[0][1:] + '|ERROR: Please specify filename')
          continue
        if msg[1].lower() in ['whohas'] and self.check_file(msg[2]):
          client_send(self.socket, '@' + msg[0][1:] + '|ME')
        elif msg[1].lower() in ['getfile']:
          msg += client_recv(self.socket)[1:]  # add cip and cport sent from client
          udpserver = UDPServer(self, msg)
          empty_tuple = ()
          thread.start_new_thread(udpserver.execute, empty_tuple)
        elif msg[0].lower() == '#me':
          arg = None if len(msg) < 3 else msg[2].lower()
          self.handle_user_commands(msg[1].lower(), arg)

  def listen_to_user(self):
    """
    Until client is suspended, keep listening to inputs from user and forward the message to the server.
    Also, on sensing a 'getfile' input, send IP and port details to destination, and start a udpclient thread.
    """
    while not self.suspended:
      user_input = raw_input()
      client_send(self.socket, user_input)
      user_input = user_input.rstrip('\n')
      user_input = user_input.split("|")
      if len(user_input) > 2 and user_input[1] == 'getfile':
        s = socket(AF_INET, SOCK_DGRAM)
        cp = bind_to_random(s)
        client_send(self.socket, '|'.join([user_input[0], str(self.ip), str(cp)]))
        empty_tuple = ()
        udpclient = UDPClient(self, user_input, s, cp)
        thread.start_new_thread(udpclient.execute, empty_tuple)

  def execute(self):
    """
    Keep listening to messages from server and inputs from user in parallel. Exit when suspended.
    """
    empty_tuple = ()
    thread.start_new_thread(self.listen_to_server, empty_tuple)
    self.listen_to_user()
    self.socket.close()


c1 = Client()
c1.execute()
