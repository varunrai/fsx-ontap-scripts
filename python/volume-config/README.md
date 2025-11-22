# ONTAP Volume Configuration Script

This script provides comprehensive volume management for FSx for NetApp ONTAP with full NAS configuration support.

## Features

- **Create volumes** with NAS parameters (UNIX permissions, UID/GID, security style)
- **Update existing volumes** with new NAS configuration
- **View volume details** including all NAS settings
- **List all volumes** with their configurations

## Requirements

```bash
pip install netapp-ontap
```

## Usage

### Create a New Volume

```bash
python ontap-volume-config.py \
  --host 10.0.1.156 \
  --user fsxadmin \
  --password YourPassword \
  --svm fsx \
  create \
  --name vol1 \
  --aggregate aggr1 \
  --size 10240 \
  --junction-path /vol1 \
  --security-style unix \
  --unix-permissions=---rwxrwx--- \
  --uid 0 \
  --gid 1000 \
  --export-policy default
```

### Update Volume NAS Configuration

```bash
python ontap-volume-config.py \
  --host 10.10.10.10 \
  --user fsxadmin \
  --password FILESYSTEM_PWD \
  --svm fsx \
  update \
  --name vol1 \
  --unix-permissions=---rwxrwx--- \
  --gid 2000
```

### Get Volume Information

```bash
python ontap-volume-config.py \
  --host 10.10.10.10 \
  --user fsxadmin \
  --password FILESYSTEM_PWD \
  --svm fsx \
  info \
  --name vol1
```

### List All Volumes

```bash
python ontap-volume-config.py \
  --host 10.0.1.156 \
  --user fsxadmin \
  --password YourPassword \
  --svm fsx \
  list
```

## Parameters

Full list of parameters refer to the docs - https://library.netapp.com/ecmdocs/ECMLP3351667/html/resources/volume.html


## Examples

### Create a volume for HPC workloads

```bash
python ontap-volume-config.py \
  --host 10.10.10.10 --user fsxadmin --password FILESYSTEM_PWD --svm fsx \
  create --name vol1 --aggregate aggr1 --size 512GB \
  --security-style unix --unix-permissions=---rwxrwx--- --gid 5000
```

### Update permissions for a shared volume

```bash
python ontap-volume-config.py \
  --host 10.10.10.10 --user fsxadmin --password FILESYSTEM_PWD --svm fsx \
  update --name vol1 --unix-permissions=---rwxrwx--- --gid 1001
```

### Check volume configuration

```bash
python ontap-volume-config.py \
  --host 10.10.10.10 --user fsxadmin --password FILESYSTEM_PWD --svm fsx \
  info --name vol1
```
