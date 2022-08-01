import SDL_Pi_HM3301
import time
import traceback
import pigpio
import os

mypi = pigpio.pi()

mySDA = 21
mySCL = 20

hm3301 = SDL_Pi_HM3301.SDL_Pi_HM3301(SDA=mySDA, SCL=mySCL, pi=mypi)

time.sleep(0.01)


def startPigpiod():
    result = os.system('pigpiod &')
    return result 


def getSensorData():
    try:
        while True:
            myData = hm3301.get_data()
            print ("data=",myData)
            if (hm3301.checksum() != True):
                print("Checksum Error!")

            time.sleep(3)
    except:
        print("Error")
        print(traceback.format_exc())
        hm3301.close()


if __name__ == "__main__":
    exit_code = startPigpiod()
    if exit_code == 0:
        getSensorData()
    else:
        print("pigpiod not running")