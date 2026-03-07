import os, time
print("ALII Protection Agent - ACTIVE")
while True:
    # Check critical processes
    if not os.system("pgrep mosquitto > /dev/null"):
        print("Mosquitto OK")
    else:
        os.system("systemctl restart mosquitto")
        print("Mosquitto restarted")
    time.sleep(300)
