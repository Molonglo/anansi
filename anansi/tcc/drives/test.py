import ns_drive as ns

x = ns.NSDriveInterface()
x.get_status()
x.set_tilts_from_counts(26000,46000)

