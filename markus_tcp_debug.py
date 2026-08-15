#!/usr/bin/env python3
"""Debug TCP binding issues"""
import socket
import time

print("=== TCP Binding Debug ===")

# Test 1: Check if port is available
test_port = 9151
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", test_port))
    sock.listen(1)
    print(f"✓ Successfully bound TCP socket to port {test_port}")
    sock.close()
except Exception as e:
    print(f"✗ Failed to bind: {e}")

# Test 2: Create server and client
try:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("", 19215))
    server.listen(1)
    server.settimeout(2.0)
    print("✓ Server socket bound to port 19215")
    
    def server_thread():
        try:
            conn, addr = server.accept()
            data = conn.recv(1024)
            conn.sendall(b"OK")
            conn.close()
            print("✓ Server received and responded")
        except socket.timeout:
            print("✗ Server timeout waiting for connection")
        except Exception as e:
            print(f"✗ Server error: {e}")
    
    import threading
    t = threading.Thread(target=server_thread, daemon=True)
    t.start()
    
    time.sleep(0.1)
    
    # Client
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.settimeout(2.0)
    client.connect(("127.0.0.1", 19215))
    client.sendall(b"Hello")
    response = client.recv(1024)
    client.close()
    print(f"✓ Client received: {response}")
    
    server.close()
    
except Exception as e:
    print(f"✗ Connection test failed: {e}")

print("\nDone")