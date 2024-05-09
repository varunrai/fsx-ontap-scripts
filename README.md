# fsx-ontap-scripts
Various automation scripts for Amazon FSx for NetApp ONTAP

## [sm-dp-volume-clone.py](/python/sm-dp-volume-clone.py) - The script allows a DP volume in a SnapMirror Relationship to be cloned for testing. 
- Check for the SnapMirror Relationship for the Destination Volume
- Check and Delete Clones (created previously)
- Resync SnapMirror if in Broken-Off state
- Wait for sync to complete
- Break the SnapMirror Relationship
- Create Clone