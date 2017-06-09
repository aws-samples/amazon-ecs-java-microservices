#!/bin/python
import argparse
import json
import logging
import os
import time
import uuid
from os.path import expanduser
from random import randint

import boto3

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def delete_ecs_cluster(stack_name):
    cf_client = boto3.client('cloudformation')
    ec2_client = boto3.client('ec2')

    try:
        response = cf_client.delete_stack(StackName=stack_name)
        stack_delete_status = cf_client.describe_stacks(StackName=stack_name)
        logger.info("Delete stack: " + json.dumps(response))
        while stack_delete_status['Stacks'][0]['StackStatus'] == 'DELETE_IN_PROGRESS':
            time.sleep(10)
            stack_delete_status = cf_client.describe_stacks(StackName=stack_name)
            logger.info("Delete stack status: " + stack_delete_status['Stacks'][0]['StackStatus'])
            if stack_delete_status['Stacks'][0]['StackStatus'] == 'DELETE_FAILED':
                logger.warning('Delete failed. Retry delete')
                resources = cf_client.delete_stack(StackName=stack_name)
                return resources
            elif stack_delete_status['Stacks'][0]['StackStatus'] == 'DELETE_IN_PROGRESS':
                continue
            else:
                logger.info("Delete cluster complete")
    except Exception as e:
        logger.error(e)

    try:
        response = ec2_client.delete_key_pair(KeyName=stack_name + 'key')
        logger.info("Delete key: " + json.dumps(response))
    except Exception as e:
        logger.error(e)


def create_ecs_cluster(stack_name):
    cf_client = boto3.client('cloudformation')
    ec2_client = boto3.client('ec2')

    filename = './ecs-cluster.cf'
    with open(filename, 'r+') as f:
        cloudformation_json = json.load(f)

    describe_images_response = ec2_client.describe_images(
        DryRun=False,
        Owners=[
            'amazon',
        ],
        Filters=[
            {
                'Name': 'name',
                'Values': [
                    'amzn-ami-2016.09.f-amazon-ecs-optimized',
                ]
            },
        ]
    )
    try:
        ec2_client.create_key_pair(
            DryRun=False,
            KeyName=stack_name + 'key'
        )
    except Exception as e:
        pass

    try:
        response = cf_client.create_stack(
            StackName=stack_name,
            TemplateBody=json.dumps(cloudformation_json),
            Parameters=[
                {
                    'ParameterKey': 'AsgMaxSize',
                    'ParameterValue': '2',
                    'UsePreviousValue': True
                },
                {
                    'ParameterKey': 'EcsAmiId',
                    'ParameterValue': describe_images_response['Images'][0]['ImageId'],
                    'UsePreviousValue': True
                },
                {
                    'ParameterKey': 'EcsClusterName',
                    'ParameterValue': stack_name,
                    'UsePreviousValue': True
                },
                {
                    'ParameterKey': 'KeyName',
                    'ParameterValue': stack_name + 'key',
                    'UsePreviousValue': True
                },
                {
                    'ParameterKey': 'EcsInstanceType',
                    'ParameterValue': 'm4.large',
                    'UsePreviousValue': True
                },
                {
                    'ParameterKey': 'DBUsername',
                    'ParameterValue': 'PetClinicDB'
                },
                {
                    'ParameterKey': 'DBPassword',
                    'ParameterValue': 'PetClinicPassw0rd'
                }
            ],
            TimeoutInMinutes=123,
            Capabilities=[
                'CAPABILITY_IAM',
            ],
            OnFailure='DELETE',
            Tags=[
                {
                    'Key': 'Name',
                    'Value': stack_name
                },
            ]
        )

    except cf_client.exceptions.AlreadyExistsException:
        logger.warning("CF Stack already exists")
        pass

    stack_create_status = cf_client.describe_stacks(StackName=stack_name)

    resources = cf_client.describe_stack_resources(StackName=stack_name)
    return resources


def create_ecs_cluster_mysql(stack_name, stack_name_ecs_cluster, vpc_id, subnet1, subnet2, role_arns, region):
    cf_client = boto3.client('cloudformation')
    elb_client = boto3.client('elb')
    ecs_client  = boto3.client('ecs')

    filename = './ecs-cluster-mysql.yaml'
    with open(filename, 'r+') as f:
        cf_template = f.read()

    try:
        response = cf_client.create_stack(
            StackName=stack_name,
            TemplateBody=cf_template,
            Parameters=[
                {
                    'ParameterKey': 'AsgMaxSize',
                    'ParameterValue': '2'
                },
                {
                    'ParameterKey': 'DesiredCapacity',
                    'ParameterValue': '2'
                },
                {
                    'ParameterKey': 'VPC',
                    'ParameterValue': vpc_id
                },
                {
                    'ParameterKey': 'Subnet1',
                    'ParameterValue': subnet1
                },
                {
                    'ParameterKey': 'Subnet2',
                    'ParameterValue': subnet2
                },
                {
                    'ParameterKey': 'KeyName',
                    'ParameterValue': stack_name_ecs_cluster + 'key'
                },
                {
                    'ParameterKey': 'InstanceType',
                    'ParameterValue': 'm4.large'
                }
            ],
            TimeoutInMinutes=123,
            Capabilities=[
                'CAPABILITY_IAM',
            ],
            OnFailure='DELETE',
            Tags=[
                {
                    'Key': 'Name',
                    'Value': stack_name
                },
            ]
        )

    except cf_client.exceptions.AlreadyExistsException:
        logger.warning("CF Stack already exists")
        pass

    time.sleep(10)

    stack_create_status = cf_client.describe_stacks(StackName=stack_name)

    while stack_create_status['Stacks'][0]['StackStatus'] == 'CREATE_IN_PROGRESS':
        time.sleep(10)
        stack_create_status = cf_client.describe_stacks(StackName=stack_name)
        logger.info("Create stack status: " + stack_create_status['Stacks'][0]['StackStatus'])
        if stack_create_status['Stacks'][0]['StackStatus'] == 'CREATE_COMPLETE':
            pass
        elif stack_create_status['Stacks'][0]['StackStatus'] == 'CREATE_IN_PROGRESS':
            continue
        else:
            raise Exception("Failed to create cluster")

    ecs_cluster = cf_client.describe_stack_resources(StackName=stack_name)
    for resource in ecs_cluster['StackResources']:
        if resource['ResourceType'] == 'AWS::ECS::Cluster':
            ecs_cluster_name = resource['PhysicalResourceId']
        if resource['ResourceType'] == 'AWS::EC2::SecurityGroup':
            if resource['LogicalResourceId'] == 'ELBSecurityGroup':
                elb_security_group = resource['PhysicalResourceId']

    try:
        elb_name = stack_name+'-elb'
        #Create an ELB for MySQL
        create_elb_response = elb_client.create_load_balancer(
            LoadBalancerName=elb_name,
            Listeners=[
                {
                    'Protocol': 'TCP',
                    'LoadBalancerPort': 3306,
                    'InstancePort': 3306
                },
            ],
            Subnets=[
                subnet1,
                subnet2
            ],
            SecurityGroups=[
                elb_security_group,
            ],
            Scheme='internal',
            Tags=[
                {
                    'Key': 'Name',
                    'Value': stack_name+'-elb'
                },
            ]
        )

        dns_name = create_elb_response['DNSName']

        response = elb_client.configure_health_check(
            LoadBalancerName=elb_name,
            HealthCheck={
                'Target': 'TCP:3306',
                'Interval': 30,
                'Timeout': 5,
                'UnhealthyThreshold': 2,
                'HealthyThreshold': 2
            }
        )

    except Exception as e:
        logger.error(e)


    service=stack_name
    try:
        containerDefinitions=[
            {
                'name': service,
                'environment': [
                    {
                        'name': 'MYSQL_ROOT_PASSWORD',
                        'value': 'password'
                    }
                ],
                'image': 'mysql',
                'cpu': 1024,
                'memory': 1024,
                'essential': True,
                'portMappings': [
                    {
                        'containerPort': 3306,
                        'hostPort': 3306
                    }
                ],
                'logConfiguration': {
                    'logDriver': 'awslogs',
                    'options': {
                        'awslogs-group': '/spring-ecs',
                        'awslogs-region': region,
                        'awslogs-stream-prefix': 'petclinic'
                    }
                }
            }
        ]

        register_task_response = ecs_client.register_task_definition(
            family=service,
            taskRoleArn=role_arns['taskrolearn'], #TODO change to role_arn
            networkMode='bridge',
            containerDefinitions=containerDefinitions
        )
    except Exception as e:
        logger.error(e)
        pass

    try:
        create_service_response = ecs_client.create_service(
            cluster=ecs_cluster_name,
            serviceName=service,
            taskDefinition=service,
            loadBalancers=[
                {
                    #'targetGroupArn': target_group_arn,
                    'loadBalancerName': elb_name,
                    'containerName': service,
                    'containerPort': 3306
                },
            ],
            desiredCount=1,
            clientToken=str(uuid.uuid4()),
            role=role_arns['ecsrolearn'], #TODO change to role_arn
            deploymentConfiguration={
                'maximumPercent': 600,
                'minimumHealthyPercent': 100
            },
            placementStrategy=[
                {
                    'type': 'spread',
                    'field': 'attribute:ecs.availability-zone'
                },
            ]
        )
    except Exception as e:
        logger.error(e)

    my_sql_options = {'dns_name': dns_name, 'username': 'root', 'password': 'password'}
    return my_sql_options


def delete_roles(task_role_policy=None, ecs_role_policy='arn:aws:iam::aws:policy/AmazonEC2ContainerServiceFullAccess',
                 ecs_agent_role_policy='arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role'):
    iam_client = boto3.client('iam')
    iam_client.detach_role_policy(
        RoleName='PetECSServiceRole',
        PolicyArn=ecs_role_policy
    )
    iam_client.delete_role(RoleName='PetECSServiceRole')

    if (task_role_policy != None):
        iam_client.detach_role_policy(
            RoleName='PetECSTaskRole',
            PolicyArn=task_role_policy
        )
    iam_client.delete_role(RoleName='PetECSTaskRole')

    iam_client.detach_role_policy(
        RoleName='PetECSAgentRole',
        PolicyArn=ecs_agent_role_policy
    )

    iam_client.delete_role(RoleName='PetECSAgentRole')

    logger.info("Roles deleted")


def create_roles(task_role_policy=None, ecs_role_policy='arn:aws:iam::aws:policy/AmazonEC2ContainerServiceFullAccess',
                 ecs_agent_role_policy='arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role'):
    iam_client = boto3.client('iam')
    # Create task role using an empty policy
    try:
        task_assume_policy = {
            'Statement': [
                {
                    'Principal': {
                        'Service': ['ecs-tasks.amazonaws.com']
                    },
                    'Effect': 'Allow',
                    'Action': ['sts:AssumeRole']
                },
            ]
        }

        ecs_assume_policy = {
            'Statement': [
                {
                    'Principal': {
                        'Service': ['ecs.amazonaws.com']
                    },
                    'Effect': 'Allow',
                    'Action': ['sts:AssumeRole']
                },
            ]
        }

        ecsagent_assume_policy = {
            'Statement': [
                {
                    'Principal': {
                        'Service': ['ec2.amazonaws.com']
                    },
                    'Effect': 'Allow',
                    'Action': ['sts:AssumeRole']
                },
            ]
        }

        create_ecs_role_response = iam_client.create_role(
            Path='/',
            RoleName='PetECSServiceRole',
            AssumeRolePolicyDocument=json.dumps(ecs_assume_policy)
        )
        ecs_role_arn = create_ecs_role_response['Role']['Arn']
        iam_client.attach_role_policy(
            RoleName='PetECSServiceRole',
            PolicyArn=ecs_role_policy
        )
        logger.info("ECS Service Role Create: " + ecs_role_arn)
        time.sleep(1)

        create_task_role_response = iam_client.create_role(
            Path='/',
            RoleName='PetECSTaskRole',
            AssumeRolePolicyDocument=json.dumps(task_assume_policy)
        )
        time.sleep(1)
        task_role_arn = create_task_role_response['Role']['Arn']
        if task_role_policy:
            iam_client.attach_role_policy(
                RoleName='PetECSTaskRole',
                PolicyArn=task_role_policy
            )
        logger.info("Task Role Create: " + task_role_arn)
        time.sleep(1)

        create_ecsagent_role_response = iam_client.create_role(
            Path='/',
            RoleName='PetECSAgentRole',
            AssumeRolePolicyDocument=json.dumps(ecsagent_assume_policy)
        )
        ecsagent_role_arn = create_ecsagent_role_response['Role']['Arn']
        iam_client.attach_role_policy(
            RoleName='PetECSAgentRole',
            PolicyArn=ecs_agent_role_policy
        )
        logger.info("ECS Agent Role Create: " + ecsagent_role_arn)

        role_arns = {'taskrolearn': task_role_arn, 'ecsrolearn': ecs_role_arn, 'ecsagentrolearn': ecsagent_role_arn}
        return role_arns
    except Exception as e:
        logger.error(e)

        response = iam_client.get_role(
            RoleName='PetECSServiceRole'
        )
        ecs_role_arn = response['Role']['Arn']

        response = iam_client.get_role(
            RoleName='PetECSTaskRole'
        )
        task_role_arn = response['Role']['Arn']

        response = iam_client.get_role(
            RoleName='PetECSAgentRole'
        )
        ecsagent_role_arn = response['Role']['Arn']
        role_arns = {'taskrolearn': task_role_arn, 'ecsrolearn': ecs_role_arn, 'ecsagentrolearn': ecsagent_role_arn}
        return role_arns


def docker_login_config():
    ecr_client = boto3.client('ecr')
    # Get latest authorization token and put it in ~/.docker/config.json
    ecr_login_token = ecr_client.get_authorization_token().get('authorizationData')[0].get('authorizationToken').encode(
        'utf-8')
    hostname = ecr_client.get_authorization_token().get('authorizationData')[0]['proxyEndpoint'].encode('utf-8')[8:]

    home = expanduser("~")
    filename = home + '/.docker/config.json'
    with open(filename, 'r+') as f:
        data = json.load(f)
        data['auths'] = {
            hostname: {
                "auth": ecr_login_token
            }
        }
        #data['auths'][hostname]['auth'] = ecr_login_token
        # logger.info('Writing docker configuration as '+str(data)
        f.seek(0)
        f.write(json.dumps(data))
        f.truncate()


def setup_securitygroups_permission(ecs_security_group, elb_security_group):
    client = boto3.client('ec2')
    logger.info('Security Group allow internet access to ELB port 80')
    # Allow internet access to ELB:80
    client.authorize_security_group_ingress(
        GroupId=elb_security_group,
        IpProtocol='tcp',
        FromPort=80,
        ToPort=80,
        CidrIp='0.0.0.0/0'
    )
    logger.info('Security Group allow ELB to access ECS ports 31000-61000')
    # Allow ECS allows inbound from ELB
    client.authorize_security_group_ingress(
        GroupId=ecs_security_group,
        IpPermissions=[
            {'IpProtocol': 'tcp',
             'FromPort': 31000,
             'ToPort': 61000,
             'UserIdGroupPairs': [{'GroupId': elb_security_group}]}
        ],
    )


def setup(project_name='spring-petclinic-rest', service_list={'spring-petclinic-rest': '8080'}, region='us-west-2'):
    ecr_client = boto3.client('ecr')
    elb_client = boto3.client('elbv2')
    ecs_client = boto3.client('ecs')
    ec2_client = boto3.client('ec2')

    role_arns = create_roles()
    docker_login_config()
    elb_subnets = []
    logger.info('Creating ECS Cluster')
    create_ecs_cluster(project_name)
    repository_uri = []

    for service in service_list:
        logger.info("Create resources for service: " + service)

        # Create repository ignore repository exists error
        create_repository_response = ecr_client.create_repository(repositoryName=service)
        logger.info("Create ECR repository")
        uri = create_repository_response['repository']['repositoryUri'].encode('utf-8')
        repository_uri.append({service: uri})

        # Set repository host URL in pom.xml
        os.environ["docker_registry_host"] = uri.split('/')[0]
        logger.info('Compile project, package, bake image, and push to registry for ' + service)
        # Compile project, package, bake image, and push to registry
        os.system('mvn package docker:build -DpushImage -Dmaven.test.skip=true')

    cf_client = boto3.client('cloudformation')
    stack_create_status = cf_client.describe_stacks(StackName=project_name)
    resources = cf_client.describe_stack_resources(StackName=project_name)

    while stack_create_status['Stacks'][0]['StackStatus'] == 'CREATE_IN_PROGRESS':
        time.sleep(10)
        stack_create_status = cf_client.describe_stacks(StackName=project_name)
        logger.info("Create stack status: " + stack_create_status['Stacks'][0]['StackStatus'])
        if stack_create_status['Stacks'][0]['StackStatus'] == 'CREATE_COMPLETE':
            resources = cf_client.describe_stack_resources(StackName=project_name)
        elif stack_create_status['Stacks'][0]['StackStatus'] == 'CREATE_IN_PROGRESS':
            continue
        else:
            raise Exception("Failed to create cluster")

    for resource in resources['StackResources']:
        if resource['LogicalResourceId'] == 'EcsSecurityGroup':
            ecs_security_group = resource['PhysicalResourceId']
        if resource['LogicalResourceId'] == 'ElbSecurityGroup':
            elb_security_group = resource['PhysicalResourceId']
        if resource['LogicalResourceId'] == 'PubELBSubnetAz1':
            elb_subnets.append(resource['PhysicalResourceId'])
        if resource['LogicalResourceId'] == 'PubELBSubnetAz2':
            elb_subnets.append(resource['PhysicalResourceId'])
        if resource['LogicalResourceId'] == 'PubELBSubnetAz3':
            elb_subnets.append(resource['PhysicalResourceId'])
        if resource['LogicalResourceId'] == 'Vpc':
            vpc_id = resource['PhysicalResourceId']

    stack_create_status = cf_client.describe_stacks(StackName=project_name)
    dns_name = stack_create_status['Stacks'][0]['Outputs'][0]['OutputValue'].encode('utf-8')

    my_sql_options = {'dns_name': dns_name, 'username': 'PetClinicDB', 'password': 'PetClinicPassw0rd'}

    logger.info("Creating ELB")
    elb_name = project_name + '-elb'
    # Create an ELBv2
    create_elb_response = elb_client.create_load_balancer(
        Name=elb_name,
        Subnets=elb_subnets,
        SecurityGroups=[elb_security_group],
        Scheme='internet-facing',
        Tags=[
            {
                'Key': 'Name',
                'Value': project_name + '-rest-monolithic'
            },
        ],
        IpAddressType='ipv4'
    )
    elb_arn = create_elb_response['LoadBalancers'][0]['LoadBalancerArn'].encode('utf-8')
    elb_dns = create_elb_response['LoadBalancers'][0]['DNSName'].encode('utf-8')

    # Create default / target group
    create_target_group_response = elb_client.create_target_group(
        Name=project_name + '-elb-tg',
        Protocol='HTTP',
        Port=80,
        VpcId=vpc_id,
        HealthCheckPath='/',
        HealthCheckIntervalSeconds=30,
        HealthCheckTimeoutSeconds=5,
        HealthyThresholdCount=5,
        UnhealthyThresholdCount=2,
        Matcher={
            'HttpCode': '200'
        }
    )
    target_group_arn = create_target_group_response['TargetGroups'][0]['TargetGroupArn'].encode('utf-8')
    logger.info("ELB Target Group created: " + json.dumps(create_target_group_response))
    # Create ELB listener for port 80
    create_listener_response = elb_client.create_listener(
        LoadBalancerArn=elb_arn,
        Protocol='HTTP',
        Port=80,
        DefaultActions=[
            {
                'Type': 'forward',
                'TargetGroupArn': target_group_arn
            },
        ]
    )
    listener_arn = create_listener_response['Listeners'][0]['ListenerArn'].encode('utf-8')
    logger.info("ELB Listener Created: " + json.dumps(create_listener_response))

    for service in service_list:
        logger.info("Create resources for service: " + service)

        # Create target group for service
        create_target_group_response = elb_client.create_target_group(
            Name=project_name + str(service_list.keys().index(service)) + '-tg',
            Protocol='HTTP',
            Port=int(service_list[service]),
            VpcId=vpc_id,
            HealthCheckPath='/',
            HealthCheckIntervalSeconds=60,
            HealthCheckTimeoutSeconds=25,
            HealthyThresholdCount=5,
            UnhealthyThresholdCount=3,
            Matcher={
                'HttpCode': '200'
            }
        )
        target_group_arn = create_target_group_response['TargetGroups'][0]['TargetGroupArn'].encode('utf-8')
        logger.info("ELB Target Group created: ")
        # Create routing rule to application
        create_rule_response = elb_client.create_rule(
            ListenerArn=listener_arn,
            Conditions=[
                {
                    'Field': 'path-pattern',
                    'Values': [
                        '/*'
                    ]
                },
            ],
            Priority=randint(1, 1000),
            Actions=[
                {
                    'Type': 'forward',
                    'TargetGroupArn': target_group_arn
                },
            ]
        )

        containerDefinitions = [
            {
                'name': service,
                'image': repository_uri[service_list.keys().index(service)][service] + ':latest',
                'essential': True,
                'portMappings': [
                    {
                        'containerPort': int(service_list[service]),
                        'hostPort': 0
                    }
                ],
                'memory': 1024,
                'cpu': 500,
                'environment': [
                    {
                        'name': 'SPRING_PROFILES_ACTIVE',
                        'value': 'mysql'
                    },
                    {
                        'name': 'SPRING_DATASOURCE_URL',
                        'value': my_sql_options['dns_name']
                    },
                    {
                        'name': 'SPRING_DATASOURCE_USERNAME',
                        'value': my_sql_options['username']
                    },
                    {
                        'name': 'SPRING_DATASOURCE_PASSWORD',
                        'value': my_sql_options['password']
                    }
                ],
                'dockerLabels': {
                    'string': 'string'
                },
                'logConfiguration': {
                    'logDriver': 'awslogs',
                    'options': {
                        'awslogs-group': "ECSLogGroup-" + project_name,
                        'awslogs-region': region,
                        'awslogs-stream-prefix': project_name
                    }
                }
            }
        ]

        register_task_response = ecs_client.register_task_definition(
            family=service,
            taskRoleArn=role_arns['taskrolearn'],
            networkMode='bridge',
            containerDefinitions=containerDefinitions
        )

        create_service_response = ecs_client.create_service(
            cluster=project_name,
            serviceName=service,
            taskDefinition=service,
            loadBalancers=[
                {
                    'targetGroupArn': target_group_arn,
                    'containerName': service,
                    'containerPort': int(service_list[service])
                },
            ],
            desiredCount=2,
            clientToken=str(uuid.uuid4()),
            role=role_arns['ecsrolearn'],
            deploymentConfiguration={
                'maximumPercent': 600,
                'minimumHealthyPercent': 100
            },
            placementStrategy=[
                {
                    'type': 'spread',
                    'field': 'attribute:ecs.availability-zone'
                },
            ]
        )

    return elb_dns


def cleanup(project_name='spring-petclinic-rest', service_list={'spring-petclinic-rest': '8080'}, region='us-west-2'):
    ecr_client = boto3.client('ecr')
    ecs_client = boto3.client('ecs')
    elbv2_client = boto3.client('elbv2')

    for service in service_list:
        try:
            ecr_client.delete_repository(repositoryName=service, force=True)
        except Exception as e:
            logger.error(e)
        try:
            task_definition = ecs_client.describe_task_definition(taskDefinition=service)
            ecs_client.deregister_task_definition(
                taskDefinition=task_definition['taskDefinition']['family'].encode('utf-8') + ':' + str(
                    task_definition['taskDefinition']['revision']))
        except Exception as e:
            logger.error(e)
        try:
            ecs_client.update_service(cluster=project_name, service=service, desiredCount=0)
            ecs_client.delete_service(cluster=project_name, service=service)
            logger.info('Deleted service: '+service)

        except Exception as e:
            logger.error(e)

    logger.info('Draining services traffics')
    try:
        load_balancer = elbv2_client.describe_load_balancers(Names=[project_name + '-elb'])
        elbv2_client.delete_load_balancer(LoadBalancerArn=load_balancer['LoadBalancers'][0]['LoadBalancerArn'])
        time.sleep(10)
    except Exception as e:
        logger.error(e)
    target_groups = elbv2_client.describe_target_groups()['TargetGroups']
    for target_group in target_groups:
        target_group_name = target_group['TargetGroupName'][0:len(project_name)]
        if target_group_name == project_name:
            try:
                logger.info('Deleting target group ' + target_group_name)
                elbv2_client.delete_target_group(TargetGroupArn=target_group['TargetGroupArn'])
            except Exception as e:
                logger.error(e)
        else:
            logger.warn('No target group found: '+target_group_name)
    logger.info('Deleting ELBv2')

    try:
        delete_ecs_cluster(project_name)
    except Exception as e:
        logger.error(e)

    target_groups = elbv2_client.describe_target_groups()['TargetGroups']
    for target_group in target_groups:
        target_group_name = target_group['TargetGroupName'][0:len(project_name)]
        if target_group_name == project_name:
            try:
                logger.info('Deleting target group ' + target_group_name)
                elbv2_client.delete_target_group(TargetGroupArn=target_group['TargetGroupArn'])
            except Exception as e:
                logger.error(e)
        else:
            logger.warn('No target group found: '+target_group_name)
    logger.info("Deleting roles")
    try:
        delete_roles()
    except Exception as e:
        logger.error(e)


def main():
    parser = argparse.ArgumentParser(description="Execute input file. Supports only python or sh file.")
    parser.add_argument('-m', '--mode', required=True, help="execution mode -m cleanup or -m setup")
    parser.add_argument('-p', '--project_name', required=False, default='spring-petclinic-rest',
                        help="Name of the project")
    parser.add_argument('-r', '--region', required=True, default='us-west-2', help="Region. Default 'us-west-2'")
    parser.add_argument('-s', '--service_list', required=False, default={'spring-petclinic-rest': '8080'},
                        help="Service list. Default {'spring-petclinic-rest': '8080'}")
    args = parser.parse_args()

    project_name = args.project_name
    service_list = args.service_list
    region = args.region
    mode = args.mode
    os.environ["AWS_DEFAULT_REGION"] = region

    logger.info("Mode: " + mode)

    if mode == 'setup':
        setup_results = setup(project_name=project_name, service_list=service_list, region=region)
        logger.info("Setup is complete your endpoint is http://"+setup_results)
    elif mode == 'cleanup':
        cleanup_results = cleanup(project_name=project_name, service_list=service_list, region=region)
    else:
        parser.print_help()
        raise Exception("Not supported mode")


if __name__ == "__main__":
    main()
