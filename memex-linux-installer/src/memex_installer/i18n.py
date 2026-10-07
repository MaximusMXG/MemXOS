"""EN/FR error catalog for wizard and completer screens."""

ERRORS: dict[str, dict[str, dict[str, str]]] = {
    "ME-BITLOCKER": {
        "en": {
            "title": "BitLocker is on",
            "body": "Windows on this drive is encrypted with BitLocker. Linux cannot safely shrink that partition.",
            "action": "In Windows, turn BitLocker off for this drive, reboot this USB, and try again.",
        },
        "fr": {
            "title": "BitLocker est activé",
            "body": "Windows sur ce disque est chiffré avec BitLocker. Linux ne peut pas réduire cette partition en toute sécurité.",
            "action": "Dans Windows, désactivez BitLocker pour ce disque, redémarrez avec cette clé USB, puis réessayez.",
        },
    },
    "ME-NO-WINDOWS": {
        "en": {
            "title": "No Windows found",
            "body": "Dual-boot was selected, but no Windows install was found on any disk.",
            "action": "Install Windows with the normal shop process first, or choose Linux only.",
        },
        "fr": {
            "title": "Windows introuvable",
            "body": "Le double démarrage a été choisi, mais aucune installation Windows n'a été trouvée.",
            "action": "Installez d'abord Windows avec le processus habituel, ou choisissez Linux seulement.",
        },
    },
    "ME-SPACE": {
        "en": {
            "title": "Not enough free space",
            "body": "Shrinking Windows would leave less than 64 GB for Windows, or there is not enough free space for the Linux size you chose.",
            "action": "Pick a smaller Linux size, or install Linux on a different disk.",
        },
        "fr": {
            "title": "Espace insuffisant",
            "body": "Réduire Windows laisserait moins de 64 Go pour Windows, ou il n'y a pas assez d'espace pour la taille Linux choisie.",
            "action": "Choisissez une taille Linux plus petite, ou installez Linux sur un autre disque.",
        },
    },
    "ME-WINDOWS-HIBERNATED": {
        "en": {
            "title": "Windows was not fully shut down",
            "body": "Windows is hibernated (Fast Startup) or its disk was not closed cleanly, so Linux cannot safely shrink it. Nothing has been changed.",
            "action": "In Windows, turn off Fast Startup (Control Panel > Power Options > Choose what the power buttons do), then Restart (not Shut down) Windows, run chkdsk if asked, then reboot this USB.",
        },
        "fr": {
            "title": "Windows n'a pas été complètement arrêté",
            "body": "Windows est en hibernation (démarrage rapide) ou son disque n'a pas été fermé proprement; Linux ne peut pas le réduire en toute sécurité. Rien n'a été modifié.",
            "action": "Dans Windows, désactivez le démarrage rapide (Panneau de configuration > Options d'alimentation > Choisir l'action des boutons d'alimentation), puis Redémarrez (et non Arrêtez) Windows, lancez chkdsk si demandé, puis redémarrez sur cette clé USB.",
        },
    },
    "ME-USB-TARGET": {
        "en": {
            "title": "Cannot install on the USB stick",
            "body": "The selected target is the installer USB itself.",
            "action": "Choose the PC's SSD or hard drive, not the installer stick.",
        },
        "fr": {
            "title": "Impossible d'installer sur la clé USB",
            "body": "La cible sélectionnée est la clé USB d'installation.",
            "action": "Choisissez le SSD ou le disque du PC, pas la clé d'installation.",
        },
    },
    "ME-DISK-GONE": {
        "en": {
            "title": "Disk disappeared",
            "body": "The selected disk is no longer present.",
            "action": "Reseat the drive, then restart this USB installer.",
        },
        "fr": {
            "title": "Disque disparu",
            "body": "Le disque sélectionné n'est plus présent.",
            "action": "Rebranchez le disque, puis redémarrez cette clé USB.",
        },
    },
    "ME-RAID-MODE": {
        "en": {
            "title": "Storage is in RAID / Intel RST mode",
            "body": "This PC's storage is set to Intel RST / VMD (RAID) mode, so Linux may not see the drive or can't safely use it.",
            "action": "Linux only (wipes the drive): in BIOS/UEFI setup, change storage/SATA mode from RAID/RST/VMD to AHCI (or disable VMD), save, and reboot this USB.\n"
                      "Dual-boot: do NOT change the BIOS yet. First boot Windows to Safe Mode once "
                      "(admin Command Prompt: bcdedit /set {current} safeboot minimal), switch to AHCI, "
                      "boot Windows, then run bcdedit /deletevalue {current} safeboot. Or ask a senior tech.",
        },
        "fr": {
            "title": "Stockage en mode RAID / Intel RST",
            "body": "Le stockage de ce PC est en mode Intel RST / VMD (RAID); Linux peut ne pas voir le disque ou ne peut pas l'utiliser en toute sécurité.",
            "action": "Linux seulement (efface le disque) : dans le BIOS/UEFI, passez le mode de stockage/SATA de RAID/RST/VMD à AHCI (ou désactivez VMD), enregistrez, puis redémarrez avec cette clé USB.\n"
                      "Double démarrage : ne changez PAS le BIOS tout de suite. Démarrez d'abord Windows en mode sans échec une fois "
                      "(invite de commandes admin : bcdedit /set {current} safeboot minimal), passez à AHCI, "
                      "démarrez Windows, puis exécutez bcdedit /deletevalue {current} safeboot. Ou demandez à un technicien senior.",
        },
    },
    "ME-INSTALL-FAIL": {
        "en": {
            "title": "Install failed",
            "body": "The unattended Kubuntu install did not finish.",
            "action": "Do not unplug the Windows drive. Reboot this USB and run the wizard again.",
        },
        "fr": {
            "title": "Échec de l'installation",
            "body": "L'installation Kubuntu automatique ne s'est pas terminée.",
            "action": "Ne débranchez pas le disque Windows. Redémarrez cette clé USB et relancez l'assistant.",
        },
    },
    "ME-NO-NET": {
        "en": {
            "title": "Waiting for network",
            "body": "Setup needs ethernet or internet to install drivers and apps.",
            "action": "Plug in an ethernet cable or connect to Wi-Fi. This screen will continue automatically.",
        },
        "fr": {
            "title": "En attente du réseau",
            "body": "La configuration a besoin d'Internet pour installer les pilotes et les applications.",
            "action": "Branchez un câble Ethernet ou connectez-vous au Wi-Fi. Cet écran continuera automatiquement.",
        },
    },
    "ME-STUCK": {
        "en": {
            "title": "This looks stuck",
            "body": "A setup step has made no progress for several minutes.",
            "action": "Leave the PC powered on and press Retry. If it fails again, leave it for a Linux-capable tech.",
        },
        "fr": {
            "title": "Ça semble bloqué",
            "body": "Une étape n'a fait aucun progrès depuis plusieurs minutes.",
            "action": "Laissez le PC allumé et appuyez sur Réessayer. En cas d'échec, laissez-le à un technicien Linux.",
        },
    },
    "ME-STEP-FAIL": {
        "en": {
            "title": "Setup failed",
            "body": "A setup step failed (driver, update, or app install).",
            "action": "Press Retry. The PC will also try again on the next boot.",
        },
        "fr": {
            "title": "Échec de la configuration",
            "body": "Une étape a échoué (pilote, mise à jour ou application).",
            "action": "Appuyez sur Réessayer. Le PC réessaiera aussi au prochain démarrage.",
        },
    },
    "ME-TWO-DISK": {
        "en": {
            "title": "Two-drive dual-boot",
            "body": "Windows is on a different disk. Linux will use the entire selected disk (it will be wiped). Windows will not be partitioned. This is the preferred layout.",
            "action": "Confirm the selected disk model and size, then continue.",
        },
        "fr": {
            "title": "Double démarrage sur deux disques",
            "body": "Windows est sur un autre disque. Linux utilisera tout le disque sélectionné (il sera effacé). Windows ne sera pas partitionné. C'est la configuration recommandée.",
            "action": "Vérifiez le modèle et la taille du disque sélectionné, puis continuez.",
        },
    },
}
