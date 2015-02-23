import drive_control_thread as dr
import sys

east_count = int(sys.argv[1])
west_count = int(sys.argv[2])
east_speed = sys.argv[3]
west_speed = sys.argv[4]

try:
    x = dr.NSDriveInterface(timeout=2)
    x.set_tilts_from_counts(east_count,west_count,east_speed,west_speed)
    x.join()
except:
    x = dr.NSDriveInterface(timeout=2)
    x.stop()
