# Creality Cloud Dev para Home Assistant

Integración independiente para conectar **CC Tools Dev** con Home Assistant. Puede convivir con [Creality Cloud de TitoTB](https://github.com/TitoTB/Creality-Cloud-HA), incluso usando la misma cuenta de Creality Cloud.

| Integración | Dominio | Conexión habitual |
|---|---|---|
| Creality Cloud de TitoTB | `creality_cloud` | CC Tools original, puerto 8080 |
| Creality Cloud Dev | `creality_cloud_dev` | CC Tools Dev, puerto 8088 |

**Versión inicial independiente: 1.0.6-dev.1**, basada en TitoTB 1.0.5 y la corrección de reinicio de 1.0.5-dev. Es una pre-release pendiente de validación real en Home Assistant.

## Requisitos

- Home Assistant **2026.8 o posterior**.
- [**CC Tools Dev 1.0.46**](https://github.com/micasadomotica/CC-Tools-HA/releases/tag/dev-v1.0.46) como versión estable recomendada, probada en Home Assistant. Debe estar iniciado y con el perfil de Creality actualizado.
- Acceso de Home Assistant a la URL de CC Tools Dev.
- Supervisor y una URL HTTP local directa para el reinicio automático. La consulta de datos admite HTTP/HTTPS; los destinos remotos, con proxy o ambiguos no permiten decidir qué aplicación reiniciar.

## Instalación desde HACS

1. Añade `https://github.com/micasadomotica/Creality-Cloud-Dev-HA` como repositorio personalizado de tipo **Integración**.
2. Activa las versiones beta, descarga **Creality Cloud Dev 1.0.6-dev.1** y reinicia Home Assistant.
3. En **Ajustes > Dispositivos y servicios > Añadir integración**, busca **Creality Cloud Dev**.
4. Introduce `http://IP_DE_HOME_ASSISTANT:8088`, o el puerto que hayas configurado para Dev. El asistente siempre pide la URL; puedes dejar la aplicación original encendida.
5. Comprueba que aparece el hub **MiCasaDomotica · Dev** (o tu nombre de perfil) dentro de Creality Cloud Dev. Los dispositivos de las impresoras también llevan el sufijo **Dev**.

Creality Cloud de TitoTB y Creality Cloud Dev aparecen como dos integraciones distintas. Ambas pueden consultar la misma cuenta, pero debes repartir las tareas programadas entre las aplicaciones para evitar acciones duplicadas.

Dentro de Dev solo se permite un hub por cuenta. Añadir otra vez esa cuenta no cambia su conexión. Para cambiar la URL, utiliza **Reconfigurar** en el menú del hub; se comprueba que sigue siendo la misma cuenta y se conservan las entidades.

## Reinicio automático

Está desactivado por defecto. Al activarlo, comprueba `restart_app` y `restart_app_name` en los atributos del interruptor. Para una aplicación Dev local, normalmente indican `local_cc_tools` y **CC Tools Dev**.

La integración consulta Supervisor antes de activarlo y justo antes de cada reinicio, contrastando la dirección y el puerto reales. No utiliza un destino fijo ni se basa solo en que el puerto sea 8088. Si no existe una coincidencia única, no reinicia ninguna aplicación.

Mantiene los controles de tareas bloqueadas, la espera de dos horas entre reinicios, el límite de tres reinicios en 24 horas y el periodo de estabilización. Los datos del watchdog y los eventos usan el dominio `creality_cloud_dev`, separados de la integración original.

## Datos disponibles

- Sesión Abierta/Cerrada, última comprobación y motivo del cierre.
- Puntos totales y obtenidos hoy, boletos e impulsos disponibles.
- Estado del último pedido.
- Estado de las impresoras, impresiones del día, última/próxima impresión y último G-code.
- Interruptor de impresiones programadas por impresora y reinicio automático por hub.

Los eventos usan el prefijo `creality_cloud_dev`. La integración consulta la API de CC Tools; no inicia sesión directamente en Creality Cloud.

## Validación y soporte

40 pruebas automáticas cubren la separación de dominios, la misma cuenta en ambas integraciones, altas duplicadas, reconfiguración, dispositivos, sesión y destino de reinicio. La validación en una instalación real de Home Assistant queda pendiente.

Comunica los problemas en [Issues](https://github.com/micasadomotica/Creality-Cloud-Dev-HA/issues), indicando las versiones y la URL sin datos privados.

## Atribución y licencia

Basado en [Creality Cloud HA de TitoTB](https://github.com/TitoTB/Creality-Cloud-HA) y el trabajo de Aguacatec. Se conservan el historial y la [licencia MIT](LICENSE). Creality Cloud Dev y CC Tools no son productos oficiales de Creality.
