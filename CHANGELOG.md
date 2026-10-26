# Changelog

## 1.0.8

- Fixes automatic restart target detection when a stopped or errored local CC Tools app retains the same internal IP as the repository app after migration.
- Gives an exact Supervisor hostname priority over reused IP addresses, requiring the internal port 8080 and a unique app name. IP addresses and other aliases still require an unambiguous target.
- Preserves configured URLs, entities, restart cooldowns and daily limits. Adds regression coverage for both repository and local hostnames, reused IPs and ambiguous targets.
- Updates the README with the migration-related restart fix and upgrade instructions.

## 1.0.7

- Detects the running repository app `34e9898c_cc_tools`; offers a manual Home Assistant URL if unavailable.
- Adds a separate Creality Cloud Models device with a scheduled uploads switch and six sensors: default category, available designs, last model upload, last upload, next upload and uploads today.
- Reads persistent delivery history through the CC Tools Models API, including designs removed by cleanup, and preserves schedule settings when toggling uploads.
- Isolates Models API failures from account and printer polling. Existing hubs keep their URLs and entity identifiers.
- Updates installation instructions and the CC Tools Dev repository requirement.

## 1.0.6-dev.1

- Creates the independent Creality Cloud Dev integration (`creality_cloud_dev`) to coexist with TitoTB Creality Cloud.
- Always asks for the Dev URL; adding an existing account never silently changes its endpoint.
- Adds explicit URL reconfiguration for the same account, preserving its entities.
- Separates devices, event names and watchdog storage; labels Dev devices clearly.
- Preserves all 1.0.5-dev features, including session data and restart routing by Supervisor URL/port.
- Requires Home Assistant 2026.8+. New entities must be reviewed before replacing references from the legacy integration.

## 1.0.5-dev

- Integrates TitoTB 1.0.4 and 1.0.5: account Session sensor, session diagnostics and printer links through the registered account device ID.
- Keeps automatic restart bound to the configured URL and Supervisor host/port mappings, including local CC Tools Dev; never falls back to a fixed upstream app.
- Preserves URL-change reconnection, entity identifiers, restart cooldowns and daily limits.
- Requires Home Assistant 2026.8.0 or newer. Pre-release pending validation in Home Assistant.

## 1.0.4-dev.1

- Resolves the CC Tools app to restart from the configured URL and current Supervisor host/port mappings, including local CC Tools Dev alongside the upstream app.
- Blocks recovery for unresolved, remote or ambiguous targets instead of restarting a fixed app.
- Exposes the selected restart app in switch attributes and verifies it again immediately before recovery.
- Reloads the integration when setup updates an existing account's URL.
- Preserves scheduler checks, cooldowns, restart limits and existing entity IDs. This development build still needs validation in Home Assistant.

## 1.0.5

- Adds a Session sensor to the Creality Cloud account device.
- Reports the session as Open or Closed using the state confirmed by CC Tools.
- Exposes the last session check and closure reason as diagnostic attributes.

## 1.0.4

- Migrates printer device hierarchy from the deprecated `via_device` field to `via_device_id`.
- Registers the Creality Cloud account device before linking printer devices to it.
- Requires Home Assistant 2026.8.0 or newer.

## 1.0.3

- Adds an opt-in Automatic restart switch for recovering a stalled CC Tools add-on.
- Detects two consecutive missed schedule slots while respecting replanning and later successful executions.
- Recovers scheduler operations that remain stale for 30 minutes.
- Adds restart cooldown, daily limit and stabilization protections without creating Home Assistant notifications.

## 1.0.2

- Moves print sensors and the scheduled-prints switch to each printer device.
- Renames the printer switch to Scheduled prints.
- Removes the manual Send next print button.

## 1.0.1

- Adds a latest order sensor with the current status and useful order attributes.
- Removes redundant automation, browser, scheduler and per-task entities.
- Keeps the available boosts sensor and the print-related controls and entities.

## 1.0.0

- Initial HACS release.
- Adds account, points, rewards, task and order entities.
- Adds one Home Assistant device per configured printer.
- Adds task switches, manual action buttons and Home Assistant events.
- Includes English and Spanish translations.
