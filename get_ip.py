import socket
hostname = socket.gethostname()
ip_address = socket.gethostbyname(hostname)
print(f"ادخل هذا الرابط في موبايلك: http://{ip_address}:5000/store/sara-fashion")