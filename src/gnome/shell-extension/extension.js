import GObject from "gi://GObject";
import St from "gi://St";
import Gio from "gi://Gio";
import GLib from "gi://GLib";

import * as Main from "resource:///org/gnome/shell/ui/main.js";
import * as PanelMenu from "resource:///org/gnome/shell/ui/panelMenu.js";
import * as PopupMenu from "resource:///org/gnome/shell/ui/popupMenu.js";

const BUS_NAME = "org.frostyard.Kapsule";
const OBJ_PATH = "/org/frostyard/Kapsule";
const IFACE_NAME = "org.frostyard.Kapsule.Manager";

const ManagerIface = `
<node>
  <interface name="${IFACE_NAME}">
    <method name="ListContainers">
      <arg direction="out" type="a(sssss)" name="containers"/>
    </method>
    <method name="StartContainer">
      <arg direction="in" type="s" name="name"/>
      <arg direction="out" type="o" name="operation"/>
    </method>
    <method name="StopContainer">
      <arg direction="in" type="s" name="name"/>
      <arg direction="in" type="b" name="force"/>
      <arg direction="out" type="o" name="operation"/>
    </method>
  </interface>
</node>
`;

const ManagerProxy = Gio.DBusProxy.makeProxyWrapper(ManagerIface);

const KapsuleIndicator = GObject.registerClass(
class KapsuleIndicator extends PanelMenu.Button {
    _init() {
        super._init(0.0, "Kapsule");

        this._icon = new St.Icon({
            icon_name: "utilities-terminal-symbolic",
            style_class: "system-status-icon",
        });
        this.add_child(this._icon);

        this._proxy = null;
        this._buildMenu();
        this._connectProxy();
    }

    _connectProxy() {
        try {
            this._proxy = new ManagerProxy(
                Gio.DBus.system,
                BUS_NAME,
                OBJ_PATH
            );
        } catch (e) {
            log(`Kapsule: Failed to connect to daemon: ${e.message}`);
        }
    }

    _buildMenu() {
        this.menu.removeAll();
        this._loadingItem = new PopupMenu.PopupMenuItem("Loading...", {
            reactive: false,
        });
        this.menu.addMenuItem(this._loadingItem);
    }

    _onOpenStateChanged(menu, open) {
        super._onOpenStateChanged(menu, open);
        if (open) this._refresh();
    }

    _refresh() {
        if (!this._proxy) {
            this.menu.removeAll();
            this.menu.addMenuItem(
                new PopupMenu.PopupMenuItem("Daemon not running", {
                    reactive: false,
                })
            );
            return;
        }

        this._proxy.ListContainersRemote((result, error) => {
            this.menu.removeAll();

            if (error) {
                this.menu.addMenuItem(
                    new PopupMenu.PopupMenuItem(`Error: ${error.message}`, {
                        reactive: false,
                    })
                );
                return;
            }

            const containers = result[0];
            if (containers.length === 0) {
                this.menu.addMenuItem(
                    new PopupMenu.PopupMenuItem("No containers", {
                        reactive: false,
                    })
                );
                return;
            }

            for (const [name, status, image, created, mode] of containers) {
                const running = status === "Running";
                const label = `${name}  ${running ? "\u25cf" : "\u25cb"}`;
                const item = new PopupMenu.PopupMenuItem(label);

                if (running) {
                    item.connect("activate", () => {
                        GLib.spawn_command_line_async(
                            `ptyxis --tab-with-profile-name=${name}`
                        );
                    });
                } else {
                    item.connect("activate", () => {
                        this._proxy.StartContainerRemote(name, () => {});
                    });
                }

                this.menu.addMenuItem(item);
            }

            this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

            const settingsItem = new PopupMenu.PopupMenuItem("Open Kapsule Settings");
            settingsItem.connect("activate", () => {
                GLib.spawn_command_line_async("kapsule-settings");
            });
            this.menu.addMenuItem(settingsItem);
        });
    }

    destroy() {
        this._proxy = null;
        super.destroy();
    }
});

export default class KapsuleExtension {
    constructor(metadata) {
        this._metadata = metadata;
    }

    enable() {
        this._indicator = new KapsuleIndicator();
        Main.panel.addToStatusArea("kapsule", this._indicator);
    }

    disable() {
        this._indicator?.destroy();
        this._indicator = null;
    }
}
