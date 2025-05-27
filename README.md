# **Zaragoza Tram**
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs) ![GitHub release (latest by date)](https://img.shields.io/github/v/release/jrgim/Zaragoza_tram?style=flat-square)

Welcome to the **Zaragoza Tram** integration for Home Assistant! This integration allows you to create sensors that show the remaining time for the next two trams to arrive at a specific stop in Zaragoza.
This integration obtains the data thanks to the API made available by the Zaragoza City Council. [API REST Zaragoza](https://www.zaragoza.es/sede/portal/datos-abiertos/servicio/catalogo/327) 

## **Installation**

### **1. Manual**

1. Download the files from this repository.
2. Copy the `zaragoza_tram` folder into the `custom_components` directory inside your Home Assistant configuration.
- If the `custom_components` folder does not exist, create it in the root directory of your configuration.
3. Restart Home Assistant.

### **2. Using HACS**

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jrgim&repository=Zaragoza_tram&category=integration)
1. Add this repository as a custom repository in HACS.
2. Search for "Zaragoza Tram" in HACS and install it.
3. Restart Home Assistant.

## **Settings**

### **From the User Interface**

1. Go to **Settings** → **Devices and Integrations**.
2. Click the "+" button and search for "Zaragoza Tram".
3. Select the stop you want to configure from the drop-down list.
4. Save the changes and that's it: you'll have two sensors automatically configured!
