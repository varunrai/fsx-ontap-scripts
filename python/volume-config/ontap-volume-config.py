#!/usr/bin/env python3

from netapp_ontap import config, HostConnection, NetAppRestError
from netapp_ontap.resources import Volume
import argparse
import logging
import sys

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class OntapVolumeManager:
    def __init__(self, hostname, username, password, vserver_name):
        self.hostname = hostname
        self.vserver_name = vserver_name
        
        # Configure connection
        config.CONNECTION = HostConnection(
            hostname, username=username, password=password, verify=False
        )
    
    def create_volume(self, volume_name, aggregate_name, size_mb, junction_path=None,
                     security_style="unix", unix_permissions=755, uid=0, gid=0,
                     export_policy="default", snapshot_policy="default"):
        """
        Create a new volume with specified NAS configuration
        
        Args:
            volume_name: Name of the volume
            aggregate_name: Aggregate where volume will be created
            size_mb: Size in MB
            junction_path: Junction path (e.g., /volume_name)
            security_style: unix, ntfs, or mixed
            unix_permissions: UNIX permissions in octal (e.g., 755, 777)
            uid: User ID for volume ownership
            gid: Group ID for volume ownership
            export_policy: Export policy name
            snapshot_policy: Snapshot policy name
        """
        try:
            logger.info(f"Creating volume '{volume_name}'...")
            
            # Check if volume already exists
            existing = list(Volume.get_collection(
                **{"svm.name": self.vserver_name, "name": volume_name}
            ))
            
            if existing:
                logger.warning(f"Volume '{volume_name}' already exists")
                return None
            
            # Set default junction path if not provided
            if junction_path is None:
                junction_path = f"/{volume_name}"
            
            # Create volume with NAS configuration
            volume = Volume(
                svm={"name": self.vserver_name},
                name=volume_name,
                aggregates=[{"name": aggregate_name}],
                size=size_mb * 1024 * 1024,  # Convert MB to bytes
                nas={
                    "path": junction_path,
                    "security_style": security_style,
                    "unix_permissions": unix_permissions,
                    "uid": uid,
                    "gid": gid,
                    "export_policy": {"name": export_policy}
                },
                snapshot_policy={"name": snapshot_policy}
            )
            
            volume.post()
            logger.info(f"✓ Volume '{volume_name}' created successfully")
            logger.info(f"  Junction Path: {junction_path}")
            logger.info(f"  Security Style: {security_style}")
            logger.info(f"  UNIX Permissions: {unix_permissions}")
            logger.info(f"  UID: {uid}, GID: {gid}")
            
            return volume
            
        except NetAppRestError as err:
            logger.error(f"Error creating volume: {err}")
            return None
    
    def update_volume_nas_config(self, volume_name, unix_permissions=None, uid=None, 
                                gid=None, security_style=None, export_policy=None):
        """
        Update NAS configuration on an existing volume
        
        Args:
            volume_name: Name of the volume to update
            unix_permissions: New UNIX permissions (optional)
            uid: New user ID (optional)
            gid: New group ID (optional)
            security_style: New security style (optional)
            export_policy: New export policy (optional)
        """
        try:
            logger.info(f"Updating volume '{volume_name}' NAS configuration...")
            
            # Find the volume
            volume = Volume.find(
                **{"svm.name": self.vserver_name, "name": volume_name}
            )
            
            if not volume:
                logger.error(f"Volume '{volume_name}' not found")
                return False
            
            # Track what we're updating
            updates = []
            
            # Update NAS configuration parameters if provided
            if unix_permissions is not None:
                volume.nas.unix_permissions = unix_permissions
                updates.append(f"UNIX Permissions: {unix_permissions}")
            
            if uid is not None:
                volume.nas.uid = uid
                updates.append(f"UID: {uid}")
            
            if gid is not None:
                volume.nas.gid = gid
                updates.append(f"GID: {gid}")
            
            if security_style is not None:
                volume.nas.security_style = security_style
                updates.append(f"Security Style: {security_style}")
            
            if export_policy is not None:
                volume.nas.export_policy = {"name": export_policy}
                updates.append(f"Export Policy: {export_policy}")
            
            if not updates:
                logger.warning("No updates specified")
                return False
            
            # Apply the changes
            volume.patch()
            
            logger.info(f"✓ Volume '{volume_name}' updated successfully")
            for update in updates:
                logger.info(f"  {update}")
            
            return True
            
        except NetAppRestError as err:
            logger.error(f"Error updating volume: {err}")
            return False
        except AttributeError as err:
            logger.error(f"Error accessing volume attributes: {err}")
            logger.info("Note: Some attributes may not be settable after volume creation")
            return False
    
    def get_volume_info(self, volume_name):
        """Get detailed information about a volume"""
        try:
            logger.info(f"Retrieving volume '{volume_name}' information...")
            
            # Get volume with specific fields to ensure NAS info is retrieved
            volumes = list(Volume.get_collection(
                **{"svm.name": self.vserver_name, "name": volume_name},
                fields="name,size,state,nas,snapshot_policy,aggregates"
            ))
            
            if not volumes:
                logger.error(f"Volume '{volume_name}' not found")
                return None
            
            volume = volumes[0]
            
            logger.info(f"\nVolume Details for '{volume_name}':")
            logger.info(f"SVM: {self.vserver_name}")
            
            if hasattr(volume, 'size'):
                logger.info(f"Size: {volume.size / (1024**3):.2f} GB")
            
            if hasattr(volume, 'state'):
                logger.info(f"State: {volume.state}")
            
            if hasattr(volume, 'aggregates') and volume.aggregates:
                aggr_names = [a.name for a in volume.aggregates if hasattr(a, 'name')]
                if aggr_names:
                    logger.info(f"Aggregate(s): {', '.join(aggr_names)}")
            
            # Display NAS configuration
            if hasattr(volume, 'nas') and volume.nas:
                logger.info(f"\nNAS Configuration:")
                
                if hasattr(volume.nas, 'path'):
                    logger.info(f"Junction Path: {volume.nas.path}")
                
                if hasattr(volume.nas, 'security_style'):
                    logger.info(f"Security Style: {volume.nas.security_style}")
                
                if hasattr(volume.nas, 'unix_permissions'):
                    logger.info(f"UNIX Permissions: {volume.nas.unix_permissions}")
                
                if hasattr(volume.nas, 'uid'):
                    logger.info(f"UID: {volume.nas.uid}")
                
                if hasattr(volume.nas, 'gid'):
                    logger.info(f"GID: {volume.nas.gid}")
                
                if hasattr(volume.nas, 'export_policy') and volume.nas.export_policy:
                    if hasattr(volume.nas.export_policy, 'name'):
                        logger.info(f"Export Policy: {volume.nas.export_policy.name}")
            else:
                logger.info(f"NAS Configuration: Not available")
            
            if hasattr(volume, 'snapshot_policy') and volume.snapshot_policy:
                if hasattr(volume.snapshot_policy, 'name'):
                    logger.info(f"Snapshot Policy: {volume.snapshot_policy.name}")
            
            return volume
            
        except NetAppRestError as err:
            logger.error(f"Error retrieving volume information: {err}")
            return None
    
    def list_volumes(self):
        """List all volumes in the SVM"""
        try:
            logger.info(f"Listing volumes for SVM '{self.vserver_name}'...")
            
            volumes = list(Volume.get_collection(
                **{"svm.name": self.vserver_name},
                fields="name,size,state,nas.path,nas.security_style,nas.unix_permissions,nas.uid,nas.gid"
            ))
            
            if not volumes:
                logger.info("No volumes found")
                return []
            
            logger.info(f"Found {len(volumes)} volume(s):")
            for vol in volumes:
                vol.get()
                size_gb = vol.size / (1024**3) if hasattr(vol, 'size') else 0
                logger.info(f"  - {vol.name} ({size_gb:.2f} GB)")
                
                if hasattr(vol, 'nas') and vol.nas:
                    logger.info(f"    Path: {getattr(vol.nas, 'path', 'N/A')}, "
                              f"Style: {getattr(vol.nas, 'security_style', 'N/A')}, "
                              f"Perms: {getattr(vol.nas, 'unix_permissions', 'N/A')}, "
                              f"GID: {getattr(vol.nas, 'gid', 'N/A')}")
            
            return volumes
            
        except NetAppRestError as err:
            logger.error(f"Error listing volumes: {err}")
            return []


def main():
    parser = argparse.ArgumentParser(description='ONTAP Volume Configuration Manager')
    parser.add_argument('--host', required=True, help='ONTAP management hostname or IP')
    parser.add_argument('--user', required=True, help='ONTAP username')
    parser.add_argument('--password', required=True, help='ONTAP password')
    parser.add_argument('--svm', required=True, help='SVM (vserver) name')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Create volume command
    create_parser = subparsers.add_parser('create', help='Create a new volume')
    create_parser.add_argument('--name', required=True, help='Volume name')
    create_parser.add_argument('--aggregate', required=True, help='Aggregate name')
    create_parser.add_argument('--size', type=int, required=True, help='Size in MB')
    create_parser.add_argument('--junction-path', help='Junction path (default: /volume_name)')
    create_parser.add_argument('--security-style', default='unix', 
                              choices=['unix', 'ntfs', 'mixed'], help='Security style')
    create_parser.add_argument('--unix-permissions', help='UNIX permissions (e.g., ---rwxrwx---). Use = for symbolic: --unix-permissions=rwxrwxr--')
    create_parser.add_argument('--uid', type=int, default=0, help='User ID')
    create_parser.add_argument('--gid', type=int, default=0, help='Group ID')
    create_parser.add_argument('--export-policy', default='default', help='Export policy name')
    create_parser.add_argument('--snapshot-policy', default='default', help='Snapshot policy name')
    
    # Update volume command
    update_parser = subparsers.add_parser('update', help='Update volume NAS configuration')
    update_parser.add_argument('--name', required=True, help='Volume name')
    update_parser.add_argument('--unix-permissions', help='New UNIX permissions (e.g., ---rwxrwx---). Use = for symbolic: --unix-permissions=rwxrwxr--')
    update_parser.add_argument('--uid', type=int, help='New User ID')
    update_parser.add_argument('--gid', type=int, help='New Group ID')
    update_parser.add_argument('--security-style', choices=['unix', 'ntfs', 'mixed'], 
                              help='New security style')
    update_parser.add_argument('--export-policy', help='New export policy name')
    
    # Info command
    info_parser = subparsers.add_parser('info', help='Get volume information')
    info_parser.add_argument('--name', required=True, help='Volume name')
    
    # List command
    subparsers.add_parser('list', help='List all volumes')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Create volume manager
    manager = OntapVolumeManager(
        hostname=args.host,
        username=args.user,
        password=args.password,
        vserver_name=args.svm
    )
    
    # Execute command
    if args.command == 'create':
        unix_perms = args.unix_permissions
        manager.create_volume(
            volume_name=args.name,
            aggregate_name=args.aggregate,
            size_mb=args.size,
            junction_path=args.junction_path,
            security_style=args.security_style,
            unix_permissions=unix_perms,
            uid=args.uid,
            gid=args.gid,
            export_policy=args.export_policy,
            snapshot_policy=args.snapshot_policy
        )
    
    elif args.command == 'update':
        unix_perms = args.unix_permissions
        manager.update_volume_nas_config(
            volume_name=args.name,
            unix_permissions=unix_perms,
            uid=args.uid,
            gid=args.gid,
            security_style=args.security_style,
            export_policy=args.export_policy
        )
    
    elif args.command == 'info':
        manager.get_volume_info(args.name)
    
    elif args.command == 'list':
        manager.list_volumes()


if __name__ == "__main__":
    main()
