#!/usr/bin/env python

import bme680
import time
import json
from threading import Thread, local
from flask import Flask

sensor_type = 'bme680'
software_version = '0.0.1'
filename = '/shared/{}.json'.format(sensor_type)
errorlog = '/shared/{}-error.log'.format(sensor_type)

app = Flask(__name__)

# Global Vars - DO NOT TOUCH #
last_update = ''

##############################

def thread_running():
    alive = getsensordata_thread.is_alive()
    if alive == True:
        return "ok"
    elif alive == False:
        return "failed"
    else:
        return "unknown"

def health_data():
    thread_status = thread_running()
    return {"sensor_type": sensor_type, "software_version": software_version, "last_sensor_update": last_update, "sensor_process": thread_status, "last_data_update": last_update}

def localTime():
    seconds = time.time()
    result = time.localtime(seconds)
    local_time = time.strftime("%d-%m-%Y %H:%M:%S", result)
    return local_time

def updateFile(output):
    f = open(filename, 'w+')
    f.write(output)
    f.close()

def updateLog(log):
    f = open(errorlog, 'a')
    f.write(log)
    f.close()

def trackLastUpdate():
    local_time = localTime()
    last_update = local_time
    return last_update

def getSensorData(last_update):
    try:
        sensor = bme680.BME680(bme680.I2C_ADDR_PRIMARY)
    except (RuntimeError, IOError):
        sensor = bme680.BME680(bme680.I2C_ADDR_SECONDARY)
    
    sensor.set_humidity_oversample(bme680.OS_2X)
    sensor.set_pressure_oversample(bme680.OS_4X)
    sensor.set_temperature_oversample(bme680.OS_8X)
    sensor.set_filter(bme680.FILTER_SIZE_3)
    sensor.set_gas_status(bme680.ENABLE_GAS_MEAS)

    sensor.set_gas_heater_temperature(320)
    sensor.set_gas_heater_duration(150)
    sensor.select_gas_heater_profile(0)

    # Up to 10 heater profiles can be configured, each
    # with their own temperature and duration.
    # sensor.set_gas_heater_profile(200, 150, nb_profile=1)print(f"Time remaining for sensor burn-in:  {remain_time}", end='\r')
    # sensor.select_gas_heater_profile(1)

    start_time = time.time()
    curr_time = time.time()
    burn_in_time = 30 # Set to 30 for testing, 300 for prod

    burn_in_data = []
    
    try:
        print('Collecting gas resistance burn-in data for {} mins\n'.format(burn_in_time / 60))
        while curr_time - start_time < burn_in_time:
            curr_time = time.time()
            time_running = curr_time - start_time
            remain_time = burn_in_time - time_running
            remain_time = int(remain_time)
            if remain_time <= 9:
                print(f"Time remaining for sensor burn-in:  {remain_time}s", end='\r')
            else:
                print(f"Time remaining for sensor burn-in: {remain_time}s", end='\r')

            if sensor.get_sensor_data() and sensor.data.heat_stable:
                gas = sensor.data.gas_resistance
                burn_in_data.append(gas)
                #print('Gas: {} Ohms'.format(gas))
                time.sleep(1)
            gas_baseline = sum(burn_in_data[-50:]) / 50.0

            hum_baseline = 40.0

            hum_weighting = 0.25

            #print('Gas Baseline: {} Ohms, humidity baseline: {:.2f} %RH\n'.format(gas_baseline,hum_baseline))

        print('Polling sensor data, check {} for current data'.format(filename))

        output = {}
        while True:
            
            if type(output) is str:
                output = output.replace("\'", "\"")
                output = json.loads(output)

            if 'temperature_c' in output.keys():
                print(f"Sensor Type: {output['sensor_type']}", end='\n')
                print(f"Reading Time: {output['local_time']}", end='\n')
                print(f"Temperature: {output['temperature_c']} C / {output['temperature_f']} F", end='\n')
                print(f"Air Pressure: {output['pressure']} hPA", end='\n')
                print(f"Humidity: {output['humidity']} %RH", end='\n')
                print(f"Air Quality Score: {output['air_quality_score']:.2f}", end='\n')
                print(f"\n")
            else:
                print('Loading initial readings\n')
                print('\n')

            if sensor.get_sensor_data():
                
                output["sensor_type"] = sensor_type
                output["local_time"] = localTime()
                temp_c = '{:.2f}'.format(sensor.data.temperature)
                temp_f = '{:.2f}'.format(sensor.data.temperature * 1.8 + 32)
                press = '{:.2f}'.format(sensor.data.pressure)
                humid = '{:.2f}'.format(sensor.data.humidity)
                output["temperature_c"] = float(temp_c)
                output["temperature_f"] = float(temp_f)
                output["pressure"] = float(press)
                output["humidity"] = float(humid)

                if sensor.data.heat_stable:
                    gas = sensor.data.gas_resistance
                    gas_offset = gas_baseline - gas

                    hum = sensor.data.humidity
                    hum_offset = hum - hum_baseline

                    if hum_offset > 0:
                        hum_score = (100 - hum_baseline - hum_offset)
                        hum_score /= (100 - hum_baseline)
                        hum_score *= (hum_weighting * 100)
                    
                    else:
                        hum_score = (hum_baseline + hum_offset)
                        hum_score /= hum_baseline
                        hum_score *= (hum_weighting * 100)
                    
                    if gas_offset > 0:
                        gas_score = (gas / gas_baseline)
                        gas_score *= (100 - (hum_weighting * 100))

                    else:
                        gas_score = 100 - (hum_weighting * 100)

                    # Calculate air_quality_score.
                    air_quality_score = hum_score + gas_score

                    output["gas_resistance"] = float(gas)
                    output["air_quality_score"] = air_quality_score
                    output["gas_score"] = gas_score
                    output["gas_baseline"] = gas_baseline
                    output["gas_offset"] = gas_offset
                    output["hum_score"] = hum_score
                    output["hum_baseline"] = hum_baseline
                    output["hum_offset"] = hum_offset
                    output = str(output)
                    updateFile(output)
                    last_update = trackLastUpdate()
                    return last_update
                else:
                    output = str(output)
                    updateFile(output)
                    last_update = trackLastUpdate()
                    return last_update


            time.sleep(5)

    except KeyboardInterrupt:
        pass

    except Exception as e:
        updateLog(e)

@app.route("/health", methods=["GET"])
def health():
    cur_health = health_data()
    return cur_health

if __name__ == "__main__":
    getsensordata_thread = Thread(target=getSensorData, args=(last_update,))
    getsensordata_thread.start()
    
    app.run(host='0.0.0.0', port=8080, debug=True)