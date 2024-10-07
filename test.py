import time
from ppk2_api import PPK2_API
import logging

# Configuration
PPK2_COM_PORT = 'COM3'  # Replace with your PPK2 communication port on Windows
VOLTAGES = [0, 1500, 3000]  # Voltages in mV to cycle through
POWER_CYCLE_INTERVAL = 3  # Time in seconds for each voltage level
POWER_OFF_INTERVAL = 2  # Time in seconds to keep power off between cycles

# Configure logging
logging.basicConfig(filename='power_toggle_test.log', level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logging.info('Starting power toggle test')

# Initialize PPK2
logging.info('Initializing PPK2')

ppk = PPK2_API(PPK2_COM_PORT)
ppk.use_source_meter()

try:
    while True:
        for voltage in VOLTAGES:
            logging.info(f"Setting voltage to {voltage} mV")
            print(f"Setting voltage to {voltage} mV")
            ppk.set_source_voltage(voltage)  # Set voltage in mV
            ppk.start_measuring()  # Start supplying power
            # Hold voltage for defined interval
            time.sleep(POWER_CYCLE_INTERVAL)
            ppk.stop_measuring()  # Stop supplying power between voltage changes

            # Test if power is really off after stop_measuring
            logging.info("Testing if power is off after stop_measuring")
            print("Testing if power is off after stop_measuring")
            
            # logging.info("Turning power OFF")
            # print("Turning power OFF")
            # ppk.set_source_voltage(0)  # Set voltage to 0 to turn off power
            time.sleep(POWER_OFF_INTERVAL)  # Keep power off for defined interval

finally:
    logging.info('Test completed, ' +
                #  'disabling power and ' +
                 'closing connections')
    # ppk.set_source_voltage(0)  # Ensure power is turned off
    ppk.close()
