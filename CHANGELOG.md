# Changelog

## 1.0.4-dev.1

- Resolves the CC Tools app to restart from the configured URL and current Supervisor host/port mappings, including local CC Tools Dev alongside the upstream app.
- Blocks recovery for unresolved, remote or ambiguous targets instead of restarting a fixed app.
- Exposes the selected restart app in switch attributes and verifies it again immediately before recovery.
- Reloads the integration when setup updates an existing account's URL.
- Preserves scheduler checks, cooldowns, restart limits and existing entity IDs. This development build still needs validation in Home Assistant.

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
