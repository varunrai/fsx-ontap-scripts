#!/usr/bin/env python3

from netapp_ontap import config, HostConnection, NetAppRestError
from netapp_ontap.resources import NfsService, LdapService, NameMapping, CifsShare, UnixUser, UnixGroup, CifsShareAcl, Svm
import logging
import time

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OntapHPCConfig:
    def __init__(self, hostname, username, password, vserver_name, domain, base_dn, bind_dn,
                 volume_share_name, volume_path,
                 unix_user_name, unix_user_id, unix_user_gid,
                 unix_group_name, unix_group_id):
        self.hostname = hostname
        self.vserver_name = vserver_name
        self.domain = domain
        self.base_dn = base_dn
        self.bind_dn = bind_dn
        self.volume_share_name = volume_share_name
        self.volume_path = volume_path
        self.unix_user_name = unix_user_name
        self.unix_user_id = unix_user_id
        self.unix_user_gid = unix_user_gid
        self.unix_group_name = unix_group_name
        self.unix_group_id = unix_group_id
        
        # Configure connection
        config.CONNECTION = HostConnection(
            hostname, username=username, password=password, verify=False
        )
    
    def modify_nfs_service(self):
        """Modify NFS service settings"""
        try:
            logger.info("Modifying NFS service...")
            nfs_service = NfsService.find(svm={"name": self.vserver_name})
            
            # Modify NFS settings
            nfs_service.v4_id_domain = f"{self.domain}"
            nfs_service.protocol.v4_enabled = True  
            nfs_service.protocol.v3_enabled = True  2
            
            nfs_service.patch()
            logger.info("✓ NFS service modified successfully")
            
        except NetAppRestError as err:
            logger.error(f"Error modifying NFS service: {err}")
    
    def create_ldap_configuration(self):
        """Create LDAP service configuration"""
        try:
            logger.info("Configuring LDAP service...")
            
            # Check if LDAP service exists
            existing_services = list(LdapService.get_collection(
                **{"svm.name": self.vserver_name}
            ))
            
            if existing_services:
                logger.info("LDAP service already exists, modifying configuration...")
                ldap_service = LdapService.find(svm={"name": self.vserver_name})
                
                # Update existing LDAP service
                ldap_service.base_dn = self.base_dn
                ldap_service.ad_domain = self.domain
                ldap_service.schema = "AD-IDMU"
                ldap_service.port = 389
                ldap_service.ldap_enabled = True
                
                ldap_service.patch()
                logger.info("✓ LDAP service modified successfully")
            else:
                # Create new LDAP service
                ldap_service = LdapService(
                    svm={"name": self.vserver_name},
                    base_dn=self.base_dn,
                    ad_domain=self.domain,
                    schema="AD-IDMU",
                    port=389,
                    bind_dn=self.bind_dn, 
                    ldap_enabled=True
                )
                
                ldap_service.post()
                logger.info("✓ LDAP service created successfully")
            
            # Wait for LDAP service to be ready
            time.sleep(5)
            
        except NetAppRestError as err:
            logger.error(f"Error configuring LDAP service: {err}")
    
    def modify_ns_switch(self):
        """Modify name service switch configuration using Svm resource"""
        try:
            logger.info("Modifying name service switch...")
            
            # Get the SVM resource
            svm = Svm.find(name=self.vserver_name)
            if not svm:
                logger.warning("SVM not found: %s", self.vserver_name)
                return
            
            # Define the sources for each database
            sources = ["files", "ldap"]         

            svm.nsswitch = {
                "passwd": sources,
                "group": sources,
                "namemap": sources
            }
            
            svm.patch()
            logger.info("✓ Name service switch modified successfully")
            
        except NetAppRestError as err:
            logger.error(f"Error modifying name service switch: {err}")
        except Exception as err:
            logger.error(f"Unexpected error modifying name service switch: {err}")
    
    def create_name_mappings(self):
        """Create name mappings for Windows-UNIX user mapping"""
        try:
            logger.info("Creating name mappings...")
            
            # Check if mappings already exist
            existing_mappings = list(NameMapping.get_collection(
                **{"svm.name": self.vserver_name}
            ))
            
            # Populate fields for each mapping
            for mapping in existing_mappings:
                mapping.get()
            
            # Create win-unix mapping
            win_unix_pattern = f"{self.domain}\\\\(.+)"
            win_unix_exists = any(m.pattern == win_unix_pattern for m in existing_mappings)
            
            if not win_unix_exists:
                win_unix_mapping = NameMapping(
                    svm={"name": self.vserver_name},
                    direction="win_unix",
                    pattern=win_unix_pattern,
                    replacement="\\1",
                    index=1
                )
                win_unix_mapping.post()
                logger.info("✓ Windows to UNIX name mapping created")
            else:
                logger.info("Windows to UNIX mapping already exists")
            
            # Create unix-win mapping
            unix_win_pattern = "(.+)"
            unix_win_exists = any(m.pattern == unix_win_pattern for m in existing_mappings)
            
            if not unix_win_exists:
                unix_win_mapping = NameMapping(
                    svm={"name": self.vserver_name},
                    direction="unix_win", 
                    pattern=unix_win_pattern,
                    replacement=f"{self.domain}\\\\\\1",
                    index=1
                )
                unix_win_mapping.post()
                logger.info("✓ UNIX to Windows name mapping created")
            else:
                logger.info("UNIX to Windows mapping already exists")
            
        except NetAppRestError as err:
            logger.error(f"Error creating name mappings: {err}")
    
    def create_cifs_share(self):
        """Create CIFS share"""
        try:
            logger.info("Creating CIFS share...")
            
            # Check if share exists
            existing_shares = list(CifsShare.get_collection(
                **{"svm.name": self.vserver_name, "name": self.volume_share_name}
            ))
            
            if not existing_shares:
                # Create share
                share = CifsShare(
                    svm={"name": self.vserver_name},
                    name=self.volume_share_name,
                    path=self.volume_path,
                    properties=["browsable", "showsnapshot"]
                )
                share.post()
                logger.info(f"✓ CIFS share '{self.volume_share_name}' created successfully")
            else:
                logger.info(f"CIFS share '{self.volume_share_name}' already exists")
            
            # Show share details
            shares = list(CifsShare.get_collection(
                **{"svm.name": self.vserver_name, "name": self.volume_share_name}
            ))
            
            for share in shares:
                share.get()
                logger.info(f"Share details: Name={share.name}, Path={share.path}")
                
        except NetAppRestError as err:
            logger.error(f"Error creating CIFS share: {err}")
    
    def create_unix_user(self):
        """Create UNIX user"""
        try:
            logger.info("Creating UNIX user...")
            
            # Check if user exists
            try:
                UnixUser.find(svm={"name": self.vserver_name}, name=self.unix_user_name)
                logger.info(f"UNIX user '{self.unix_user_name}' already exists")
            except NetAppRestError:
                # User doesn't exist, create it
                user = UnixUser(
                    svm={"name": self.vserver_name},
                    name=self.unix_user_name,
                    id=self.unix_user_id,
                    primary_gid=self.unix_user_gid
                )
                user.post()
                logger.info(f"✓ UNIX user '{self.unix_user_name}' created successfully")
            
        except NetAppRestError as err:
            logger.error(f"Error creating UNIX user: {err}")
    
    def create_unix_group(self):
        """Create UNIX group"""
        try:
            logger.info("Creating UNIX group...")
            
            # Check if group exists
            try:
                UnixGroup.find(svm={"name": self.vserver_name}, name=self.unix_group_name)
                logger.info(f"UNIX group '{self.unix_group_name}' already exists")
            except NetAppRestError:
                # Group doesn't exist, create it
                group = UnixGroup(
                    svm={"name": self.vserver_name},
                    name=self.unix_group_name, 
                    id=self.unix_group_id
                )
                group.post()
                logger.info(f"✓ UNIX group '{self.unix_group_name}' created successfully")
            
        except NetAppRestError as err:
            logger.error(f"Error creating UNIX group: {err}")
    
    def create_ad_group_mapping(self):
        """Create Windows AD group to UNIX group mapping"""
        try:
            logger.info("Creating AD group mapping...")
            
            pattern = f"{self.domain}\\\\{self.unix_group_name}"
            
            # Check if mapping exists
            existing_mappings = list(NameMapping.get_collection(
                **{"svm.name": self.vserver_name, "direction": "win_unix"}
            ))
            
            # Populate fields for each mapping
            for mapping in existing_mappings:
                mapping.get()
            
            mapping_exists = any(m.pattern == pattern for m in existing_mappings)
            
            if not mapping_exists:
                mapping = NameMapping(
                    svm={"name": self.vserver_name},
                    direction="win_unix",
                    pattern=pattern,
                    replacement=self.unix_group_name,
                    index=2
                )
                mapping.post()
                logger.info("✓ AD group mapping created successfully")
            else:
                logger.info("AD group mapping already exists")
            
        except NetAppRestError as err:
            logger.error(f"Error creating AD group mapping: {err}")
    
    def configure_share_permissions(self):
        """Configure share permissions for the share"""
        try:
            # Remove Everyone access if it exists
            try:
                everyone_acl = CifsShareAcl.find(
                    svm={"name": self.vserver_name},
                    share=self.volume_share_name,
                    user_or_group="Everyone"
                )
                everyone_acl.delete()
                logger.info("✓ Removed Everyone access")
            except NetAppRestError:
                logger.info("Everyone access not found or already removed")
            
            # Add design_share group with full control
            try:
                CifsShareAcl.find(
                    svm={"name": self.vserver_name},
                    share=self.volume_share_name,
                    user_or_group=self.unix_group_name
                )
                logger.info(f"{self.unix_group_name} group permission already exists")
            except NetAppRestError:
                design_acl = CifsShareAcl(
                    svm={"name": self.vserver_name},
                    share=self.volume_share_name,
                    user_or_group=self.unix_group_name,
                    permission="full_control"
                )
                design_acl.post()
                logger.info(f"✓ Added {self.unix_group_name} group with full control")
            
            # Add Administrators with full control
            try:
                CifsShareAcl.find(
                    svm={"name": self.vserver_name},
                    share=self.volume_share_name,
                    user_or_group="BUILTIN\\Administrators"
                )
                logger.info("Administrators permission already exists")
            except NetAppRestError:
                admin_acl = CifsShareAcl(
                    svm={"name": self.vserver_name},
                    share="design_share",
                    user_or_group="BUILTIN\\Administrators",
                    permission="full_control"
                )
                admin_acl.post()
                logger.info("✓ Added BUILTIN\\Administrators with full control")
            
        except NetAppRestError as err:
            logger.error(f"Error configuring share permissions: {err}")
    
    def run_all_configurations(self):
        """Execute all configurations in sequence"""
        logger.info(f"Starting ONTAP configuration for vserver: {self.vserver_name}")
        
        # Execute configurations in order
        self.modify_nfs_service()
        self.create_ldap_configuration()
        self.modify_ns_switch()  
        self.create_name_mappings()
        self.create_unix_user()
        self.create_unix_group()
        self.create_ad_group_mapping()
        self.create_cifs_share()
        
        logger.info("✓ All configurations completed!")

def main():
    # Configuration - Update these values for your environment
    HOSTNAME = "---ManagementEndpoint---"
    USERNAME = "fsxadmin"
    PASSWORD = "---ManagementPassword---"
    VSERVER_NAME = "fsx"
    DOMAIN = "ad.fsxn.com"
    BASE_DN = "DC=ad,DC=fsxn,DC=com"
    
    # Volume and share configuration
    VOLUME_SHARE_NAME = "vol1"
    VOLUME_PATH = "/vol1"
    
    # UNIX user configuration
    UNIX_USER_NAME = "unix_user_to_create"
    UNIX_USER_ID = 123
    UNIX_USER_GID = 456
    
    # UNIX group configuration
    UNIX_GROUP_NAME = "unix_group_to_create"
    UNIX_GROUP_ID = 123456
    
    # Create configurator instance
    configurator = OntapHPCConfig(
        hostname=HOSTNAME,
        username=USERNAME,
        password=PASSWORD,
        vserver_name=VSERVER_NAME,
        domain=DOMAIN,
        base_dn=BASE_DN,
        bind_dn=f"cn=ldapuser,cn=users,{BASE_DN}",
        volume_share_name=VOLUME_SHARE_NAME,
        volume_path=VOLUME_PATH,
        unix_user_name=UNIX_USER_NAME,
        unix_user_id=UNIX_USER_ID,
        unix_user_gid=UNIX_USER_GID,
        unix_group_name=UNIX_GROUP_NAME,
        unix_group_id=UNIX_GROUP_ID
    )
    
    # Run all configurations
    configurator.run_all_configurations()

if __name__ == "__main__":
    main()
