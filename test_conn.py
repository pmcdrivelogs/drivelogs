from urllib.parse import urlparse
import socket, ssl, sys
u = urlparse("https://ynycrntzptuperennsrt.supabase.co")  # e.g. https://xyz.supabase.co
host = u.hostname
try:
    s = socket.create_connection((host, 443), timeout=10)
    ctx = ssl.create_default_context()
    ssl_sock = ctx.wrap_socket(s, server_hostname=host)
    print("Connected:", ssl_sock.version())
    ssl_sock.close()
except Exception as e:
    print("Connection failed:", e)
    sys.exit(1)