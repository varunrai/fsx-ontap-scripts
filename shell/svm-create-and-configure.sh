#!/bin/bash

# The script create an SVM using the AWS CLI, add preferred DC, 
# and configures the "File System Administrators Group"

region='<AWS Region>'

domainName='ad.fsxn.com'
ou='OU=FSXN,DC=ad,DC=fsxn,DC=com'
fileAdminGroup='<File System Administrators Group>'
serviceAcc='<AD Service Account User>'
dnsip1='<DNS IP 1>'
dnsip2='<DNS IP 2>'
svmName='<SVM NAME>'
fileSystemId='<File System Id>'
fsxnManagementIP='<File System Management IP>'
svmNetBiosName=$svmName

echo "SVM Creation using script"

echo -n 'Enter the password for '$serviceAcc': '
read -s password
echo
echo -n 'Re-enter the password for '$serviceAcc': '
read -s repassword
echo

if [ $password != $repassword ]; then
       echo "Entered passwords do not match"
       exit;
fi

echo -n 'Enter the password for FileSystem Admin 'fsxadmin': '
read -s fsxpassword
echo

echo "Creating Storage Virtual Machine for ${fileSystemId}"

response=$(aws fsx create-storage-virtual-machine --file-system-id $fileSystemId --name $svmName --active-directory-configuration SelfManagedActiveDirectoryConfiguration='{DomainName="'$domainName'", OrganizationalUnitDistinguishedName="'$ou'", UserName="'$serviceAcc'",Password="'$password'", DnsIps=["'$dnsip1'","'$dnsip2'"]}',NetBiosName=$svmNetBiosName --region $region)

# shellcheck disable=SC2181
if [[ $? -ne 0 ]]; then
        errecho "ERROR: Creating SVM with message: .\n$response"
        return 1
fi

search=0
while [ $search == 0 ]
do
        echo -n "Checking Status.. "
        # Code to be executed
        svm_status=$(aws fsx describe-storage-virtual-machines --region $region --query 'StorageVirtualMachines[?Name==`'$svmName'`].[Name, Lifecycle]' --output text)
        echo -n "{${svm_status}]"
        echo
        if [[ $svm_status == *CREATED* ]]; then
                echo "SVM Created Successfully"

                output=$(curl --request GET "https://$fsxnManagementIP/api/protocols/cifs/local-groups?svm.name=$svmName&name=BUILTIN\\Administrators&fields=name,members" --user fsxadmin:$fsxpassword --insecure)
                svm_uuid=$(echo $output | python3 -c "import sys, json; print(json.load(sys.stdin)['records'][0]['svm']['uuid'])")
                group_uuid=$(echo $output | python3 -c "import sys, json; print(json.load(sys.stdin)['records'][0]['sid'])")

                echo "Adding the Preferred DC"
                curl --request POST "https://$fsxnManagementIP/api/protocols/active-directory/$svm_uuid/preferred-domain-controllers" --user fsxadmin:$fsxpassword --insecure -d '{"fqdn": "'$domain'","server_ip": "'$dnsip1'"}'
                curl --request POST "https://$fsxnManagementIP/api/protocols/active-directory/$svm_uuid/preferred-domain-controllers" --user fsxadmin:$fsxpassword --insecure -d '{"fqdn": "'$domain'","server_ip": "'$dnsip2'"}'

                echo "Adding the DC Discovery Mode"
                curl --request PATCH "https://$fsxnManagementIP/api/protocols/cifs/domains/$svm_uuid" --user fsxadmin:$fsxpassword --insecure -d '{"server_discovery_mode": "none"}'

                echo "Adding the group to File System Administrators Group"
                curl --request POST "https://$fsxnManagementIP/api/protocols/cifs/local-groups/$svm_uuid/$group_uuid/members" --user fsxadmin:$fsxpassword --insecure -d '{"name":"'$domainName'\\'$fileAdminGroup'"}'

                break;
        fi


        if [[ $svm_status == *FAILED* ]]; then
                echo "SVM creation failed"
                break;
        fi

        if [[ $svm_status == *MISCONFIGURED* ]]; then
                echo "SVM creation failed"
                break;
        fi
        sleep 20
done
