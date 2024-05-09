""" Create Clone from a DP Volume in a non-prod environment """
import time
from netapp_ontap import config, HostConnection, NetAppRestError
from netapp_ontap.resources import SnapmirrorRelationship, Volume

FSXN_MANAGEMENT_ENDPOINT = "<FILESYSTEM MANAGMENT ENDPOINT>"
FSXN_USER = "fsxadmin"
FSXN_USER_PWD = "<PASSWORD>"

SVM_NAME = "fsx0svm1"
VOL_NAME = "vol_secondary"
CLONE_NAME = "vol_clone"
CLONE_JUNCTION_PATH = "/vol_clone"

config.CONNECTION = HostConnection(FSXN_MANAGEMENT_ENDPOINT, FSXN_USER, FSXN_USER_PWD, verify=False)

def print_snapmirror_details(snapmirror):
    """ Prints SnapMirror Relationship Info """
    print("Source: " + snapmirror.source.path + " --> Destination: " +
          snapmirror.destination.path + ", UUID: " + snapmirror.uuid + 
          ", Status: " + snapmirror.state)

def update_snapmirror_state(snapmirror, new_state):
    """ Updates SnapMirror Relationship State """
    snapmirror.state = new_state
    if snapmirror.patch(poll=True):
        print("Snapmirror Relationship Updated Successfully to " + new_state)

def handle_netapp_error(action, action_name, *args):
    """ Handles NetApp REST exceptions """
    try:
        return action(*args)
    except NetAppRestError as error:
        print("Exception caught while " + action_name + ": " + str(error))
        raise

def search_snapmirror_relationships():
    """ Find the SnapMirror Relationship for the Destination SVM and Volume name """
    return SnapmirrorRelationship.find(destination={"path": SVM_NAME + ":" + VOL_NAME})

def delete_volume_clones(vol_name):
    """ Delete Volume Clones """
    for volume in Volume.get_collection(**{"clone.is_flexclone": True, "clone.parent_volume.name": vol_name}):
        print("Parent Volume: " + vol_name + " --> Clone: " +
              volume.name + ", Cloned Volume UUID: " + volume.uuid)
        print("Deleting Clone: " + volume.name)
        volume.delete(force=True)

def create_clone(svm_uuid, vol_name, clone_name):
    """ Create Volume Clone """
    print("Retrieving Parent Volume Details")
    parent_volume = Volume.find(name=vol_name)
    print("Creating Clone: " + clone_name)
    tmp = {'uuid': svm_uuid}
    dataobj = {}
    dataobj['svm'] = tmp
    dataobj['name'] = clone_name
    clone_volume_json = 
    {
        "is_flexclone": bool("true"), 
        "parent_svm": 
        {
            "name": SVM_NAME, "uuid": svm_uuid
        }, 
        "parent_volume": 
        {
            "name": parent_volume.name, "uuid": parent_volume.uuid
        }
    }
    dataobj['clone'] = clone_volume_json
    volume = Volume.from_dict(dataobj)
    volume.post(poll=True)


print("Searching for SnapMirror Relationship for Destination SVM: " +
      SVM_NAME + " and Volume: " + VOL_NAME)
snapmirrorRelationship = handle_netapp_error(search_snapmirror_relationships, "searching for SnapMirror Relationships")
print_snapmirror_details(snapmirrorRelationship)

svmUUID = snapmirrorRelationship.destination.svm.uuid
print("Searching for Clones of volume: " + snapmirrorRelationship.destination.path)
handle_netapp_error(delete_volume_clones, "searching for clones", VOL_NAME)


print("Resuming the SnapMirror Relationship")
if snapmirrorRelationship.state == "broken_off":
    update_snapmirror_state(snapmirrorRelationship, "snapmirrored")

print("Checking the sync status")
time.sleep(5)
smStatus = SnapmirrorRelationship.find(uuid=snapmirrorRelationship.uuid)
while smStatus.state == "snapmirrored" and smStatus.transfer.state == "transferring":
    print("Data is being synced from source. Waiting 5 seconds..")
    time.sleep(5)
    smStatus = SnapmirrorRelationship.find(uuid=snapmirrorRelationship.uuid)
    if (smStatus.state == "snapmirrored" and smStatus.transfer.state == "success"):
        print("Data Sync complete from source")

print("Breaking the SnapMirror Relationship")
if snapmirrorRelationship.state == "snapmirrored":
    update_snapmirror_state(snapmirrorRelationship, "broken_off")

handle_netapp_error(
    create_clone, "retrieving parent volume details", svmUUID, VOL_NAME, CLONE_NAME)
