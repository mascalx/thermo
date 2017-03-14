#!/usr/bin/python -d
# -*- coding: utf-8 -*-
# **********************************************************
# Thermostat for Raspberry Pi
# with 2.2" lcd display and 4 hw buttons
# **********************************************************
# Copyright 2017 Mascal
# Version 0.6
# **********************************************************

# **********************************************************
# Imports
# **********************************************************

import os
import sys
import thread
import urllib2
import json
import time
import datetime
import locale
import logging
import LM75
import socket
from PIL import Image, ImageFont, ImageDraw
import Adafruit_ILI9341 as TFT
import Adafruit_GPIO as GPIO
import Adafruit_GPIO.SPI as SPI
from flask import Flask, render_template, request, Response
from functools import wraps   # required for authentication functions
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)

# **********************************************************
# User definitions
# **********************************************************

WUCODE='xxxxxxxxxxxxxxx' # Weather Underground code license to access their API
WUADDRESS='/geolookup/conditions/lang:IT/q/Italy/Ravenna.json' # Address to retrieve weather conditions from WU
USER='username' # User for web access
PASSW='password' # Password for web access
WPORT=1111 # Port for web access

# **********************************************************
# Definitions
# **********************************************************

version="0.6"
BLACK=(0,0,0)
WHITE=(255,255,255)
deg=u"\N{DEGREE SIGN}"
FIXED_CAL=-10.0 # Fixed internal calibration
RELAY_WAIT=30 # Seconds to wait before acting again on the relay
DISPLAY_ON=10 # Seconds for display backlight
temp_set=20.0 # Target temperature
temp=20.0 # Actual temperature
current_hour=time.localtime().tm_hour # Actual hour of the day
T_CAL=0.0 # Calibration value added to the value read from sensor
ivac=datetime.date.fromtimestamp(time.time()) # start date for holidays
fvac=datetime.date.fromtimestamp(time.time()) # end date for holidays
tvac=15.0 # Temp set for holidays
MAN=0 # Mode manual
AUTO=1 # Mode automatic
SEMI=2 # Mode semi-automatic (only current hour is manual then auto again)
mode=AUTO # Actual thermostat mode
heating=False # Heating system status
on_menu=False # If user is into configuration mode, some update should not be performed
menu=0 # Current menu (0 = not in menu)
wait_action=RELAY_WAIT # Counter for two subsequent actions on the relay
light=DISPLAY_ON # Counter for turning off the lcd backlight (seconds)
temp_list=[20.0,20.0,20.0,20.0,20.0,20.0,20.0,20.0,20.0,20.0,20.0,20.0,20.0,20.0,20.0,20.0,20.0,20.0,20.0,20.0,20.0,20.0,20.0,20.0] # Hourly (0-23) temperature sets for automatic mode
weather={'temp':'--', 'hum':'--', 'wspd':'--', 'wdir':'N', 'icon':'sunny'}
sensor=sensor = LM75.LM75()
DC = 25        # TFT parameter
RST = 23       # TFT parameter
SPI_PORT = 0   # TFT parameter
SPI_DEVICE = 0 # TFT parameter
backlight = 18 # LCD backlight
GPIO.setup(backlight, GPIO.OUT)
B1 = 17 # Button 1 ******Verificare
GPIO.setup(B1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
B2 = 22 # Button 2 ******Verificare
GPIO.setup(B2, GPIO.IN, pull_up_down=GPIO.PUD_UP)
B3 = 23 # Button 3 ******Verificare
GPIO.setup(B3, GPIO.IN, pull_up_down=GPIO.PUD_UP)
B4 = 27 # Button 4 ******Verificare
GPIO.setup(B4, GPIO.IN, pull_up_down=GPIO.PUD_UP)
RELAY = 24 # Relay control
GPIO.setup(RELAY, GPIO.OUT)
GPIO.output(RELAY,1) # initial status = heating off (relay not active)
tlist=[] # Array for temp mean
max_t_num = 10 # Numbero of readings for mean calculation

# Creates screen image and TFT instance
screen = Image.new("RGB", (320, 240), "white")
disp = TFT.ILI9341(DC, rst=RST, spi=SPI.SpiDev(SPI_PORT, SPI_DEVICE, max_speed_hz=64000000))
disp.begin()

# **********************************************************
# Thermostat functions
# **********************************************************

#** Returns if the Raspberry is connected to the LAN
def Connected():
    ipaddress=socket.gethostbyname(socket.gethostname())
    if ipaddress=="127.0.0.1":
        return False
    else:
        return True

#** Save current configuration
def SaveConfiguration():
    global temp_set
    global T_CAL
    global temp_list
    try:
        with open("thermo.config", 'w') as configurazione:
            configurazione.write("%0.1f\n" % temp_set)
            configurazione.write("%0.1f\n" % T_CAL)
            configurazione.write("%0.1f\n" % tvac)
            configurazione.write("%s\n" % ivac.isoformat())
            configurazione.write("%s\n" % fvac.isoformat())
            for t in temp_list:
                configurazione.write("%0.1f\n" % t)
            configurazione.close()
    except:
        pass

#** Load saved configuration
def LoadConfiguration():
    global temp_set
    global T_CAL
    global temp_list
    global tvac
    global ivac
    global fvac
    try:
        with open("thermo.config", 'r') as configurazione:
            content = configurazione.read().splitlines()
            temp_set = float(content[0])
            T_CAL = float(content[1])
            tvac = float(content[2])
            ivac = datetime.datetime.strptime(content[3],"%Y-%m-%d").date()
            fvac = datetime.datetime.strptime(content[4],"%Y-%m-%d").date()
            for i in range(0,23):
                temp_list[i] = float(content[i+5])
            configurazione.close()
    except:
        pass
        
#** Draws the image to the display
def TFT_Display():
    disp.display(screen.rotate(270))
    
#** Draws the main screen schema
def ClearScreen(display): 
    draw = ImageDraw.Draw(display)
    draw.rectangle([(0,0),display.size], fill = WHITE) # Clear the display
    draw.line([(0, 52), (319, 52)], fill = BLACK, width=2)
    #draw.line([(0, 53), (319, 53)], fill = BLACK)
    draw.line([(0, 200), (319, 200)], fill = BLACK, width=2)
    #draw.line([(0, 201), (319, 201)], fill = BLACK)
    draw.line([(79, 200), (79, 239)], fill = BLACK)
    draw.line([(159, 200), (159, 239)], fill = BLACK)
    draw.line([(239, 200), (239, 239)], fill = BLACK)
    del draw

#** Write text left-aligned
def Write(display,style,text,pos,color): 
    draw = ImageDraw.Draw(display)
    draw.text(pos,text,font=style,fill=color)
    del draw

#** Write text centered
def WriteCenter(display,style,text,pos,color): 
    draw = ImageDraw.Draw(display)
    width=draw.textsize(text,font=style)[0] # Width of text
    X, Y = pos
    draw.text(((X-width/2),Y),text,font=style,fill=color)
    del draw

#** Write text right-aligned
def WriteRight(display,style,text,pos,color): 
    draw = ImageDraw.Draw(display)
    width=draw.textsize(text,font=style)[0] # Width of text
    X, Y = pos
    draw.text((X-width,Y),text,font=style,fill=color)
    del draw

#** Show current weather conditions
def Conditions(display,icon,temp,hum,wspd,wdir): 
    draw = ImageDraw.Draw(display)
    draw.rectangle([(0,0),(320,51)], fill = WHITE) # Clear the conditions bar
    icon = Image.open("static/icons/"+icon+".gif").convert('RGBA')
    display.paste(icon,(0,2),icon)
    Write(display,font_small,'%s%s' % (temp,deg),(56,18),BLACK)
    WriteCenter(display,font_small,hum,(160,18),BLACK)
    WriteRight(display,font_small,'%skm/h' % wspd,(279,18),BLACK)
    icon = Image.open("static/icons/"+wdir+".gif").convert('RGBA')
    display.paste(icon,(285,12),icon)
    del icon
    del draw
    TFT_Display()

#** Draw buttons labels
def Buttons(display,b1,b2,b3,b4): 
    draw = ImageDraw.Draw(display)
    draw.rectangle([(0,202),(78,241)], fill = WHITE) # Clear the buttons bar
    draw.rectangle([(80,202),(158,241)], fill = WHITE)
    draw.rectangle([(160,202),(238,241)], fill = WHITE)
    draw.rectangle([(240,202),(318,241)], fill = WHITE)
    WriteCenter(display,font_small,b1,(40,213),BLACK)
    WriteCenter(display,font_small,b2,(120,213),BLACK)
    WriteCenter(display,font_small,b3,(200,213),BLACK)
    WriteCenter(display,font_small,b4,(280,213),BLACK)
    del draw
    TFT_Display()

#** Show current thermostat status
def Status(display,temp,tset,mode,heating): 
    draw = ImageDraw.Draw(display)
    draw.rectangle([(0,54),(320,199)], fill = WHITE) # Clear the status bar
    if (mode==AUTO):
        Write(display,font_small,"AUTO",(4,61),BLACK)
    if (mode==MAN):
        Write(display,font_small,"MANUALE",(4,61),BLACK)
    if (mode==SEMI):
        Write(display,font_small,"AUTO(M)",(4,61),BLACK)
    if (heating):
        icon = Image.open("static/icons/flame.gif").convert('RGBA')
        display.paste(icon,(151,58),icon)
        del icon
    d=datetime.date.fromtimestamp(time.time())
    if (d>=ivac) and (d<=ivac):
        icon = Image.open("static/holiday.png").convert('RGBA')
        display.paste(icon,(8,95),icon)
        del icon
    locale.setlocale(locale.LC_ALL, "")
    Write(display,font_small,time.strftime("%d %B %Y"),(5,179),BLACK)
    WriteRight(display,font_small,time.strftime("%H:%M"),(314,179),BLACK)
    locale.setlocale(locale.LC_ALL, locale.getdefaultlocale())
    WriteCenter(display,font_big,' %s%s' % (temp,deg),(162,105),BLACK)
    WriteRight(display,font_medium,'%s%s' % (tset,deg),(317,58),BLACK)
    del draw
    TFT_Display()

#** Set lcd backlight value
def LCD_Light(val): 
    global backlight
    if (val==1):
        GPIO.output(backlight, GPIO.HIGH)
    else:
        GPIO.output(backlight, GPIO.LOW)

#** Get data from temp sensor or last temp if got an error
def GetTemperature(): 
    global sensor
    global temp
    global FIXED_CAL
    global T_CAL
    global tlist
    global max_t_num
    try:
        if (len(tlist)==max_t_num): # Remove oldest value if needed
            tlist.pop(0)
        tlist.append(sensor.getTemp()) # Add new temperature value
        t=sum(tlist, 0.0) / len(tlist) # Calculates mean value
    except:
        t=temp # In case of error just use latest value
    return t+FIXED_CAL+T_CAL

#** Get button pressed
def GetButton(): 
    global B1
    global B2
    global B3
    global B4
    btn = 0
    if GPIO.input(B1)==0: btn = 1
    if GPIO.input(B2)==0: btn = 2
    if GPIO.input(B3)==0: btn = 3
    if GPIO.input(B4)==0: btn = 4
    return btn
    
#** Show main menu
def ShowMenu1(display): 
    draw = ImageDraw.Draw(display)
    draw.rectangle([(0,54),(320,199)], fill = WHITE) # Clear the status bar
    Write(display,font_medium,"1.Programma orario",(15,70),BLACK)
    Write(display,font_medium,"2.Vacanza",(15,100),BLACK)
    Write(display,font_medium,"3.Opzioni",(15,130),BLACK)
    del draw
    TFT_Display()
    
#** Act on button press and thermostat status
def ManageButton(btn): 
    global screen
    global menu
    global mode
    global AUTO
    global SEMI
    global MAN
    global mode
    global heating
    global temp_set
    global temp
    global light
    global on_menu
    global DISPLAY_ON
    if (menu==0)and(light>0): # Normal display
        if (btn==1): # MENU
            on_menu=True
            menu=1
            ShowMenu1(lcd)
            Buttons(screen,"1","2","3","Esci")
        elif (btn==2): # T-
            temp_set=temp_set-0.5
            if (mode==AUTO):
                mode=SEMI
            CheckTemp()
        elif (btn==3): # T+
            temp_set=temp_set+0.5
            if (mode==AUTO):
                mode=SEMI
            CheckTemp()
        else: # A/M
            if (mode==MAN)or(mode==SEMI):
                mode=AUTO
                CheckTemp()
            else:    
                mode=MAN
    elif (menu==1): # Main menu
        if (btn==1):
            pass
        elif (btn==2):
            pass
        elif (btn==3):
            pass
        else:
            Status(screen,"%0.1f" % temp,"%0.1f" % temp_set,mode,heating)
            Buttons(screen,"Menu","T-","T+","A/M")
            on_menu=False
            menu=0
    elif (menu==2): # Program
        if (btn==1):
            pass
        elif (btn==2):
            pass
        elif (btn==3):
            pass
        else:
            pass
    elif (menu==3): # Vacation
        if (btn==1):
            pass
        elif (btn==2):
            pass
        elif (btn==3):
            pass
        else:
            pass
    elif (menu==4): # Misc options
        if (btn==1):
            pass
        elif (btn==2):
            pass
        elif (btn==3):
            pass
        else:
            pass
    else: # Temperature calibration
        if (btn==1):
            pass
        elif (btn==2):
            pass
        elif (btn==3):
            pass
        else:
            pass
    if (btn!=0): # Turn on backlight
        light=DISPLAY_ON

#** Check if it needs to turn on or off the heating
def CheckTemp(): 
    global temp
    global temp_set
    global heating
    global mode
    global current_hour
    global wait_action
    global RELAY_WAIT
    global ivac
    global fvac
    global tvac
    if (current_hour!=time.localtime().tm_hour): # Change of the hour
        current_hour=time.localtime().tm_hour
        if (mode==SEMI): # If the thermostat was in semi automatic mode, it reverts to full automatic
            mode=AUTO
    if (mode==AUTO): # If mode is automatic, gets target temp from the hourly list
        temp_set=temp_list[current_hour]
    d=datetime.date.fromtimestamp(time.time())
    if (d>=ivac) and (d<=ivac): # If inside holidays range, use related temperature and reverts to automatic
        temp=tvac
        mode=AUTO
    if (temp<temp_set)and(wait_action==0): # Turn on the heating system if possible
        heating=True
        GPIO.output(RELAY,0)
        wait_action=RELAY_WAIT
    if (temp>temp_set)and(wait_action==0): # Turn off the heating system if possible
        heating=False
        GPIO.output(RELAY,1)
        wait_action=RELAY_WAIT

# **********************************************************
# Threads section
# **********************************************************
       
#** Execute recurrent operations (data updates, counters, etc.)
def UpdateStatus(): 
    global screen
    global mode
    global heating
    global temp_set
    global temp
    global light
    global on_menu
    global weather
    global wait_action
    s=9
    w=599
    c=0
    while True:  # endless loop
        CheckTemp() # Check for relay activation
        if (light>0): # Backlight management
            light=light-1
            LCD_Light(1)
        else:
            LCD_Light(0)
            if (on_menu):
                on_menu=False
                menu=0
                s=9
        if (wait_action>0): # Relay next actions delay management
            wait_action=wait_action-1
        s=s+1
        if (s==10): # Get the actual temperature every 10 seconds
            s=0
            if (on_menu==False):
                temp=GetTemperature()
                Status(screen,"%0.1f" % temp,"%0.1f" % temp_set,mode,heating)
        c=c+1    
        if (c == 300): # Every 5 minutes (300 seconds) check lan connection. If not connected tries to restart wlan
            c=0
            if not(Connected()):
                print "NOT CONNECTED"
                os.system('sudo ifup --force wlan0');
        w=w+1
        if (w==600): # Get updated weather conditions and display it every 10 minutes
            w=0
            try:
                f = urllib2.urlopen('http://api.wunderground.com/api/'+WUCODE+'/geolookup/conditions/lang:IT/q/Italy/Ravenna.json')
                json_string = f.read()
                parsed_json = json.loads(json_string)
                try:
                    weather['temp'] = parsed_json['current_observation']['temp_c']
                except:
                    weather['temp'] = "--"            
                try:
                    weather['hum'] = parsed_json['current_observation']['relative_humidity']
                except:
                    weather['hum'] = "--"
                try:
                    weather['wdir'] = parsed_json['current_observation']['wind_dir']
                except:
                    weather['wdir'] = "N"
                try:
                    weather['wspd'] = parsed_json['current_observation']['wind_kph']
                except:
                    weather['wspd'] = "--"
                try:
                    weather['icon'] = parsed_json['current_observation']['icon']
                except:
                    weather['icon'] = "sunny"
                Conditions(screen,weather['icon'],weather['temp'],weather['hum'],weather['wspd'],weather['wdir'])
            except:
                w=540 # If there was an error try to update in 1 minute       
        time.sleep(1)
        
#** Main loop for thermostat manager
def Main(): 
    global mode
    global temp_set
    global temp
    global heating
    btn=0
    temp=GetTemperature()
    while True:
        btn=GetButton() # Check for button pressed
        if (btn>0): ManageButton(btn) # Manage the pressed button
        if (on_menu==False): # If not into a menu, displays the main screen
            Status(screen,"%0.1f" % temp,"%0.1f" % temp_set,mode,heating)
        while btn>0: # Wait for button release to avoid repetitions
            btn=GetButton()
            
# **********************************************************
# WEB section
# **********************************************************
app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD']= True
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

#** Enabled users/passwords
def check_auth(username, password): 
    global USER
    global PASSW
    return username == USER and password == PASSW

#** Sends a 401 response that enables basic auth"""
def authenticate(): 
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Termostato RPi"'})

#** Checks if user has properly logged in
def requires_auth(f): 
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            time.sleep(3)  
            return authenticate()
        return f(*args, **kwargs)
    return decorated
        
#** Homepage
@app.route("/")
@requires_auth
def Homepage():
    global mode
    global heating
    global temp_set
    global temp
    global version
    global temp_list
    global T_CAL
    global tvac
    global ivac
    global fvac
    if heating:
        heat="flame.gif"
    else:
        heat="none.gif"
    if (mode==AUTO):
        modo="AUTO"
    if (mode==SEMI):
        modo="AUTO(M)"
    if (mode==MAN):
        modo="MANUALE"
    templateData = {
        'title' : 'Termostato',
        'temp' : temp,
        'set_temp' : temp_set,
        'heat' : heat,
        'auto' : modo,
        'tcal' : T_CAL,
        'version' : version,
        'tvac' : tvac,
        'ivac' : ivac,
        'fvac' : fvac,
        'w_temp' : weather['temp'],
        'w_hum' : weather['hum'],
        'w_wspd' : weather['wspd'],
        'w_wdir' : weather['wdir'],
        'w_icon' : weather['icon'],
        'tlist' : temp_list
    }
    return render_template('index.html', **templateData)

#** Set the specified parameter
@app.route("/setdata", methods=['GET'])
#@requires_auth
def SetData():
    global T_CAL
    global temp_list
    global temp_set
    global mode
    global SEMI
    global MAN
    global AUTO
    global screen
    global temp
    global heating
    global tvac
    global ivac
    global fvac
    par=request.args.get('dato')
    valore=request.args.get('valore')
    if (par=="btn"): 
        btn=int(valore)
        if (btn==2): # T-
            temp_set=temp_set-0.5
            if (mode==AUTO):
                mode=SEMI
            CheckTemp()
        elif (btn==3): # T+
            temp_set=temp_set+0.5
            if (mode==AUTO):
                mode=SEMI
            CheckTemp()
        else: # A/M
            if (mode==MAN)or(mode==SEMI):
                mode=AUTO
                CheckTemp()
            else:    
                mode=MAN
    if (par=="set"): 
        temp_set=float(valore)
        mode=SEMI
        Status(screen,"%0.1f" % temp,"%0.1f" % temp_set,mode,heating)
        SaveConfiguration()
    if (par=="cal"): 
        T_CAL=float(valore)
        SaveConfiguration()
    if (par=="tvac"): 
        tvac=float(valore)
        SaveConfiguration()
    if (par=="ivac"): 
        ivac=datetime.datetime.strptime(valore,"%Y-%m-%d").date()
        SaveConfiguration()
    if (par=="fvac"): 
        fvac=datetime.datetime.strptime(valore,"%Y-%m-%d").date()
        SaveConfiguration()
    if (par=="prog"):
        indice=int(request.args.get('indice'))
        temp_list[indice]=float(valore)
        SaveConfiguration()
    return "ok"

#** Execute the requested task
@app.route("/operate", methods=['GET'])
#@requires_auth
def Operate():
    par=request.args.get('act')
    func = request.environ.get('werkzeug.server.shutdown')
    if (par=='reb'): 
        func()
        os.system('/usr/bin/sudo reboot now')
    if (par=='shut'):
        func()
        os.system('sudo poweroff')
    return "ok"

#** Return the current temp from the sensor
@app.route("/getcurtemp")
#@requires_auth
def GetCurrentTemp():
    global temp
    return "%0.1f" % temp

#** Return the set temp
@app.route("/getsettemp")
#@requires_auth
def GetSetTemp():
    global temp_set
    return "%0.1f" % temp_set

#** Return the calibration
@app.route("/getcal")
#@requires_auth
def GetCal():
    global T_CAL
    return "%0.1f" % T_CAL

#** Return the program list
@app.route("/getlist")
#@requires_auth
def GetList():
    global temp_list
    return "%s" % temp_list

#** Return the mode
@app.route("/getmode")
#@requires_auth
def GetMode():
    global mode
    if (mode==AUTO):
        modo="AUTO"
    if (mode==SEMI):
        modo="AUTO(M)"
    if (mode==MAN):
        modo="MANUALE"
    return modo

#** Return the heating state
@app.route("/getheat")
#@requires_auth
def GetHeating():
    global heating
    if heating:
        heat="flame.gif"
    else:
        heat="none.gif"
    return heat

# **********************************************************
# Startup
# **********************************************************

if __name__ == "__main__":
    LoadConfiguration()

    # Initialize main display
    font_big = ImageFont.truetype('freesansbold.ttf', 56)
    font_medium = ImageFont.truetype('freesansbold.ttf', 30)
    font_small = ImageFont.truetype('freesansbold.ttf', 16)
    light=DISPLAY_ON
    ClearScreen(screen)
    Buttons(screen,"Menu","T-","T+","A/M")
  
    # Start parallel threads
    thread.start_new_thread(UpdateStatus, ()) # Thread for updating status
    thread.start_new_thread(Main, ()) # Main thread
    
    time.sleep(5)

    # Start the web server
    app.run(host='0.0.0.0', port=WPORT, debug=False)
