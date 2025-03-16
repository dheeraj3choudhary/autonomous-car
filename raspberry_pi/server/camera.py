from picamera2 import Picamera2, Preview
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput
from threading import Condition
import io
import time

class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()
        return len(buf)

class Camera:
    def __init__(self, resolution=(400, 300)):
        self.resolution = resolution
        self.camera = None
        self.streaming_output = None
        self.encoder = None
        self.is_streaming = False
        
    def initialize(self):
        """Initialize the camera with the specified resolution."""
        self.camera = Picamera2()
        config = self.camera.create_video_configuration(main={"size": self.resolution})
        self.camera.configure(config)
        
    def start_preview(self):
        """Start camera preview (useful for debugging on the Pi itself)."""
        if not self.camera:
            self.initialize()
        self.camera.start_preview(Preview.QTGL)
        self.camera.start()
        
    def capture_image(self, file_path="image.jpg"):
        """Capture a single image to the specified file path."""
        if not self.camera:
            self.initialize()
            self.camera.start()
        self.camera.capture_file(file_path)
        return file_path
        
    def start_streaming(self):
        """Start video streaming for network transmission."""
        if self.is_streaming:
            return
            
        if not self.camera:
            self.initialize()
            
        self.streaming_output = StreamingOutput()
        self.encoder = JpegEncoder(q=70)  # Adjust quality (q) as needed for performance
        self.camera.start()
        self.camera.start_encoder(self.encoder, FileOutput(self.streaming_output))
        self.is_streaming = True
        print("Camera streaming started")
        
    def get_frame(self):
        """Get the latest frame from the stream."""
        if not self.is_streaming:
            return None
            
        with self.streaming_output.condition:
            self.streaming_output.condition.wait()
            return self.streaming_output.frame
            
    def stop_streaming(self):
        """Stop the video stream."""
        if not self.is_streaming:
            return
            
        if self.camera:
            self.camera.stop_encoder()
            self.is_streaming = False
        print("Camera streaming stopped")
        
    def close(self):
        """Close the camera and release resources."""
        if self.is_streaming:
            self.stop_streaming()
        if self.camera:
            self.camera.close()
            self.camera = None
        print("Camera resources released")

# Example usage
if __name__ == "__main__":
    camera = Camera()
    try:
        # Test image capture
        print("Capturing test image...")
        camera.capture_image("test_image.jpg")
        print("Image captured")
        
        # Test streaming
        print("Starting video stream...")
        camera.start_streaming()
        
        # Grab a few frames to test
        for i in range(10):
            frame = camera.get_frame()
            print(f"Frame {i+1} received: {len(frame)} bytes")
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        print("Interrupted by user")
    finally:
        camera.close()
        print("Test complete")