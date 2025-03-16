import time
import signal
import sys
import json
import threading
from camera import Camera
from tcp_server import TCPServer
from motor import MotorController

class LaneFollowingCar:
    def __init__(self):
        """Initialize the lane following car system."""
        # Initialize components
        self.camera = Camera()
        self.tcp_server = TCPServer()
        self.motor_controller = MotorController()
        
        # Command parser for handling client commands
        self.commands = {
            "MOTOR": self.handle_motor_command,
            "STOP": self.handle_stop_command,
            "STREAM": self.handle_stream_command,
            "STATUS": self.handle_status_command
        }
        
        # Status flags
        self.running = False
        self.streaming = False
        self.video_thread = None
        self.command_thread = None
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
    def start(self):
        """Start the lane following car system."""
        print("Starting lane following car system...")
        self.running = True
        
        # Start TCP server
        self.tcp_server.start_server()
        
        # Initialize camera
        self.camera.initialize()
        
        # Start command processing thread
        self.command_thread = threading.Thread(target=self.process_commands)
        self.command_thread.daemon = True
        self.command_thread.start()
        
        print("System started and ready for commands")
        
    def process_commands(self):
        """Process commands from clients."""
        while self.running:
            # Get command queue from TCP server
            queue = self.tcp_server.get_command_queue()
            
            # Process any received commands
            while not queue.empty():
                client_address, command_text = queue.get()
                self.parse_and_execute_command(client_address, command_text)
                
            # Short sleep to prevent CPU hogging
            time.sleep(0.01)
            
    def parse_and_execute_command(self, client_address, command_text):
        """Parse and execute a command from a client."""
        try:
            # Basic command parsing - can be enhanced based on your protocol
            parts = command_text.strip().split('#')
            if not parts:
                return
                
            command = parts[0].upper()
            args = parts[1:] if len(parts) > 1 else []
            
            print(f"Received command: {command}, args: {args}")
            
            # Execute command if it exists in command handlers
            if command in self.commands:
                response = self.commands[command](args)
                # Send response back to client
                if response:
                    self.tcp_server.send_command_response(client_address, response)
            else:
                print(f"Unknown command: {command}")
                self.tcp_server.send_command_response(client_address, f"ERROR#Unknown command: {command}")
                
        except Exception as e:
            print(f"Error processing command: {e}")
            self.tcp_server.send_command_response(client_address, f"ERROR#{str(e)}")
            
    def handle_motor_command(self, args):
        """Handle motor control command."""
        try:
            if len(args) != 4:
                return "ERROR#Invalid motor command format. Expected 4 speed values."
                
            speeds = [int(speed) for speed in args]
            self.motor_controller.set_motor_speeds(speeds[0], speeds[1], speeds[2], speeds[3])
            return "OK#MOTOR"
        except Exception as e:
            return f"ERROR#{str(e)}"
            
    def handle_stop_command(self, args):
        """Handle stop command."""
        self.motor_controller.stop()
        return "OK#STOP"
        
    def handle_stream_command(self, args):
        """Handle video streaming command."""
        if not args:
            return "ERROR#Missing streaming command (START/STOP)"
            
        action = args[0].upper()
        
        if action == "START":
            if not self.streaming:
                self.start_video_streaming()
                return "OK#STREAM#STARTED"
            else:
                return "OK#STREAM#ALREADY_RUNNING"
        elif action == "STOP":
            if self.streaming:
                self.stop_video_streaming()
                return "OK#STREAM#STOPPED"
            else:
                return "OK#STREAM#NOT_RUNNING"
        else:
            return f"ERROR#Unknown streaming command: {action}"
            
    def handle_status_command(self, args):
        """Handle status request command."""
        status = {
            "running": self.running,
            "streaming": self.streaming,
            "video_clients": self.tcp_server.has_video_clients(),
            "command_clients": self.tcp_server.has_command_clients()
        }
        return f"STATUS#{json.dumps(status)}"
        
    def start_video_streaming(self):
        """Start video streaming."""
        if self.streaming:
            return
            
        self.streaming = True
        self.camera.start_streaming()
        
        # Start video streaming thread
        self.video_thread = threading.Thread(target=self.stream_video_frames)
        self.video_thread.daemon = True
        self.video_thread.start()
        
        print("Video streaming started")
        
    def stop_video_streaming(self):
        """Stop video streaming."""
        if not self.streaming:
            return
            
        self.streaming = False
        
        # Wait for video thread to finish
        if self.video_thread:
            self.video_thread.join(timeout=2.0)
            self.video_thread = None
            
        self.camera.stop_streaming()
        print("Video streaming stopped")
        
    def stream_video_frames(self):
        """Stream video frames to connected clients."""
        while self.streaming and self.running:
            # Check if there are any video clients
            if not self.tcp_server.has_video_clients():
                time.sleep(0.1)
                continue
                
            # Get a frame from the camera
            frame = self.camera.get_frame()
            if frame:
                # Send frame to all video clients
                self.tcp_server.send_video_data(frame)
                
            # Short sleep to control frame rate
            time.sleep(0.03)  # ~30 FPS
            
    def stop(self):
        """Stop the lane following car system."""
        print("Stopping lane following car system...")
        self.running = False
        
        # Stop video streaming
        if self.streaming:
            self.stop_video_streaming()
            
        # Stop motors
        self.motor_controller.stop()
        
        # Wait for threads to finish
        if self.command_thread:
            self.command_thread.join(timeout=2.0)
            
        # Stop TCP server
        self.tcp_server.stop_server()
        
        # Release camera resources
        self.camera.close()
        
        # Release motor controller resources
        self.motor_controller.close()
        
        print("System stopped")
        
    def signal_handler(self, sig, frame):
        """Handle termination signals."""
        print("Received termination signal, shutting down...")
        self.stop()
        sys.exit(0)

# Main entry point
if __name__ == "__main__":
    car = LaneFollowingCar()
    try:
        car.start()
        
        # Keep the main thread alive
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("Interrupted by user")
    finally:
        car.stop()