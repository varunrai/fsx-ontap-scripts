# fsx-ontap-scripts
Various automation scripts for Amazon FSx for NetApp ONTAP

## [ontap-ad-config.py](/python/ad-config/ontap-ad-config.py) - The script automates ONTAP configuration for Active Directory integrated/multi-protocol environments
- Modify NFS service settings (NFSv3/v4, ID domain)
- Create and configure LDAP service with AD integration
- Configure name service switch (nsswitch) for LDAP and files
- Create Windows-to-UNIX and UNIX-to-Windows name mappings
- Create CIFS shares for UNIX-style volumes
- Create UNIX users and groups
- Configure AD group to UNIX group mappings
- Set up CIFS share permissions with AD integration

> [!NOTE]
> The script requires the NetApp ONTAP Python SDK (`netapp-ontap` package). All configuration parameters (hostname, credentials, SVM name, domain, volume paths, user/group names and IDs) are configurable in the main() function. The script is designed for environments requiring multi-protocol (NFS/CIFS) access with Active Directory authentication.


## [sm-dp-volume-clone.py](/python/sm-dp-volume-clone.py) - The script allows a DP volume in a SnapMirror Relationship to be cloned for testing. 
- Check for the SnapMirror Relationship for the Destination Volume
- Check and Delete Clones (created previously)
- Resync SnapMirror if in Broken-Off state
- Wait for sync to complete
- Break the SnapMirror Relationship
- Create Clone

> [!NOTE]
> There are several ways of creating a clone one of which does not require breaking the SnapMirror relationship. This scenario is meant for non-prod environments where continuity of SnapMirror is not essential and the environment requires the latest data when performing the clone refresh.


## [svm-create-and-configure.sh](/shell/svm-create-and-configure.sh) - The script creates an SVM through commandline
- Create the SVM using the AWS CLI
- Adds the Preferred DC
- Configure the file system administrators group

> [!NOTE]
> The script assumes that AWS CLI is already installed and SVM is to be configured with Active Directory
