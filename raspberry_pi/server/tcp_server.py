import socket
import threading
import queue
import struct
import time
import fcntl
import signal
import sys

class TCPServer:
    def __init__(self):
        """Initialize the TCP server."""
        self.command_socket = None
        self.video_socket = None
        self.command_clients = {}
        self.video_clients = {}
        self.message_queue = queue.Queue()
        self.running = False
        self.command_thread = None
        self.video_thread = None
        self.max_clients = 1
        
    def get_ip_address(self, interface='wlan0'):
        """Get the IP address of the specified network interface."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            ip_address = socket.inet_ntoa(fcntl.ioctl(
                s.fileno(),
                0x8915,  # SIOCGIFADDR
                struct.pack('256s', interface.encode('utf-8')[:15])
            )[20:24])
            return ip_address
        except Exception as e:
            print(f"Error getting IP address: {e}")
            return "127.0.0.1"  # Default to localhost if error
            
    def start_server(self, command_port=5000, video_port=8000):
        """Start both command and video TCP servers."""
        self.running = True
        
        # Setup signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        # Get the IP address
        ip_address = self.get_ip_address()
        print(f"Server IP address: {ip_address}")
        
        # Start command server
        self.command_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.command_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.command_socket.bind((ip_address, command_port))
        self.command_socket.listen(1)
        print(f"Command server started on {ip_address}:{command_port}")
        
        # Start video server
        self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.video_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.video_socket.bind((ip_address, video_port))
        self.video_socket.listen(1)
        print(f"Video server started on {ip_address}:{video_port}")
        
        # Start client handling threads
        self.command_thread = threading.Thread(target=self.handle_command_clients)
        self.command_thread.daemon = True
        self.command_thread.start()
        
        self.video_thread = threading.Thread(target=self.handle_video_clients)
        self.video_thread.daemon = True
        self.video_thread.start()
        
    def handle_command_clients(self):
        """Accept and handle command client connections."""
        self.command_socket.settimeout(1)  # 1 second timeout for accept()
        
        while self.running:
            try:
                # Accept new client connections
                client_socket, client_address = self.command_socket.accept()
                if len(self.command_clients) >= self.max_clients:
                    # If max clients reached, reject new connection
                    client_socket.close()
                    print(f"Rejected command connection from {client_address}")
                    continue
                    
                print(f"New command connection from {client_address}")
                self.command_clients[client_socket] = client_address
                
                # Start client thread
                client_thread = threading.Thread(
                    target=self.handle_client_commands,
                    args=(client_socket, client_address)
                )
                client_thread.daemon = True
                client_thread.start()
                
            except socket.timeout:
                # Timeout on accept, just continue
                continue
            except Exception as e:
                print(f"Error accepting command connection: {e}")
                time.sleep(1)
                
    def handle_video_clients(self):
        """Accept and handle video client connections."""
        self.video_socket.settimeout(1)  # 1 second timeout for accept()
        
        while self.running:
            try:
                # Accept new client connections
                client_socket, client_address = self.video_socket.accept()
                if len(self.video_clients) >= self.max_clients:
                    # If max clients reached, reject new connection
                    client_socket.close()
                    print(f"Rejected video connection from {client_address}")
                    continue
                    
                print(f"New video connection from {client_address}")
                self.video_clients[client_socket] = client_address
                
                # No need for separate thread for video clients as we just send data to them
                
            except socket.timeout:
                # Timeout on accept, just continue
                continue
            except Exception as e:
                print(f"Error accepting video connection: {e}")
                time.sleep(1)
                
    def handle_client_commands(self, client_socket, client_address):
        """Handle commands from a connected client."""
        try:
            client_socket.settimeout(60)  # 60 second timeout
            
            while self.running:
                # Receive data
                data = client_socket.recv(1024)
                if not data:
                    # Connection closed by client
                    break
                    
                # Decode and process command
                command = data.decode('utf-8')
                print(f"Received from {client_address}: {command}")
                
                # Add to command queue
                self.message_queue.put((client_address, command))
                
        except socket.timeout:
            print(f"Timeout on connection from {client_address}")
        except Exception as e:
            print(f"Error handling client {client_address}: {e}")
        finally:
            # Clean up client connection
            if client_socket in self.command_clients:
                del self.command_clients[client_socket]
            client_socket.close()
            print(f"Command connection from {client_address} closed")
            
    def send_video_data(self, frame_data):
        """Send video frame data to all connected video clients."""
        if not self.video_clients:
            return False
            
        # Calculate frame size
        size = len(frame_data)
        size_data = struct.pack('<L', size)
        
        # List of clients to be removed (if send fails)
        clients_to_remove = []
        
        for client_socket, client_address in self.video_clients.items():
            try:
                # Send frame size followed by frame data
                client_socket.sendall(size_data)
                client_socket.sendall(frame_data)
            except Exception as e:
                print(f"Error sending video to {client_address}: {e}")
                clients_to_remove.append(client_socket)
                
        # Remove failed clients
        for client_socket in clients_to_remove:
            client_address = self.video_clients[client_socket]
            del self.video_clients[client_socket]
            client_socket.close()
            print(f"Video connection from {client_address} closed")
            
        return True
        
    def send_command_response(self, client_address, response):
        """Send response to a specific command client."""
        for client_socket, addr in self.command_clients.items():
            if addr == client_address:
                try:
                    client_socket.sendall(response.encode('utf-8'))
                    return True
                except Exception as e:
                    print(f"Error sending response to {client_address}: {e}")
                    # Will be cleaned up by the client handler thread
                    return False
        return False
        
    def broadcast_command(self, message):
        """Send a command to all connected command clients."""
        if not self.command_clients:
            return False
            
        clients_to_remove = []
        
        for client_socket, client_address in self.command_clients.items():
            try:
                client_socket.sendall(message.encode('utf-8'))
            except Exception as e:
                print(f"Error broadcasting to {client_address}: {e}")
                clients_to_remove.append(client_socket)
                
        # Remove failed clients
        for client_socket in clients_to_remove:
            # Will be cleaned up by the client handler thread
            pass
            
        return True
        
    def has_video_clients(self):
        """Check if there are any connected video clients."""
        return len(self.video_clients) > 0
        
    def has_command_clients(self):
        """Check if there are any connected command clients."""
        return len(self.command_clients) > 0
        
    def get_command_queue(self):
        """Get the command message queue."""
        return self.message_queue
        
    def stop_server(self):
        """Stop the server and close all connections."""
        self.running = False
        
        # Close all client connections
        for client_socket in list(self.command_clients.keys()):
            client_socket.close()
        self.command_clients.clear()
        
        for client_socket in list(self.video_clients.keys()):
            client_socket.close()
        self.video_clients.clear()
        
        # Close server sockets
        if self.command_socket:
            self.command_socket.close()
        if self.video_socket:
            self.video_socket.close()
            
        print("TCP server stopped")
        
    def signal_handler(self, sig, frame):
        """Handle termination signals."""
        print("Received termination signal, shutting down...")
        self.stop_server()
        sys.exit(0)

# Example usage
if __name__ == "__main__":
    server = TCPServer()
    try:
        server.start_server()
        print("Server running. Press Ctrl+C to stop.")
        
        # Keep the main thread alive
        while True:
            time.sleep(1)
            
            # Process any received commands
            queue = server.get_command_queue()
            while not queue.empty():
                client_address, command = queue.get()
                print(f"Processing command from {client_address}: {command}")
                
                # Example response
                response = f"Received: {command}"
                server.send_command_response(client_address, response)
                
    except KeyboardInterrupt:
        print("Interrupted by user")
    finally:
        server.stop_server()