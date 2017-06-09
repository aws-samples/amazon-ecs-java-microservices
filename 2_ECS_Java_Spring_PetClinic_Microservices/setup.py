#!/bin/python
import boto3, json, os, logging, uuid, time, argparse, botocore
from os.path import expanduser
from random import randint

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
                    'ParameterValue': '3',
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
                    'ParameterValue': 'c4.xlarge',
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

    resources = cf_client.describe_stack_resources(StackName=stack_name)
    return resources


def delete_roles(task_role_policy=None, ecs_role_policy='arn:aws:iam::aws:policy/AmazonEC2ContainerServiceFullAccess',
                 ecs_agent_role_policy='arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role'):
    iam_client = boto3.client('iam')
    iam_client.detach_role_policy(
        RoleName='MicroECSServiceRole',
        PolicyArn=ecs_role_policy
    )
    iam_client.delete_role(RoleName='MicroECSServiceRole')

    if (task_role_policy != None):
        iam_client.detach_role_policy(
            RoleName='MicroECSTaskRole',
            PolicyArn=task_role_policy
        )
    iam_client.delete_role(RoleName='MicroECSTaskRole')

    iam_client.detach_role_policy(
        RoleName='MicroECSAgentRole',
        PolicyArn=ecs_agent_role_policy
    )

    iam_client.delete_role(RoleName='MicroECSAgentRole')

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
            RoleName='MicroECSServiceRole',
            AssumeRolePolicyDocument=json.dumps(ecs_assume_policy)
        )
        ecs_role_arn = create_ecs_role_response['Role']['Arn']
        iam_client.attach_role_policy(
            RoleName='MicroECSServiceRole',
            PolicyArn=ecs_role_policy
        )
        logger.info("ECS Service Role Create: " + ecs_role_arn)
        time.sleep(1)

        create_task_role_response = iam_client.create_role(
            Path='/',
            RoleName='MicroECSTaskRole',
            AssumeRolePolicyDocument=json.dumps(task_assume_policy)
        )
        time.sleep(1)
        task_role_arn = create_task_role_response['Role']['Arn']
        if task_role_policy:
            iam_client.attach_role_policy(
                RoleName='MicroECSTaskRole',
                PolicyArn=task_role_policy
            )
        logger.info("Task Role Create: " + task_role_arn)
        time.sleep(1)

        create_ecsagent_role_response = iam_client.create_role(
            Path='/',
            RoleName='MicroECSAgentRole',
            AssumeRolePolicyDocument=json.dumps(ecsagent_assume_policy)
        )
        ecsagent_role_arn = create_ecsagent_role_response['Role']['Arn']
        iam_client.attach_role_policy(
            RoleName='MicroECSAgentRole',
            PolicyArn=ecs_agent_role_policy
        )
        logger.info("ECS Agent Role Create: " + ecsagent_role_arn)

        role_arns = {'taskrolearn': task_role_arn, 'ecsrolearn': ecs_role_arn, 'ecsagentrolearn': ecsagent_role_arn}
        return role_arns
    except Exception as e:
        logger.error(e)


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
        data['auths'][hostname]['auth'] = ecr_login_token
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


def setup(project_name='spring-petclinic-rest',
          service_list={'spring-petclinic-rest-system': '8080','spring-petclinic-rest-owner': '8080', 'spring-petclinic-rest-pet': '8080','spring-petclinic-rest-vet': '8080','spring-petclinic-rest-visit': '8080'}
          , region='us-west-2'):
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
        uri = create_repository_response['repository']['repositoryUri']
        repository_uri.append({service: uri})

        # Set repository host URL in pom.xml
        os.environ["docker_registry_host"] = uri.split('/')[0]
        logger.info('Compile project, package, bake image, and push to registry for ' + service)
        # Compile project, package, bake image, and push to registry
        os.chdir(service)
        os.system('mvn package docker:build -DpushImage -Dmaven.test.skip=true')
        os.chdir('..')

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

    # my_sql_options = create_ecs_cluster_mysql(project_name+'-mysql', project_name, vpc_id, subnets[0], subnets[1], role_arns, region)

    # print my_sql_options

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
                'Value': project_name + '-rest-micro'
            },
        ],
        IpAddressType='ipv4'
    )
    elb_arn = create_elb_response['LoadBalancers'][0]['LoadBalancerArn'].encode('utf-8')
    elb_dns = create_elb_response['LoadBalancers'][0]['DNSName'].encode('utf-8')

    # Create default / target group
    create_default_target_group_response = elb_client.create_target_group(
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
    default_target_group_arn = create_default_target_group_response['TargetGroups'][0]['TargetGroupArn'].encode('utf-8')
    logger.info("ELB Target Group created: " + json.dumps(create_default_target_group_response))
    # Create ELB listener for port 80
    create_listener_response = elb_client.create_listener(
        LoadBalancerArn=elb_arn,
        Protocol='HTTP',
        Port=80,
        DefaultActions=[
            {
                'Type': 'forward',
                'TargetGroupArn': default_target_group_arn
            },
        ]
    )
    listener_arn = create_listener_response['Listeners'][0]['ListenerArn'].encode('utf-8')
    logger.info("ELB Listener Created: " + json.dumps(create_listener_response))

    for service in service_list:
        # Create target group for service
        if service == 'spring-petclinic-rest-system':
            target_group_arn = default_target_group_arn
        else:
            create_target_group_response = elb_client.create_target_group(
                Name=project_name + str(service_list.keys().index(service)) + '-tg',
                Protocol='HTTP',
                Port=int(service_list[service]),
                VpcId=vpc_id,
                HealthCheckPath='/',
                HealthCheckIntervalSeconds=60,
                HealthCheckTimeoutSeconds=30,
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
                            '/' + service[22:]+'*'
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
        logger.info('Create Task Definition for: ' + service_list[service])
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
                'cpu': 1024,
                'environment': [
                    {
                        'name': 'SERVICE_ENDPOINT',
                        'value': elb_dns
                    },
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
        logger.info('Create service for: ' + service_list[service])
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


def cleanup(project_name='spring-petclinic-rest',
            service_list={'spring-petclinic-rest-system': '8080','spring-petclinic-rest-owner': '8080', 'spring-petclinic-rest-pet': '8080','spring-petclinic-rest-vet': '8080','spring-petclinic-rest-visit': '8080'}, region='us-west-2'):
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
            logger.info('Deleted service: ' + service)

        except Exception as e:
            logger.error(e)

    try:
        load_balancer = elbv2_client.describe_load_balancers(Names=[project_name + '-elb'])
        elbv2_client.delete_load_balancer(LoadBalancerArn=load_balancer['LoadBalancers'][0]['LoadBalancerArn'])
        time.sleep(10)
    except Exception as e:
        logger.error(e)
    logger.info('Draining services traffics')
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
            logger.warn('No target group found: ' + target_group_name)
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
            logger.warn('No target group found: ' + target_group_name)
    logger.info("Deleting roles")
    try:
        delete_roles()
    except Exception as e:
        logger.error(e)


def main():
    parser = argparse.ArgumentParser(description="Execute input file. Supports only python or sh file.")
    parser.add_argument('-m', '--mode', required=True, help="execution mode -m cleanup or -m setup")
    parser.add_argument('-p', '--project_name', required=False, default='spring-petclinic-micro',
                        help="Name of the project")
    parser.add_argument('-r', '--region', required=True, help="Region is required.")
    parser.add_argument('-s', '--service_list', required=False,
                        default={'spring-petclinic-rest-system': '8080','spring-petclinic-rest-owner': '8080', 'spring-petclinic-rest-pet': '8080','spring-petclinic-rest-vet': '8080','spring-petclinic-rest-visit': '8080'},
                        help="Service list. Default {'spring-petclinic-rest-owner' : '8080',"
                             "'spring-petclinic-rest-pet' : '8080','spring-petclinic-rest-system' : '8080',"
                             "'spring-petclinic-rest-vet' : '8080','spring-petclinic-rest-visit' : '8080'}")
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
