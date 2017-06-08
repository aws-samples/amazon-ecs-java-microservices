# Part I: Lift-n-shift Your Java Spring application to containers on ECS

Containers are a method of operating system virtualization that allow you to run an application and its dependencies in resource-isolated processes. Containers allow you to easily package an application&#39;s code, configurations, and dependencies into easy to use building blocks that deliver environmental consistency, operational efficiency, developer productivity, and version control. Containers can help ensure that applications deploy quickly, reliably, and consistently regardless of deployment environment. Containers also give you more granular control over resources giving your infrastructure improved efficiency.

Running a single container on a single server is easy. ECS is a cluster management service that helps you manage a group of clusters through a graphical user interface or by accessing a command line. With ECS you can install, operate, and scale your own cluster management infrastructure. With simple API calls, you can launch and stop Docker-enabled applications, query the complete state of your cluster, and access many familiar features like security groups, Elastic Load Balancing, EBS volumes, and IAM roles. You can use Amazon ECS to schedule the placement of containers across your cluster based on your resource needs and availability requirements. You can also integrate your own scheduler or third-party schedulers to meet business or application specific requirements.

In this blog, we will talk about how you can containerize an existing Java Spring application and use ECS to run this container at scale and high availability.

The application example we will be using is a modified fork of the popular Spring Pet Clinic REST application.


# Containerize your Spring application

To transform your existing Java Spring application into container you must compile, package, build a container image with the application package, and execution instruction. In addition, in order to run your container in the container cluster, it must be stored in a scaleable container registry so that during a docker run, each of the cluster&#39;s node can download the container in parallel without impacting the performance. Amazon EC2 Container Registry (ECR) is a fully-managed  [Docker](https://aws.amazon.com/docker/) container registry that makes it easy for developers to store, manage, and deploy Docker container images. Amazon ECR is integrated with Amazon EC2 Container Service (ECS), simplifying your development to production workflow.

Amazon EC2 Container Registry (ECR) is a fully-managed  [Docker](https://aws.amazon.com/docker/) container registry that makes it easy for developers to store, manage, and deploy Docker container images. Amazon ECR is integrated with Amazon EC2 Container Service (ECS), simplifying your development to production workflow.

All of the above steps can be simplified by using Docker Maven Plugin which will compile, package, build container, tag the container, and upload container to registry as a single step.

## Setup steps:

1. Create an ECR repository to store your container and configure docker client connection to ECR. Run the following python script:

2. Create a Dockerfile that will instruct on how to layer your Spring application as a new layer on a base container image.

3. Now that you have done all of the setup, you can update your code, build, package, containerize, tag, and push your container image to ECR repository with just a single command line execution.

mvn package docker:build -DpushImage

# Run Your Container at Scale

## Create an ECS cluster

One quick way of doing this is to run ecs-cli tool to create a cluster by running the command below. More info on ecs-cli tool [http://docs.aws.amazon.com/AmazonECS/latest/developerguide/ECS\_CLI.html](http://docs.aws.amazon.com/AmazonECS/latest/developerguide/ECS_CLI.html)

ecs-cli up --keypair _id\_rsa_ --capability-iam --size _2_ --instance-type _t2.medium_

Go into Cloudformation template to retrieve the IAM role that was created by ecs-cli and attach the policies required for ECS cluster to retrieve image from ECR, register new containers instance to ELB, get CloudWatch data for autoscaling..etc.

Create IAM Resources

You will need to create two IAM roles:

1. The Amazon ECS container agent running on EC2 makes calls to the Amazon ECS API actions on your behalf, so container instances that run the agent require an IAM policy and role for the service to know that the agent belongs to you. Before you can launch container instances and register them into a cluster, you must create an IAM role for those container instances to use when they are launched.
2. The Amazon ECS service scheduler makes calls to the Amazon EC2 and Elastic Load Balancing APIs on your behalf to register and deregister container instances with your load balancers. Before you can attach a load balancer to an Amazon ECS service, you must create an IAM role for your services to use before you start them. This requirement applies to any Amazon ECS service that you plan to use with a load balancer.

In most cases, the Amazon ECS service role is created for you automatically in the console first-run experience. You can use the following procedure to check if your account already has the Amazon ECS service role.

1. IAM role for Amazon ECS tasks, you can specify an IAM role that can be used by the containers in a task. Applications must sign their AWS API requests with AWS credentials, and this feature provides a strategy for managing credentials for your applications to use, similar to the way that Amazon EC2 instance profiles provide credentials to EC2 instances. Instead of creating and distributing your AWS credentials to the containers or using the EC2 instance&#39;s role, you can associate an IAM role with an ECS task definition

## Create an Application Load Balancer

## Create a CloudWatch Log Group

## Create a Target Group

Create a Target Group in the same VPC as your ECS cluster and some port number. The port number can be override when registering the target from ECS Service.

## Create a Task Definition



## Create service

