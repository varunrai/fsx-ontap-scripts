from netapp_ontap import config, HostConnection, NetAppRestError
from netapp_ontap.resources import SnapmirrorRelationship, Volume
import time

fsxn_management_endpoint = "<FILESYSTEM MANAGMENT ENDPOINT>"
fsxn_user = "fsxadmin"
fsxn_user_pwd = "<PASSWORD>"

svm_name = "fsx0svm1"
vol_name = "vol_secondary"
clone_name = "vol_clone"
clone_junction_path = "/vol_clone"

config.CONNECTION = HostConnection(fsxn_management_endpoint, fsxn_user, fsxn_user_pwd, verify=False)

def print_snapmirror_details(snapmirror):
    print("Source: " + snapmirror.source.path + " --> Destination: " +
          snapmirror.destination.path + ", UUID: " + snapmirror.uuid + ", Status: " + snapmirror.state)


def update_snapmirror_state(snapmirror, new_state):
    snapmirror.state = new_state
    if snapmirror.patch(poll=True):
        print("Snapmirror Relationship Updated Successfully to " + new_state)


def handle_netapp_error(action, action_name, *args):
    try:
        return action(*args)
    except NetAppRestError as error:
        print("Exception caught while " + action_name + ": " + str(error))


def search_snapmirror_relationships():
    return SnapmirrorRelationship.find(destination={"path": svm_name + ":" + vol_name})


def delete_volume_clones(vol_name):
    for volume in Volume.get_collection(**{"clone.is_flexclone": True, "clone.parent_volume.name": vol_name}):
        print("Parent Volume: " + vol_name + " --> Clone: " +
              volume.name + ", Cloned Volume UUID: " + volume.uuid)
        print("Deleting Clone: " + volume.name)
        volume.delete(force=True)


def create_clone(svm_uuid, vol_name, clone_name):
    print("Retrieving Parent Volume Details")
    parent_volume = Volume.find(name=vol_name)
    print("Creating Clone: " + clone_name)
    tmp = {'uuid': svm_uuid}
    dataobj = {}
    dataobj['svm'] = tmp
    dataobj['name'] = clone_name
    clone_volume_json = {"is_flexclone": bool("true"), "parent_svm": {
        "name": svm_name, "uuid": svm_uuid}, "parent_volume": {"name": parent_volume.name, "uuid": parent_volume.uuid}}
    dataobj['clone'] = clone_volume_json
    volume = Volume.from_dict(dataobj)
    volume.post(poll=True)


print("Searching for SnapMirror Relationship for Destination SVM: " +
      svm_name + " and Volume: " + vol_name)
snapmirror = handle_netapp_error(search_snapmirror_relationships, "searching for SnapMirror Relationships")
print_snapmirror_details(snapmirror)

svm_uuid = snapmirror.destination.svm.uuid
print("Searching for Clones of volume: " + snapmirror.destination.path)
handle_netapp_error(delete_volume_clones, "searching for clones", vol_name)


print("Resuming the SnapMirror Relationship")
if snapmirror.state == "broken_off":
    update_snapmirror_state(snapmirror, "snapmirrored")

print("Checking the sync status")
time.sleep(5)
smStatus = SnapmirrorRelationship.find(uuid=snapmirror.uuid)
while smStatus.state == "snapmirrored" and smStatus.transfer.state == "transferring":
    print("Data is being synced from source. Waiting 5 seconds..")
    time.sleep(5)
    smStatus = SnapmirrorRelationship.find(uuid=snapmirror.uuid)
    if (smStatus.state == "snapmirrored" and smStatus.transfer.state == "success"):
        print("Data Sync complete from source")

print("Breaking the SnapMirror Relationship")    
if snapmirror.state == "snapmirrored":
    update_snapmirror_state(snapmirror, "broken_off")

handle_netapp_error(
    create_clone, "retrieving parent volume details", svm_uuid, vol_name, clone_name)
