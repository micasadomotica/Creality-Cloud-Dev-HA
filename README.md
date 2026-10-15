# Creality Cloud for Home Assistant

This fork adds automatic restart routing for **CC Tools Dev** and the original CC Tools app. Version **1.0.5-dev** includes TitoTB's 1.0.5 integration, including the Session sensor and the printer device hierarchy changes from 1.0.4. The development build has automated tests but still needs validation in Home Assistant.

Custom Home Assistant integration that exposes the account, rewards and printers managed by the [CC Tools add-on](https://github.com/TitoTB/CC-Tools-HA).

## Requirements

- Home Assistant 2026.8 or newer.
- The [CC Tools add-on](https://github.com/TitoTB/CC-Tools-HA) version 1.0.27 or newer, configured and signed in to Creality Cloud.
- Home Assistant must be able to reach the add-on HTTP endpoint.

This integration does not connect directly to Creality Cloud and does not replace CC Tools. Scheduling, favorite profiles, G-code selection and other advanced settings remain in CC Tools.

## Installation with HACS

1. Open HACS in Home Assistant.
2. Go to **Integrations** and open the custom repositories menu.
3. Add `https://github.com/micasadomotica/Creality-Cloud-HA` as an **Integration** repository. If you already use TitoTB's repository, switch the installed integration to this fork; both provide the same `creality_cloud` integration and cannot be installed side by side.
4. Install **Creality Cloud**.
5. Restart Home Assistant.
6. Open **Settings > Devices & services > Add integration** and search for **Creality Cloud**.

The setup flow first tries to detect the CC Tools add-on automatically. If it cannot be reached using its internal add-on address, enter the URL shown by CC Tools, for example `http://192.168.1.44:8080`.

For this development pre-release, enable beta versions for this repository in HACS and select [**1.0.5-dev**](https://github.com/micasadomotica/Creality-Cloud-HA/releases/tag/v1.0.5-dev) when downloading. Restart Home Assistant after replacing the integration files. If upgrading from 1.0.4-dev.1, update the existing integration; there is no need to remove the configured account or its entities. Home Assistant 2026.8 or newer is required.

## Connecting CC Tools Dev and automatic restart

1. Keep CC Tools Dev running and signed in. Temporarily stop the original CC Tools app so setup asks for a URL instead of detecting it automatically.
2. Add **Creality Cloud** in **Settings > Devices & services** and enter `http://IP_OF_HOME_ASSISTANT:8088` (or the external port configured for Dev).
3. Complete setup. If this Creality account already exists, its URL is updated and the integration reconnects to the new endpoint instead of adding a duplicate account.
4. Enable **Automatic restart** on the account device. Its `restart_app` and `restart_app_name` attributes show the selected Supervisor app, normally `local_cc_tools` / CC Tools Dev.
5. Start the original CC Tools app again if you use both, keeping each scheduled task assigned to only one installation.

Before enabling recovery and immediately before each restart, this fork reads Supervisor's installed CC Tools apps, host addresses and actual port bindings. A URL ending in `:8088` selects Dev only when Supervisor confirms that binding. Other ports and direct internal app addresses work too. Recovery never falls back to the original CC Tools app.

Automatic restart requires Supervisor and a direct local HTTP URL. A remote host, HTTPS/reverse-proxy URL, missing app or ambiguous binding cannot be resolved safely: enabling recovery reports an error and an existing watchdog will skip the restart. Normal data polling remains available. Existing cooldown, daily restart limits and scheduler checks are unchanged.

TitoTB's 1.0.5 integration still uses the fixed restart target `8966b8c7_cc_tools`, even when another URL is configured. This fork resolves the target from Supervisor instead. The Session sensor requires session data from CC Tools 1.0.29 or newer; CC Tools Dev 1.0.45 already provides it.

## Devices and entities

The main device uses the name of the signed-in Creality Cloud profile. Each printer configured in CC Tools is represented as a separate device.

The integration provides:

- Session status (Open/Closed), last check time and closure reason.
- Total points and points earned today.
- Lottery tickets and available boosts.
- Latest shop order status and details.
- Printer status, daily count, last/next print and last G-code.
- A scheduled-prints switch on each printer device.
- An opt-in automatic-restart switch that recovers CC Tools after two missed scheduled tasks or a scheduler that remains stale for 30 minutes.

## Support

Questions, suggestions and support are available in the [Aguacatec Telegram community](https://t.me/aguacatec_es/13374).

## Disclaimer

**Creality Cloud for Home Assistant and CC Tools are not official applications** and are not affiliated with Creality or Creality Cloud. They are community projects developed by Aguacatec to improve the 3D-printing experience and its integration with home automation.

The goal is not to violate or circumvent Creality Cloud rules. Use these tools at your own risk and always comply with the platform rules.

## License

[MIT](LICENSE)
