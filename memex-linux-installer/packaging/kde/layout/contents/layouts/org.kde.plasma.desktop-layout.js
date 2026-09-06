// Memory Express initial desktop. Plasma scripting API: develop.kde.org/docs/plasma/scripting/
var panel = new Panel;
panel.location = "bottom";
panel.height = 48;
var launcher = panel.addWidget("org.kde.plasma.kickoff");
launcher.currentConfigGroup = ["Shortcuts"];
launcher.writeConfig("global", "Alt+F1");
var tasks = panel.addWidget("org.kde.plasma.icontasks");
tasks.currentConfigGroup = ["General"];
var pins = ["preferred://browser", "applications:org.kde.dolphin.desktop"];
var profile = new ConfigFile("/etc/memex/plasma-profile");
profile.group = "General";
if (profile.readEntry("Gaming", "false") === "true") {
    pins.push("applications:steam.desktop");
}
tasks.writeConfig("launchers", pins.join(","));
panel.addWidget("org.kde.plasma.systemtray");
panel.addWidget("org.kde.plasma.digitalclock");
panel.addWidget("org.kde.plasma.showdesktop");
