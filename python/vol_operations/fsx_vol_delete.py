import datetime
import urllib3
from netapp_ontap import config, HostConnection, NetAppRestError
from netapp_ontap.resources import Volume

# Suppress warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def setup_connection(cluster_ip, username, password):
    """Initializes the connection to the ONTAP cluster."""
    config.CONNECTION = HostConnection(
        cluster_ip,
        username=username,
        password=password,
        verify=False
    )

def is_older_than_24h(vol):
    """Returns True if the volume was created more than 24 hours ago."""
    try:
        if not hasattr(vol, 'create_time') or not vol.create_time:
            return False

        now = datetime.datetime.now(datetime.timezone.utc)
        age = now - vol.create_time

        is_old = age.total_seconds() > (24 * 3600)
        print(f"  [*] Volume age: {age.days}d {age.seconds//3600}h. Older than 24h: {is_old}")
        return is_old
    except Exception as e:
        print(f"  [-] Error processing timestamp: {e}")
        return False

def check_for_clones(vol_uuid):
    """Checks if any volumes are clones of the target volume."""
    try:
        # Using the requested dictionary unpacking format
        clone_params = {
            "clone.parent_volume.uuid": vol_uuid
        }
        clones = list(Volume.get_collection(**clone_params))
        return len(clones) > 0
    except NetAppRestError as e:
        print(f"  [-] Error checking clones: {e}")
        return True # Safety fallback

def delete_volume_immediately(cluster_ip, username, password, svm_name, vol_name):
    """Modular logic to evaluate and delete a volume."""
    setup_connection(cluster_ip, username, password)

    print(f"Evaluating Volume: {vol_name}...")

    try:
        # 1. Fetch Volume using requested parameter format
        query_params = {
            "name": vol_name,
            "svm.name": svm_name,
            "fields": "uuid,create_time,name"
        }
        volumes = list(Volume.get_collection(**query_params))

        if not volumes:
            print(f"  [-] Volume '{vol_name}' not found.")
            return

        vol = volumes[0]

        # 2. Logic: Check Age (>24h)
        if not is_older_than_24h(vol):
            print("  [-] Logic Check: Volume is too new (< 24h). Skipping.")
            return

        # 3. Logic: Check for Clones
        if check_for_clones(vol.uuid):
            print("  [-] Logic Check: Volume has active clones. Skipping.")
            return

        # 4. Immediate Deletion (Bypassing Recovery Queue)
        # force=True translates to the REST parameter ?force=true
        print(f"  [!] All checks passed. Deleting {vol_name} immediately...")
        vol.delete(force=True)
        print("  [+] Success: Volume deleted and recovery queue bypassed.")

    except NetAppRestError as e:
        print(f"  [-] ONTAP API Error: {e}")
    except Exception as e:
        print(f"  [-] Unexpected Error: {e}")

if __name__ == "__main__":
    # --- Input Variables ---
    HOST = "x.x.x.x"      # Replace with your FileSystem Management IP
    USER = "fsxadmin"           
    PASS = "------" # Replace with your filesystem password
    SVM = "fsxxxxxx"     # Replace with the SVM hosting the volume
    VOL = "data_xxxxxx"  # Replace with the name of the FlexVol

    delete_volume_immediately(HOST, USER, PASS, SVM, VOL)
