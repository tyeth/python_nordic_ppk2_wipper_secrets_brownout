import time
import serial
import ppk2
import logging

# Configuration
SERIAL_PORT = '/dev/ttyUSB0'  # Replace with your serial port
BAUD_RATE = 115200
PPK2_COM_PORT = '/dev/ttyACM0'  # Replace with your PPK2 communication port
START_VOLTAGE = 2.7  # Start voltage in volts
END_VOLTAGE = 3.6  # End voltage in volts
STEP_VOLTAGE = 0.01  # Step increase in volts
CYCLE_RETRIES = 4  # Number of retries per voltage step
ATTEMPT_TIMEOUT = 20

# Configure logging
logging.basicConfig(filename='voltage_test.log', level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logging.info('Starting voltage cycle test')

# Initialize PPK2
logging.info('Initializing PPK2')
ppk = ppk2.PPK2(PPK2_COM_PORT)
ppk.set_mode(ppk2.PPK2.Mode.SOURCE)
ppk.set_voltage(START_VOLTAGE)
ppk.enable_power(True)

# Initialize serial connection
def initialize_serial_connection():
    while True:
        try:
            logging.info('Attempting to initialize serial connection')
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=10)
            logging.info('Serial connection established')
            return ser
        except serial.SerialException as e:
            logging.error(f'Serial connection failed: {e}, retrying...')
            time.sleep(0.1)

ser = initialize_serial_connection()

def check_boot_success():
    nonlocal ATTEMPT_TIMEOUT
    ser.reset_input_buffer()
    boot_success = False
    secrets_found = False

    start_time = time.time()
    while time.time() - start_time < ATTEMPT_TIMEOUT:
        try:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8').strip()
                logging.debug(f"Serial output: {line}")
                if 'Connected to WiFi!' in line:
                    boot_success = True
                    secrets_found = True
                    break
                elif ('ERROR: Unable to parse secrets.json file' in line
                      or 'ERROR: Invalid IO credentials' in line or
                      'Fatal Error: Halted execution' in line or
                      'reset your board' in line
                      ):
                    boot_success = True
                    secrets_found = False
                    break
        except serial.SerialException as e:
            logging.error(f"Serial read error: {e}, attempting to reconnect")
            ser.close()
            ser = initialize_serial_connection()
    return boot_success, secrets_found

try:
    voltage = START_VOLTAGE
    while voltage <= END_VOLTAGE:
        logging.info(f"Testing voltage: {voltage:.2f}V")
        print(f"Testing voltage: {voltage:.2f}V")
        ppk.set_voltage(voltage)

        for cycle in range(CYCLE_RETRIES):
            logging.info(f"Cycle {cycle + 1} at {voltage:.2f}V")
            print(f"Cycle {cycle + 1} at {voltage:.2f}V")
            ppk.toggle_power(False)  # Power off
            logging.debug("Power off")
            time.sleep(0.75)  # Minimal wait to allow power to settle
            ppk.toggle_power(True)  # Power on
            logging.debug("Power on")

            # Start logging power measurements during boot
            ppk.start_measurement()

            # Attempt to reconnect immediately after power on
            ser = initialize_serial_connection()

            success, secrets_found = check_boot_success()

            # Stop logging power measurements after boot check
            ppk.stop_measurement()
            power_data = ppk.get_measurement_data()
            with open(f'power_data_{voltage:.2f}V_cycle_{cycle + 1}.csv', 'w') as f:
                f.write('Timestamp,Voltage,Current')
                for entry in power_data:
                    f.write(f"{entry['timestamp']},{entry['voltage']},{entry['current']}")

            if success:
                if secrets_found:
                    logging.info(f"Voltage {voltage:.2f}V: Boot successful and secrets found.")
                    print(f"Voltage {voltage:.2f}V: Boot successful and secrets found.")
                else:
                    logging.error(f"Voltage {voltage:.2f}V: Boot successful but secrets missing.")
                    print(f"Voltage {voltage:.2f}V: Boot successful but secrets missing.")
                    raise ValueError()
            else:
                logging.error(f"Voltage {voltage:.2f}V: Boot failed.")
                print(f"Voltage {voltage:.2f}V: Boot failed.")

        voltage += STEP_VOLTAGE
        time.sleep(1)

finally:
    logging.info('Test completed, disabling power and closing connections')
    ppk.enable_power(False)
    ppk.close()
    ser.close()