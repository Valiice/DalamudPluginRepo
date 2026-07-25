# Valiice's Dalamud Plugin Repository

This is a custom plugin repository for **Dalamud**, the plugin framework for Final Fantasy XIV. It contains a collection of quality-of-life and utility plugins.

## Available Plugins
<!--START_MARKER-->
| Plugin Name | Description | Source |
| :--- | :--- | :---: |
| **SpotifyHonorific** | **Your Spotify song as an honorific**<br>Update honorific title based on your currently playing Spotify track | [Repo](https://github.com/Valiice/SpotifyHonorific) |
| **Drop Rate Logger** | **Logs drops to server**<br>Loot Tracking System. Logs drops to server. | [Repo](https://github.com/Valiice/LootTracker) |
| **Discord Chat Webhook** | **Simple, lightweight relay of game chat to Discord via Webhook.**<br>Relays chat to Discord via Webhook. | [Repo](https://github.com/Valiice/DiscordChatWebhook) |
| **Job Auto Switcher** | **Never miss a queue pop because of the wrong job again.**<br>Automatically switches your gearset to match the queued job when you click Commence, bypassing the 'class/job is different' error. | [Repo](https://github.com/Valiice/JobAutoSwitcher) |
| **Retainer Inventory Price** | **Calculate the total market value of all your retainers**<br>Scans your retainer inventories when you open them and calculates their total estimated market value using Universalis prices. | [Repo](https://github.com/Valiice/RetainerInventoryPrice) |
| **Foxy Jumpscare** | **Random FNAF-style jumpscares for FFXIV!**<br>Triggers random fullscreen Withered Foxy jumpscares during gameplay, inspired by Five Nights at Freddy's mods. | [Repo](https://github.com/Valiice/FoxyJumpscare) |
| **ProvokeCounter** | **Counts how many times tanks provoke in your party.**<br>Displays a counter badge on the party list for each party member who uses Provoke. Resets per zone. Toggle with /provokecounter, reset with /provokecounter reset. | [Repo](https://github.com/Valiice/ProvokeCounter) |
| **EmoteReactor** | **React with an emote when someone emotes at you**<br>Define rules: when a player targets you and performs an emote, automatically perform an emote back. | [Repo](https://github.com/Valiice/EmoteReactor) |
| **RaceFilter** | **Hide and mute players by race and gender.**<br>Rule-based filtering: hide models, suppress chat, and mute voices/footsteps of players by race and/or gender. Friends, party, alliance, and FC members are exempt. Pauses automatically in duties. | [Repo](https://github.com/Valiice/RaceFilter) |
<!--END_MARKER-->
---

## Installation

1.  Open the **Dalamud Settings** menu in-game.
    * Type `/xlsettings` in the chat window.
    * *Or* click the "Settings" button at the bottom of the Plugin Installer (`/xlplugins`).
2.  Navigate to the **Experimental** tab.
3.  Locate the **Custom Plugin Repositories** section.
4.  Paste the following URL into the empty text input field (the last box with a `+` next to it):
    ```
    https://raw.githubusercontent.com/Valiice/DalamudPluginRepo/master/repo.json
    ```
5.  Click the **+** (Plus) button to add the repository.
6.  Click the **💾** (Disk/Save) button to save your changes.

Once added, these plugins will appear inside the **Plugin Installer** (accessible via `/xlplugins`), usually under a custom category or by searching for their names.

## Support & Feedback

If you encounter issues with a specific plugin, please open an issue on its respective GitHub repository linked in the table above.

## License

This repository and its contents are licensed under the **GNU Affero General Public License v3.0**. See the [LICENSE](./LICENSE) file for more details.
