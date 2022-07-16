#!/usr/bin/env python

import datetime
import time
import json
import os
import requests
import docker
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

# Global variables

load_dotenv()

influxurl = os.getenv('INFLUXURL')
token = os.getenv('TOKEN')
org = os.getenv('ORG')
bucket = os.getenv('BUCKET')
lake = os.getenv('LAKE')
friendly_name = os.getenv('FRIENDLY_NAME')
customer_id = os.getenv('CUSTOMER_ID')
node_uuid = os.getenv('NODE_UUID')
path = os.getenv('JSON_PATH')


# DB Connections
try:
    client = InfluxDBClient(url=influxurl, token=token)
    write_api = client.write_api(write_options=SYNCHRONOUS)
    ping = client.ping()
    if ping == True:
        print("Connected to influxdb server - {}".format(influxurl))
    else:
        print("Couldn't connect")
except Exception as e:
    print("Failed to connect to influxdb with error {}".format(e))

# Docker Connection
try:
    docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
except Exception as e:
    print("Failed to connect to docker")

# Functions
def getFileList():
    filelist = os.listdir(path)
    jsonfiles = []
    for f in filelist:
        if f.endswith('.json'):
            jsonfiles.append(f)
    return jsonfiles

def parseFile(file):
    with open(file, 'r') as file:
        output = file.read()
    if type(output) is str:
        output = output.replace("\'", "\"")
        output = json.loads(output)
    file.close()
    return output

def prepareReading(friendly_name,customer_id,measurement_name,value):
    point = Point("reading")\
        .tag("friendly_name", friendly_name)\
        .tag("customer_id", customer_id)\
        .field(measurement_name, value)\
        .time(datetime.datetime.utcnow(), WritePrecision.NS)
    #insert logic for a healthcheck point
    point_dl = Point("reading")\
        .tag("friendly_name", "Data Lake")\
        .tag("customer_id", "VGT")\
        .field(measurement_name, value)\
        .time(datetime.datetime.utcnow(), WritePrecision.NS)
    return point,point_dl

# def prepareHealthReadings(friendly_name,customer_id,containers_details_health):
#     fields = ['']
    
#     for c in containers_details_health:
#         sensor_type = ''
#     point_list = []
#     point_health = Point("health_data")\
#         .tag("friendly_name", friendly_name)\
#         .tag("customer_id", customer_id)\
#         .tag("sensor_type", sensor_type)
        

def sendData(point,point_dl,containers_details_health):
    try:
        write_api.write(record=point, org=org, bucket=bucket)
        print("Wrote point")
    except Exception as e:
        print("Cannot write customer datapoint with error {}".format(e))
    
    try:
        write_api.write(record=point_dl, org=org, bucket=lake)
    except Exception as e:
        print("Cannot write lake datapoint with error {}".format(e))
    
    # Write ability to send health data to IDB

def getContainers():
    container_list = docker_client.containers.list(all)
    list = []
    for c in container_list:
        list.append(c.attrs)
    container_details = []  
    for c in list:
        cont = docker_client.containers.get(c['Id'])
        top_titles = cont.top().pop('Titles')
        top_proc = cont.top().pop('Processes')
        processes = []
        for p in top_proc:
            process = dict(zip(top_titles, p))
            processes.append(process)
        
        print(processes)
        container = {}
        image_attrs = cont.image.attrs
        container['id'] = cont.id
        container['name'] = cont.name
        container['hostname'] = c['Config']['Hostname']
        container['status'] = cont.status
        container['state'] = c['State']
        container['image_tags'] = image_attrs['RepoTags']
        container['created'] = c['Created']
        container['running_processes'] = processes
        container['networks'] = c['NetworkSettings']
        print(container)
        container_details.append(container)
    return container_details

def getHealthData(container_details):
    for c in container_details:
        cont_name = c['name']
        health_port = '8080'
        health_path = '/health'
        try:
            response = requests.get('http://{}:{}{}'.format(cont_name,health_port,health_path))
            if response.status_code == 200:
                c['health_data'] = response.json()
            else:
                print('idk')
        except Exception as e:
            print(e)
    return container_details

def publish():
    print('Reading data')
    old_measurements = {}
    while True:
        jsonfiles = getFileList()
        container_details = getContainers()
        container_details_health = getHealthData(container_details)
        print(container_details_health)
        for f in jsonfiles:
            try:
                fullpath = path + f
                output = parseFile(fullpath)
                
                for key in output:
                    if key != 'sensor_type' and key != 'local_time':
                        measurement_name = '{}-{}'.format(output['sensor_type'],key)
                        value = output[key]
                        if measurement_name in old_measurements.keys():
                            if old_measurements[measurement_name] != value:
                                print("{}: Old measurement: {} doesn't match new measurement: {}, sending!".format(measurement_name,old_measurements[measurement_name],value))
                                point,point_dl = prepareReading(friendly_name,customer_id,measurement_name, value)
                                sendData(point,point_dl,container_details_health)
                                old_measurements[measurement_name] = value
                            else:
                                print("{}: Old and new measurements matched.".format(measurement_name))
                        else:
                            point,point_dl = prepareReading(friendly_name,customer_id,measurement_name, value)
                            sendData(point,point_dl,container_details_health)
                            old_measurements[measurement_name] = value 

                
            except Exception as e:
                print("************************************************************************************")
                print("************************************************************************************")
                print("Failure... with error {}".format(e))
                print("************************************************************************************")
                print("************************************************************************************")
                pass
        
        time.sleep(1)  

    
if __name__ == "__main__":
    publish()
