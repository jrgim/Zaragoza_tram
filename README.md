# **Zaragoza Tram**
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

![logo tranvia y reloj](logo.png)

¡Bienvenido a la integración **Zaragoza Tram** para Home Assistant! Esta integración te permite crear sensores que muestran el tiempo restante para los dos próximos tranvías en llegar a una parada específica de Zaragoza.
Esta integracion obtiene los datos gracias a la API que pone a disposicion el Ayuntamiento de Zaragoza. [API REST Zaragoza](https://www.zaragoza.es/sede/portal/datos-abiertos/servicio/catalogo/327) 

## **Instalación**

### **1. Manual**

1. Descarga los archivos de este repositorio.
2. Copia la carpeta `zaragoza_tram` en el directorio `custom_components` dentro de tu configuración de Home Assistant.
    - Si no existe la carpeta `custom_components`, créala en el directorio raíz de tu configuración.
3. Reinicia Home Assistant.

### **2. Usando HACS**

1. Añade este repositorio como un repositorio personalizado en HACS.
2. Busca "Zaragoza Tram" en HACS e instálalo.
3. Reinicia Home Assistant.

## **Configuración**

### **Desde la Interfaz de Usuario**

1. Ve a **Configuración** → **Dispositivos e Integraciones**.
2. Haz clic en el botón "+" y busca "Zaragoza Tram".
3. Selecciona la parada que deseas configurar desde la lista desplegable.
4. Guarda los cambios y listo: ¡tendrás dos sensores configurados automáticamente!
