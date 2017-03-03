# Thermo
RPi smart thermostat

Uses Pi Zero with display, temperature sensor and solid state relay.

BOM:
- RPi Zero (new W version or old version with wifi dongle)
- Temp sensor: http://wiki.52pi.com/index.php/Raspberry_Pi_LM75B_temperature_Sensor_v1.0_SKU:EP-0031
- TFT display: https://thepihut.com/products/adafruit-pitft-2-2-hat-mini-kit-320x240-2-2-tft-no-touch
- Relay Panasonic AQV252

To prepare the RPi you should use the Raspbian image provided by adafruit (if you are using their display modules) or configure your RPi following their instructions.
Also follow the instructions for the temperature sensor in the link above.

Software uses Flask for web interface, so you need to install it

To be done (random order):
- Electrical schematic
- Terminate menu management ("local" side as web side is ok)
- Better localization (now every sentence is hard coded when used inside the main source)
- Upload stl supports for 3D printing
- Step by step install instructions
- Blog post for detailed description on https://rpihome.blogspot.com
