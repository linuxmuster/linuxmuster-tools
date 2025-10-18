import socket

SERVER_HOSTNAME  = socket.gethostname()

server_ip = socket.gethostbyname_ex(SERVER_HOSTNAME)[2]

try:
    SERVER_IP =  [ip for ip in server_ip if not ip.startswith("127.")][0]
except IndexError:
    SERVER_IP = "Can not determine server's ip"