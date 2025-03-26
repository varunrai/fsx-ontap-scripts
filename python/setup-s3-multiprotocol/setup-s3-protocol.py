import requests
import urllib3
from requests.auth import HTTPBasicAuth
from InquirerPy import inquirer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

from rich.live import Live
from rich.table import Table

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration Parameters
CLUSTER_IP = '10.0.1.14'
USERNAME = 'fsxadmin'
PASSWORD = 'SuperSecretPassw0rd'
AGGREGATE = 'aggr1'
S3_USER = 's3user'
REQUEST_TIMEOUT = 60

# API Configuration
HEADERS = {'Content-Type': 'application/json', 'Accept': 'application/json'}

# Rich console instance
console = Console()


class ONTAPS3:
    BASE_URL = None
    AUTH = None

    def __init__(self, base_url, auth):
        self.BASE_URL = base_url
        self.AUTH = auth

    def get_svms(self):
        """Retrieve SVMs"""
        url = f"{self.BASE_URL}/svm/svms?fields=cifs.ad_domain.fqdn,cifs.enabled,cifs.allowed&return_records=true&return_timeout={REQUEST_TIMEOUT}"
        response = requests.get(url, headers=HEADERS,
                                auth=self.AUTH, verify=False)
        return response.json().get('records', [{}]) if response.ok else None

    def get_svm_cifs_info(self):
        """Retrieve SVM CIFS Information"""
        url = f"{self.BASE_URL}/svm/svms?fields=cifs.ad_domain.fqdn,cifs.enabled,cifs.allowed&return_records=true&return_timeout={REQUEST_TIMEOUT}"
        response = requests.get(url, headers=HEADERS,
                                auth=self.AUTH, verify=False)
        return response.json() if response.ok else None

    def get_svm_uuid(self, svm_name):
        """Retrieve SVM UUID by name"""
        url = f"{self.BASE_URL}/svm/svms?name={svm_name}"
        response = requests.get(url, headers=HEADERS,
                                auth=self.AUTH, verify=False)
        return response.json().get('records', [{}])[0].get('uuid') if response.ok else None

    def get_volumes_by_svm(self, svm_uuid):
        """Retrieve list of volumes for a specified SVM UUID"""
        url = f"{self.BASE_URL}/storage/volumes?svm.uuid={svm_uuid}&is_constituent=false&is_object_store=false&is_svm_root=false&fields=nas.path&return_records=true&return_timeout={REQUEST_TIMEOUT}"
        response = requests.get(url, headers=HEADERS,
                                auth=self.AUTH, verify=False)
        return response.json().get('records', []) if response.ok else []

    def get_svm_domain_info(self, svm_uuid):
        """Retrieve SVM CIFS Information"""
        url = f"{self.BASE_URL}/protocols/cifs/services/{svm_uuid}"
        response = requests.get(url, headers=HEADERS,
                                auth=self.AUTH, verify=False)
        return response.json() if response.ok else None

    def create_s3_certificate(self, svm_uuid, common_name):
        """Create self-signed certificate for S3"""
        url = f"{self.BASE_URL}/security/certificates?return_records=true"
        payload = {
            "common_name": common_name,
            "type": "server",           # Certificate type for S3 service
            "svm": {"uuid": svm_uuid}   # Ties certificate to SVM
        }
        response = requests.post(
            url, json=payload, headers=HEADERS, auth=self.AUTH, verify=False)
        return response.json().get('records', [])[0] if response.ok else []

    def get_s3_certificates(self, svm_uuid):
        """Get certificate for S3"""
        url = f"{self.BASE_URL}/security/certificates?svm.uuid={svm_uuid}&type=server&fields=uuid,common-name,serial_number"

        response = requests.get(
            url, headers=HEADERS, auth=self.AUTH, verify=False)
        return response.json().get('records', []) if response.ok else []

    def get_s3_certificate(self, cert_uuid):
        """Get certificate for S3"""
        url = f"{self.BASE_URL}/security/certificates?uuid={cert_uuid}&type=server&fields=uuid,common-name,serial_number"

        response = requests.get(
            url, headers=HEADERS, auth=self.AUTH, verify=False)
        return response.json().get('records', [{}])[0] if response.ok else []

    def create_object_server(self, s3_server_name, cert_uuid, svm_uuid):
        """Create Object Server"""
        url = f"{self.BASE_URL}/protocols/s3/services?return_records=true"
        payload = {
            "certificate": {
                "uuid": cert_uuid
            },
            "comment": s3_server_name,
            "enabled": True,
            "is_http_enabled": True,
            "is_https_enabled": True,
            "name": s3_server_name,
            "port": 80,
            "secure_port": 443,
            "svm": {
                "uuid": svm_uuid
            }
        }

        response = requests.post(
            url, json=payload, headers=HEADERS, auth=self.AUTH, verify=False)
        if response.ok:
            console.print(Panel.fit(
                f"Object Server Created: {s3_server_name}", title="Operation Status"))
            return response.json().get('records', [])[0]
        else:
            console.print(Panel.fit(
                f"Object Server Creation Failed", title="Operation Status"))
            return []

    def get_s3_object_servers(self):
        """Get all S3 Object Servers"""
        url = f"{self.BASE_URL}/protocols/s3/services?fields=name,enabled,is_http_enabled,is_https_enabled,port,secure_port," \
            "svm.uuid,svm.name,certificate.uuid,certificate.name,buckets.nas_path,buckets.name,buckets.uuid," \
            f"buckets.volume.name,buckets.volume.uuid,buckets.type,buckets.comment&return_records=true&return_timeout={REQUEST_TIMEOUT}"

        response = requests.get(
            url, headers=HEADERS, auth=self.AUTH, verify=False)
        return response.json().get('records', []) if response.ok else []

    def get_s3_object_server(self, svm_uuid):
        """Get S3 Object Server"""
        url = f"{self.BASE_URL}/protocols/s3/services?svm.uuid={svm_uuid}&fields=name,enabled&return_records=true&return_timeout={REQUEST_TIMEOUT}"

        response = requests.get(
            url, headers=HEADERS, auth=self.AUTH, verify=False)
        return response.json().get('records', [])[0] if response.ok else []

    def create_bucket(self, volume, bucket_name):
        """Create a bucket"""
        url = f"{self.BASE_URL}/protocols/s3/buckets?return_records=true&return_timeout=0"

        payload = {
            "comment": f"Bucket for {volume.get('name')}",
            "name": bucket_name,
            "nas_path": volume.get('nas', 'N/A').get('path', 'N/A'),
            "svm": {
                "uuid": volume.get('svm').get('uuid')
            },
            "type": "nas"
        }

        response = requests.post(
            url, json=payload, headers=HEADERS, auth=self.AUTH, verify=False)

        return response.json().get('records', [])[0] if response.ok else []


class Display:
    def object_server_details(self, object_server):
        """Display Object Server details in a rich panel"""
        detail_table = Table.grid(padding=1)
        detail_table.add_column(style="bold cyan")
        detail_table.add_column(style="bold green")

        detail_table.add_row("Name:", object_server.get('name', 'N/A'))
        detail_table.add_row(
            "Enabled:", f"{object_server.get('enabled', 'N/A')}")
        detail_table.add_row("Http Port:", str(
            object_server.get('port', 'N/A')))
        detail_table.add_row(
            "Http Enabled:", f"{object_server.get('is_http_enabled', 'N/A')}")
        detail_table.add_row(
            "Https Port:", str(object_server.get('secure_port', 'N/A')))
        detail_table.add_row(
            "Https Enabled:", f"{object_server.get('is_http_enabled', 'N/A')}")

        panels = []
        if not (object_server.get('buckets', [])):
            bucket_table = Table.grid(padding=1)
            bucket_table.add_row("[blue]No buckets found[/blue]")
            panels.append(bucket_table)

        for bucket in object_server.get('buckets', []):
            bucket_table = Table.grid(padding=1)
            bucket_table.add_column(style="bold cyan")
            bucket_table.add_column(style="bold green")
            bucket_table.add_row("NAS Path:", bucket.get('nas_path', 'N/A'))
            bucket_table.add_row("Volume:", bucket.get(
                'volume', {}).get('name', 'N/A'))
            bucket_table.add_row("Volume UUID:", bucket.get(
                'volume', {}).get('uuid', 'N/A'))
            bucket_table.add_row("Comment:", bucket.get('comment', 'N/A'))
            panels.append(Panel.fit(bucket_table,
                                    title=f"[bold]Bucket - {bucket.get('name', 'N/A')}[/bold]",
                                    border_style="bright_yellow"))

        detail_table.add_row("Buckets:", "")
        for panel in panels:
            detail_table.add_row("", panel)

        console.print(Panel.fit(detail_table,
                                title="[bold]Object Server Details[/bold]",
                                border_style="bright_yellow"))

    def volume_details(self, volume):
        """Display volume details in a rich panel"""
        detail_table = Table.grid(padding=1)
        detail_table.add_column(style="bold cyan")
        detail_table.add_column(style="bold green")

        detail_table.add_row("Name:", volume.get('name', 'N/A'))
        detail_table.add_row("UUID:", volume.get('uuid', 'N/A'))

        if ((volume.get('nas', 'N/A') == 'N/A') or
            (volume.get('nas', 'N/A') != 'N/A' and
                volume.get('nas', 'N/A').get('path', 'N/A') == 'N/A')):
            detail_table.add_row("Junction Path:", "N/A")
        else:
            detail_table.add_row("Junction Path:", volume.get(
                'nas', 'N/A').get('path', 'N/A'))
        console.print(Panel.fit(detail_table,
                                title="[bold]Volume Details[/bold]",
                                border_style="bright_yellow"))

    def svm_info_table(self, svm, cifs_info, object_server=None):
        """Display SVM information in a rich panel"""
        svm_table = Table.grid(
            pad_edge=True, expand=True, collapse_padding=True)
        svm_table.add_row(
            f"[bold][bright_blue]SVM Name:[/bright_blue][/bold] [dodger_blue3]{svm.get('name','N/A')}[/dodger_blue3]")
        svm_table.add_row(
            f"[bold][bright_blue]SVM UUID:[/bright_blue][/bold] [dodger_blue3]{svm.get('uuid','N/A')}[/dodger_blue3]")

        if svm['cifs']['allowed'] == True and svm['cifs'].get('enabled', False) == True:
            svm_table.add_row(
                f"[bold][bright_blue]AD Domain:[/bright_blue][/bold] [dodger_blue3]{svm['cifs']['ad_domain']['fqdn']}[/dodger_blue3]")
            if cifs_info:
                svm_table.add_row(
                    f"[bold][bright_blue]AD or Workgroup:[/bright_blue][/bold] [dodger_blue3]{cifs_info.get('domain_workgroup')}[/dodger_blue3]")
                svm_table.add_row(
                    f"[bold][bright_blue]FQDN:[/bright_blue][/bold] [dodger_blue3]{cifs_info.get('name')}.{cifs_info['ad_domain']['fqdn']}[/dodger_blue3]")

        if (object_server):
            detail_table = Table.grid(pad_edge=True, padding=(0, 1))
            detail_table.add_column(style="bold bright_yellow")
            detail_table.add_column(style="bold dodger_blue3")

            detail_table.add_row("Name:", object_server.get('name', 'N/A'))
            detail_table.add_row(
                "Enabled:", f"{object_server.get('enabled', 'N/A')}")
            detail_table.add_row("Http Port:", str(
                object_server.get('port', 'N/A')))
            detail_table.add_row(
                "Http Enabled:", f"{object_server.get('is_http_enabled', 'N/A')}")
            detail_table.add_row(
                "Https Port:", str(object_server.get('secure_port', 'N/A')))
            detail_table.add_row(
                "Https Enabled:", f"{object_server.get('is_http_enabled', 'N/A')}")

            panels = []
            if not (object_server.get('buckets', [])):
                bucket_table = Table.grid(padding=0)
                bucket_table.add_row("[blue]No buckets found[/blue]")
                panels.append(bucket_table)

            for bucket in object_server.get('buckets', []):
                bucket_table = Table.grid(
                    pad_edge=True, padding=(0, 0))
                bucket_table.add_column(style="bold purple3")
                bucket_table.add_column(style="bold dodger_blue3")
                bucket_table.add_row(
                    "NAS Path:", bucket.get('nas_path', 'N/A'))
                bucket_table.add_row("Type:", bucket.get('type', 'N/A'))
                bucket_table.add_row("Volume:", bucket.get(
                    'volume', {}).get('name', 'N/A'))
                bucket_table.add_row("Volume UUID:", bucket.get(
                    'volume', {}).get('uuid', 'N/A'))
                bucket_table.add_row("Comment:", bucket.get('comment', 'N/A'))
                panels.append(Panel.fit(bucket_table,
                                        title=f"[bold]\_/ Bucket - {bucket.get('name', 'N/A')}[/bold]",
                                        border_style="purple3"))

            detail_table.add_row("Buckets ==>>", "")
            for panel in panels:
                detail_table.add_row("", panel)

            svm_table.add_row(Panel.fit(detail_table,
                                        title="[bold]Object Server Details[/bold]",
                                        border_style="bright_yellow"))

        # Display SVM information
        console.print(Panel.fit(
            svm_table,
            title="[reverse] Storage Virtual Machine [/]",
            border_style="bright_blue"
        ))

    def build_cert_common_name_suggestions(self, svm, cifs_info):
        suggested_options = []
        suggested_options.append(f"s3.{svm.get('name')}")
        if svm['cifs']['allowed'] == True and svm['cifs'].get('enabled', False) == True:
            suggested_options.append(
                f"s3.{cifs_info.get('name')}.{cifs_info['ad_domain']['fqdn']}")

        suggested_options.append(f"Custom")
        return suggested_options

    def cert_table(self, certificate):
        console.print(Panel.fit(
            f"[bold]Name:[/bold] [cyan]{certificate.get('name', 'N/A')}[/cyan]\n" +
            f"[bold]UUID:[/bold] [cyan]{certificate.get('uuid', 'N/A')}[/cyan]\n" +
            f"[bold]Serial:[/bold] [cyan]{certificate.get('serial_number', 'N/A')}[/cyan]\n" +
            f"[bold]Common Name:[/bold] [cyan]{certificate.get('common_name', 'N/A')}[/cyan]",
            title="[reverse] Certificate [/]",
            border_style="bright_blue"
        ))

    def prompt(self, prompt):
        return inquirer.text(
            message=prompt,
            qmark="📦",
            amark="➤"
        ).execute()

    def secure_prompt(self, prompt):
        return inquirer.secret(
            message=prompt,
            qmark="📦",
            amark="➤"
        ).execute()

    def prompt_options(self, prompt, choices):
        return inquirer.select(
            message=prompt,
            choices=choices,
            qmark="📦",
            amark="➤",
            pointer="👉"
        ).execute()


def main():
    display = Display()

    # Welcome screen
    console.print(Panel.fit(
        Markdown("# Amazon FSx for NetApp ONTAP - Enable S3 Protocol on NAS volumes",
                 style="bold blue"
                 )))

    CLUSTER_IP = display.prompt(
        "[?] Enter the FSxN Management Endpoint Address:")
    USERNAME = display.prompt("[?] Enter the ONTAP Username:")
    PASSWORD = display.secure_prompt("[?] Enter the ONTAP Password:")

    # API Configuration
    BASE_URL = f'https://{CLUSTER_IP}/api'
    AUTH = HTTPBasicAuth(USERNAME, PASSWORD)

    # Initialize ONTAP S3 API
    s3 = ONTAPS3(BASE_URL, AUTH)

    # Get and display SVMs
    if not (svms := s3.get_svms()):
        console.print(Panel("[yellow]No SVMs found[/yellow]",
                            title="Empty Result"))
        return

    while True:
        selected_svm = display.prompt_options(
            "[?] Select a SVM:", [f"{svm['uuid']} ({svm['name']})" for svm in svms]).split(" ")[0]

        svm = next(v for v in svms if v['uuid'] == selected_svm)

        # Get Domain Info
        cifs_info = None
        if svm['cifs']['allowed'] == True and svm['cifs'].get('enabled', False) == True:
            cifs_info = s3.get_svm_domain_info(selected_svm)

        # Get All Object Servers
        object_servers = s3.get_s3_object_servers()
        object_server = next(
            (v for v in object_servers if v['svm']['uuid'] == selected_svm), None)

        display.svm_info_table(svm, cifs_info, object_server)

        if not object_server:
            certificates = s3.get_s3_certificates(selected_svm)
            if not (certificates):
                console.print(Panel("[yellow]No certificates found[/yellow]",
                                    title="Empty Result"))

            if display.prompt("[?] Use Existing Certificate?").lower() == "y":
                selected_certificate = display.prompt_options("[?] Select a Certificate:", (
                    f"{vol['uuid']} ({vol['name']})" for vol in certificates)).split(" ")[0]

                # Find Cert details
                certificate = next(
                    v for v in certificates if v['uuid'] == selected_certificate)
                display.cert_table(certificate)

            else:
                suggested_options = display.build_cert_common_name_suggestions(
                    svm, cifs_info)

                cert_common_name = display.prompt_options(
                    "[?] Suggested Cert Common Name:", suggested_options).split(" ")[0]

                if (cert_common_name == "Custom"):
                    cert_common_name = display.prompt(
                        "[?] Enter Common Name:")

                # Create certificate
                created_cert = s3.create_s3_certificate(
                    selected_svm, cert_common_name)
                certificate = s3.get_s3_certificate(created_cert.get('uuid'))
                display.cert_table(certificate)

            while True:
                object_server_name = display.prompt("[?] Enter the Object Server Name (Note: that the object-store-server name"
                                                    " must not begin with a bucket name. For virtual hosted style (VHS) API access,"
                                                    " you must use the same hostname as the server name configured here.):")

                if not object_server_name:
                    console.print(Panel(
                        "[yellow]Object Server Name cannot be empty![/yellow]", title="Error"))
                    continue

                # Create Object Server
                object_server = s3.create_object_server(
                    object_server_name, certificate.get('uuid'), selected_svm)

                break

        # Get and display volumes
        if not (volumes := s3.get_volumes_by_svm(selected_svm)):
            console.print(Panel("[yellow]No volumes found[/yellow]",
                                title="Empty Result"))
            return

        selected_volume = display.prompt_options(
            "[?] Select a volume to create a bucket:", (f"{vol['uuid']} ({vol['name']})" for vol in volumes)).split(" ")[0]

        # Find full volume details
        volume = next(v for v in volumes if v['uuid'] == selected_volume)
        display.volume_details(volume)

        bucket_name = display.prompt(
            "[?] Enter the Bucket Name:")

        # Create bucket
        bucket = s3.create_bucket(volume, bucket_name)
        if bucket:
            console.print(Panel.fit(
                "[green]Operation completed successfully![/green]", title="Bucket Created"))

        if not display.prompt("[?] Select another SVM?"):
            break

    console.print(Panel(
        "[green]Operation completed successfully![/green]", title="Completion Status"))


if __name__ == "__main__":
    main()
