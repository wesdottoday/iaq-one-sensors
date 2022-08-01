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
from flask import Flask, request
import sys

app = Flask(__name__)

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
logfile = '/mnt/shared/publisher.log'

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

def prepareReading(friendly_name,customer_id,measurement_name,measurement):
    point = Point("reading")\
        .tag("friendly_name", friendly_name)\
        .tag("customer_id", customer_id)\
        .field(measurement_name, measurement)\
        .time(datetime.datetime.utcnow(), WritePrecision.NS)
    #insert logic for a healthcheck point

    return point

# def prepareHealthReadings(friendly_name,customer_id,containers_details_health):
#     fields = ['']
    
#     for c in containers_details_health:
#         sensor_type = ''
#     point_list = []
#     point_health = Point("health_data")\
#         .tag("friendly_name", friendly_name)\
#         .tag("customer_id", customer_id)\
#         .tag("sensor_type", sensor_type)
        

def sendData(point):
    try:
        write_api.write(record=point, org=org, bucket=bucket)
        print("Wrote point")
    except Exception as e:
        print("Cannot write customer datapoint with error {}".format(e))
    
    # try:
    #     write_api.write(record=point_dl, org=org, bucket=lake)
    # except Exception as e:
    #     print("Cannot write lake datapoint with error {}".format(e))
    
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
        
        #print(processes)
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
        #print(container)
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

def publish(payload):
    while True:
        container_details = getContainers()
        try:
            for key in payload:
                if key != 'sensor_type' and key != 'local_time':
                    measurement_name = '{}-{}'.format(payload['sensor_type'],key)
                    measurement = payload[key]
                    
                    point = prepareReading(friendly_name,customer_id,measurement_name,measurement)
                    sendData(point)

            
        except Exception as e:
            print("************************************************************************************")
            print("************************************************************************************")
            print("Failure... with error {}".format(e))
            print("************************************************************************************")
            print("************************************************************************************")
            pass
        
        time.sleep(1)  

@app.route("/node/update", methods=["POST"])
def nodeUpdate():
    content_type = request.headers.get('Content-Type')
    if (content_type == 'application/json'):
        payload = request.json
        if type(payload) is str:
                payload = payload.replace("\'", "\"")
                payload = json.loads(payload)
        try:
            publish(payload)
        except Exception as e:
            print(e)
        
        return "Ack", 200
    else: 
        return 'Content-Type: {} not supported!'.format(content_type)

@app.route("/publisher/health")
def publisherHealth():
    return "healthy", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=True)
