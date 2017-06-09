## Deploying in containers

In this example we take our java application and put it into a container for deployment on EC2 Container Service.

### Why containers?

__Improved Pipeline__: The container also allows an engineering organization to create a standard pipeline for the application lifecycle. For example:

1. Developers build and run container locally.
2. CI server runs the same container and executes integration tests against it to make sure it passes expectations.
3. Same container is shipped to a staging environment where its runtime behavior can be checked using load tests or manual QA.
4. Same container is finally shipped to production.

Being able to ship the exact same container through all four stages of the process makes delivering a high quality, reliable application considerably easier.

__No mutations to machines:__ When applications are deployed directly onto instances you run the risk of a bad deploy corrupting an instance configuration in a way that is hard to recover from. For example imagine a deployed application which requires some custom configurations in `/etc`. This can become a very fragile deploy as well as one that is hard to roll back if needed. However with a containerized application the container carries its own filesystem with its own `/etc` and any custom configuration changes that are part of this container will be sandboxed to that application's environment only. The underlying instance's configurations stay the same. In fact a container can't even make persistant filesystem changes without an explicit mounted volume which grants the container access to a limited area on the host instance.

## Why EC2 Container Service?

EC2 Container Service provides orchestration for your containers. It automates the process of launching containers across your fleet of instances according to rules your specify, then automates keeping track of where those containers are running so that you can use a load balancer to get traffic to them. It also has built in features to roll out deploys with zero downtime, gather metrics and logs from your containers, and auto scale the number of containers you are running based on metrics.

## Application Changes for Docker

To transform your existing Java Spring application into container you must compile, package, build a container image with the application package, and execution instruction. In addition, in order to run your container in the container cluster, it must be stored in a scaleable container registry. Amazon EC2 Container Registry (ECR) is a fully-managed  [Docker](https://aws.amazon.com/docker/) container registry that makes it easy for developers to store, manage, and deploy Docker container images. Amazon ECR is integrated with Amazon EC2 Container Service (ECS), simplifying your development to production workflow.

![alt text](https://github.com/awslabs/amazon-ecs-java-microservices/blob/master/images/ecs-spring-monolithic-containers.png)


1.  __Dependency Injection using Spring:__ We have modified the code to be separate interfaces into pet, owner, visit, etc as a first step towards microservice. We use Spring framework Repository annotation to inject the dependency in the specific path.  
   
2. __Create `Dockerfile`:__ This file is basically a build script that creates the container. The base container that the dockerfile starts from contains a specific version of java. We use the [docker-spotify](https://github.com/spotify/docker-maven-plugin) plugin to run the maven build and create artifacts . The result is a container image that is a reliable unit of deployment. The container can be run locally, or run on a remote server. It will run the same in both places. 

3. __Provision `AWS resources`:__ the setup.py provisions the AWS resources such as ECS, ECR, IAM Roles, ALB, RDS MySQL, AWS networking resources.

## Prerequisites

You will need to have the latest version of the AWS CLI and maven installed before running the deployment script.  If you need help installing either of these components, please follow the links below:

[Installing the AWS CLI](http://docs.aws.amazon.com/cli/latest/userguide/installing.html)
[Installing Maven](https://maven.apache.org/install.html)

## Deployment

1. Clone this repository - ```git clone <>```
2. Run python ```setup.py -m setup -r <your region>```

## Test 

1. ```curl <your endpoint from output above>/<endpoint> ```

supported endpoints  are /, /pet, /vet, /owner, /visit

## Clean up

1. Run python setup.py -m cleanup -r <your region>

## NextStep

[Lets break this app into microservices](https://github.com/awslabs/aws-java-microservice-refarch/tree/master/2_ECS_Java_Spring_PetClinic_Microservices)
