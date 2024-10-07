import time
import serial
# https://github.com/IRNAS/ppk2-api-python
from ppk2_api.ppk2_api import PPK2_API  # or PPK2_MP for multiprocessing version
import logging

# Configuration
SERIAL_PORT = 'COM36' # '/dev/ttyUSB0'  # Replace with your serial port
BAUD_RATE = 115200
PPK2_COM_PORT = 'COM34' # '/dev/ttyACM0'  # Replace with your PPK2 communication port
START_VOLTAGE = 3.6  # Start voltage in volts
END_VOLTAGE = 2.6  # End voltage in volts
STEP_VOLTAGE = 0.1  # Step increase in volts
CYCLE_RETRIES = 5  # Number of retries per voltage step
ATTEMPT_TIMEOUT = 20

# Configure logging
logging.basicConfig(handlers=[logging.FileHandler('voltage_test.log', 'w', 'utf-8',
                                                    delay=True), logging.StreamHandler()],
                      level=logging.DEBUG,
                      format='%(asctime)s - %(levelname)s - %(message)s')
logging.info('Starting voltage cycle test')

# Initialize PPK2
logging.info('Initializing PPK2')
ppk = PPK2_API(PPK2_COM_PORT)  # or PPK2_MP for multiprocessing
logging.info(f"ppk2 get_modifiers: {ppk.get_modifiers()}")
ppk.use_source_meter()
ppk.set_source_voltage(int(START_VOLTAGE * 1000))
ppk.start_measuring()

# Initialize serial connection
def initialize_serial_connection(timeout=5):
    logging.info(f'Initializing serial connection to DUT {SERIAL_PORT} at {BAUD_RATE} baud')
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            logging.debug('Attempting to initialize serial connection')
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=10)
            logging.info(f'Serial connection established {SERIAL_PORT} at {BAUD_RATE} baud')
            return ser
        except serial.SerialException as e:
            logging.debug(f'Serial connection failed: {e}, retrying...')
            time.sleep(0.1)
    
    return None


ser = None
try:
    ser = initialize_serial_connection(3)
except Exception as e:
    logging.debug(f'Failed to establish serial connection: {e}')


def check_boot_success():
    global ATTEMPT_TIMEOUT, ser
    try:
        ser.reset_input_buffer()
    except Exception as e:
        logging.error(f"Failed to reset serial input buffer: {e}")
        # ser = initialize_serial_connection()
    boot_success = False
    secrets_found = False

    start_time = time.time()
    while time.time() - start_time < ATTEMPT_TIMEOUT:
        try:
            if ser is not None and ser.in_waiting > 0:
                line = ser.readline().decode('utf-8').strip()
                logging.info(f"Serial output: {line}")
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
            elif ser is None:
                time.sleep(0.1)
                ser = initialize_serial_connection()
        except serial.SerialException as e:
            logging.debug(f"Serial read error: {e}, attempting to reconnect")
            if ser is not none and hasattr(ser,"close"):
                ser.close()
            ser = initialize_serial_connection()
    return boot_success, secrets_found

try:
    if START_VOLTAGE < END_VOLTAGE:
        new_start = END_VOLTAGE
        END_VOLTAGE = START_VOLTAGE
        START_VOLTAGE = new_start

    voltage = START_VOLTAGE
    while voltage >= END_VOLTAGE:
        logging.info(f"Testing voltage: {voltage:.2f}V")
        print(f"Testing voltage: {voltage:.2f}V")
        ppk.set_source_voltage(int(voltage * 1000))  # Update voltage in mV

        for cycle in range(CYCLE_RETRIES):
            logging.info(f"Cycle {cycle + 1} at {voltage:.2f}V")
            print(f"Cycle {cycle + 1} at {voltage:.2f}V")
            ppk.toggle_DUT_power("OFF")  # Power off
            logging.debug("Power off")
            time.sleep(0.75)  # Minimal wait to allow power to settle
            ppk.toggle_DUT_power("ON")  # Power on
            logging.debug("Power on")

            # Start logging power measurements during boot
            ppk.start_measuring()

            # Attempt to reconnect immediately after power on
            ser = initialize_serial_connection()

            success, secrets_found = check_boot_success()

            # Fetch power measurements after boot check
            read_data = ppk.get_data()
            if read_data != b'':
                samples = ppk.get_samples(read_data)
                with open(f'power_data_{voltage:.2f}V_cycle_{cycle + 1}.csv', 'w') as f:
                    f.write('Timestamp,Voltage,Current\n')
                    timestamp = time.time()  # Using current timestamp for logging
                    for current in samples:
                        f.write(f"{timestamp},{voltage},{current}\n")

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
    ppk.stop_measuring()
    ppk.toggle_DUT_power("OFF")  # Power on
    if ser:
        ser.close()
