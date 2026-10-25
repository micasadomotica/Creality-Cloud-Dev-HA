# Creality Cloud Dev para Home Assistant

Integración independiente para conectar **CC Tools Dev** con Home Assistant. Puede convivir con [Creality Cloud de TitoTB](https://github.com/TitoTB/Creality-Cloud-HA), incluso usando la misma cuenta de Creality Cloud.

| Integración | Dominio | Conexión habitual |
|---|---|---|
| Creality Cloud de TitoTB | `creality_cloud` | CC Tools original, puerto 8080 |
| Creality Cloud Dev | `creality_cloud_dev` | CC Tools Dev, puerto 8088 |

**Versión 1.0.7**. Detecta CC Tools Dev del repositorio y añade el dispositivo **Creality Cloud Models** para consultar las subidas y controlar su programación. Conserva los dispositivos y entidades existentes al actualizar.

## Requisitos

- Home Assistant **2026.8 o posterior**.
- [**CC Tools Dev HA**](https://github.com/micasadomotica/CC-Tools-Dev-HA), iniciado y con el perfil de Creality actualizado.
- Acceso de Home Assistant a la URL de CC Tools Dev.
- Supervisor y una URL HTTP local directa para el reinicio automático. La consulta de datos admite HTTP/HTTPS; los destinos remotos, con proxy o ambiguos no permiten decidir qué aplicación reiniciar.

## Instalación desde HACS

1. Añade `https://github.com/micasadomotica/Creality-Cloud-Dev-HA` como repositorio personalizado de tipo **Integración**.
2. Descarga **Creality Cloud Dev 1.0.7** y reinicia Home Assistant.
3. En **Ajustes > Dispositivos y servicios > Añadir integración**, busca **Creality Cloud Dev**.
4. Si `34e9898c_cc_tools` está iniciado y responde con un perfil válido, se conecta automáticamente. Si no puede detectarlo, introduce `http://IP_DE_HOME_ASSISTANT:8088` o `http://homeassistant.local:8088`, con el puerto que hayas configurado. Puedes dejar la aplicación original encendida.
5. Comprueba que aparece el hub con tu nombre de perfil y el sufijo **Dev**, sus impresoras y el dispositivo **Creality Cloud Models · Dev**.

La detección utiliza `http://34e9898c-cc-tools:8080` en la red interna de Home Assistant, según su [convención de nombres DNS](https://contributors.home-assistant.io/apps/guides/communication/). El puerto 8088 corresponde al acceso externo habitual. Solo se prueba esa aplicación; no se seleccionan automáticamente la versión local ni la de TitoTB.

Para actualizar una instalación existente, actualiza primero CC Tools Dev desde la tienda de Apps y después esta integración desde HACS; reinicia Home Assistant. No elimines el hub: conservará su URL, sus entidades y el historial. La detección automática se aplica al añadir un hub nuevo.

Creality Cloud de TitoTB y Creality Cloud Dev aparecen como dos integraciones distintas. Ambas pueden consultar la misma cuenta, pero debes repartir las tareas programadas entre las aplicaciones para evitar acciones duplicadas.

Dentro de Dev solo se permite un hub por cuenta. Añadir otra vez esa cuenta no cambia su conexión. Para cambiar la URL, utiliza **Reconfigurar** en el menú del hub; se comprueba que sigue siendo la misma cuenta y se conservan las entidades.

## Reinicio automático

Está desactivado por defecto. Al activarlo, comprueba `restart_app` y `restart_app_name` en los atributos del interruptor. Para la aplicación de este repositorio, normalmente indican `34e9898c_cc_tools` y **CC Tools Dev**.

La integración consulta Supervisor antes de activarlo y justo antes de cada reinicio, contrastando la dirección y el puerto reales. No utiliza un destino fijo ni se basa solo en que el puerto sea 8088. Si no existe una coincidencia única, no reinicia ninguna aplicación.

Mantiene los controles de tareas bloqueadas, la espera de dos horas entre reinicios, el límite de tres reinicios en 24 horas y el periodo de estabilización. Los datos del watchdog y los eventos usan el dominio `creality_cloud_dev`, separados de la integración original.

## Datos disponibles

- Sesión Abierta/Cerrada, última comprobación y motivo del cierre.
- Puntos totales y obtenidos hoy, boletos e impulsos disponibles.
- Estado del último pedido.
- Estado de las impresoras, impresiones del día, última/próxima impresión y último G-code.
- Interruptor de impresiones programadas por impresora y reinicio automático por hub.

Los eventos usan el prefijo `creality_cloud_dev`. La integración consulta la API de CC Tools; no inicia sesión directamente en Creality Cloud.

## Creality Cloud Models

El dispositivo es independiente de las impresoras y pertenece al mismo hub de cuenta.

| Entidad | Contenido |
|---|---|
| Scheduled upload models / Subidas de modelos programadas | Activa o pausa la programación guardada en CC Tools. |
| Categoría predeterminada | Categoría y subcategoría, por ejemplo `Impresoras 3D / Otro`. |
| Diseños disponibles | Diseños válidos del último escaneo que todavía pueden enviarse. |
| Last model upload / Último diseño subido | Nombre del último diseño enviado correctamente; ID y enlace en sus atributos. |
| Last upload / Última subida | Fecha y hora del último envío confirmado. |
| Next upload / Próxima subida | Fecha y hora previstas de la próxima ejecución programada. |
| Uploads today / Subidas hoy | Número de diseños enviados correctamente hoy, en la zona horaria de CC Tools. |

Configura y guarda primero la selección inicial, el límite diario y la franja horaria en **Subir diseños** de CC Tools. Después puedes activar y desactivar la programación desde Home Assistant. El interruptor conserva esos ajustes y la limpieza automática; apagarlo no cancela una subida que ya esté en curso. Si falta la configuración o pertenece a otra cuenta, muestra el error sin activarla.

El interruptor incluye `last_status` y `last_message` para consultar el último resultado o error, además del horario y el límite diario. El sensor de diseños disponibles incluye la fecha del último escaneo y cualquier error de biblioteca; no realiza un escaneo de archivos en cada consulta.

La última subida y el contador diario proceden del registro persistente de envíos, incluidos los diseños cuyos archivos locales ya se han limpiado. Cuentan diseños, no ejecuciones ni puntos de recompensa. Una ejecución con varios diseños incrementa el contador por cada envío confirmado; los fallidos o pendientes de comprobación no cuentan. Se incluyen envíos manuales y programados.

Sin envíos anteriores, los sensores de última subida aparecen desconocidos y el contador vale cero. Con la programación apagada, la próxima subida aparece desconocida. Una fecha prevista no garantiza la ejecución: depende de la sesión, la disponibilidad de diseños y el estado del planificador de CC Tools.

Se consulta `GET /api/integration/models` y el interruptor utiliza `PATCH /api/integration/models` con `{"enabled": true}` o `false`. Si la app todavía no ofrece ese endpoint, solo las entidades de Models aparecen no disponibles; actualiza CC Tools Dev. La cuenta y las impresoras siguen funcionando.

## Validación y soporte

Las pruebas automáticas cubren detección y URL manual, separación de cuentas y dispositivos, reconfiguración, sensores y controles de Models, fallos de API y destino de reinicio. GitHub Actions ejecuta también HACS y Hassfest. La validación en una instalación real de Home Assistant queda pendiente.

Comunica los problemas en [Issues](https://github.com/micasadomotica/Creality-Cloud-Dev-HA/issues), indicando las versiones y la URL sin datos privados.

## Atribución y licencia

Basado en [Creality Cloud HA de TitoTB](https://github.com/TitoTB/Creality-Cloud-HA) y el trabajo de Aguacatec. Se conservan el historial y la [licencia MIT](LICENSE). Creality Cloud Dev y CC Tools no son productos oficiales de Creality.
