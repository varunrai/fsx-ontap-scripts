# fsx-ontap-scripts
Various automation scripts for Amazon FSx for NetApp ONTAP

## [sm-dp-volume-clone.py](/python/sm-dp-volume-clone.py) - The script allows a DP volume in a SnapMirror Relationship to be cloned for testing. 
- Check for the SnapMirror Relationship for the Destination Volume
- Check and Delete Clones (created previously)
- Resync SnapMirror if in Broken-Off state
- Wait for sync to complete
- Break the SnapMirror Relationship
- Create Clone

> [!NOTE]
> There are several ways of creating a clone one of which does not require breaking the SnapMirror relationship. This scenario is meant for non-prod environments where continuity of SnapMirror is not essential and the environment requires the latest data when performing the clone refresh.


## [svm-create-and-configure.sh](/shell/svm-create-and-configure.sh) - The script creates an SVM through commandline, adds the preferred DC, and configures the file system administrators group. 

> [!NOTE]
> The script assumes that AWS CLI is already installed and SVM is to be configured with Active Directory