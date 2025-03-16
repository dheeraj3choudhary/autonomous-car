import time

class MotorController:
    def __init__(self):
        """Initialize the motor controller using PCA9685.
        
        This class reuses parts of the existing Freenove code for motor control
        but with a simplified interface for our project.
        """
        try:
            from pca9685 import PCA9685
            self.pwm = PCA9685(0x40)  # Initialize using I2C address 0x40
            self.pwm.set_pwm_freq(50)  # Set PWM frequency to 50Hz
            self.initialized = True
        except ImportError:
            print("Warning: PCA9685 module not found. Motors will not function.")
            self.initialized = False
        except Exception as e:
            print(f"Error initializing motor controller: {e}")
            self.initialized = False
            
    def _duty_range(self, duty):
        """Limit duty cycle value to valid range."""
        if duty > 4095:
            return 4095
        elif duty < -4095:
            return -4095
        return duty
            
    def _set_motor(self, motor_index, duty):
        """Set the speed of a single motor.
        
        Args:
            motor_index: Motor index (0-3)
            duty: Duty cycle (-4095 to 4095), negative for reverse
        """
        if not self.initialized:
            return
            
        duty = self._duty_range(duty)
        
        # Motor pin mapping based on Freenove's design
        if motor_index == 0:  # Left upper wheel
            if duty > 0:
                self.pwm.set_motor_pwm(0, 0)
                self.pwm.set_motor_pwm(1, duty)
            elif duty < 0:
                self.pwm.set_motor_pwm(1, 0)
                self.pwm.set_motor_pwm(0, abs(duty))
            else:
                self.pwm.set_motor_pwm(0, 4095)
                self.pwm.set_motor_pwm(1, 4095)
        elif motor_index == 1:  # Left lower wheel
            if duty > 0:
                self.pwm.set_motor_pwm(3, 0)
                self.pwm.set_motor_pwm(2, duty)
            elif duty < 0:
                self.pwm.set_motor_pwm(2, 0)
                self.pwm.set_motor_pwm(3, abs(duty))
            else:
                self.pwm.set_motor_pwm(2, 4095)
                self.pwm.set_motor_pwm(3, 4095)
        elif motor_index == 2:  # Right upper wheel
            if duty > 0:
                self.pwm.set_motor_pwm(6, 0)
                self.pwm.set_motor_pwm(7, duty)
            elif duty < 0:
                self.pwm.set_motor_pwm(7, 0)
                self.pwm.set_motor_pwm(6, abs(duty))
            else:
                self.pwm.set_motor_pwm(6, 4095)
                self.pwm.set_motor_pwm(7, 4095)
        elif motor_index == 3:  # Right lower wheel
            if duty > 0:
                self.pwm.set_motor_pwm(4, 0)
                self.pwm.set_motor_pwm(5, duty)
            elif duty < 0:
                self.pwm.set_motor_pwm(5, 0)
                self.pwm.set_motor_pwm(4, abs(duty))
            else:
                self.pwm.set_motor_pwm(4, 4095)
                self.pwm.set_motor_pwm(5, 4095)
                
    def set_motor_speeds(self, left_upper, left_lower, right_upper, right_lower):
        """Set speeds for all four motors.
        
        Args:
            left_upper: Left upper motor speed (-4095 to 4095)
            left_lower: Left lower motor speed (-4095 to 4095)
            right_upper: Right upper motor speed (-4095 to 4095)
            right_lower: Right lower motor speed (-4095 to 4095)
            
        Positive values move forward, negative values move backward.
        """
        if not self.initialized:
            return
            
        # Apply duty cycle limits
        left_upper = self._duty_range(left_upper)
        left_lower = self._duty_range(left_lower)
        right_upper = self._duty_range(right_upper)
        right_lower = self._duty_range(right_lower)
        
        # Set individual motor speeds
        self._set_motor(0, left_upper)
        self._set_motor(1, left_lower)
        self._set_motor(2, right_upper)
        self._set_motor(3, right_lower)
        
    def move_forward(self, speed=2000):
        """Move the car forward at the specified speed."""
        self.set_motor_speeds(speed, speed, speed, speed)
        
    def move_backward(self, speed=2000):
        """Move the car backward at the specified speed."""
        self.set_motor_speeds(-speed, -speed, -speed, -speed)
        
    def turn_left(self, speed=2000):
        """Turn the car left at the specified speed."""
        self.set_motor_speeds(-speed, -speed, speed, speed)
        
    def turn_right(self, speed=2000):
        """Turn the car right at the specified speed."""
        self.set_motor_speeds(speed, speed, -speed, -speed)
        
    def stop(self):
        """Stop all motors."""
        self.set_motor_speeds(0, 0, 0, 0)
        
    def close(self):
        """Release resources."""
        if self.initialized:
            self.stop()
            try:
                self.pwm.close()
            except:
                pass

# Example usage
if __name__ == "__main__":
    motor = MotorController()
    try:
        print("Testing motors. Motors will move for 2 seconds in each direction.")
        
        print("Moving forward...")
        motor.move_forward()
        time.sleep(2)
        
        print("Moving backward...")
        motor.move_backward()
        time.sleep(2)
        
        print("Turning left...")
        motor.turn_left()
        time.sleep(2)
        
        print("Turning right...")
        motor.turn_right()
        time.sleep(2)
        
        print("Stopping...")
        motor.stop()
        
    except KeyboardInterrupt:
        print("Interrupted by user")
    finally:
        motor.close()
        print("Test complete")