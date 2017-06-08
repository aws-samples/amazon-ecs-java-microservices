# Convert Java Spring application to microservices and deploy to containers on ECS

This project, we will talk about how you can containerize an existing Java Spring application and use ECS to run this container at scale and high availability.

The application example we will be using is a modified fork of the popular Spring Pet Clinic REST application.


# Containerize your Spring application

To transform your existing Java Spring application into container you must compile, package, build a container image with the application package, and execution instruction. In addition, in order to run your container in the container cluster, it must be stored in a scaleable container registry so that during a docker run, each of the cluster&#39;s node can download the container in parallel without impacting the performance. Amazon EC2 Container Registry (ECR) is a fully-managed  [Docker](https://aws.amazon.com/docker/) container registry that makes it easy for developers to store, manage, and deploy Docker container images. Amazon ECR is integrated with Amazon EC2 Container Service (ECS), simplifying your development to production workflow.


All of the above steps can be simplified by using Docker Maven Plugin which will compile, package, build container, tag the container, and upload container to registry as a single step.

## Setup steps:

1. Clone this repository - git clone <>
2. Run python setup.py -m setup -r <your region>
3. mvn package docker:build -DpushImage

## Cleanup :
1. Run python setup.py -m cleanup -r <your region>
