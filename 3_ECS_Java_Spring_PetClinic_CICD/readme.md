# Github

## Introduction
In this reference architecture, we will be using AWS CodeCommit, AWS CodePipeline, AWS CodeBuild to demonstrate continuous delivery of a Java Spring Boot microservices. We will be using the Spring PetClinic found [here](https://github.com/awslabs/amazon-ecs-java-microservices/tree/master/2_ECS_Java_Spring_PetClinic_Microservices).

Spring Pet Clinic consists of 5 microservices - ```spring-petclinic-rest-owner, spring-petclinic-rest-pet, spring-petclinic-rest-system, spring-petclinic-rest-vet``` and ```spring-petclinic-rest-visit```. Each microservice has a seperate AWS CodeCommit source repository.  There are also 5 AWS CodePipeline, so each microservice can be seperately built and deployed on ECS. Each repo has its own ```Dockerfile```

To abstract the underlying infrastructure away from the developer, we also provide a simple json file which provides information on how each microservice should be configured. Each microservice has its own ```ecs-service-config.json``` which is a simple json file to tell AWS CodePipeline how to deploy the ECS task and service.

For each AWS CodePipeline, there are 4 stages:
 - Petclinic Microservice Source Code and Cloudformation template for ECS Task (AWS CodeCommit)
 - Build (AWS CodeBuild)
 - Approval
 - Deploy to ECS Cluster (AWS Cloudformation)

 ![pipeline](images/Pipeline.png)

We will be using the following AWS Services in an AWS Region of your choice, please make sure the region selected has the following AWS services:
- Amazon S3
- AWS Cloudformation
- AWS CodePipeline
- AWS CodeCommit
- AWS CodeBuild
- EC2 Container Service (ECS)
- EC2 Container Registry (ECR)
- Amazon Application Load Balancer
- Amazon EC2 Systems Manager Parameter Store


## Let's Get Started

In this step, we download the Java Spring PetClinic Microservices from github.com and upload the five Java projects into 5 AWS CodeCommit Repositories.

#### Checklist before you start
* Check that you have AWS CLI installed with permission to create AWS CodeCommit repository.
* Check that you can git push to your AWS CodeCommit repository using ssh
* Check that AWS_DEFAULT_REGION is set to a region you want to deploy this project.

#### Clone the project from github.com
```
#Need to change to just grab it from the current project instead of the other folder.

mkdir /tmp/scratch && cd /tmp/scratch
#TOFIX: git clone <awslabs github repo of this project>  

```

#### Create 5 AWS CodeCommit Repositories for the microservices
```bash
cd amazon-ecs-java-microservices-master/2_ECS_Java_Spring_PetClinic_Microservices

for repo in spring-petclinic-rest-owner spring-petclinic-rest-pet \
spring-petclinic-rest-system spring-petclinic-rest-vet spring-petclinic-rest-visit
do
  export gitSSHUrl=$(aws codecommit create-repository --repository-name $repo | \
  python -c "import sys, json; print json.load(sys.stdin)['repositoryMetadata']['cloneUrlSsh']")
  cd $repo
  git init
  git add .
  git commit -am "First Commit"
  git remote add origin $gitSSHUrl
  git push --set-upstream origin master
  cd ..
done

```
#### Verify

Check that you have 5 CodeCommit Repositories for the PetClinic Microservices. Also ensure these files are in each repository:
- ```Dockerfile``` in ```src/main/docker/``` directory
- ```ecs-service-config.json```


```bash
aws codecommit list-repositories |jq -r '.repositories[]|.repositoryName'

  spring-petclinic-rest-owner
  spring-petclinic-rest-pet
  spring-petclinic-rest-system
  spring-petclinic-rest-vet
  spring-petclinic-rest-visit
```

#### Upload infrastructure automation CloudFormation Template to S3
We will be using nested Cloudformation in this project. The ```AWS::CloudFormation::Stack``` resource type is used to create child stacks from a master stack. The CloudFormation stack resource requires the templates of the child stacks to be stored in the S3 bucket.
S3 is also used by AWS CodePipeline as a Source repository for the Cloudformation template that deploys each individual microservice as a ECS Service.
AWS CodePipeline expects the S3 bucket to be versioned too.

- To create a S3 bucket with versioning

```
  export account_id=<AccountId>
  export infra_bucket_name=petclinic-infra-auto-$account_id
  export region=<AWS-Region>
  aws s3 mb s3://$infra_bucket_name
  aws s3api put-bucket-versioning --bucket $infra_bucket_name --versioning-configuration Status=Enabled

```

- Upload Cloudformation templates in "infra-automation" folder to this S3 bucket

```
  #cd amazon-ecs-java-microservices-master/2_ECS_Java_Spring_PetClinic_Microservices/infra-automation
  cd ./infra-automation
  aws s3 sync . s3://$infra_bucket_name

```
#### Verify
```
aws s3 ls s3://$infra_bucket_name

```

## Create Custom CodeBuild Environment
AWS CodeBuild is a fully managed build service that compiles source code, runs tests, and produces software packages that are ready to deploy. In this project, we use CodeBuild to build both the Java application (using Maven) and its Docker image. The Docker image is a Java environment that launches the Spring Boot application. Once the Docker image is built, we use CodeBuild to push the Docker image to ECR.

```
//diagram
   |-------------------------- CodePipeline -----------------------------------|
   v                                                                           v
CodeCommit --> CodeBuild(Custome Build Environment) --> ECR (Spring Boot App Container)
```

CodeBuild provides default build environments that support different programming languages and frameworks, the build environments are Docker images which contain the tools to build and test your applications. A list of these Docker images can be found [here](http://docs.aws.amazon.com/codebuild/latest/userguide/build-env-ref-available.html). One of the image, ```aws/codebuild/docker:1.12.1``` allows CodeBuild to build Docker images, but it does not contain the Java SDK and Maven tool needed to build our Java applications.

To avoid installing the Java SDK and Maven tool each time we build our project, we can create a custom build environment.
CodeBuild custom build environment is a Docker image which is pre-installed with all the dependencies for our pet-clinic microservices. These dependencies include Java SDK, Maven and AWS CLI. Another benefit of using a custom build environment is that it allows us to have control over the version of the  build tools and Java SDK.

To build the Docker image for our custom build environment, we are going to use a simple CI/CD process. The Dockerfile and script that define this custom container will be store in a CodeCommit Repository. A CodePipeline will use this CodeCommit Repository as Source and build the container using the default ```aws/codebuild/docker:1.12.1``` image.

#### Create AWS CodeCommit Repository for the CodeBuild Custom Build Environment

```bash
#cd amazon-ecs-java-microservices-master/2_ECS_Java_Spring_PetClinic_Microservices/codebuild-custom-env
cd ../codebuild-custom-env
export gitSSHUrl=$(aws codecommit create-repository --repository-name codebuildcustomenv | \
python -c "import sys, json; print json.load(sys.stdin)['repositoryMetadata']['cloneUrlSsh']")
git init
git add .
git commit -am "First Commit"
git remote add origin $gitSSHUrl
git push --set-upstream origin master
```

#### Create AWS CodeBuild Custom Environment
Using AWS Console, navigate to Cloudformation console and launch the following Cloudformation template from your ```<infra-automation-bucket-name>``` bucket.

```bash
aws cloudformation create-stack --stack-name codebuild-custom --template-url \
https://s3-$region.amazonaws.com/$infra_bucket_name/codebuild-custom-container-ci.yaml \
--parameters ParameterKey=CodeCommitRepo,ParameterValue=codebuildcustomenv \
ParameterKey=ECRRepositoryName,ParameterValue=custombuild \
--capabilities CAPABILITY_IAM

```

#### Verify

In ECR console, verify that you have the ```codebuild-custom-env``` container image. Note the repository URI. eg: ```123456789012.dkr.ecr.<AWS::Region>.amazonaws.com/custombuild```, we will use this in our next step.


## Create an ECS Cluster with RDS, AWS CodePipelines

#### Create EC2 Parameter store for RDS Database password
Parameter Store, part of Amazon EC2 Systems Manager, provides a centralized, encrypted store to manage our RDS database connection information and password. As we cannot provision a "SecureString" Parameter using Cloudformaion, let's add our RDS database password using AWS CLI.

```bash
aws ssm put-parameter --name /DeploymentConfig/Prod/DBPassword --value <mysqlpassword> --type SecureString
```
The above command will encrypt our database password using KMS key ```alias/aws/ssm```. Take note of the arn for ```alias/aws/ssm```.

Using AWS Console, navigate to Cloudformation console and launch the following Cloudformation template from your ```$infra_bucket_name``` bucket. Make sure you specific the same database password for the ```DBPassword``` parameter as the one in ```/DeploymentConfig/Prod/DBPassword```.

```bash

export mysshkey=<EC2 SSH Key>

aws cloudformation create-stack --stack-name petclinic-cicd --template-url \
https://s3-$region.amazonaws.com/$infra_bucket_name/master-ecs.yaml --parameters \
ParameterKey=CodeBuildContainerSpringBootDocker,ParameterValue=$account_id.dkr.ecr.$region.amazonaws.com/custombuild:latest \
ParameterKey=InfraAutomationCfnBucket,ParameterValue=$infra_bucket_name \
ParameterKey=KeyPair,ParameterValue=$mysshkey \
ParameterKey=DBPassword,ParameterValue=$(aws ssm get-parameters --name /DeploymentConfig/Prod/DBPassword --with-decryption --query 'Parameters[0].Value') \
ParameterKey=SsmKMSKeyArn,ParameterValue=$(aws kms describe-key --key-id 'alias/aws/ssm' --query 'KeyMetadata.Arn') \
--capabilities CAPABILITY_IAM

```
![cloudformation complete](images/CloudformationComplete.png)

You need to provide the following parameters:
- ```<AWS:AccountId>.dkr.ecr.<AWS::Region>.amazonaws.com/custombuild:latest```
- ```$infra_bucket_name``` bucket name
- Your EC2 SSH Keypair
- Database password to RDS
- ARN of KMS key - alias/aws/ssm

#### Verify
Verify that you have:
 - ECS Cluster
 - Application Load Balancer (ALB)
 - 5 AWS CodePipeline
 - EC2 Parameter Store containing the 3 parameters for RDS

 ![SSM](images/ssm.png)


#### Explore the ECS Cluster, ECR Repo
 - 5 ECS Services and 5 Task Definition
 - 5 ECR Repo

The CodePipelines are configured with *Manual Approval* step. Navigate to each CodePipeline and click on the Approval step to let CodePipeline deploy the ECS service.

Also, note that we have encrypted the database password in the Parameter Store, only the EC2 Tasks with their Task IAM role can decrypt the password. The database password does not show up as *Environment Variables* in the ECS Console (see diagram below).

![ECS Task Env](images/ecs-task.png)

You can check the log of each microservice using Cloudwatch log. Navigate to the Cloudwatch Log Group ```<env-name>-EcsCluster``` and locate the commit hash and microservice name.

![Cloudwatch Log](images/CWLog.png)


## Deploy a change to one of the microservices
A benefit of microservices is that we can we scale each microservice independently. Let's suppose we want to increase the container count from 2 to 4 for the ```spring-petclinic-rest-pet``` microservice.

```bash
cd amazon-ecs-java-microservices-master/2_ECS_Java_Spring_PetClinic_Microservices/spring-petclinic-rest-pet
#edit ecs-service-config.json :change  "count": "2" to "count": "4"
#commit the change
git commit -am "Update spring-petclinic-rest-pet microservice to 4 containers"
#push the change to trigger the update of this microservice
git -f push
```
Application Load Balancer provides path-base routing to each of the microservices as depicted [here](https://d2908q01vomqb2.cloudfront.net/1b6453892473a467d07372d45eb05abc2031647a/2017/07/10/ecs-spring-microservice-containers.png).
Notice also how we can use this ```ecs-service-config.json``` file to set the path-base routing and routing priority of each microservice. This json file is used by AWS CodePipeline Parameter override when it performs a Cloudformation deployment of the ECS Service.

#### Verify
- Validate that AWS CodePipeline of ```spring-petclinic-rest-pet``` is triggered and a new container is built.
- Validate a new copy of the container in ECR
- Validate that the ECS Service for ```spring-petclinic-rest-pet``` is updated to 4


## Cleanup

To delete the AWS resources:
- Delete the 5 templates of ECS Services (Cloudformation Console)
- Delete the 5 petclinic docker images from ECR  (ECS Console)
- Delete the master stack (Cloudformation console)
 - If the ECS Cluster deletion fails, go to ECS Console to delete it
- Delete the 5 CodePipeline buckets (S3 console)
  - Cloudformation cannot delete an S3 bucket that is not empty. We will delete the bucket manually using AWS Console or AWS CLI
```
	aws s3 rb s3://<infra-automation-bucket-name> --force
```
- Delete the snapshot of RDS (RDS console -> snapshot)
- Delete CodeCommit Repositories


```bash
for repo in spring-petclinic-rest-owner spring-petclinic-rest-pet spring-petclinic-rest-system spring-petclinic-rest-vet spring-petclinic-rest-visit
do
  aws codecommit delete-repository --repository-name $repo
done
```


## Conclusion

In this post, we demostrated how to setup a CI/CD pipeline using AWS CodeCommit, AWS CodePipeline, AWS CodeBuild and AWS Cloudformation for Java Microservices.
